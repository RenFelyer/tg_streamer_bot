import logging
import sys
from datetime import timedelta
from pathlib import Path

import av

from app.core.config import settings
from app.utils.streaming import (
    AUDIO_TIME_BASE,
    VIDEO_TIME_BASE,
    StreamContext,
    create_silence_frame,
    interleave_frames,
    prepare_video_frame,
)

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s | %(levelname)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)


# Длительность видео по умолчанию
AUDIO_FRAME = create_silence_frame()
VIDEO_FRAME = prepare_video_frame(settings.assets_dir / 'technical_cookies.jpg')
DEFAULT_DURATION_SECONDS = 5


def produce_video(image_path: Path, duration_seconds: int = DEFAULT_DURATION_SECONDS) -> None:
    video_path = image_path.with_suffix('.mp4')

    if video_path.exists() and video_path.is_file():
        logger.info('Removing existing video file: %s', video_path)
        video_path.unlink(missing_ok=True)

    logger.info('Creating video: %s (duration: %d sec)', video_path.name, duration_seconds)
    with av.open(video_path, mode='w') as output_container:
        ctx = StreamContext(output_container)

        try:
            for frame in interleave_frames(AUDIO_FRAME, VIDEO_FRAME, duration_seconds):
                ctx.encode_mux(frame)

        except KeyboardInterrupt:
            logger.info('Keyboard interrupt received. Stopping encoding...')

        finally:
            logger.info('Encoding completed. Total duration: %s', timedelta(seconds=int(ctx.duration)))
            ctx.flush(close=True)

    logger.info('Video file created: %s', video_path)


if __name__ == '__main__':
    identifier = input('Enter image filename: ').strip()
    image_path = settings.assets_dir / (identifier or 'technical_cookies.jpg')

    if not image_path.exists():
        logger.error('Image file does not exist: %s', image_path)
        sys.exit(1)

    logger.info('Image: %s', image_path.name)
    produce_video(image_path, duration_seconds=DEFAULT_DURATION_SECONDS)
