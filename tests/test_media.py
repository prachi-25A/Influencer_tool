from pathlib import Path

from transcription.audio_processor import load_audio
from transcription.video_processor import extract_audio


def test_load_audio_mp3(tmp_path):
    sample_path = tmp_path / "sample.mp3"
    sample_path.write_bytes(b"real audio bytes")

    result = load_audio(sample_path)

    assert result.exists()
    assert result.suffix == ".mp3"


def test_extract_audio_mp4(monkeypatch, tmp_path):
    sample_path = tmp_path / "sample.mp4"
    sample_path.write_bytes(b"real video bytes")

    class Audio:
        def write_audiofile(self, output_path, logger=None):
            Path(output_path).write_bytes(b"wav bytes")

    class VideoClip:
        audio = Audio()

        def __init__(self, path):
            self.path = path

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr("transcription.video_processor.VideoFileClip", VideoClip)
    output = extract_audio(sample_path)

    assert output.exists()
    assert output.suffix == ".wav"
