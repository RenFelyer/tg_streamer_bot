import logging
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yt_dlp
from yt_dlp.utils import DownloadError

from app.core.config import settings
from app.core.interfaces import ContentDownloader
from app.core.schemas import MediaPaths

if TYPE_CHECKING:
    from yt_dlp import _Params


# Настройка логирования
logger = logging.getLogger(__name__)


class YTDownloader(ContentDownloader):
    def __init__(self, download_dir: Path) -> None:
        self.ydl_opts: _Params = {
            # 1. Вывод
            'outtmpl': str(download_dir / '%(title)s [%(id)s].%(ext)s'),
            # 2. Формат
            'format': 'bestaudio+(bestvideo[height<=720]/bestvideo)/best',
            'merge_output_format': 'mp4',
            # 3. Поведение
            'noplaylist': True,
            'overwrites': False,
            'continuedl': True,
            # 4. Превью
            'writethumbnail': True,
            # 5. Имитация (без опасных пропусков)
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'web'],
                    'skip': ['dash', 'hls'],
                },
            },
            # 6. Логи
            'quiet': True,
            'no_warnings': True,
            'verbose': False,
            'progress_hooks': [self.progress_hooks],
            # 7. Постобработка
            'postprocessors': [
                {
                    'key': 'FFmpegMetadata',
                    'add_chapters': True,
                    'add_metadata': True,
                },
                {
                    'key': 'FFmpegThumbnailsConvertor',
                    'format': 'jpg',
                },
                {
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                },
            ],
            'postprocessor_args': {
                'thumbnailsconvertor': ['-vf', 'scale=480:-1'],
            },
        }
        super().__init__(download_dir)

    def progress_hooks(self, d: Mapping[str, Any]) -> None:
        if d['status'] != 'downloading':
            return

        logger.info('Загрузка: %s - %s complete', Path(d['filename']).name, d['_percent_str'])

    def get_media_by_id(self, video_id: str) -> MediaPaths:
        return MediaPaths(
            mediafile_id=video_id,
            mediafile_path=next(settings.multimedia_dir.glob(f'*[[]{video_id}].mp4'), None),
            thumbnail_path=next(settings.multimedia_dir.glob(f'*[[]{video_id}].jpg'), None),
        )

    def get_video_id(self, url: str) -> str | None:
        ydl_opts: _Params = {
            'quiet': True,
            'extract_flat': True,
            'force_generic_extractor': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info.get('id')
        except Exception:
            logger.exception('Не удалось извлечь ID из ссылки: %s', url)
            return None

    def download(self, url: str) -> MediaPaths | None:
        video_id = self.get_video_id(url)
        if not video_id:
            return None

        if (existing_media := self.get_media_by_id(video_id)).exists:
            logger.info('Видео %s уже существует, пропускаем скачивание.', video_id)
            return existing_media

        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                ydl.download([url])

            return self.get_media_by_id(video_id)

        except DownloadError:
            logger.exception('DownloadError при обработке URL %s', url)

        except Exception:
            logger.exception('Необработанная ошибка при скачивании %s', url)

        return None
