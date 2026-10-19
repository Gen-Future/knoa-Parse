"""Small synthetic documents for engine acceptance; no user data or network."""
import io
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import xml.etree.ElementTree as ET


def make_fixtures(directory: Path) -> dict[str, Path]:
    from docx import Document
    from openpyxl import Workbook
    from PIL import Image
    from pptx import Presentation
    from pptx.util import Inches

    directory.mkdir(parents=True, exist_ok=True)
    image = io.BytesIO()
    Image.new("RGB", (32, 16), "blue").save(image, "PNG")
    doc = Document()
    doc.add_heading("Knoa 合成文档", 0)
    doc.add_paragraph("重复段落")
    doc.add_paragraph("重复段落")
    doc.add_paragraph("第一条", style="List Bullet")
    table = doc.add_table(rows=2, cols=2)
    for row, values in zip(table.rows, [("名称", "数值"), ("橙汁", "25")]):
        for cell, value in zip(row.cells, values):
            cell.text = value
    doc.add_picture(io.BytesIO(image.getvalue()))
    doc.sections[0].header.paragraphs[0].text = "合成页眉"
    doc.save(directory / "sample.docx")

    slides = Presentation()
    slide = slides.slides.add_slide(slides.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1))
    box.text_frame.text = "Knoa 幻灯片正文"
    slide.notes_slide.notes_text_frame.text = "这是演讲者备注"
    slide.shapes.add_picture(io.BytesIO(image.getvalue()), Inches(1), Inches(3))
    table = slide.shapes.add_table(2, 2, Inches(1), Inches(4), Inches(5), Inches(1)).table
    table.cell(0, 0).text, table.cell(0, 1).text = "项目", "数量"
    table.cell(1, 0).text, table.cell(1, 1).text = "原生表格", "3"
    slides.save(directory / "sample.pptx")

    book = Workbook()
    sheet = book.active
    sheet.title = "数据"
    for index, row in enumerate([("名称", "数量", "单价", "金额"),
                                 ("橙汁", 2, 12.5, "=D4*E4"),
                                 ("苹果汁", 3, 10, "=D5*E5")], 3):
        for col, value in enumerate(row, 3):
            sheet.cell(index, col, value)
    sheet["H2"], sheet["H2"].number_format = 0.1, "0%"
    sheet["H3"], sheet["H3"].number_format = datetime(2026, 1, 2), "yyyy-mm-dd"
    sheet["J20"] = "=SUM(F4:F5)"  # No cached value, outside the main table.
    sheet.merge_cells("C10:D10")
    sheet["C10"] = "合并备注"
    sheet.row_dimensions[5].hidden = True
    sheet.column_dimensions["E"].hidden = True
    secret = book.create_sheet("内部")
    secret["A1"] = "隐藏工作表内容"
    secret.sheet_state = "hidden"
    path = directory / "sample.xlsx"
    book.save(path)
    # A synthetic cache value distinguishes formula from stored calculation result.
    with ZipFile(path) as z:
        entries = {i.filename: z.read(i) for i in z.infolist()}
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    xml = ET.fromstring(entries["xl/worksheets/sheet1.xml"])
    cell = xml.find('.//s:c[@r="F4"]', ns)
    cell.find("s:v", ns).text = "25"
    entries["xl/worksheets/sheet1.xml"] = ET.tostring(xml, encoding="utf-8")
    with ZipFile(path, "w", ZIP_DEFLATED) as z:
        for name, raw in entries.items():
            z.writestr(name, raw)

    make_pdf(directory / "sample.pdf", ["Native PDF evidence", "Second native page"])
    make_pdf(directory / "blank.pdf", [None])
    Image.new("RGB", (100, 100), "white").save(directory / "image-only.pdf", "PDF")
    return {p.suffix[1:]: p for p in directory.glob("sample.*")}


def make_pdf(path: Path, pages: list[str | None]):
    """Minimal valid PDF with known text positions, using no extra fixture dependency."""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b""]
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    kids = []
    for text in pages:
        page_id, stream_id = len(objects) + 1, len(objects) + 2
        kids.append(f"{page_id} 0 R")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {stream_id} 0 R >>".encode())
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode() if text else b""
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
    objects[1] = f"<< /Type /Pages /Count {len(pages)} /Kids [{' '.join(kids)}] >>".encode()
    raw = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(raw))
        raw.extend(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(raw)
    raw.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        raw.extend(f"{offset:010d} 00000 n \n".encode())
    raw.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    path.write_bytes(raw)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    for name, path in make_fixtures(args.directory).items():
        print(name, path)
