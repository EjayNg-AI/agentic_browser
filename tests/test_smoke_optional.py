import httpx
import pytest


def test_cdp_reachable_optional() -> None:
    try:
        resp = httpx.get("http://127.0.0.1:9222/json/version", timeout=1.5)
    except Exception:
        pytest.skip("CDP endpoint not reachable")
    if resp.status_code != 200:
        pytest.skip("CDP endpoint not ready")
    data = resp.json()
    assert "Browser" in data
