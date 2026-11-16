import json
from unittest.mock import Mock, patch

import pytest
import requests
from PIL import Image

from table_extractor.core import ExtractionError
from table_extractor.demo import demo_image, demo_payload
from table_extractor.provider import OpenAIExtractor, prepare_image


def response(payload=None, status="completed"):
    return Mock(
        ok=True,
        json=Mock(
            return_value={
                "status": status,
                "id": "test-response",
                "model": "test-snapshot",
                "usage": {"input_tokens": 123, "output_tokens": 45},
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(demo_payload() if payload is None else payload),
                            }
                        ],
                    }
                ],
            }
        ),
    )


def test_request_uses_image_schema_timeout_and_no_storage():
    with patch("requests.Session.post", return_value=response()) as post:
        payload, metadata = OpenAIExtractor("private-test-key", "test-model", 30).extract(b"image")
    assert payload == demo_payload()
    body = post.call_args.kwargs["json"]
    assert body["store"] is False
    assert body["text"]["format"]["strict"] is True
    assert post.call_args.kwargs["timeout"] == (15, 30)
    assert metadata["model"] == "test-snapshot"
    assert metadata["usage"]["input_tokens"] == 123
    assert "private-test-key" not in json.dumps(metadata)


@pytest.mark.parametrize(
    "mock_response",
    [
        response(status="incomplete"),
        Mock(
            ok=True,
            json=Mock(
                return_value={
                    "status": "completed",
                    "output": [{"type": "message", "content": [{"type": "refusal"}]}],
                }
            ),
        ),
        Mock(ok=True, json=Mock(return_value={"status": "completed", "output": None})),
        Mock(ok=True, json=Mock(side_effect=ValueError("invalid json"))),
    ],
)
def test_incomplete_refused_and_malformed_responses_fail(mock_response):
    with patch("requests.Session.post", return_value=mock_response):
        with pytest.raises(ExtractionError):
            OpenAIExtractor("test-key").extract(b"image")


def test_network_errors_do_not_expose_secrets():
    with patch("requests.Session.post", side_effect=requests.Timeout("secret-data")):
        with pytest.raises(ExtractionError) as error:
            OpenAIExtractor("private-test-key").extract(b"image")
    assert "secret" not in str(error.value)
    assert "private-test-key" not in str(error.value)


@pytest.mark.parametrize(
    "failure, expected",
    [
        (requests.exceptions.SSLError("secret-data"), "certificado TLS"),
        (requests.exceptions.ProxyError("secret-data"), "proxy"),
        (requests.exceptions.ConnectTimeout("secret-data"), "conectar"),
        (requests.exceptions.ReadTimeout("secret-data"), "OPENAI_TIMEOUT"),
        (requests.exceptions.ConnectionError("secret-data"), "DNS"),
        (requests.RequestException("secret-data"), "comunicacao"),
    ],
)
def test_network_failures_have_specific_safe_messages(failure, expected):
    with patch("requests.Session.post", side_effect=failure):
        with pytest.raises(ExtractionError) as error:
            OpenAIExtractor("private-test-key").extract(b"image")
    assert expected in str(error.value)
    assert "secret-data" not in str(error.value)
    assert "private-test-key" not in str(error.value)


def test_http_errors_do_not_dump_response_body():
    with patch("requests.Session.post", return_value=Mock(ok=False, status_code=429)):
        with pytest.raises(ExtractionError, match="429"):
            OpenAIExtractor("test-key").extract(b"image")


def test_image_roundtrip_and_invalid_bytes():
    normalized = prepare_image(demo_image())
    assert normalized.startswith(b"\x89PNG")
    with pytest.raises(ExtractionError):
        prepare_image(b"not an image")


def test_oversized_image_rejected_before_decode():
    with pytest.raises(ExtractionError, match="15 MiB"):
        prepare_image(b"x" * (15 * 1024 * 1024 + 1))


def test_unsupported_image_format(tmp_path):
    path = tmp_path / "image.gif"
    Image.new("RGB", (10, 10)).save(path)
    with pytest.raises(ExtractionError, match="Formatos"):
        prepare_image(path.read_bytes())
