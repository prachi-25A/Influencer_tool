from pipeline import compute_content_hash


def test_duplicate_hash_normalizes_case_and_spacing():
    first = compute_content_hash("India has 10 AI centres.")
    second = compute_content_hash("  india   has 10 ai centres.  ")

    assert first == second
