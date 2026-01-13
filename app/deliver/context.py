from fractions import Fraction

from av import AudioFrame, AudioStream, VideoFrame, VideoStream
from av.container import OutputContainer
from av.filter import Graph

from app.deliver.constants import (
    AUDIO_BITRATE,
    AUDIO_FORMAT,
    AUDIO_FRAME_SIZE,
    AUDIO_LAYOUT,
    AUDIO_RATE,
    AUDIO_TIME_BASE,
    VIDEO_BITRATE,
    VIDEO_HEIGHT,
    VIDEO_PIX_FMT,
    VIDEO_RATE,
    VIDEO_TIME_BASE,
    VIDEO_WIDTH,
)
from app.deliver.interfaces import ContextDeliver
from app.deliver.utils import create_audio_graph, create_video_graph, iter_filtered_frames


class AVContext(ContextDeliver):
    def __init__(self, container: OutputContainer, *, low_latency: bool = True) -> None:
        self.container = container
        self._low_latency = low_latency

        self.video_stream: VideoStream = self._setup_video_stream()
        self.audio_stream: AudioStream = self._setup_audio_stream()

        self.video_graph: Graph | None = None
        self.audio_graph: Graph | None = None

        self.offset_audio_pts: int = 0
        self.offset_video_pts: int = 0

    def _setup_video_stream(self) -> VideoStream:
        stream = self.container.add_stream('h264', rate=VIDEO_RATE)
        stream.width = VIDEO_WIDTH
        stream.height = VIDEO_HEIGHT
        stream.pix_fmt = VIDEO_PIX_FMT
        stream.bit_rate = VIDEO_BITRATE
        stream.time_base = VIDEO_TIME_BASE
        stream.gop_size = int(VIDEO_RATE * 2)
        if self._low_latency:
            stream.options = {
                'preset': 'ultrafast',
                'tune': 'zerolatency',
                'profile': 'baseline',
            }
        return stream

    def _setup_audio_stream(self) -> AudioStream:
        stream = self.container.add_stream('aac', rate=AUDIO_RATE)
        stream.layout = AUDIO_LAYOUT
        stream.format = AUDIO_FORMAT
        stream.bit_rate = AUDIO_BITRATE
        stream.time_base = AUDIO_TIME_BASE
        return stream

    def _encode_video(self, frame: VideoFrame | None) -> None:
        if frame is not None:
            self.offset_video_pts += 1
            frame.time_base = VIDEO_TIME_BASE
            frame.pts = self.offset_video_pts

        for packet in self.video_stream.encode(frame):
            self.container.mux(packet)

    def _encode_audio(self, frame: AudioFrame | None) -> None:
        if frame is not None:
            self.offset_audio_pts += frame.samples
            frame.time_base = AUDIO_TIME_BASE
            frame.pts = self.offset_audio_pts

        for packet in self.audio_stream.encode(frame):
            self.container.mux(packet)

    def create_graph(self, stream: AudioStream | VideoStream) -> None:
        """Создает граф фильтров для указанного потока."""
        if isinstance(stream, VideoStream):
            self.video_graph = create_video_graph(stream)

        elif isinstance(stream, AudioStream):
            self.audio_graph = create_audio_graph(stream)

        else:
            raise TypeError(f'Unsupported stream type for graph creation: {type(stream).__name__}')

    def encode_video(self, frame: VideoFrame | None, *, apply_filters: bool = True) -> None:
        """Кодирует видео-фрейм и записывает пакеты в контейнер."""
        if self.video_graph is not None and apply_filters:
            for filtered_frame in iter_filtered_frames(self.video_graph, frame):
                if not isinstance(filtered_frame, VideoFrame):
                    continue

                self._encode_video(filtered_frame)

        elif frame is not None:
            self._encode_video(frame)

    def encode_audio(self, frame: AudioFrame | None, *, apply_filters: bool = True) -> None:
        """Кодирует аудио-фрейм и записывает пакеты в контейнер."""
        if self.audio_graph is not None and apply_filters:
            for filtered_frame in iter_filtered_frames(self.audio_graph, frame):
                if not isinstance(filtered_frame, AudioFrame):
                    continue

                self._encode_audio(filtered_frame)

        elif frame is not None:
            self._encode_audio(frame)

    @property
    def audio_duration(self) -> Fraction:
        return self.offset_audio_pts * AUDIO_TIME_BASE

    @property
    def video_duration(self) -> Fraction:
        return self.offset_video_pts * VIDEO_TIME_BASE

    def flush(self) -> None:
        if self.audio_graph is not None:
            self.encode_audio(None)
            self.audio_graph = None

        if self.video_graph is not None:
            self.encode_video(None)
            self.video_graph = None

    def close(self) -> None:
        self.flush()
        self._encode_audio(None)
        self._encode_video(None)


__all__ = ['AVContext']
