from app.services.scoring import assign_ranks


def test_tie_group_ordered_by_rules():
    a = {"candidate_id": "a", "total": 80.0, "must_coverage": 1.0,
         "preferred_coverage": 0.5, "mean_confidence": 0.9}
    b = {"candidate_id": "b", "total": 79.0, "must_coverage": 1.0,
         "preferred_coverage": 1.0, "mean_confidence": 0.5}
    ranked = assign_ranks([a, b])
    assert ranked[0]["tie_group"] == ranked[1]["tie_group"]
    assert ranked[0]["candidate_id"] == "b"  # higher preferred coverage wins
    assert all(x["close_call"] for x in ranked)
