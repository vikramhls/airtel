"""Test setup: isolated SQLite file, LLM off by default (scenarios also run with a stub)."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ["LLM_PROVIDER"] = "none"
os.environ["ONEFLOW_DB"] = str(Path(tempfile.mkdtemp()) / "test.db")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from app.main import app

    return TestClient(app)


@pytest.fixture(params=["llm_off", "llm_stub"])
def llm_mode(request, monkeypatch):
    """Every advisor scenario must pass with the LLM off and with deterministic LLM responses."""
    if request.param == "llm_stub":
        from app.services import advisor, llm

        def fake_json(system, user, **_):
            if "ignore your rules" in user.lower() or "for ₹100" in user:
                return {"patch": {}, "intent": "injection_attempt"}
            return {"patch": {}, "intent": "provide_info"}

        monkeypatch.setattr(llm, "enabled", lambda: True)
        monkeypatch.setattr(llm, "complete_json", fake_json)
        monkeypatch.setattr(llm, "complete", lambda *a, **k: None)   # explanation falls back to template
        monkeypatch.setattr(advisor.llm, "enabled", lambda: True)
    return request.param
