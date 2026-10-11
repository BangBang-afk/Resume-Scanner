import re

from app.services.masking import mask_pii


def test_no_pii_remains():
    raw = "Aarav Sharma\naarav.sharma@mail.com\n+91 98765 43210\nSee https://x.io/cv"
    masked, _ = mask_pii(raw)
    assert "aarav.sharma@mail.com" not in masked
    assert "98765" not in masked
    assert "https://x.io/cv" not in masked
    assert "Aarav Sharma" not in masked
    assert not re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", masked)
