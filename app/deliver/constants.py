from fractions import Fraction

from app.core.config.environ import settings

AUDIO_RATE = 48000
AUDIO_FORMAT = 'fltp'
AUDIO_LAYOUT = 'stereo'
AUDIO_FRAME_SIZE = 1024
AUDIO_BITRATE = 128_000  # 128 Kbps

VIDEO_RATE = Fraction(30000, 1001)
VIDEO_PIX_FMT = 'yuv420p'
VIDEO_BITRATE = 2_000_000  # 2 Mbps
VIDEO_WIDTH = settings.width
VIDEO_HEIGHT = settings.height

VIDEO_TIME_BASE = Fraction(1, VIDEO_RATE)
AUDIO_TIME_BASE = Fraction(1, AUDIO_RATE)

MIN_SYNC_DELAY: float = 0.001
MAX_SYNC_DELAY: float = 0.050
SYNC_TOLERANCE = Fraction(50, 1000)

__all__ = [
    'AUDIO_BITRATE',
    'AUDIO_FORMAT',
    'AUDIO_FRAME_SIZE',
    'AUDIO_LAYOUT',
    'AUDIO_RATE',
    'AUDIO_TIME_BASE',
    'MAX_SYNC_DELAY',
    'MIN_SYNC_DELAY',
    'SYNC_TOLERANCE',
    'VIDEO_BITRATE',
    'VIDEO_HEIGHT',
    'VIDEO_PIX_FMT',
    'VIDEO_RATE',
    'VIDEO_TIME_BASE',
    'VIDEO_WIDTH',
]
