import logging
import time
from collections.abc import Generator
from pathlib import Path
from threading import Event

import av
from av import AudioFrame, VideoFrame

from app.core.enums import StreamVisualMode
from app.deliver.constants import MAX_SYNC_DELAY, MIN_SYNC_DELAY
from app.deliver.context import AVContext
from app.deliver.interfaces import PlayerDeliver
from app.deliver.schemas import MediaAssetPaths, StreamerState
from app.deliver.utils import create_silence_frame, prepare_video_frame

logger = logging.getLogger(__name__)

Frame = AudioFrame | VideoFrame
FrameGenerator = Generator[Frame]


class AVFrameGenerator:
    def __init__(self, state: StreamerState) -> None:
        self.state = state

    @property
    def is_paused(self) -> bool:
        return not self.state.player.is_playing

    @property
    def is_running(self) -> bool:
        return not self.state.shutdown_event.is_set()

    def _get_thumbnail(self, media: MediaAssetPaths) -> VideoFrame:
        return prepare_video_frame(media.thumbnail) if media.exists else self.state.video_frame

    def _generate_placeholder_frames(
        self,
        video_frame: VideoFrame | None = None,
        audio_frame: AudioFrame | None = None,
    ) -> FrameGenerator:
        ctx = self.state.context
        video = video_frame or self.state.video_frame
        audio = audio_frame or self.state.audio_frame

        while self.is_running:
            if ctx.video_duration <= ctx.audio_duration:
                yield video

            else:
                yield audio

            if ctx.is_audio_video_synced:
                break

    def _generate_pause_frames(self, last_video_frame: VideoFrame) -> FrameGenerator:
        while self.is_paused and self.is_running:
            yield from self._generate_placeholder_frames(video_frame=last_video_frame)

    def _process_track(self, media: MediaAssetPaths) -> FrameGenerator:
        thumbnail = self._get_thumbnail(media)
        try:
            with av.open(media.mediafile, 'r') as container:
                ctx, player = self.state.context, self.state.player
                video_stream = next(iter(container.streams.video), None)
                audio_stream = next(iter(container.streams.audio), None)

                if video_stream:
                    ctx.create_graph(video_stream)

                if audio_stream:
                    ctx.create_graph(audio_stream)

                for packet in container.demux(video_stream, audio_stream):
                    for frame in packet.decode():
                        if not self.is_running or player.get_current() is not media:
                            return

                        if isinstance(frame, VideoFrame):
                            yield from self._process_video_frame(frame, thumbnail)
                        elif isinstance(frame, AudioFrame):
                            yield frame

        finally:
            self.state.context.flush()
            self.state.player.next()

    def _process_video_frame(self, frame: VideoFrame, thumbnail: VideoFrame) -> FrameGenerator:
        yield from self._generate_pause_frames(frame)

        match self.state.player.visual_mode:
            case StreamVisualMode.VIDEO_PLACEHOLDER:
                yield self.state.video_frame
            case StreamVisualMode.VIDEO_THUMBNAIL:
                yield thumbnail
            case StreamVisualMode.VIDEO_CONTENT:
                yield frame

    def generate_frames(self) -> FrameGenerator:
        while self.is_running:
            if track := self.state.player.get_current():
                yield from self._process_track(track)
            else:
                yield from self._generate_placeholder_frames()


class AVStreamer:
    def __init__(self, rtmps_url: str, player: PlayerDeliver, placeholder: Path) -> None:
        self._rtmps_url = rtmps_url
        self._player = player
        self._placeholder = placeholder
        self._shutdown_event = Event()

        self._stream_ctx: AVContext | None = None
        self._state: StreamerState | None = None

    @property
    def is_running(self) -> bool:
        return not self._shutdown_event.is_set()

    def run(self) -> None:
        try:
            logger.info('Запуск AVStreamer для %s', self._rtmps_url)
            with av.open(self._rtmps_url, 'w', format='flv') as broadcast:
                self._stream_ctx = AVContext(broadcast, low_latency=True)
                self._state = StreamerState(
                    audio_frame=create_silence_frame(),
                    video_frame=prepare_video_frame(self._placeholder),
                    context=self._stream_ctx,
                    player=self._player,
                    shutdown_event=self._shutdown_event,
                )
                self._run_streaming()

        except OSError:
            if self.is_running:
                logger.exception('Ошибка RTMPS соединения')

        except Exception:
            if self.is_running:
                logger.exception('Неожиданная ошибка в RTMP Player')

        finally:
            if self.is_running:
                self._shutdown_event.set()

            if self._stream_ctx is not None:
                self._stream_ctx.close()
                self._stream_ctx = None

            logger.info('RTMP Player остановлен')

    def _run_streaming(self) -> None:
        if self._state is None or self._stream_ctx is None:
            raise RuntimeError('Streamer state or context is not initialized.')

        start_time = time.time()
        frame_generator = AVFrameGenerator(self._state)
        for frame in frame_generator.generate_frames():
            if not self.is_running:
                break

            # Check if frame is cached
            is_cached = self._state.is_cached(frame)

            # Encode frame
            if isinstance(frame, AudioFrame):
                self._stream_ctx.encode_audio(frame, apply_filters=not is_cached)
            elif isinstance(frame, VideoFrame):
                self._stream_ctx.encode_video(frame, apply_filters=not is_cached)

            # Sync playback
            elapsed = time.time() - start_time
            delay = float(self._stream_ctx.duration) - elapsed

            if delay > MIN_SYNC_DELAY:
                self.wait(min(delay, MAX_SYNC_DELAY))

    def wait(self, delay: float) -> None:
        self._shutdown_event.wait(delay)

    def stop(self) -> None:
        if self.is_running:
            logger.info('Остановка AVStreamer для %s', self._rtmps_url)
            self._shutdown_event.set()
            return

        logger.info('AVStreamer для %s уже остановлен', self._rtmps_url)
