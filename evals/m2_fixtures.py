"""Deterministic, authored M2 inputs. No user data, downloads, models or rendering tools."""
import io
import zlib
from datetime import datetime, timedelta
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo
import xml.etree.ElementTree as ET

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ET.register_namespace("w", W)
R = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"


def normalize_office(raw: bytes) -> bytes:
    """Freeze ZIP/core-property dates, including embedded chart workbooks."""
    output = io.BytesIO()
    with ZipFile(io.BytesIO(raw)) as source, ZipFile(output, "w", ZIP_DEFLATED) as target:
        for name in sorted(source.namelist()):
            data = source.read(name)
            if name.endswith(".xlsx"):
                data = normalize_office(data)
            if name == "docProps/core.xml":
                node = ET.fromstring(data)
                for key in ("created", "modified"):
                    item = node.find("{http://purl.org/dc/terms/}" + key)
                    if item is not None:
                        item.text = "2026-01-01T00:00:00Z"
                data = ET.tostring(node, encoding="utf-8")
            entry = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.create_system = 3
            entry.external_attr = 0o600 << 16
            target.writestr(entry, data)
    return output.getvalue()


def word(path: Path):
    from docx import Document
    from docx.enum.section import WD_SECTION_START

    doc = Document()
    doc.add_heading("中文研究记录", 0)
    doc.add_paragraph("重复证据")
    doc.add_paragraph("重复证据")
    doc.add_paragraph("链接与修订：")
    table = doc.add_table(rows=3, cols=3)
    table.cell(0, 0).merge(table.cell(0, 2)).text = "合并表头"
    for row, values in zip(table.rows[1:], (("甲组", "2", "25"), ("乙组", "3", "30"))):
        for cell, text in zip(row.cells, values):
            cell.text = text
    doc.sections[0].header.paragraphs[0].text = "研究页眉"
    doc.sections[0].footer.paragraphs[0].text = "研究页脚"
    section = doc.add_section(WD_SECTION_START.NEW_PAGE)
    section.header.is_linked_to_previous = False
    section.header.paragraphs[0].text = "第二节页眉"
    doc.add_paragraph("第二节正文")
    doc.save(path)
    with ZipFile(path) as package:
        entries = {name: package.read(name) for name in package.namelist()}
    root = ET.fromstring(entries["word/document.xml"])
    para = root.findall(f"{{{W}}}body/{{{W}}}p")[3]
    for tag, text in (("ins", "插入内容"), ("del", "已删除内容")):
        wrapper = ET.SubElement(para, f"{{{W}}}{tag}", {f"{{{W}}}id": "1", f"{{{W}}}author": "合成作者"})
        run = ET.SubElement(wrapper, f"{{{W}}}r")
        ET.SubElement(run, f"{{{W}}}" + ("delText" if tag == "del" else "t")).text = text
    link = ET.SubElement(para, f"{{{W}}}hyperlink", {f"{{{W}}}anchor": "local-bookmark"})
    ET.SubElement(ET.SubElement(link, f"{{{W}}}r"), f"{{{W}}}t").text = "本地链接文字"
    ET.SubElement(ET.SubElement(para, f"{{{W}}}r"), f"{{{W}}}footnoteReference", {f"{{{W}}}id": "1"})
    notes = ET.Element(f"{{{W}}}footnotes")
    note = ET.SubElement(notes, f"{{{W}}}footnote", {f"{{{W}}}id": "1"})
    ET.SubElement(ET.SubElement(ET.SubElement(note, f"{{{W}}}p"), f"{{{W}}}r"), f"{{{W}}}t").text = "脚注证据，不应静默丢失"
    rels = ET.fromstring(entries["word/_rels/document.xml.rels"])
    ET.SubElement(rels, f"{{{R}}}Relationship", Id="rIdM2Footnote",
                  Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes", Target="footnotes.xml")
    content_types = ET.fromstring(entries["[Content_Types].xml"])
    ET.SubElement(content_types, f"{{{CT}}}Override", PartName="/word/footnotes.xml",
                  ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml")
    for name, element in (("word/document.xml", root), ("word/footnotes.xml", notes),
                          ("word/_rels/document.xml.rels", rels), ("[Content_Types].xml", content_types)):
        entries[name] = ET.tostring(element, encoding="utf-8")
    with ZipFile(path, "w", ZIP_DEFLATED) as package:
        for name, data in entries.items():
            package.writestr(name, data)


def slides(path: Path):
    from pptx import Presentation
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE
    from pptx.util import Inches

    deck = Presentation()
    first = deck.slides.add_slide(deck.slide_layouts[6])
    group = first.shapes.add_group_shape()
    group.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1)).text = "分组内正文"
    first.shapes.add_textbox(Inches(1), Inches(2), Inches(5), Inches(1)).text = "跨页重复"
    first.notes_slide.notes_text_frame.text = "第一页备注"
    second = deck.slides.add_slide(deck.slide_layouts[6])
    second.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1)).text = "跨页重复"
    second.notes_slide.notes_text_frame.text = "第二页备注"
    table = second.shapes.add_table(2, 3, Inches(1), Inches(2), Inches(5), Inches(1)).table
    table.cell(0, 0).merge(table.cell(0, 2))
    table.cell(0, 0).text = "演示合并表头"
    for index, value in enumerate(("甲组", "4", "50")):
        table.cell(1, index).text = value
    chart = CategoryChartData()
    chart.categories = ["一月", "二月"]
    chart.add_series("收入", (10, 20))
    second.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(4), Inches(5), Inches(2), chart)
    deck.save(path)


def workbook(path: Path, formulas_only: bool = False):
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, Reference
    from openpyxl.comments import Comment

    book = Workbook()
    book.active.title = "空白首表"
    data = book.create_sheet("数据 同名")
    for address, value in {"C3": "中文字段", "D3": "原始值", "C4": "重复证据", "D4": 0,
                           "C5": "重复证据", "D5": False, "D6": "#DIV/0!", "D7": "00123",
                           "D8": datetime(2026, 10, 19), "D9": timedelta(hours=49, minutes=30),
                           "F20": "=SUM(D4:D5)"}.items():
        data[address] = value
    data["D8"].number_format = "yyyy-mm-dd"
    data["D9"].number_format = "[h]:mm:ss"
    data["C4"].comment = Comment("原生批注内容", "合成作者")
    data.merge_cells("H3:J4")
    data["H3"] = "二维合并"
    data.column_dimensions.group("D", "F", hidden=True)
    data.row_dimensions[5].hidden = True
    hidden = book.create_sheet("极隐藏")
    hidden["A1"], hidden.sheet_state = "不能遗漏的隐藏原文", "veryHidden"
    if formulas_only:
        book.remove(data)
        sheet = book.create_sheet("纯公式")
        sheet["B7"] = "=1+2"
        sheet["AA9"] = "=SUM(B7,4)"
    else:
        chart = BarChart()
        chart.add_data(Reference(data, min_col=4, min_row=3, max_row=4), titles_from_data=True)
        chart_sheet = book.create_chartsheet("图表页", index=1)
        chart_sheet.add_chart(chart)
    book.save(path)
    book.close()


def pdf(path: Path, pages: list[dict]):
    """Known PDF operators/ToUnicode map; no OCR, font download or PDF writer dependency."""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    # Identity-H + an authored ToUnicode map makes extraction independent of host fonts.
    cmap = (b"/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n"
            b"/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
            b"/CMapName /KnoaUCS def /CMapType 2 def\n1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
            b"1 beginbfrange <0000> <FFFF> <0000> endbfrange\nendcmap CMapName currentdict /CMap defineresource pop end end")
    objects.append(b"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light /Encoding /Identity-H /DescendantFonts [5 0 R] /ToUnicode 6 0 R >>")
    objects.append(b"<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light /CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 0 >> /DW 1000 >>")
    objects.append(b"<< /Length " + str(len(cmap)).encode() + b" >>\nstream\n" + cmap + b"\nendstream")
    bitmap = zlib.compress(bytes([230, 230, 230]) * 100 * 100)
    objects.append(b"<< /Type /XObject /Subtype /Image /Width 100 /Height 100 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length " + str(len(bitmap)).encode() + b" >>\nstream\n" + bitmap + b"\nendstream")
    kids = []
    for page in pages:
        page_id, stream_id = len(objects) + 1, len(objects) + 2
        kids.append(f"{page_id} 0 R")
        objects.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Rotate {page.get('rotation', 0)} "
                        f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> /XObject << /Im1 7 0 R >> >> /Contents {stream_id} 0 R >>").encode())
        operations = []
        for text, x, y in page.get("texts", []):
            operations.append(f"BT /F2 12 Tf {x} {y} Td <{text.encode('utf-16-be').hex()}> Tj ET")
        if page.get("image"):
            operations.append("q 480 0 0 600 60 60 cm /Im1 Do Q")
        stream = "\n".join(operations).encode()
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
    objects[1] = f"<< /Type /Pages /Count {len(pages)} /Kids [{' '.join(kids)}] >>".encode()
    raw, offsets = bytearray(b"%PDF-1.4\n"), [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(raw))
        raw.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(raw)
    raw.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        raw.extend(f"{offset:010d} 00000 n \n".encode())
    raw.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    path.write_bytes(raw)


def make_fixtures(directory: Path, documents: bool = True):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "unicode.txt").write_bytes("\ufeff中文😀\r\n重复证据\r\n重复证据\n```代码```".encode("utf-8"))
    (directory / "invalid.txt").write_bytes(b"\xff\xfeinvalid")
    (directory / "nested.json").write_bytes('\ufeff{"中文":{"a/b~c":[0,false,null,"00123","😀"]},"列表":[]}'.encode("utf-8"))
    (directory / "duplicate.json").write_bytes(b'{"x":1,"x":2}')
    if not documents:
        return
    word(directory / "complex.docx")
    slides(directory / "complex.pptx")
    workbook(directory / "types.xlsx")
    workbook(directory / "formulas.xlsx", formulas_only=True)
    for name in ("complex.docx", "complex.pptx", "types.xlsx", "formulas.xlsx"):
        path = directory / name
        path.write_bytes(normalize_office(path.read_bytes()))
    pdf(directory / "cjk.pdf", [{"texts": [("左栏重复", 72, 720), ("右栏重复", 330, 720), ("中文原生证据", 72, 680)]},
                               {"rotation": 90, "texts": [("旋转中文", 72, 720)]}])
    pdf(directory / "mixed.pdf", [{"texts": [("Native header", 72, 740)], "image": True}])
    pdf(directory / "image-only.pdf", [{"image": True}])
    (directory / "broken.pdf").write_bytes(b"%PDF-1.7\ncorrupt")
    for suffix, part in (("docx", "word/document.xml"), ("pptx", "ppt/presentation.xml"), ("xlsx", "xl/workbook.xml")):
        with ZipFile(directory / ("broken." + suffix), "w", ZIP_DEFLATED) as package:
            package.writestr("[Content_Types].xml", f'<Types xmlns="{CT}"/>')
            package.writestr(part, "<broken>")
        path = directory / ("broken." + suffix)
        path.write_bytes(normalize_office(path.read_bytes()))
