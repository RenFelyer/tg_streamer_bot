from abc import ABC, abstractmethod
from pathlib import Path

from app.receive.schemas import DownloadResult, MediaPaths


class ContentReceiver(ABC):
    """Абстрактный класс для получения медиаконтента."""

    def __init__(self, download_dir: Path) -> None:
        self.download_dir = download_dir

    @abstractmethod
    def download(self, url: str) -> DownloadResult:
        """Загружает медиа по URL и возвращает результат."""

    @abstractmethod
    def get_media_by_id(self, video_id: str) -> MediaPaths:
        """Возвращает пути к медиафайлам по идентификатору."""

    @abstractmethod
    def get_video_id(self, url: str) -> str | None:
        """Извлекает идентификатор видео из URL."""


__all__ = ['ContentReceiver']
