from app.services.extractor import _find_quote


def test_bad_quote_dropped():
    assert _find_quote("never present xyz", "some resume text") is None


def test_good_quote_kept():
    ev = _find_quote("Python", "Skills:\nPython, Docker")
    assert ev is not None and ev.quote == "Python"
