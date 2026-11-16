"""Exportacao local com texto literal em planilhas e CSV."""

import csv
import json
import uuid
from io import BytesIO, StringIO
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill


def safe_csv_cell(value):
    if value is None:
        return ""
    # CSV nao possui tipos: neutraliza formulas ao abrir em programas de planilha.
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return value


def document_json(document: dict) -> bytes:
    return json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")


def table_csv(document: dict) -> bytes:
    stream = StringIO(newline="")
    writer = csv.writer(stream)
    table = document["table"]
    writer.writerow([safe_csv_cell(cell) for cell in table["columns"]])
    writer.writerows([[safe_csv_cell(cell) for cell in row] for row in table["rows"]])
    return stream.getvalue().encode("utf-8-sig")


def table_excel(document: dict) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Tabela"
    table = document["table"]
    for row_number, row in enumerate([table["columns"], *table["rows"]], 1):
        for column_number, value in enumerate(row, 1):
            cell = sheet.cell(row_number, column_number, "" if value is None else value)
            cell.data_type = "s"
            if row_number == 1:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="164E63")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    metadata = workbook.create_sheet("Validacao")
    entries = [
        ("Status", document["status"]),
        ("Modo", document["metadata"]["mode"]),
        ("Modelo", document["metadata"]["model"]),
        ("SHA-256 da imagem normalizada", document["metadata"]["image_sha256"]),
        *[("Aviso", issue) for issue in document["validation_issues"]],
    ]
    for row_number, row in enumerate(entries, 1):
        for column_number, value in enumerate(row, 1):
            cell = metadata.cell(row_number, column_number, str(value))
            cell.data_type = "s"
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def save_outputs(document: dict, directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    # Uma pasta por execucao evita sobrescrever extracoes anteriores.
    run_dir = directory / (document["metadata"]["created_at"][:10] + "-" + uuid.uuid4().hex[:12])
    run_dir.mkdir()
    paths = []
    for name, content in (
        ("result.json", document_json(document)),
        ("table.csv", table_csv(document)),
        ("table.xlsx", table_excel(document)),
    ):
        path = run_dir / name
        path.write_bytes(content)
        paths.append(path)
    return paths
