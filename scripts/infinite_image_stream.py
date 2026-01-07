import logging
import sys
import time
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


PLACEHOLDER_IMAGE = settings.assets_dir / 'technical_cookies.jpg'
AUDIO_FRAME = create_silence_frame()
VIDEO_FRAME = prepare_video_frame(PLACEHOLDER_IMAGE)


def stream_to_telegram(rtmps_url: str) -> None:
    """Stream an infinite loop of a single image with silent audio to a Telegram RTMPS endpoint."""
    logger.info('Connecting to: %s', rtmps_url[:50] + '...')

    with av.open(rtmps_url, mode='w', format='flv') as broadcast:
        ctx = StreamContext(broadcast, low_latency=True)
        try:
            start_time = time.time()
            logger.info('Starting infinite stream. Press Ctrl+C to stop.')
            for frame in interleave_frames(AUDIO_FRAME, VIDEO_FRAME):
                ctx.encode_mux(frame)

                elapsed = time.time() - start_time
                delay = ctx.duration - elapsed
                if delay > 0:
                    time.sleep(delay)

        except KeyboardInterrupt:
            logger.info('Keyboard interrupt received. Stopping stream...')

        finally:
            logger.info('Stream ended. Total duration: %s', timedelta(seconds=int(ctx.duration)))
            ctx.flush(close=True)


if __name__ == '__main__':
    rtmps_url = settings.rtmps_url
    if not rtmps_url or 'rtmp' not in rtmps_url.lower():
        logger.error('Invalid RTMPS URL. Check TG_LINK and TG_CODE in .env')
        sys.exit(1)

    logger.info('Target: Telegram RTMPS')
    stream_to_telegram(rtmps_url)
