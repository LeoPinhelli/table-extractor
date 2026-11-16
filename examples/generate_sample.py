"""Gera uma imagem de exemplo sem dados externos: python examples/generate_sample.py."""

from pathlib import Path

from table_extractor.demo import demo_image

if __name__ == "__main__":
    path = Path(__file__).with_name("sample.png")
    path.write_bytes(demo_image())
    print(path)
