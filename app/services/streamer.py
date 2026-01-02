import time
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING

import av
from av.audio.frame import AudioFrame
from av.video.frame import VideoFrame

from app.core.config import settings
from app.core.interfaces import StreamManager
from app.core.schemas import MediaPaths

if TYPE_CHECKING:
    from av.audio.stream import AudioStream
    from av.container.input import InputContainer
    from av.container.output import OutputContainer
    from av.video.stream import VideoStream


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


class TGStreamer(StreamManager):
    def __init__(self) -> None:
        super().__init__()

        self.media_reader: InputContainer | None = None
        self.broadcaster: OutputContainer | None = None
        self.audio_stream: AudioStream | None = None
        self.video_stream: VideoStream | None = None

    def start_stream(self) -> None:
        """Запускает потоковую передачу."""
        self.broadcaster = av.open(settings.rtmps_url, 'w', format='flv')
        self.audio_stream = self.broadcaster.add_stream('aac', rate=AUDIO_RATE)
        self.audio_stream.layout = AUDIO_LAYOUT
        self.audio_stream.format = AUDIO_FORMAT
        self.audio_stream.bit_rate = AUDIO_BITRATE

        self.video_stream = self.broadcaster.add_stream('h264', rate=VIDEO_RATE)
        self.video_stream.width = VIDEO_WIDTH
        self.video_stream.height = VIDEO_HEIGHT
        self.video_stream.pix_fmt = VIDEO_PIX_FMT  # Важно для совместимости
        self.video_stream.gop_size = int(VIDEO_RATE * 2)  # GOP size of 2 seconds
        self.video_stream.bit_rate = VIDEO_BITRATE
        self.video_stream.options = {
            'preset': 'ultrafast',  # Быстрое кодирование, чтобы не было лагов
            'tune': 'zerolatency',  # Минимальная задержка
        }

    def select_track(self, index: int) -> None:
        """Принудительно переключает курсор на указанный индекс."""
        if not (0 <= index < len(self.media_queue)):
            return

        self.current_index = index
        media = self.media_queue[self.current_index]
        self.media_reader = av.open(media.mediafile_path, mode='r')

    def pause_current_track(self) -> None:
        raise NotImplementedError

    def resume_current_track(self) -> None:
        raise NotImplementedError

    def restart_current_track(self) -> None:
        raise NotImplementedError

    def next_track(self) -> None:
        raise NotImplementedError

    def prev_track(self) -> None:
        raise NotImplementedError

    def run(self) -> None:
        pass
