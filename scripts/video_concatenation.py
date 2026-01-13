import logging
import time
from datetime import timedelta
from pathlib import Path

import av

from app.core.config import settings
from app.services.downloader import YTDownloader
from app.utils.streaming import StreamContext, create_silence_frame, prepare_video_frame

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s | %(levelname)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)


PLACEHOLDER_IMAGE = settings.assets_dir / 'technical_cookies.jpg'

AUDIO_FRAME = create_silence_frame()
VIDEO_FRAME = prepare_video_frame(PLACEHOLDER_IMAGE)


def add_placeholder(ctx: StreamContext, duration: int) -> None:
    logger.info('Adding placeholder: %d seconds', duration)
    old_progress = old_seconds = -1
    initial_duration = ctx.duration

    while ctx.duration < initial_duration + duration:
        if ctx.video_duration <= ctx.audio_duration:
            ctx.encode_video(VIDEO_FRAME)
        else:
            ctx.encode_audio(AUDIO_FRAME)

        progress = int((ctx.duration - initial_duration) / duration * 100)
        seconds = int(ctx.duration - initial_duration)

        if progress != old_progress and seconds != old_seconds:
            logger.debug(
                'Placeholder: %3d%% | Segment: %s | Total: %s (V: %s / A: %s)',
                progress,
                timedelta(seconds=seconds),
                timedelta(seconds=int(ctx.duration)),
                timedelta(seconds=int(ctx.video_duration)),
                timedelta(seconds=int(ctx.audio_duration)),
            )
            old_progress, old_seconds = progress, seconds


def add_mediafile(ctx: StreamContext, media_path: Path) -> None:
    logger.info('Adding media file: %s', media_path.name)

    with av.open(media_path, mode='r') as src_container:
        audio_stream = next(iter(src_container.streams.audio), None)
        video_stream = next(iter(src_container.streams.video), None)

        if not src_container.duration:
            logger.warning('Media file has no duration info: %s', media_path)
            return

        duration = int(src_container.duration / av.time_base)
        logger.info('Media duration: %s', timedelta(seconds=duration))

        if audio_stream is not None:
            ctx.create_graph(audio_stream)

        if video_stream is not None:
            ctx.create_graph(video_stream)

        old_progress = old_seconds = -1
        for packet in src_container.demux(audio_stream, video_stream):
            max_time = 0.0
            for frame in packet.decode():
                if isinstance(frame, av.AudioFrame):
                    max_time = frame.time or max_time
                    ctx.encode_audio(frame)

                elif isinstance(frame, av.VideoFrame):
                    max_time = frame.time or max_time
                    ctx.encode_video(frame)

            progress = int((max_time / duration) * 100)
            seconds = int(max_time)

            if progress != old_progress and seconds != old_seconds:
                logger.debug(
                    'Media: %3d%% | Processed: %s | Total: %s (V: %s / A: %s)',
                    progress,
                    timedelta(seconds=seconds),
                    timedelta(seconds=int(ctx.duration)),
                    timedelta(seconds=int(ctx.video_duration)),
                    timedelta(seconds=int(ctx.audio_duration)),
                )
                old_progress, old_seconds = progress, seconds

        ctx.flush(close=False)
        logger.info('Media file added successfully')


def concatenate_videos(*videos: Path, output_path: Path) -> None:
    if output_path.exists() and output_path.is_file():
        logger.info('Removing existing video file: %s', output_path.name)
        output_path.unlink(missing_ok=True)

    start_time = time.time()
    slots = len(videos) * 2 + 1
    queue = [videos[i // 2] if i % 2 else 10 for i in range(slots)]

    logger.info('Total segments to process: %d (%d videos + %d placeholders)', slots, len(videos), slots - len(videos))

    with av.open(output_path, mode='w') as container:
        ctx = StreamContext(container)
        segment_number = 0

        while queue:
            segment_number += 1
            item = queue.pop(0)

            if isinstance(item, Path):
                logger.info('--- Segment %d/%d: Media ---', segment_number, slots)
                add_mediafile(ctx, item)

            elif isinstance(item, int):
                logger.info('--- Segment %d/%d: Placeholder ---', segment_number, slots)
                add_placeholder(ctx, item)

            else:
                raise TypeError('Unexpected item in queue.')

        logger.info('Finalizing video...')
        ctx.flush(close=True)
        logger.info(
            'Final duration: %s (V: %s / A: %s)',
            timedelta(seconds=int(ctx.duration)),
            timedelta(seconds=int(ctx.video_duration)),
            timedelta(seconds=int(ctx.audio_duration)),
        )

    elapsed_time = time.time() - start_time
    logger.info('Concatenation finished in %s', timedelta(seconds=int(elapsed_time)))


if __name__ == '__main__':
    downloader = YTDownloader(download_dir=settings.multimedia_dir)
    video_ids = [
        input('Введите ID первого видео: ').strip() or 'clwYCPS71uU',
        input('Введите ID второго видео: ').strip() or 'em2sOOWVPYM',
    ]

    video_paths = [downloader.get_media_by_id(video_id) for video_id in video_ids if video_id]
    video_paths = [path.mediafile_path for path in video_paths if path and path.mediafile_path]
    output_filename = f'concatenated_{"_".join(video_ids)}.mp4'

    logger.info('Starting video concatenation process...')
    concatenate_videos(*video_paths, output_path=settings.assets_dir / output_filename)
    logger.info('Video concatenation completed successfully.')
