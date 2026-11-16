from copy import deepcopy

import pytest

from table_extractor.core import ExtractionError, ValidationProfile, build_document, load_json, validate_table
from table_extractor.demo import demo_payload


def test_valid_synthetic_table_and_traceability():
    result = build_document(demo_payload(), b"image", model="test-model")
    assert result["status"] == "validated"
    assert len(result["metadata"]["image_sha256"]) == 64
    assert result["table"]["rows"][0][2] == "18,50"
    assert result["metadata"]["created_at"].endswith("+00:00")


@pytest.mark.parametrize(
    "mutation, expected",
    [
        (lambda p: p["rows"][0].__setitem__(1, None), "ilegivel"),
        (lambda p: p["rows"][0].append("extra"), "quantidade"),
        (lambda p: p["columns"].__setitem__(1, " item "), "duplicados"),
        (lambda p: p.__setitem__("rows", []), "pelo menos"),
        (lambda p: p["warnings"].append("texto borrado"), "borrado"),
        (lambda p: p.__setitem__("is_table", False), "Nenhuma tabela"),
    ],
)
def test_uncertain_results_need_review(mutation, expected):
    payload = demo_payload()
    mutation(payload)
    document = build_document(payload, b"image", model="test")
    assert document["status"] == "needs_review"
    assert any(expected in issue for issue in document["validation_issues"])


def test_profile_checks_headers_keys_numbers_and_bounds():
    profile = ValidationProfile.from_dict(
        {
            "expected_columns": ["Item", "Quantidade", "Preco unitario"],
            "unique_columns": ["Item"],
            "min_rows": 3,
            "numeric_columns": {"Preco unitario": {"decimal_separator": ",", "min": 0, "max": 100}},
        }
    )
    assert validate_table(demo_payload(), profile) == []
    payload = demo_payload()
    payload["rows"][1] = ["Caderno", "30", "999,00"]
    issues = validate_table(payload, profile)
    assert any("duplicada" in issue for issue in issues)
    assert any("limites" in issue for issue in issues)


def test_compound_key_allows_repeated_values_in_individual_columns():
    payload = demo_payload()
    payload["rows"][1][0] = "Caderno"
    profile = ValidationProfile.from_dict({"unique_columns": ["Item", "Quantidade"]})
    assert validate_table(payload, profile) == []


def test_missing_profile_column_and_mismatched_order_are_reported():
    profile = ValidationProfile.from_dict(
        {"expected_columns": ["Quantidade", "Item"], "unique_columns": ["Codigo"]}
    )
    issues = validate_table(demo_payload(), profile)
    assert any("ordem" in issue for issue in issues)
    assert any("Codigo" in issue for issue in issues)


@pytest.mark.parametrize("value", ["1.234,56", "R$ 10,00", "NaN", "Infinity", "10%"])
def test_ambiguous_numeric_formats_are_flagged(value):
    payload = demo_payload()
    payload["rows"][0][2] = value
    profile = ValidationProfile.from_dict({"numeric_columns": {"Preco unitario": {"decimal_separator": ","}}})
    assert any("numerico invalido" in issue for issue in validate_table(payload, profile))


@pytest.mark.parametrize(
    "data",
    [
        [],
        {"unexpected": True},
        {"min_rows": True},
        {"min_rows": 0},
        {"unique_columns": ["A", "A"]},
        {"expected_columns": "A"},
        {"numeric_columns": {"A": {"min": "NaN"}}},
        {"numeric_columns": {"A": {"min": 10, "max": 1}}},
        {"numeric_columns": {"A": {"decimal_separator": ";"}}},
    ],
)
def test_bad_profiles_fail_early(data):
    with pytest.raises(ExtractionError):
        ValidationProfile.from_dict(data)


@pytest.mark.parametrize(
    "change",
    [
        {"is_table": 1},
        {"columns": [None]},
        {"rows": [[12]]},
        {"warnings": "bad"},
        {"extra": 1},
    ],
)
def test_malformed_model_payload_is_rejected(change):
    payload = deepcopy(demo_payload())
    payload.update(change)
    with pytest.raises(ExtractionError):
        validate_table(payload)


def test_non_finite_json_is_rejected():
    with pytest.raises(ExtractionError):
        load_json('{"x": NaN}')
