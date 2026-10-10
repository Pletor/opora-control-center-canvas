from backend.api.http_etag import etag_of, matches


def test_etag_is_an_opaque_hash_that_separates_projects_and_parameters():
    tag = etag_of("state", "p1", "draft", ("state", 3, "2026-10-10T10:00:00+00:00"))
    assert tag.startswith('"') and tag.endswith('"') and len(tag) == 42
    assert "p1" not in tag and "2026" not in tag
    assert tag == etag_of("state", "p1", "draft", ["state", 3, "2026-10-10T10:00:00+00:00"])
    assert tag != etag_of("state", "p2", "draft", ("state", 3, "2026-10-10T10:00:00+00:00"))
    assert tag != etag_of("state", "p1", "other", ("state", 3, "2026-10-10T10:00:00+00:00"))
    assert tag != etag_of("state", "p1", "draft", ("state", 4, "2026-10-10T10:00:00+00:00"))


def test_if_none_match_accepts_lists_weak_tags_and_star_only():
    tag = etag_of("x")
    assert matches(tag, tag) and matches(f'"a", {tag}', tag) and matches(f"W/{tag}", tag) and matches("*", tag)
    assert not matches(None, tag) and not matches("", tag) and not matches('"a"', tag)
    assert not matches(tag.strip('"'), tag)
