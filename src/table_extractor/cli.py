import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .core import ExtractionError, ValidationProfile, build_document, load_json
from .demo import demo_image, demo_payload
from .exporters import save_outputs
from .provider import MAX_IMAGE_BYTES, OpenAIExtractor, prepare_image


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Converta uma imagem de tabela em JSON, CSV e Excel.")
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--image", type=Path, help="Imagem PNG, JPEG ou WebP local")
    inputs.add_argument("--demo", action="store_true", help="Demonstracao sintetica offline, sem IA")
    parser.add_argument("--profile", type=Path, help="Perfil JSON opcional de validacao")
    parser.add_argument("--output", type=Path, default=Path("outputs"))
    parser.add_argument("--model", help="Modelo com visao e suporte a JSON Schema")
    args = parser.parse_args(argv)
    try:
        load_dotenv(Path.cwd() / ".env", override=False)
        profile = (
            ValidationProfile.from_dict(load_json(args.profile.read_text(encoding="utf-8")))
            if args.profile
            else None
        )
        if args.demo:
            image = prepare_image(demo_image())
            document = build_document(
                demo_payload(), image, model="offline-fixture", mode="demo", profile=profile
            )
        else:
            if args.image.stat().st_size > MAX_IMAGE_BYTES:
                raise ExtractionError("Envie uma imagem de ate 15 MiB.")
            image = prepare_image(args.image.read_bytes())
            try:
                timeout = int(os.getenv("OPENAI_TIMEOUT", "120"))
            except ValueError:
                raise ExtractionError("OPENAI_TIMEOUT deve ser um inteiro positivo.") from None
            extractor = OpenAIExtractor(
                os.getenv("OPENAI_API_KEY", ""),
                args.model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                timeout,
            )
            payload, metadata = extractor.extract(image)
            document = build_document(payload, image, profile=profile, **metadata)
        paths = save_outputs(document, args.output)
        if args.demo:
            (paths[0].parent / "sample.png").write_bytes(image)
            print("DEMO: resposta sintetica predefinida; nenhuma chamada a IA foi realizada.")
        print(f"Status: {document['status']}; linhas: {len(document['table']['rows'])}")
        for issue in document["validation_issues"]:
            print(f"- {issue}")
        for path in paths:
            print(path.resolve())
        return 2 if document["status"] == "needs_review" else 0
    except (ExtractionError, UnicodeError, OSError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1
