from fractions import Fraction
from typing import Final

from app.core.config.environ import settings

AUDIO_RATE: Final[int] = 48000
AUDIO_FORMAT: Final[str] = 'fltp'
AUDIO_LAYOUT: Final[str] = 'stereo'
AUDIO_FRAME_SIZE: Final[int] = 1024
AUDIO_BITRATE: Final[int] = 128_000  # 128 Kbps

VIDEO_RATE: Final[Fraction] = Fraction(30000, 1001)
VIDEO_PIX_FMT: Final[str] = 'yuv420p'
VIDEO_BITRATE: Final[int] = 2_000_000  # 2 Mbps
VIDEO_WIDTH: Final[int] = settings.width
VIDEO_HEIGHT: Final[int] = settings.height

VIDEO_TIME_BASE = Fraction(1, VIDEO_RATE)
AUDIO_TIME_BASE = Fraction(1, AUDIO_RATE)

__all__ = [
    'AUDIO_BITRATE',
    'AUDIO_FORMAT',
    'AUDIO_FRAME_SIZE',
    'AUDIO_LAYOUT',
    'AUDIO_RATE',
    'AUDIO_TIME_BASE',
    'VIDEO_BITRATE',
    'VIDEO_HEIGHT',
    'VIDEO_PIX_FMT',
    'VIDEO_RATE',
    'VIDEO_TIME_BASE',
    'VIDEO_WIDTH',
]
