from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True, kw_only=True)
class MediaPaths:
    """Пути к медиафайлу и его превью."""

    identifier: str  # Уникальный идентификатор (video_id)
    mediafile_path: Path | None  # Путь к медиафайлу
    thumbnail_path: Path | None  # Путь к превью

    @property
    def exists(self) -> bool:
        """Проверяет, существуют ли оба файла."""
        if self.mediafile_path is None or self.thumbnail_path is None:
            return False
        return self.mediafile_path.exists() and self.thumbnail_path.exists()


@dataclass(frozen=True, slots=True, kw_only=True)
class DownloadResult:
    """Результат загрузки медиа."""

    success: bool
    media: MediaPaths | None = None
    error: str | None = None


__all__ = ['DownloadResult', 'MediaPaths']
