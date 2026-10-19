"""Finite original-field supplement; Docling continues to own region discovery."""
from datetime import date, datetime, time
from pathlib import Path

from knoa_parse.core.errors import ParseError


class ExcelFields:
    def __init__(self, max_cells: int = 100000):
        self.max_cells = max_cells

    def inspect(self, path: Path) -> dict:
        from openpyxl import load_workbook
        from openpyxl.worksheet.worksheet import Worksheet
        from openpyxl.utils.cell import column_index_from_string

        def value(v):
            return v.isoformat() if isinstance(v, (date, datetime, time)) else v

        raw = path.read_bytes()
        from io import BytesIO

        formulas = load_workbook(BytesIO(raw), data_only=False, keep_links=False)
        cached = load_workbook(BytesIO(raw), data_only=True, keep_links=False)
        try:
            sheets, cells, total = [], [], 0
            for name in formulas.sheetnames:
                sheet = formulas[name]
                info = {"name": name, "state": sheet.sheet_state, "merged_ranges": []}
                sheets.append(info)
                if not isinstance(sheet, Worksheet):
                    info["kind"] = "chart_sheet"
                    continue
                total += sheet.max_row * sheet.max_column
                if total > self.max_cells:
                    raise ParseError("resource_limit", "Workbook dimensions exceed the cell inspection budget", 413)
                merged = list(sheet.merged_cells.ranges)
                info["merged_ranges"] = [str(r) for r in merged]
                hidden_columns = []
                for key, dimension in sheet.column_dimensions.items():
                    if dimension.hidden:
                        hidden_columns.append((dimension.min or column_index_from_string(key),
                                               dimension.max or column_index_from_string(key)))
                for row in sheet.iter_rows():
                    for cell in row:
                        if cell.value is None:
                            continue
                        is_formula = cell.data_type == "f"
                        if is_formula and not isinstance(cell.value, str):
                            raise ParseError("unsupported_formula", "Array/data-table formulas are not yet supported")
                        cell_value = value(cached[name][cell.coordinate].value)
                        cells.append({"sheet": name, "address": cell.coordinate,
                                      "raw_value": value(cell.value), "data_type": cell.data_type,
                                      "formula": cell.value if is_formula else None,
                                      "cached_value": cell_value if is_formula else None,
                                      "cache_state": ("not_available" if cell_value is None else "stored") if is_formula else "not_applicable",
                                      "number_format": cell.number_format,
                                      "row_hidden": bool(sheet.row_dimensions[cell.row].hidden),
                                      "column_hidden": any(lo <= cell.column <= hi for lo, hi in hidden_columns),
                                      "sheet_state": sheet.sheet_state,
                                      "merged_range": next((str(r) for r in merged if cell.coordinate in r), None)})
            return {"sheets": sheets, "cells": cells}
        finally:
            formulas.close()
            cached.close()
