import json
from unittest.mock import patch

from analysis.llm_analyzer import analyze_content
from analysis.text_normalization import normalize_text


def test_analyze_content_structure(monkeypatch):
    monkeypatch.setattr("analysis.llm_analyzer.settings.GROQ_API_KEY", "test-key")
    response = {
        "narrative": "Healthcare",
        "intent": "Awareness",
        "entities": [{"name": "Ministry of Health", "type": "Government Body", "stance": "Positive"}],
        "claims": ["Vaccines reduce serious illness."],
    }
    mock_client = _mock_groq_client(json.dumps(response))
    text = "This video promotes a health awareness campaign about vaccination and mentions the government body positively."

    with patch("analysis.llm_analyzer.get_groq_client", return_value=mock_client):
        result = analyze_content(text)

    assert "narrative" in result
    assert "intent" in result
    assert isinstance(result["entities"], list)
    assert isinstance(result["claims"], list)


def test_hindi_hinglish_language_detection():
    hindi = normalize_text("भारत में AI innovation तेजी से बढ़ रहा है")
    hinglish = normalize_text("Modi ji ne AI centres launch kiye")

    assert hindi["language"] in {"Hindi", "Hinglish"}
    assert hinglish["language"] == "Hinglish"


def _mock_groq_client(content: str):
    class Message:
        pass

    class Choice:
        pass

    class CompletionResponse:
        pass

    class Completions:
        def create(self, **kwargs):
            message = Message()
            message.content = content
            choice = Choice()
            choice.message = message
            response = CompletionResponse()
            response.choices = [choice]
            return response

    class Chat:
        completions = Completions()

    class Client:
        chat = Chat()

    return Client()
