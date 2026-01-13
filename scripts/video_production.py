import logging
import sys
from datetime import timedelta
from pathlib import Path

import av

from app.core.config import settings
from app.utils.streaming import (
    StreamContext,
    create_silence_frame,
    prepare_video_frame,
)

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s | %(levelname)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)


# Длительность видео по умолчанию
AUDIO_FRAME = create_silence_frame()
VIDEO_FRAME = prepare_video_frame(settings.assets_dir / 'technical_cookies.jpg')
DEFAULT_DURATION_SECONDS = 5


def produce_video(image_path: Path) -> None:
    video_path = image_path.with_suffix('.mp4')
    old_progress = old_seconds = -1

    if video_path.exists() and video_path.is_file():
        logger.info('Removing existing video file: %s', video_path)
        video_path.unlink(missing_ok=True)

    logger.info('Creating video: %s (duration: %d sec)', video_path.name, DEFAULT_DURATION_SECONDS)
    with av.open(video_path, mode='w') as container:
        ctx = StreamContext(container)

        while ctx.duration < DEFAULT_DURATION_SECONDS:
            if ctx.video_duration < ctx.audio_duration:
                ctx.encode_video(VIDEO_FRAME)
            else:
                ctx.encode_audio(AUDIO_FRAME)

            progress = int((ctx.duration / DEFAULT_DURATION_SECONDS) * 100)
            seconds = int(ctx.duration)
            if progress != old_progress and seconds != old_seconds:
                logger.info('Progress: %d%% / %s sec', progress, timedelta(seconds=seconds))
                old_progress, old_seconds = progress, seconds

        ctx.flush(close=True)
        logger.info('Video created successfully: %s', timedelta(seconds=int(ctx.duration)))


if __name__ == '__main__':
    identifier = input('Enter image filename: ').strip()
    image_path = settings.assets_dir / (identifier or 'technical_cookies.jpg')

    if not image_path.exists():
        logger.error('Image file does not exist: %s', image_path)
        sys.exit(1)

    logger.info('Image: %s', image_path.name)
    produce_video(image_path)
