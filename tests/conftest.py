from pathlib import Path
import pytest

@pytest.fixture(autouse=True)
def repo_cwd(monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
