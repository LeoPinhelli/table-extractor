"""Leitura de imagens e adaptador de IA; nenhum segredo e salvo na saida."""

import base64
import time
import warnings
from io import BytesIO

import requests
from PIL import Image, ImageOps, UnidentifiedImageError

from .core import EXTRACTION_PROMPT, TABLE_SCHEMA, ExtractionError, load_json
from .transport import create_session

API_URL = "https://api.openai.com/v1/responses"
MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_PIXELS = 20_000_000


def prepare_image(content: bytes) -> bytes:
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise ExtractionError("Envie uma imagem de ate 15 MiB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as source:
                if source.format not in {"PNG", "JPEG", "WEBP"}:
                    raise ExtractionError("Formatos aceitos: PNG, JPEG e WebP.")
                if source.width * source.height > MAX_PIXELS:
                    raise ExtractionError("Imagem excede o limite de 20 megapixels.")
                if getattr(source, "n_frames", 1) != 1:
                    raise ExtractionError("Envie uma imagem estatica, sem animacao.")
                image = ImageOps.exif_transpose(source).convert("RGBA")
                background = Image.new("RGBA", image.size, "white")
                background.alpha_composite(image)
                output = BytesIO()
                background.convert("RGB").save(output, format="PNG")
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise ExtractionError("Arquivo de imagem invalido ou grande demais.") from error
    normalized = output.getvalue()
    if len(normalized) > MAX_IMAGE_BYTES:
        raise ExtractionError("A imagem normalizada excede 15 MiB; reduza a resolucao.")
    return normalized


class OpenAIExtractor:
    def __init__(self, api_key: str, model: str = "gpt-4.1-mini", timeout: int = 120):
        if not api_key.strip():
            raise ExtractionError("Configure OPENAI_API_KEY para a extracao real.")
        if not model.strip() or type(timeout) is not int or timeout <= 0:
            raise ExtractionError("Modelo e timeout devem ser validos.")
        self._api_key = api_key.strip()
        self.model = model.strip()
        self.timeout = timeout

    def extract(self, image: bytes) -> tuple[dict, dict]:
        started = time.perf_counter()
        body = {
            "model": self.model,
            "store": False,
            "max_output_tokens": 12000,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": EXTRACTION_PROMPT},
                        {
                            "type": "input_image",
                            "detail": "high",
                            "image_url": "data:image/png;base64," + base64.b64encode(image).decode("ascii"),
                        },
                    ],
                }
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "image_table",
                    "strict": True,
                    "schema": TABLE_SCHEMA,
                }
            },
        }
        try:
            with create_session() as session:
                response = session.post(
                    API_URL,
                    json=body,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=(15, self.timeout),
                )
        except requests.exceptions.SSLError:
            raise ExtractionError(
                "Nao foi possivel validar o certificado TLS da API. Confira os certificados "
                "confiaveis do sistema ou configure REQUESTS_CA_BUNDLE com uma cadeia PEM valida."
            ) from None
        except requests.exceptions.ProxyError:
            raise ExtractionError(
                "Falha ao acessar o proxy. Confira HTTPS_PROXY e a conexao com a rede."
            ) from None
        except requests.exceptions.ConnectTimeout:
            raise ExtractionError("Tempo esgotado ao conectar a API. Confira rede e proxy.") from None
        except requests.exceptions.Timeout:
            raise ExtractionError(
                "Tempo esgotado aguardando a API. Tente uma imagem menor ou aumente OPENAI_TIMEOUT."
            ) from None
        except requests.exceptions.ConnectionError:
            raise ExtractionError(
                "Nao foi possivel conectar a API. Confira internet, DNS, firewall e proxy."
            ) from None
        except requests.RequestException:
            raise ExtractionError("Falha na comunicacao com a API.") from None
        if not response.ok:
            raise ExtractionError(
                f"Provedor retornou HTTP {response.status_code}; confira chave, modelo e limites."
            )
        try:
            result = response.json()
            if not isinstance(result, dict) or result.get("status") != "completed":
                raise ExtractionError("Resposta incompleta do modelo; tente uma tabela menor.")
            contents = [
                part
                for item in result.get("output", [])
                if item.get("type") == "message"
                for part in item.get("content", [])
            ]
            if any(part.get("type") == "refusal" for part in contents):
                raise ExtractionError("O modelo recusou a leitura desta imagem.")
            payload = load_json(
                "".join(part["text"] for part in contents if part.get("type") == "output_text")
            )
            metadata = {
                "model": result.get("model") or self.model,
                "response_id": result.get("id"),
                "usage": result.get("usage") or {},
                "elapsed_seconds": time.perf_counter() - started,
            }
            return payload, metadata
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            if isinstance(error, ExtractionError):
                raise
            raise ExtractionError("Resposta invalida do provedor.") from None
