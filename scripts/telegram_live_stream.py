import logging
import signal
import sys
import threading
from types import FrameType

from app.core.config import settings
from app.core.enums import StreamCursorMode, StreamVisualMode
from app.deliver import AVPlayer, AVStreamer, MediaAssetPaths, PlayerDeliver
from app.services.downloader import YTDownloader

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)s | %(threadName)s | %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

# Константы
VIDEO_ID = '3fXnMmv8zX8'
RECEIVE_INTERVAL_SECONDS = 5 * 60  # 5 минут
PLACEHOLDER_IMAGE = settings.assets_dir / 'technical_cookies.jpg'


def receive_worker(playlist: PlayerDeliver, streamer: AVStreamer) -> None:
    downloader = YTDownloader(settings.multimedia_dir)
    multimedia = downloader.get_media_by_id(VIDEO_ID)

    if multimedia is None:
        logger.error('Multimedia with ID %s not found. Stopping receive worker.', VIDEO_ID)
        streamer.stop()
        return

    if multimedia.mediafile_path is None or multimedia.thumbnail_path is None:
        logger.error('Multimedia paths are not set for ID %s. Stopping receive worker.', VIDEO_ID)
        streamer.stop()
        return

    media = MediaAssetPaths(
        mediafile=multimedia.mediafile_path,
        thumbnail=multimedia.thumbnail_path,
    )

    streamer.wait(6)
    video_name = next(iter(media.mediafile.name.rsplit(' ', maxsplit=1)), VIDEO_ID)
    while streamer.is_running:
        playlist.append(media)

        logger.info('Added new track to playlist: %s', video_name)
        streamer.wait(RECEIVE_INTERVAL_SECONDS)

    streamer.stop()
    logger.info('Receive worker stopped')


if __name__ == '__main__':
    """Точка входа."""
    rtmps_url = settings.rtmps_url

    if not rtmps_url or 'rtmp' not in rtmps_url.lower():
        logger.error('Invalid RTMPS URL. Check TG_LINK and TG_CODE in .env')
        sys.exit(1)

    logger.info('Starting Telegram live stream')
    logger.info('Video ID: %s', VIDEO_ID)
    logger.info('Receive interval: %d seconds', RECEIVE_INTERVAL_SECONDS)

    player = AVPlayer(
        visual_mode=StreamVisualMode.VIDEO_CONTENT,
        cursor_mode=StreamCursorMode.PLAY_AND_DELETE,
    )
    streamer = AVStreamer(rtmps_url, player, settings.placeholder_path)

    def signal_handler(_signum: int, _frame: FrameType | None) -> None:
        if streamer.is_running:
            logger.info('Shutdown signal received, stopping workers...')
            streamer.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    receive_thread = threading.Thread(
        args=(player, streamer),
        target=receive_worker,
        name='Receive',
        daemon=True,
    )
    deliver_thread = threading.Thread(
        target=streamer.run,
        name='Deliver',
        daemon=True,
    )
    player.is_playing = False
    receive_thread.start()
    deliver_thread.start()

    # Ждём завершения deliver потока (или прерывания)
    try:
        while deliver_thread.is_alive():
            deliver_thread.join(timeout=1.0)
    except KeyboardInterrupt:
        pass

    logger.info('All workers stopped')
