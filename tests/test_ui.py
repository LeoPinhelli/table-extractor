"""Smoke test opcional: executado quando o extra ui esta instalado."""

from pathlib import Path
from unittest.mock import patch

import pytest

testing = pytest.importorskip("streamlit.testing.v1")


def test_demo_ui_renders_and_exports_without_network():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    with patch("table_extractor.provider.requests.post", side_effect=AssertionError("network forbidden")):
        app = testing.AppTest.from_file(str(app_path)).run(timeout=20)
        assert not app.exception
        app.button[0].click().run(timeout=20)
    assert not app.exception
    document, _ = app.session_state["extraction_result"]
    assert document["metadata"]["mode"] == "demo"
    assert document["status"] == "validated"
