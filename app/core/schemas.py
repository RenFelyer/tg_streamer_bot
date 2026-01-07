from pathlib import Path

from pydantic import BaseModel, Field


class MediaPaths(BaseModel):
    """Модель для возврата путей к медиафайлам."""

    mediafile_id: str
    mediafile_path: Path | None = Field(default=None, description='Путь к видео/аудио файлу')
    thumbnail_path: Path | None = Field(default=None, description='Путь к превью')

    @property
    def exists(self) -> bool:
        """Проверяет, существуют ли найденные файлы физически."""
        m_exists = self.mediafile_path.exists() if self.mediafile_path else False
        t_exists = self.thumbnail_path.exists() if self.thumbnail_path else False
        return m_exists or t_exists


class TimingParams(BaseModel):
    """Container for encoding timing parameters."""

    video_pts_increment: int = Field(..., description='PTS increment for video frames')
    audio_pts_increment: int = Field(..., description='PTS increment for audio frames')
