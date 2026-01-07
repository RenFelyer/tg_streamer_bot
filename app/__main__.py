import logging
import sys
import time
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from av.audio.frame import AudioFrame
from av.audio.stream import AudioStream
from av.video.frame import VideoFrame
from av.video.stream import VideoStream
from PIL import Image

from app.core.config import settings
from app.core.schemas import MediaPaths
from app.services.downloader import YTDownloader
from app.services.streamer import TGStreamer

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logo_path = settings.assets_dir / 'technical_cookies.jpg'


def get_approximate_pts(stream: AudioStream | VideoStream) -> int | None:
    if stream.duration and stream.start_time is not None:
        # duration — это длительность в единицах time_base
        # start_time — это PTS первого кадра
        return stream.start_time + stream.duration

    return None


def main(media: MediaPaths) -> None:
    streamer = TGStreamer()
    streamer.start_stream()
    streamer._create_resampling()  # noqa: SLF001

    if not (streamer.audio_stream and streamer.video_stream and streamer.broadcaster and streamer.resampling):
        logger.error('Streamer is not properly initialized.')
        sys.exit(1)

    try:
        pass

    except KeyboardInterrupt:
        logger.info('Stopping stream via KeyboardInterrupt...')

    except Exception:
        logger.exception('Error during streaming')

    finally:
        # 3. Flush (сброс буферов)
        logger.info('Flushing encoders...')
        for packet in streamer.video_stream.encode(None):
            streamer.broadcaster.mux(packet)

        for packet in streamer.audio_stream.encode(None):
            streamer.broadcaster.mux(packet)

        streamer.close_stream()
        logger.info('Stream closed.')


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
