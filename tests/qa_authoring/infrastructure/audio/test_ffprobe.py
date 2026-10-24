from __future__ import annotations

import io
import json
import shutil
import wave
from pathlib import Path

import pytest

from qa_authoring.application.ports.audio_probe import ProbedAudio, UnreadableAudioError
from qa_authoring.infrastructure.audio.ffprobe import FfprobeAudioProbe

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "audio"


def _format(format_name: str, duration: str | None, codec_type: str = "audio") -> bytes:
    fmt: dict[str, str] = {"format_name": format_name}
    if duration is not None:
        fmt["duration"] = duration
    return json.dumps({"streams": [{"codec_type": codec_type}], "format": fmt}).encode()


class FakeRunner:
    """Answers ffprobe calls with canned JSON (shaped like real ffprobe 7.1 output)."""

    def __init__(self, format_json: bytes, packets: list[dict[str, str]] | None = None) -> None:
        self.format_json = format_json
        self.packets = packets or []
        self.calls: list[list[str]] = []

    async def __call__(self, args: list[str]) -> tuple[int, bytes]:
        self.calls.append(args)
        assert Path(args[-1]).is_file()  # probed from a real file, not a pipe
        if "packet=pts_time,duration_time" in args:
            return 0, json.dumps({"packets": self.packets}).encode()
        return 0, self.format_json


@pytest.mark.parametrize(
    ("format_name", "duration", "expected"),
    [
        ("wav", "1.500000", ProbedAudio(1500, "audio/wav")),
        ("ogg", "1.506500", ProbedAudio(1506, "audio/ogg")),
        ("mp3", "1.541224", ProbedAudio(1541, "audio/mpeg")),
        ("mov,mp4,m4a,3gp,3g2,mj2", "1.500000", ProbedAudio(1500, "audio/mp4")),
        ("matroska,webm", "2.000000", ProbedAudio(2000, "audio/webm")),
        ("flac", "1.0", ProbedAudio(1000, "audio/flac")),
        ("aiff", "1.0", ProbedAudio(1000, "audio/x-aiff")),
    ],
)
async def test_maps_container_and_duration(
    format_name: str, duration: str, expected: ProbedAudio
) -> None:
    runner = FakeRunner(_format(format_name, duration))
    assert await FfprobeAudioProbe(runner=runner).probe(b"bytes") == expected
    assert len(runner.calls) == 1


async def test_mediarecorder_webm_without_duration_falls_back_to_packets() -> None:
    packets = [
        {"pts_time": "-0.007000", "duration_time": "0.020000"},
        {"pts_time": "0.014000", "duration_time": "0.020000"},
        {"pts_time": "1.494000", "duration_time": "0.020000"},
    ]
    runner = FakeRunner(_format("matroska,webm", None), packets)

    probed = await FfprobeAudioProbe(runner=runner).probe(b"webm bytes")

    assert probed == ProbedAudio(1514, "audio/webm")
    assert len(runner.calls) == 2


@pytest.mark.parametrize(
    "runner",
    [
        FakeRunner(b"{}"),
        FakeRunner(_format("mp4", "1.0", codec_type="video")),
        FakeRunner(_format("matroska,webm", None), packets=[]),
        FakeRunner(b"not json"),
    ],
)
async def test_unreadable_audio(runner: FakeRunner) -> None:
    with pytest.raises(UnreadableAudioError):
        await FfprobeAudioProbe(runner=runner).probe(b"bytes")


async def test_ffprobe_failure_is_unreadable() -> None:
    async def failing(args: list[str]) -> tuple[int, bytes]:
        return 1, b""

    with pytest.raises(UnreadableAudioError):
        await FfprobeAudioProbe(runner=failing).probe(b"bytes")


async def test_missing_binary_is_unreadable() -> None:
    with pytest.raises(UnreadableAudioError, match="ffprobe"):
        await FfprobeAudioProbe(binary="/nonexistent/ffprobe").probe(b"bytes")


real_ffprobe = pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffprobe not installed")


def _wav(seconds: float) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(8000)
        out.writeframes(b"\x00\x00" * int(8000 * seconds))
    return buffer.getvalue()


@real_ffprobe
async def test_real_ffprobe_on_wav() -> None:
    assert await FfprobeAudioProbe().probe(_wav(1.25)) == ProbedAudio(1250, "audio/wav")


@real_ffprobe
async def test_real_ffprobe_on_mediarecorder_webm() -> None:
    content = (FIXTURES / "mediarecorder-no-duration.webm").read_bytes()
    probed = await FfprobeAudioProbe().probe(content)
    assert probed.mime_type == "audio/webm"
    assert 1400 <= probed.duration_ms <= 1600


@real_ffprobe
async def test_real_ffprobe_rejects_junk() -> None:
    with pytest.raises(UnreadableAudioError):
        await FfprobeAudioProbe().probe(b"definitely not audio")
