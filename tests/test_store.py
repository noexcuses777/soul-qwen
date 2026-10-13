from backend.store import Store

def test_connections_release_file(tmp_path):
    p=tmp_path/'store.db';s=Store(str(p))
    with s.connect() as c: c.execute('SELECT 1')
    # Windows cannot unlink an open sqlite handle. This checks deterministic closure.
    p.unlink();assert not p.exists()
