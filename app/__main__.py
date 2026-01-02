import logging
import sys
import time
from fractions import Fraction

import av
from av.audio.frame import AudioFrame
from av.audio.stream import AudioStream
from av.filter import Graph
from av.video.frame import VideoFrame
from av.video.stream import VideoStream

from app.core.config import settings
from app.core.schemas import MediaPaths
from app.services.downloader import YTDownloader

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

AUDIO_RATE = 48000
AUDIO_FORMAT = 'fltp'
AUDIO_LAYOUT = 'stereo'
AUDIO_FRAME_SIZE = 1024
AUDIO_BITRATE = 128_000  # 128 Kbps

VIDEO_RATE = Fraction(30000, 1001)
VIDEO_PIX_FMT = 'yuv420p'
VIDEO_BITRATE = 2_000_000  # 2 Mbps
VIDEO_WIDTH = settings.width
VIDEO_HEIGHT = settings.height


def get_approximate_pts(stream: AudioStream | VideoStream) -> int | None:
    if stream.duration and stream.start_time is not None:
        # duration — это длительность в единицах time_base
        # start_time — это PTS первого кадра
        return stream.start_time + stream.duration

    return None


def main(media: MediaPaths) -> None:  # noqa: C901, PLR0912, PLR0915
    max_out_video_pts = 0
    max_out_audio_pts = 0

    with av.open(settings.rtmps_url, 'w', format='flv') as writer:
        # 1. Настройка входных и выходных потоков
        out_audio_stream = writer.add_stream('aac', rate=AUDIO_RATE)
        out_audio_stream.layout = AUDIO_LAYOUT
        out_audio_stream.format = AUDIO_FORMAT
        out_audio_stream.bit_rate = AUDIO_BITRATE

        out_video_stream = writer.add_stream('h264', rate=VIDEO_RATE)
        out_video_stream.width = VIDEO_WIDTH
        out_video_stream.height = VIDEO_HEIGHT
        out_video_stream.pix_fmt = VIDEO_PIX_FMT  # Важно для совместимости
        out_video_stream.gop_size = int(VIDEO_RATE) * 2  # GOP size of 2 seconds
        out_video_stream.bit_rate = VIDEO_BITRATE

        out_video_stream.options = {
            'preset': 'ultrafast',  # Быстрое кодирование, чтобы не было лагов
            'tune': 'zerolatency',  # Минимальная задержка
        }

        with av.open(media.mediafile_path, 'r') as reader:
            in_audio_stream = next(iter(reader.streams.audio), None)
            in_video_stream = next(iter(reader.streams.video), None)

            if not in_audio_stream or not in_video_stream:
                logger.error('No audio or video stream found in the media file. Exiting.')
                sys.exit(1)

            resampler = av.AudioResampler(
                format=out_audio_stream.format,
                layout=out_audio_stream.layout,
                rate=out_audio_stream.rate,
            )

            graph = Graph()
            graph.link_nodes(
                graph.add_buffer(template=in_video_stream),
                graph.add('scale', f'{VIDEO_WIDTH}:{VIDEO_HEIGHT}'),
                graph.add('fps', f'fps={VIDEO_RATE}'),  # Вот наш фильтр
                graph.add('buffersink'),
            ).configure()

            # 2. Основной цикл транскодирования
            start_time = time.time()
            streams_to_decode = list(filter(None, [in_audio_stream, in_video_stream]))
            for packet in reader.demux(*streams_to_decode):
                if packet.dts is None:
                    continue

                for frame in packet.decode():
                    if not isinstance(frame, (AudioFrame, VideoFrame)):
                        continue

                    if frame.time:
                        elapsed = time.time() - start_time
                        delay = frame.time - elapsed
                        if delay > 0:
                            logger.debug('Sleeping for %.3f seconds to sync.', delay)
                            time.sleep(delay)

                    if isinstance(frame, VideoFrame):
                        graph.push(frame)
                        while True:
                            try:
                                filtered_frame = graph.pull()
                                if not isinstance(filtered_frame, VideoFrame):
                                    break

                                for out_packet in out_video_stream.encode(filtered_frame):
                                    logger.debug('Video Frame PTS: %s', out_packet.pts)
                                    if out_packet.pts is not None:
                                        max_out_video_pts = max(max_out_video_pts, out_packet.pts)
                                    writer.mux(out_packet)
                            except (av.BlockingIOError, av.EOFError):
                                break

                    if isinstance(frame, AudioFrame):
                        for resampler_frames in resampler.resample(frame):
                            for out_packet in out_audio_stream.encode(resampler_frames):
                                logger.debug('Audio Frame PTS: %s', out_packet.pts)
                                if out_packet.pts is not None:
                                    max_out_audio_pts = max(max_out_audio_pts, out_packet.pts)
                                writer.mux(out_packet)

            # 3. ВАЖНО: Flush (сброс) всего в правильном порядке
            logger.info('Flushing buffers...')

            # Шаг А: Вытряхиваем остатки из Видео-Фильтра
            graph.push(None)
            while True:
                try:
                    filtered_frame = graph.pull()

                    if not isinstance(filtered_frame, VideoFrame):
                        break

                    logger.debug('Flushing graph frame: %s', filtered_frame.pts)
                    for out_packet in out_video_stream.encode(filtered_frame):
                        if out_packet.pts is not None:
                            max_out_video_pts = max(max_out_video_pts, out_packet.pts)
                        writer.mux(out_packet)
                except (av.BlockingIOError, av.EOFError):
                    break

            # Шаг Б: Вытряхиваем остатки из Видео-Кодера
            for out_packet in out_video_stream.encode(None):
                if out_packet.pts is not None:
                    max_out_video_pts = max(max_out_video_pts, out_packet.pts)
                logger.debug('Flushing Video Encoder Packet: PTS %s', out_packet.pts)
                writer.mux(out_packet)

            # Шаг В: Вытряхиваем остатки из Аудио-Кодера
            for out_packet in out_audio_stream.encode(None):
                if out_packet.pts is not None:
                    max_out_audio_pts = max(max_out_audio_pts, out_packet.pts)
                logger.debug('Flushing Audio Encoder Packet: PTS %s', out_packet.pts)
                writer.mux(out_packet)

            # Синхронизация по времени
            if reader.duration:
                duration = reader.duration / 1_000_000
                elapsed = time.time() - start_time
                delay = duration - elapsed
                if delay > 0:
                    logger.debug('Sleeping for %.3f seconds to sync. %s', delay, elapsed)
                    time.sleep(delay)

            # 4. Вывод статистики
            logger.info(
                'Max Out Video PTS: %s, Approximate: %s',
                max_out_video_pts,
                get_approximate_pts(in_video_stream),
            )
            logger.info(
                'Max Out Audio PTS: %s, Approximate: %s',
                max_out_audio_pts,
                get_approximate_pts(in_audio_stream),
            )

            logger.debug(
                'Input Audio PTS Approximate: %s, Input Video PTS Approximate: %s',
                get_approximate_pts(in_audio_stream),
                get_approximate_pts(in_video_stream),
            )

            logger.debug(
                'Input Video Stream: %sx%s @ %sfps, Pixel Format: %s',
                in_video_stream.width,
                in_video_stream.height,
                in_video_stream.average_rate or 'N/A',
                in_video_stream.format.name,
            )
            logger.debug(
                'Output Audio Stream: %s Hz, %s, %s',
                out_audio_stream.rate,
                out_audio_stream.layout,
                out_audio_stream.format,
            )

            # 5. Завершение работы
            logger.info('Transcoding completed successfully.')


if __name__ == '__main__':
    downloader = YTDownloader(download_dir=settings.multimedia_dir)
    mediafile = downloader.get_media_by_id('-xeVJM786lQ')
    if not mediafile.exists or not mediafile.mediafile_path:
        logger.error('Media file does not exist. Exiting.')
        sys.exit(1)

    try:
        main(mediafile)
    except KeyboardInterrupt:
        logger.info('Stream stopped by user.')
