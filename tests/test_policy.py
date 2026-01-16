from humanbrowse.policy import DomainPolicy


def test_denylist_blocks_matching_domains() -> None:
    policy = DomainPolicy.from_config("denylist", ["example.com"])
    assert policy.is_allowed("https://example.com") is False
    assert policy.is_allowed("https://sub.example.com/path") is False
    assert policy.is_allowed("https://other.com") is True


def test_allowlist_allows_only_matching_domains() -> None:
    policy = DomainPolicy.from_config("allowlist", ["example.com"])
    assert policy.is_allowed("https://example.com") is True
    assert policy.is_allowed("https://sub.example.com/path") is True
    assert policy.is_allowed("https://other.com") is False


def test_policy_allows_non_http_hosts() -> None:
    policy = DomainPolicy.from_config("allowlist", ["example.com"])
    assert policy.is_allowed("about:blank") is True
