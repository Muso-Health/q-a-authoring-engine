from __future__ import annotations

import asyncio
import json
import os
import tempfile
from typing import TYPE_CHECKING, Any

from qa_authoring.application.ports.audio_probe import ProbedAudio, UnreadableAudioError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

type Runner = Callable[[list[str]], Awaitable[tuple[int, bytes]]]

_MIME_BY_FORMAT = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "ogg": "audio/ogg",
    "matroska,webm": "audio/webm",
    "mov,mp4,m4a,3gp,3g2,mj2": "audio/mp4",
    "flac": "audio/flac",
}


async def _run(args: list[str]) -> tuple[int, bytes]:
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
    )
    stdout, _ = await process.communicate()
    return process.returncode or 0, stdout


class FfprobeAudioProbe:
    """The audio probe port on ffprobe (ffmpeg). The bytes are probed from a temporary file (an
    mp4/m4a can keep its index at the end, out of reach of a pipe). Browser MediaRecorder webm
    has no container duration, so it is measured from the last audio packet instead."""

    def __init__(self, binary: str = "ffprobe", runner: Runner = _run) -> None:
        self._binary = binary
        self._runner = runner

    async def probe(self, content: bytes) -> ProbedAudio:
        with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as file:
            file.write(content)
            path = file.name
        try:
            return await self._probe_file(path)
        finally:
            os.unlink(path)

    async def _probe_file(self, path: str) -> ProbedAudio:
        info = await self._ffprobe(
            "-show_entries", "format=format_name,duration:stream=codec_type", path
        )
        streams = info.get("streams") or []
        fmt = info.get("format") or {}
        format_name = fmt.get("format_name")
        if not format_name or not any(s.get("codec_type") == "audio" for s in streams):
            raise UnreadableAudioError("no audio stream found")
        duration = _seconds(fmt.get("duration"))
        if duration is None:
            duration = await self._duration_from_packets(path)
        mime = _MIME_BY_FORMAT.get(format_name, f"audio/x-{format_name.split(',')[0]}")
        return ProbedAudio(duration_ms=int(duration * 1000), mime_type=mime)

    async def _duration_from_packets(self, path: str) -> float:
        info = await self._ffprobe(
            "-select_streams", "a:0", "-show_entries", "packet=pts_time,duration_time", path
        )
        ends = [
            start + (_seconds(packet.get("duration_time")) or 0.0)
            for packet in info.get("packets") or []
            if (start := _seconds(packet.get("pts_time"))) is not None
        ]
        if not ends:
            raise UnreadableAudioError("could not determine the audio duration")
        return max(ends)

    async def _ffprobe(self, *args: str) -> dict[str, Any]:
        command = [self._binary, "-v", "error", "-print_format", "json", *args]
        try:
            code, stdout = await self._runner(command)
        except FileNotFoundError as exc:
            raise UnreadableAudioError(f"ffprobe not found at {self._binary!r}") from exc
        if code != 0:
            raise UnreadableAudioError("ffprobe could not read the file")
        try:
            parsed: dict[str, Any] = json.loads(stdout)
        except ValueError as exc:
            raise UnreadableAudioError("unexpected ffprobe output") from exc
        return parsed


def _seconds(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
