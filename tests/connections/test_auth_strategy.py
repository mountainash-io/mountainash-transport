from mountainash_transport.connections.auth_strategy import OAuth2RefreshableAuthStrategy


class _FakeCred:
    def __init__(self, tok): self.access_token, self.token_type = tok, "Bearer"


class _FakeMgr:
    def __init__(self): self.acquired = self.refreshed = 0
    def acquire(self): self.acquired += 1; return _FakeCred("A")
    def refresh(self): self.refreshed += 1; return _FakeCred("B")


def test_get_headers_acquires_once_and_caches():
    mgr = _FakeMgr()
    s = OAuth2RefreshableAuthStrategy(mgr)
    assert s.get_headers() == {"Authorization": "Bearer A"}
    assert s.get_headers() == {"Authorization": "Bearer A"}   # cached
    assert mgr.acquired == 1


def test_refresh_updates_header():
    mgr = _FakeMgr()
    s = OAuth2RefreshableAuthStrategy(mgr)
    s.get_headers()
    assert s.refresh() is True
    assert s.get_headers() == {"Authorization": "Bearer B"}
    assert mgr.refreshed == 1


def test_apply_is_noop():
    s = OAuth2RefreshableAuthStrategy(_FakeMgr())
    assert s.apply({"x": 1}) == {"x": 1}
