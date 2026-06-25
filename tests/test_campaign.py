import json
from unittest.mock import patch

from campaign.campaign_matcher import match_campaign


def test_campaign_matching_structure(monkeypatch):
    monkeypatch.setattr("campaign.campaign_matcher.settings.GROQ_API_KEY", "test-key")
    response = {
        "theme_score": 90,
        "message_score": 85,
        "entity_score": 100,
        "purpose_score": 95,
        "strengths": ["Strong healthcare alignment."],
        "gaps": [],
        "recommendations": ["Keep required entity visible."],
    }
    mock_client = _mock_groq_client(json.dumps(response))
    campaign = {
        "theme": "Healthcare",
        "message": "Promote vaccination awareness.",
        "required_entities": ["Ministry of Health"],
        "purpose": "Awareness",
    }
    content = {
        "narrative": "Healthcare",
        "intent": "Awareness",
        "entities": [{"name": "Ministry of Health", "type": "Government Body", "stance": "Positive"}],
        "claims": ["Vaccines reduce serious illness."],
    }
    with patch("campaign.campaign_matcher.get_groq_client", return_value=mock_client):
        result = match_campaign(
            campaign_brief=campaign,
            content_narrative=content["narrative"],
            content_intent=content["intent"],
            content_entities=content["entities"],
            content_claims=content["claims"],
        )
    assert "alignment_score" in result
    assert "strengths" in result
    assert "recommendations" in result


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
