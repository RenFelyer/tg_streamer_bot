"""Непрерывная трансляция в Telegram через RTMPS.

Скрипт ведёт бесконечную трансляцию в Telegram. Основной поток управляет
двумя второстепенными потоками:

- receive: Каждые 5 минут добавляет видео в очередь на проигрывание
- deliver: Подключается к RTMPS и стримит placeholder или видео из очереди

При получении сигнала CTRL+C все потоки корректно завершаются.
"""

import logging
import queue
import signal
import sys
import threading
import time
from datetime import timedelta
from pathlib import Path

import av

from app.core.config import settings
from app.services.downloader import YTDownloader
from app.utils.streaming import (
    StreamContext,
    create_silence_frame,
    interleave_frames,
    prepare_video_frame,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(threadName)s | %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

# Константы
VIDEO_ID = '3fXnMmv8zX8'
RECEIVE_INTERVAL_SECONDS = 5 * 60  # 5 минут
PLACEHOLDER_SEGMENT_SECONDS = 1  # Длина сегмента placeholder при ожидании видео
MIN_SYNC_DELAY_PLACEHOLDER = 0.01  # Минимальная задержка синхронизации для placeholder
MAX_SYNC_DELAY_PLACEHOLDER = 0.05  # Максимальная задержка синхронизации для placeholder
MIN_SYNC_DELAY_VIDEO = 0.1  # Минимальная задержка синхронизации для видео

PLACEHOLDER_IMAGE = settings.assets_dir / 'technical_cookies.jpg'


class LiveStreamController:
    """Контроллер непрерывной трансляции в Telegram."""

    def __init__(self, rtmps_url: str) -> None:
        self.rtmps_url = rtmps_url
        self.video_queue: queue.Queue[Path] = queue.Queue()
        self.shutdown_event = threading.Event()
        self.downloader = YTDownloader(download_dir=settings.multimedia_dir)

        # Кэшируем placeholder frames
        self._audio_frame = create_silence_frame()
        self._video_frame = prepare_video_frame(PLACEHOLDER_IMAGE)

    def receive_worker(self) -> None:
        """Поток, добавляющий видео в очередь каждые 5 минут."""
        logger.info('Receive worker started')

        while not self.shutdown_event.is_set():
            try:
                self._fetch_and_enqueue_video()
            except Exception:
                logger.exception('Error in receive worker')

            # Ждём интервал с возможностью прерывания
            if self.shutdown_event.wait(timeout=RECEIVE_INTERVAL_SECONDS):
                break

        logger.info('Receive worker stopped')

    def _fetch_and_enqueue_video(self) -> None:
        """Получает видео и добавляет в очередь."""
        logger.info('Fetching video: %s', VIDEO_ID)

        media = self.downloader.get_media_by_id(VIDEO_ID)
        if not media.exists or media.mediafile_path is None:
            logger.info('Video not found locally, downloading...')
            url = f'https://www.youtube.com/watch?v={VIDEO_ID}'
            media = self.downloader.download(url)

            if media is None or media.mediafile_path is None:
                logger.error('Failed to download video: %s', VIDEO_ID)
                return

        logger.info('Adding video to queue: %s', media.mediafile_path.name)
        self.video_queue.put(media.mediafile_path)

    def deliver_worker(self) -> None:
        """Поток, стримящий контент в Telegram."""
        logger.info('Deliver worker started, connecting to: %s...', self.rtmps_url[:50])

        try:
            with av.open(self.rtmps_url, mode='w', format='flv') as broadcast:
                ctx = StreamContext(broadcast, low_latency=True)
                self._stream_loop(ctx)

        except OSError:
            if not self.shutdown_event.is_set():
                logger.exception('RTMPS connection error')
        except Exception:
            if not self.shutdown_event.is_set():
                logger.exception('Error in deliver worker')

        logger.info('Deliver worker stopped')

    def _stream_loop(self, ctx: StreamContext) -> None:
        """Основной цикл стриминга."""
        start_time = time.time()

        while not self.shutdown_event.is_set():
            video_path = self._get_next_video()

            if video_path:
                logger.info('Streaming video: %s', video_path.name)
                self._stream_video(ctx, video_path, start_time)
            else:
                self._stream_placeholder_segment(ctx, start_time)

        # Финальный flush при завершении
        ctx.flush(close=True)
        logger.info('Stream ended. Total duration: %s', timedelta(seconds=int(ctx.duration)))

    def _get_next_video(self) -> Path | None:
        """Проверяет очередь на наличие видео."""
        try:
            return self.video_queue.get_nowait()
        except queue.Empty:
            return None

    def _stream_placeholder_segment(self, ctx: StreamContext, start_time: float) -> None:
        """Стримит короткий сегмент placeholder."""
        for frame in interleave_frames(
            self._audio_frame,
            self._video_frame,
            duration_seconds=PLACEHOLDER_SEGMENT_SECONDS,
        ):
            if self.shutdown_event.is_set():
                break

            ctx.encode_mux(frame)

            # Синхронизация с реальным временем
            elapsed = time.time() - start_time
            delay = float(ctx.duration) - elapsed
            if delay > MIN_SYNC_DELAY_PLACEHOLDER:
                time.sleep(min(delay, MAX_SYNC_DELAY_PLACEHOLDER))

        ctx.flush(close=False)

    def _stream_video(self, ctx: StreamContext, media_path: Path, start_time: float) -> None:
        """Стримит видео файл."""
        try:
            with av.open(media_path, mode='r') as input_container:
                audio_stream = next(iter(input_container.streams.audio), None)
                video_stream = next(iter(input_container.streams.video), None)

                if audio_stream:
                    ctx.create_graph(stream=audio_stream)
                if video_stream:
                    ctx.create_graph(stream=video_stream)

                for packet in input_container.demux(audio_stream, video_stream):
                    if self.shutdown_event.is_set():
                        break

                    for frame in packet.decode():
                        if not isinstance(frame, (av.AudioFrame, av.VideoFrame)):
                            continue
                        if frame.pts is None or frame.time_base is None:
                            continue

                        ctx.encode_mux(frame)

                        # Синхронизация с реальным временем
                        elapsed = time.time() - start_time
                        delay = float(ctx.duration) - elapsed
                        if delay > MIN_SYNC_DELAY_VIDEO:
                            time.sleep(min(delay, MIN_SYNC_DELAY_VIDEO))

            ctx.flush(close=False)
            logger.info('Video streaming completed: %s', media_path.name)

        except Exception:
            logger.exception('Error streaming video: %s', media_path)
            ctx.flush(close=False)

    def run(self) -> None:
        """Запускает контроллер трансляции."""
        receive_thread = threading.Thread(target=self.receive_worker, name='Receive', daemon=True)
        deliver_thread = threading.Thread(target=self.deliver_worker, name='Deliver', daemon=True)

        receive_thread.start()
        deliver_thread.start()

        # Ждём завершения deliver потока (или прерывания)
        try:
            while deliver_thread.is_alive():
                deliver_thread.join(timeout=1.0)
        except KeyboardInterrupt:
            pass

        logger.info('All workers stopped')

    def shutdown(self) -> None:
        """Сигнализирует о завершении работы."""
        logger.info('Shutdown signal received')
        self.shutdown_event.set()


def main() -> None:
    """Точка входа."""
    rtmps_url = settings.rtmps_url
    if not rtmps_url or 'rtmp' not in rtmps_url.lower():
        logger.error('Invalid RTMPS URL. Check TG_LINK and TG_CODE in .env')
        sys.exit(1)

    logger.info('Starting Telegram live stream')
    logger.info('Video ID: %s', VIDEO_ID)
    logger.info('Receive interval: %d seconds', RECEIVE_INTERVAL_SECONDS)

    controller = LiveStreamController(rtmps_url)

    def signal_handler(_signum: int, _frame: object) -> None:
        controller.shutdown()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    controller.run()


if __name__ == '__main__':
    main()
