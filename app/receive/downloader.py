from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yt_dlp
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from app.receive.constants import (
    DEFAULT_MERGE_FORMAT,
    DEFAULT_THUMBNAIL_FORMAT,
    DEFAULT_THUMBNAIL_SCALE,
    DEFAULT_VIDEO_FORMAT,
)
from app.receive.interfaces import ContentReceiver
from app.receive.schemas import DownloadResult, MediaPaths

if TYPE_CHECKING:
    from collections.abc import Mapping

    from yt_dlp import _Params

logger = logging.getLogger(__name__)


class YTDLPReceiver(ContentReceiver):
    """Реализация ContentReceiver на основе yt-dlp."""

    def __init__(self, download_dir: Path) -> None:
        super().__init__(download_dir)
        self._ydl_opts = self._create_ydl_options()

    def _create_ydl_options(self) -> _Params:
        """Создаёт базовые опции для yt-dlp."""
        return {
            # Вывод
            'outtmpl': str(self.download_dir / '%(title)s [%(id)s].%(ext)s'),
            # Формат
            'format': DEFAULT_VIDEO_FORMAT,
            'merge_output_format': DEFAULT_MERGE_FORMAT,
            # Поведение
            'noplaylist': True,
            'overwrites': False,
            'continuedl': True,
            # Превью
            'writethumbnail': True,
            # Имитация
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'web'],
                    'skip': ['dash', 'hls'],
                },
            },
            # Логи
            'quiet': True,
            'no_warnings': True,
            'verbose': False,
            'progress_hooks': [self._progress_hook],
            # Постобработка
            'postprocessors': [
                {
                    'key': 'FFmpegMetadata',
                    'add_chapters': True,
                    'add_metadata': True,
                },
                {
                    'key': 'FFmpegThumbnailsConvertor',
                    'format': DEFAULT_THUMBNAIL_FORMAT,
                },
                {
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': DEFAULT_MERGE_FORMAT,
                },
            ],
            'postprocessor_args': {
                'thumbnailsconvertor': ['-vf', f'scale={DEFAULT_THUMBNAIL_SCALE}:-1'],
            },
        }

    def _progress_hook(self, data: Mapping[str, Any]) -> None:
        """Хук для отслеживания прогресса загрузки."""
        if data['status'] != 'downloading':
            return

        filename = Path(data['filename']).name
        percent = data.get('_percent_str', 'N/A')
        logger.info('Загрузка: %s - %s', filename, percent)

    def get_media_by_id(self, video_id: str) -> MediaPaths:
        """Возвращает пути к медиафайлам по идентификатору."""
        return MediaPaths(
            identifier=video_id,
            mediafile_path=next(self.download_dir.glob(f'*[[]{video_id}].mp4'), None),
            thumbnail_path=next(self.download_dir.glob(f'*[[]{video_id}].jpg'), None),
        )

    def get_video_id(self, url: str) -> str | None:
        """Извлекает идентификатор видео из URL."""
        opts: yt_dlp._Params = {
            'quiet': True,
            'noplaylist': True,
            'extract_flat': True,
            'force_generic_extractor': True,
            'no_warnings': True,
        }
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info.get('id') if info else None
        except Exception:
            logger.exception('Не удалось извлечь ID из URL: %s', url)
            return None

    def download(self, url: str) -> DownloadResult:
        """Загружает медиа по URL."""
        video_id = self.get_video_id(url)
        if not video_id:
            return DownloadResult(
                success=False,
                error='Не удалось извлечь ID видео из URL',
            )

        # Проверяем, существует ли уже
        existing_media = self.get_media_by_id(video_id)
        if existing_media.exists:
            logger.info('Видео %s уже существует, пропускаем загрузку', video_id)
            return DownloadResult(success=True, media=existing_media)

        try:
            with YoutubeDL(self._ydl_opts) as ydl:
                ydl.download([url])

            media = self.get_media_by_id(video_id)
            if media.exists:
                return DownloadResult(success=True, media=media)

            return DownloadResult(
                success=False,
                error='Файлы не найдены после загрузки',
            )

        except DownloadError as e:
            logger.exception('Ошибка загрузки URL %s', url)
            return DownloadResult(success=False, error=str(e))

        except Exception as e:
            logger.exception('Неожиданная ошибка при загрузке %s', url)
            return DownloadResult(success=False, error=str(e))


__all__ = ['YTDLPReceiver']
