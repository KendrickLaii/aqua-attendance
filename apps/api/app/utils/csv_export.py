import csv
import io

from fastapi import Response

# Cells starting with these characters are interpreted as formulas by Excel /
# LibreOffice — neutralize them to prevent CSV formula injection.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def escape_csv_cell(value) -> str:
    """Return a CSV-safe string; prefixes a quote on formula-like cells."""
    text = "" if value is None else str(value)
    if text.startswith(_FORMULA_PREFIXES):
        return "'" + text
    return text


def csv_response(filename: str, header: list[str], rows: list[list]) -> Response:
    """UTF-8 (BOM) CSV download with all cells escaped."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([escape_csv_cell(c) for c in header])
    writer.writerows([[escape_csv_cell(c) for c in row] for row in rows])
    content = "﻿" + buf.getvalue()  # UTF-8 BOM so Excel renders 中文
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
