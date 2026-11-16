import json
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook

from table_extractor.cli import main
from table_extractor.core import build_document
from table_extractor.demo import demo_image, demo_payload
from table_extractor.exporters import document_json, save_outputs, table_csv, table_excel


def test_exports_keep_leading_zeros_and_neutralize_formulas():
    payload = demo_payload()
    payload["rows"][0] = ["=1+1", "0012", "-18,50"]
    document = build_document(payload, b"image", model="test")
    workbook = load_workbook(BytesIO(table_excel(document)))
    assert workbook["Tabela"]["A2"].value == "=1+1"
    assert workbook["Tabela"]["A2"].data_type == "s"
    assert workbook["Tabela"]["B2"].value == "0012"
    assert "'=1+1" in table_csv(document).decode("utf-8-sig")
    assert json.loads(document_json(document))["table"]["rows"][0][0] == "=1+1"


def test_runs_do_not_overwrite_previous_files(tmp_path):
    document = build_document(demo_payload(), b"image", model="test")
    first = save_outputs(document, tmp_path)
    second = save_outputs(document, tmp_path)
    assert first[0].parent != second[0].parent
    assert all(path.exists() for path in first + second)


def test_demo_runs_without_api_or_credentials(tmp_path, capsys):
    with patch("table_extractor.provider.requests.post", side_effect=AssertionError("network forbidden")):
        code = main(["--demo", "--output", str(tmp_path)])
    assert code == 0
    document = json.loads(next(tmp_path.glob("*/result.json")).read_text(encoding="utf-8"))
    assert document["metadata"]["mode"] == "demo"
    assert "predefinida" in capsys.readouterr().out
    assert next(tmp_path.glob("*/sample.png")).is_file()


def test_review_exit_code_and_preserved_outputs(tmp_path):
    profile = tmp_path / "profile.json"
    profile.write_text('{"min_rows": 10}', encoding="utf-8")
    assert main(["--demo", "--profile", str(profile), "--output", str(tmp_path / "out")]) == 2
    assert next((tmp_path / "out").glob("*/table.xlsx")).exists()


def test_bad_profile_returns_error_before_network(tmp_path):
    profile = tmp_path / "profile.json"
    profile.write_text("not-json", encoding="utf-8")
    with patch("table_extractor.provider.requests.post") as post:
        assert main(["--demo", "--profile", str(profile), "--output", str(tmp_path / "out")]) == 1
        post.assert_not_called()
    assert not (tmp_path / "out").exists()


def test_live_pipeline_with_simulated_provider(tmp_path):
    image = tmp_path / "input.png"
    image.write_bytes(demo_image())
    with patch("table_extractor.cli.OpenAIExtractor") as extractor:
        extractor.return_value.extract.return_value = (
            demo_payload(),
            {
                "model": "mock-vision",
                "response_id": "r-test",
                "usage": {"input_tokens": 10},
                "elapsed_seconds": 0.1,
            },
        )
        assert main(["--image", str(image), "--output", str(tmp_path / "out")]) == 0
    document = json.loads(next((tmp_path / "out").glob("*/result.json")).read_text(encoding="utf-8"))
    assert document["metadata"]["mode"] == "live"
    assert document["metadata"]["model"] == "mock-vision"
    assert document["status"] == "validated"


def test_missing_image_does_not_create_output(tmp_path):
    assert main(["--image", str(tmp_path / "missing.png"), "--output", str(tmp_path / "out")]) == 1
    assert not (tmp_path / "out").exists()


def test_profile_with_invalid_encoding_returns_error(tmp_path):
    profile = tmp_path / "profile.json"
    profile.write_bytes(b"\xff\xfeinvalid")
    assert main(["--demo", "--profile", str(profile), "--output", str(tmp_path / "out")]) == 1
    assert not (tmp_path / "out").exists()


def test_example_profile_matches_synthetic_table():
    from table_extractor.core import ValidationProfile, load_json, validate_table

    root = Path(__file__).resolve().parents[1]
    profile = ValidationProfile.from_dict(load_json((root / "examples/validation-profile.json").read_text()))
    assert validate_table(demo_payload(), profile) == []
