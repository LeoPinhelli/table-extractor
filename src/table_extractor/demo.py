"""Dados totalmente sinteticos; demonstracao offline nao chama nem avalia um modelo."""

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


def demo_payload() -> dict:
    return {
        "is_table": True,
        "title": "Estoque ficticio",
        "columns": ["Item", "Quantidade", "Preco unitario"],
        "rows": [["Caderno", "12", "18,50"], ["Caneta", "30", "3,20"], ["Mochila", "5", "89,90"]],
        "warnings": [],
    }


def demo_image() -> bytes:
    payload = demo_payload()
    image = Image.new("RGB", (960, 360), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 22)
    except OSError:
        font = ImageFont.load_default(size=22)
    draw.text((24, 18), "DEMONSTRACAO - DADOS SINTETICOS", fill="#164e63", font=font)
    rows = [payload["columns"], *payload["rows"]]
    for index, row in enumerate(rows):
        y = 70 + index * 56
        draw.rectangle((20, y, 940, y + 56), fill="#e0f2fe" if index == 0 else "#f8fafc", outline="#94a3b8")
        for x, text in zip((36, 370, 640), row):
            draw.text((x, y + 14), text, fill="#0f172a", font=font)
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()
