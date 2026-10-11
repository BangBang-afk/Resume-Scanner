from app.services.taxonomy import normalize


def test_aliases_normalize_correctly():
    assert normalize("ML") == "machine learning"
    assert normalize("JS") == "javascript"
    assert normalize("k8s") == "kubernetes"
    assert normalize("Postgres") == "postgresql"
