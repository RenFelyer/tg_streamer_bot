from collections.abc import Generator
from fractions import Fraction
from pathlib import Path
from typing import overload

import av
import numpy as np
from av.filter import Graph
from PIL import Image

from app.deliver.constants import (
    AUDIO_FORMAT,
    AUDIO_FRAME_SIZE,
    AUDIO_LAYOUT,
    AUDIO_RATE,
    AUDIO_TIME_BASE,
    VIDEO_HEIGHT,
    VIDEO_PIX_FMT,
    VIDEO_RATE,
    VIDEO_TIME_BASE,
    VIDEO_WIDTH,
)


def create_video_graph(stream: av.VideoStream) -> Graph:
    graph = Graph()
    graph.link_nodes(
        graph.add_buffer(template=stream),
        graph.add('scale', f'{VIDEO_WIDTH}:{VIDEO_HEIGHT}'),
        graph.add('fps', f'fps={VIDEO_RATE}'),
        graph.add('format', f'pix_fmts={VIDEO_PIX_FMT}'),
        graph.add('setpts', 'PTS-STARTPTS'),
        graph.add('buffersink'),
    ).configure()
    return graph


def create_audio_graph(stream: av.AudioStream) -> Graph:
    graph = Graph()
    graph.link_nodes(
        graph.add_abuffer(template=stream),
        graph.add('aformat', f'sample_fmts={AUDIO_FORMAT}:channel_layouts={AUDIO_LAYOUT}:sample_rates={AUDIO_RATE}'),
        graph.add('asetpts', 'PTS-STARTPTS'),
        graph.add('abuffersink'),
    ).configure()
    return graph


@overload
def iter_filtered_frames(graph: Graph, frame: av.AudioFrame) -> Generator[av.AudioFrame]: ...


@overload
def iter_filtered_frames(graph: Graph, frame: av.VideoFrame) -> Generator[av.VideoFrame]: ...


@overload
def iter_filtered_frames(graph: Graph, frame: None) -> Generator[av.AudioFrame | av.VideoFrame]: ...


def iter_filtered_frames(
    graph: Graph,
    frame: av.AudioFrame | av.VideoFrame | None,
) -> Generator[av.AudioFrame | av.VideoFrame]:
    graph.push(frame)
    while True:
        try:
            filtered_frame = graph.pull()
            if filtered_frame.pts is None:
                continue

            yield filtered_frame

        except (av.BlockingIOError, av.EOFError):
            break


def create_silence_frame() -> av.AudioFrame:
    """Создает аудио-фрейм с тишиной (нули) в формате float planar (fltp)."""
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


def __calculate_pts_increments() -> tuple[int, int]:
    video_frame_duration = Fraction(1) / VIDEO_RATE
    audio_frame_duration = Fraction(AUDIO_FRAME_SIZE, AUDIO_RATE)

    video_pts_increment = int(video_frame_duration / VIDEO_TIME_BASE)
    audio_pts_increment = int(audio_frame_duration / AUDIO_TIME_BASE)
    return video_pts_increment, audio_pts_increment
