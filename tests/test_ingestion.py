from ingestion.docx_parser import parse_docx
from ingestion.pdf_parser import parse_pdf
from ingestion.txt_parser import parse_txt
from ingestion.url_parser import parse_youtube_url


def test_parse_txt(tmp_path):
    sample_path = tmp_path / "sample.txt"
    sample_path.write_text("This is a sample TXT document.", encoding="utf-8")

    result = parse_txt(sample_path)

    assert result["type"] == "txt"
    assert "sample" in result["content"].lower()


def test_parse_pdf(monkeypatch, tmp_path):
    sample_path = tmp_path / "sample.pdf"
    sample_path.write_bytes(b"%PDF-1.4")

    class Page:
        def extract_text(self):
            return "Sample PDF document."

    class Reader:
        def __init__(self, path):
            self.pages = [Page()]

    monkeypatch.setattr("ingestion.pdf_parser.PdfReader", Reader)
    result = parse_pdf(sample_path)

    assert result["type"] == "pdf"
    assert result["filename"] == "sample.pdf"
    assert "sample" in result["content"].lower()


def test_parse_docx(monkeypatch, tmp_path):
    sample_path = tmp_path / "sample.docx"
    sample_path.write_bytes(b"docx")

    class Paragraph:
        text = "Sample DOCX document."

    class Document:
        def __init__(self, path):
            self.paragraphs = [Paragraph()]

    monkeypatch.setattr("ingestion.docx_parser.Document", Document)
    result = parse_docx(sample_path)

    assert result["type"] == "docx"
    assert result["filename"] == "sample.docx"
    assert "sample" in result["content"].lower()


def test_parse_youtube_url_supports_new_transcript_api(monkeypatch):
    class Segment:
        text = "This is a caption."

    class Transcript:
        snippets = [Segment()]

    class Api:
        def fetch(self, video_id, languages=None):
            assert video_id == "UHzsRtsBEOs"
            return Transcript()

    monkeypatch.setattr("ingestion.url_parser.YouTubeTranscriptApi", Api)

    result = parse_youtube_url("https://youtube.com/shorts/UHzsRtsBEOs?si=test,")

    assert result["type"] == "url"
    assert result["filename"].endswith("si=test")
    assert "caption" in result["content"]
