from exports.exporter import export_to_csv, export_to_excel


def test_export_to_csv(tmp_path):
    items = [
        {
            "filename": "sample.mp4",
            "narrative": "Healthcare",
            "intent": "Awareness",
            "entities": [{"name": "Ministry of Health", "stance": "Positive"}],
            "claims": ["Vaccines reduce serious illness."],
            "claims_with_facts": [
                {"verdict": "True", "confidence": 90, "source": "https://example.com"}
            ],
            "alignment_score": 85,
        }
    ]
    csv_path = export_to_csv(items, output_name=str(tmp_path / "export.csv"))
    assert csv_path.exists()


def test_export_to_excel(tmp_path):
    items = [
        {
            "filename": "sample.mp4",
            "narrative": "Healthcare",
            "intent": "Awareness",
            "entities": [{"name": "Ministry of Health", "stance": "Positive"}],
            "claims": ["Vaccines reduce serious illness."],
            "claims_with_facts": [
                {"verdict": "True", "confidence": 90, "source": "https://example.com"}
            ],
            "alignment_score": 85,
        }
    ]
    xlsx_path = export_to_excel(items, output_name=str(tmp_path / "export.xlsx"))
    assert xlsx_path.exists()
