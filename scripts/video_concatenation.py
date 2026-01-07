import logging
import sys
import time
from datetime import timedelta
from pathlib import Path

import av

from app.core.config import settings
from app.services.downloader import YTDownloader
from app.utils.streaming import StreamContext, create_silence_frame, interleave_frames, prepare_video_frame

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s | %(levelname)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)


PLACEHOLDER_IMAGE = settings.assets_dir / 'technical_cookies.jpg'

AUDIO_FRAME = create_silence_frame()
VIDEO_FRAME = prepare_video_frame(PLACEHOLDER_IMAGE)


def add_placeholder(context: StreamContext, duration_seconds: int) -> None:
    for frame in interleave_frames(AUDIO_FRAME, VIDEO_FRAME, duration_seconds=duration_seconds):
        context.encode_mux(frame)

    context.flush(close=False)


def add_container(context: StreamContext, media_path: Path) -> None:
    with av.open(media_path, mode='r') as input_container:
        audio_stream = next(iter(input_container.streams.audio), None)
        video_stream = next(iter(input_container.streams.video), None)

        # Создаем граф для аудио
        if audio_stream:
            context.create_graph(stream=audio_stream)

        if video_stream:
            context.create_graph(stream=video_stream)

        for packet in input_container.demux(audio_stream, video_stream):
            for frame in packet.decode():
                if not isinstance(frame, (av.AudioFrame, av.VideoFrame)):
                    continue

                if frame.pts is None or frame.time_base is None:
                    continue

                context.encode_mux(frame)

        context.flush(close=False)


def concatenate_videos(video1_media: Path, video2_media: Path, output_path: Path) -> None:
    queue = [20, video1_media, 10, video2_media, 30]

    if output_path.exists() and output_path.is_file():
        logger.info('Removing existing video file: %s', output_path)
        output_path.unlink(missing_ok=True)
    start_time = time.time()
    with av.open(output_path, mode='w') as container:
        context = StreamContext(container)

        try:
            while queue:
                item = queue.pop(0)

                if isinstance(item, int):
                    add_placeholder(context, duration_seconds=item)
                    continue

                if isinstance(item, Path):
                    add_container(context, media_path=item)
                    continue

        except KeyboardInterrupt:
            logger.info('Video concatenation interrupted by user.')

        except Exception:
            logger.exception('Error during video concatenation')
            raise

        finally:
            context.flush(close=True)
            elapsed_time = timedelta(seconds=int(time.time() - start_time))
            logger.info('Video concatenation completed in %s', elapsed_time)


if __name__ == '__main__':
    downloader = YTDownloader(download_dir=settings.multimedia_dir)

    video1_id = input('Введите ID первого видео: ').strip()
    if not video1_id:
        logger.error('ID первого видео не может быть пустым.')
        sys.exit(1)

    video2_id = input('Введите ID второго видео: ').strip()
    if not video2_id:
        logger.error('ID второго видео не может быть пустым.')
        sys.exit(1)

    video1_media = downloader.get_media_by_id(video1_id)
    if not video1_media.exists or video1_media.mediafile_path is None:
        logger.error('Не удалось получить первое видео: %s', video1_id)
        sys.exit(1)

    video2_media = downloader.get_media_by_id(video2_id)
    if not video2_media.exists or video2_media.mediafile_path is None:
        logger.error('Не удалось получить второе видео: %s', video2_id)
        sys.exit(1)

    output_filename = f'concatenated_{video1_id}_{video2_id}.mp4'
    output_path = settings.assets_dir / output_filename
    video1_path = video1_media.mediafile_path
    video2_path = video2_media.mediafile_path

    logger.info('Starting video concatenation process...')
    concatenate_videos(video1_path, video2_path, output_path)
    logger.info('Video concatenation completed successfully.')
