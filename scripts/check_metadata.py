import logging
import sys
from datetime import timedelta
from fractions import Fraction
from pathlib import Path

import av
from av.audio.stream import AudioStream
from av.video.stream import VideoStream

from app.core.config import settings
from app.services.downloader import YTDownloader

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def main(video_path: Path) -> None:
    with av.open(video_path, mode='r') as container:
        logger.info('Container format: %s', container.format.name)
        logger.info('Number of streams: %d', len(container.streams))

        for stream in container.streams:
            logger.info('Stream #%d:', stream.index)
            logger.info('  Type: %s', stream.type)
            logger.info('  Codec: %s', stream.codec.name)
            logger.info('  Duration: %s', stream.duration)
            logger.info('  Time base: %s', stream.time_base)
            seconds = int(stream.duration * stream.time_base) if stream.duration and stream.time_base else None
            logger.info('  Total Time: %s', str(timedelta(seconds=seconds) if seconds is not None else 'N/A'))

            ticks = 'N/A'

            if isinstance(stream, VideoStream):
                logger.info('  Width: %d', stream.width)
                logger.info('  Height: %d', stream.height)
                logger.info('  Frame rate: %s', stream.base_rate)
                if stream.base_rate and stream.time_base:
                    ticks = 1 / (stream.time_base * stream.base_rate)
            elif isinstance(stream, AudioStream):
                logger.info('  Sample rate: %d', stream.rate)
                logger.info('  Channels: %d', stream.channels)
                logger.info('  Frame Size: %s', stream.frame_size)
                if stream.rate and stream.frame_size and stream.time_base:
                    audio_frame_duration = Fraction(stream.frame_size, stream.rate)
                    ticks = audio_frame_duration / stream.time_base

            logger.info('  Ticks per frame: %s', ticks)


if __name__ == '__main__':
    video_path = settings.assets_dir / 'technical_cookies.mp4'

    if not video_path.exists() or not video_path.is_file():
        downloader = YTDownloader(download_dir=settings.multimedia_dir)
        identifier = input('Enter media ID: ').strip() or '-xeVJM786lQ'
        mediafile = downloader.get_media_by_id(identifier)
        video_path = mediafile.mediafile_path

        if not video_path or not video_path.exists() or not video_path.is_file():
            settings.assets_dir.glob(f'[[]{identifier}.mp4]')

    if not video_path or not video_path.exists() or not video_path.is_file():
        logger.error('Media file not found. Exiting.')
        sys.exit(1)

    try:
        logger.info('Using media file: "%s"', video_path.name.rsplit(' ', 1)[0])
        main(video_path)
    except KeyboardInterrupt:
        logger.info('Stream stopped by user.')
