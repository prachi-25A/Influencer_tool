from transcription.whisper_transcriber import transcribe_audio


def test_whisper_transcription(monkeypatch, tmp_path):
    sample_path = tmp_path / "sample.wav"
    sample_path.write_bytes(b"wav bytes")

    class Model:
        def transcribe(self, path, temperature=0.0, language=None, verbose=False):
            return {
                "text": "This is a real mocked transcription.",
                "language": "en",
                "audio_duration": 1.25,
            }

    monkeypatch.setattr("transcription.whisper_transcriber.whisper", object())
    monkeypatch.setattr("transcription.whisper_transcriber.load_whisper_model", lambda model_name=None: Model())

    result = transcribe_audio(sample_path)

    assert result["transcript"]
    assert result["language"] in {"English", "Hindi", "Hinglish", "unknown"}
    assert result["source_file"] == str(sample_path)
