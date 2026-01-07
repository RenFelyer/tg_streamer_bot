import functools
from collections.abc import Callable, Generator
from fractions import Fraction
from pathlib import Path
from typing import Any

import av
import numpy as np
from av.container import OutputContainer
from av.filter import Graph
from PIL import Image

from app.core.config.constants import (
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
from app.core.schemas import TimingParams


class StreamContext:
    """Context for video and audio streams encoding."""

    def __init__(self, container: OutputContainer, *, low_latency: bool = True) -> None:
        self.container = container
        self._low_latency = low_latency

        # Инициализация выходных потоков в контейнере (кодеки h264/aac, битрейт, таймбейсы)
        self.video_stream: av.VideoStream = self._setup_video_stream()
        self.audio_stream: av.AudioStream = self._setup_audio_stream()

        # Графы фильтров для обработки raw-данных (скейлинг, ресемплинг, format conversion)
        # Инициализируются лениво или явно через create_graph()
        self.video_graph: Graph | None = None
        self.audio_graph: Graph | None = None

        # Глобальные смещения PTS (Presentation Time Stamp).
        # Критически важны при конкатенации: позволяют "сдвигать" время начала следующего
        # сегмента относительно конца предыдущего.
        self.offset_audio_pts: int = 0
        self.offset_video_pts: int = 0

        # Хранение последних записанных PTS для каждого потока.
        # Используются для расчета длительности и вычисления offset для следующего файла.
        self._last_audio_pts: int = 0
        self._last_video_pts: int = 0

        # Диспатчер: сопоставляет тип входящего кадра с методом его кодирования.
        self._encoders: dict[type[av.AudioFrame | av.VideoFrame], Callable[[Any], None]] = {
            av.AudioFrame: self.encode_audio,
            av.VideoFrame: self.encode_video,
        }

    def _setup_video_stream(self) -> av.VideoStream:
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

    def _setup_audio_stream(self) -> av.AudioStream:
        stream = self.container.add_stream('aac', rate=AUDIO_RATE)
        stream.layout = AUDIO_LAYOUT
        stream.format = AUDIO_FORMAT
        stream.bit_rate = AUDIO_BITRATE
        stream.time_base = AUDIO_TIME_BASE
        return stream

    def encode_mux(self, _frame: Any) -> bool:
        if isinstance(_frame, av.AudioFrame):
            self.encode_audio(_frame)
            return True

        if isinstance(_frame, av.VideoFrame):
            self.encode_video(_frame)
            return True

        return False

    def create_graph(self, stream: av.AudioStream | av.VideoStream) -> None:
        """Создает граф фильтров для указанного потока."""
        graph = Graph()
        if isinstance(stream, av.VideoStream):
            graph.link_nodes(
                graph.add_buffer(template=stream),
                graph.add('scale', f'{VIDEO_WIDTH}:{VIDEO_HEIGHT}'),
                graph.add('fps', f'fps={VIDEO_RATE}'),
                graph.add('format', f'pix_fmts={VIDEO_PIX_FMT}'),
                graph.add('setpts', 'PTS-STARTPTS'),
                graph.add('buffersink'),
            ).configure()
            self.video_graph = graph

        elif isinstance(stream, av.AudioStream):
            args = f'sample_fmts={AUDIO_FORMAT}:channel_layouts={AUDIO_LAYOUT}:sample_rates={AUDIO_RATE}'
            graph.link_nodes(
                graph.add_abuffer(template=stream),
                graph.add('aformat', args),
                graph.add('asetpts', 'PTS-STARTPTS'),
                graph.add('abuffersink'),
            ).configure()
            self.audio_graph = graph
        else:
            raise TypeError(f'Unsupported stream type for graph creation: {type(stream).__name__}')

    def encode_video(self, frame: av.VideoFrame | None) -> None:
        if self.video_graph:
            self.video_graph.push(frame)
            while True:
                try:
                    filtered_frame = self.video_graph.pull()
                    filtered_frame.dts = None  # Сброс DTS обязателен
                    if filtered_frame.pts is None:
                        continue

                    filtered_frame.time_base = VIDEO_TIME_BASE
                    filtered_frame.pts = filtered_frame.pts + self.offset_video_pts
                    self._last_video_pts = max(self._last_video_pts, filtered_frame.pts)
                    for packet in self.video_stream.encode(filtered_frame):  # type: ignore
                        self.container.mux(packet)

                except (av.BlockingIOError, av.EOFError):
                    break

        # Без графа: применяем offset к фрейму до кодирования
        elif frame is not None and frame.pts is not None:
            frame.time_base = VIDEO_TIME_BASE
            frame.pts = frame.pts + self.offset_video_pts
            self._last_video_pts = max(self._last_video_pts, frame.pts)
            for packet in self.video_stream.encode(frame):
                self.container.mux(packet)

        else:
            # Flush encoder
            for packet in self.video_stream.encode(None):
                self.container.mux(packet)

    def encode_audio(self, frame: av.AudioFrame | None) -> None:
        if self.audio_graph:
            self.audio_graph.push(frame)
            while True:
                try:
                    filtered_frame = self.audio_graph.pull()
                    filtered_frame.dts = None  # Сброс DTS обязателен
                    if filtered_frame.pts is None:
                        continue

                    filtered_frame.time_base = AUDIO_TIME_BASE
                    filtered_frame.pts = filtered_frame.pts + self.offset_audio_pts
                    self._last_audio_pts = max(self._last_audio_pts, filtered_frame.pts)
                    for packet in self.audio_stream.encode(filtered_frame):  # type: ignore
                        self.container.mux(packet)

                except (av.BlockingIOError, av.EOFError):
                    break

        # Без графа: применяем offset к фрейму до кодирования
        elif frame is not None and frame.pts is not None:
            frame.time_base = AUDIO_TIME_BASE
            frame.pts = frame.pts + self.offset_audio_pts
            self._last_audio_pts = max(self._last_audio_pts, frame.pts)
            for packet in self.audio_stream.encode(frame):
                self.container.mux(packet)

        else:
            # Flush encoder
            for packet in self.audio_stream.encode(None):
                self.container.mux(packet)

    def flush(self, *, close: bool = False) -> None:
        """Сбрасывает буферы кодировщиков."""
        while self.audio_graph or close:
            self.encode_audio(None)
            if self.audio_graph:
                self.audio_graph = None
                continue

            break

        while self.video_graph or close:
            self.encode_video(None)
            if self.video_graph:
                self.video_graph = None
                continue

            break

        # Обновляем offset после flush - это нужно для корректной конкатенации сегментов
        self.offset_audio_pts = self._last_audio_pts + 1
        self.offset_video_pts = self._last_video_pts + 1

    @property
    def duration(self) -> Fraction:
        """Возвращает текущую длительность в секундах."""
        if self._last_audio_pts > self._last_video_pts:
            return self._last_audio_pts * AUDIO_TIME_BASE

        return self._last_video_pts * VIDEO_TIME_BASE

    @property
    def offsets(self) -> tuple[int, int]:
        """Возвращает текущие смещения (audio_pts, video_pts)."""
        return (self.offset_audio_pts, self.offset_video_pts)


@functools.lru_cache(maxsize=128)
def calculate_timing_params() -> TimingParams:
    """Calculate PTS increments for synchronized encoding."""
    video_frame_duration = Fraction(1) / VIDEO_RATE
    audio_frame_duration = Fraction(AUDIO_FRAME_SIZE, AUDIO_RATE)

    return TimingParams(
        video_pts_increment=int(video_frame_duration / VIDEO_TIME_BASE),
        audio_pts_increment=int(audio_frame_duration / AUDIO_TIME_BASE),
    )


def create_silence_frame() -> av.AudioFrame:
    """Создает аудио-фрейм с тишиной (нули) в формате float planar (fltp)."""
    # Создаем массив нулей: 2 канала (stereo), длина AUDIO_FRAME_SIZE, тип float32
    array = np.zeros((2, AUDIO_FRAME_SIZE), dtype=np.float32)

    frame = av.AudioFrame.from_ndarray(array, format=AUDIO_FORMAT, layout=AUDIO_LAYOUT)
    frame.sample_rate = AUDIO_RATE
    frame.time_base = AUDIO_TIME_BASE
    return frame


def prepare_video_frame(image_path: Path) -> av.VideoFrame:
    """Создает видео-фрейм из картинки на диске."""
    if not image_path.exists():
        raise FileNotFoundError(f'Thumbnail image not found at {image_path}')

    with Image.open(image_path) as img:
        _img = img.convert('RGB')
        if _img.size != (VIDEO_WIDTH, VIDEO_HEIGHT):
            _img = _img.resize((VIDEO_WIDTH, VIDEO_HEIGHT), Image.Resampling.LANCZOS)

        frame: av.VideoFrame = av.VideoFrame.from_image(_img)
        if not isinstance(frame, av.VideoFrame):
            raise TypeError('Failed to create VideoFrame from image.')

        frame.time_base = VIDEO_TIME_BASE
        return frame.reformat(VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_PIX_FMT)


def interleave_frames(
    audio_frame: av.AudioFrame,
    video_frame: av.VideoFrame,
    duration_seconds: int | None = None,
) -> Generator[av.AudioFrame | av.VideoFrame, Any]:
    timing = calculate_timing_params()
    total_duration = Fraction(duration_seconds) if duration_seconds else None

    video_time = audio_time = Fraction(0)
    audio_pts, video_pts = 0, 0

    while True:
        video_done = total_duration is not None and video_time >= total_duration
        audio_done = total_duration is not None and audio_time >= total_duration

        if video_done and audio_done:
            break

        # Interleave: кодируем тот поток, который "отстаёт"
        if not video_done and (audio_done or video_time <= audio_time):
            video_frame.pts = video_pts
            yield video_frame
            video_pts += timing.video_pts_increment
            video_time = video_pts * VIDEO_TIME_BASE

        if not audio_done and audio_time < video_time:
            audio_frame.pts = audio_pts
            yield audio_frame
            audio_pts += timing.audio_pts_increment
            audio_time = audio_pts * AUDIO_TIME_BASE
