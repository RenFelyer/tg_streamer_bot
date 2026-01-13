from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from av import AudioFrame, VideoFrame

if TYPE_CHECKING:
    from pathlib import Path
    from threading import Event

    from app.deliver.context import AVContext
    from app.deliver.interfaces import PlayerDeliver


@dataclass(frozen=True, slots=True, kw_only=True)
class MediaAssetPaths:
    mediafile: Path  # Путь к медиафайлу
    thumbnail: Path  # Путь к превьюшке

    @property
    def exists(self) -> bool:
        return self.mediafile.exists() and self.thumbnail.exists()


@dataclass(frozen=True, slots=True, kw_only=True)
class StreamerState:
    audio_frame: AudioFrame
    video_frame: VideoFrame

    context: AVContext
    player: PlayerDeliver
    shutdown_event: Event

    def is_cached(self, frame: AudioFrame | VideoFrame) -> bool:
        return frame is self.audio_frame or frame is self.video_frame


__all__ = ['MediaAssetPaths', 'StreamerState']
