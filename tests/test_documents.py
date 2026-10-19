"""Document semantics, original fields, artifacts and the real worker boundary."""
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "evals"))

from knoa_parse.apps.runtime import make_store
from knoa_parse.apps.worker import run_once
from knoa_parse.core.errors import ParseError
from knoa_parse.core.settings import Settings
from knoa_parse.core.store import Store

DOCUMENTS_AVAILABLE = importlib.util.find_spec("docling") is not None


@unittest.skipUnless(DOCUMENTS_AVAILABLE, "Install the documents group for native engine acceptance")
class DocumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from document_fixtures import make_fixtures

        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.fixtures = make_fixtures(cls.root / "fixtures")
        cls.store = make_store(Settings(cls.root / "data"))
        cls.results = {}
        for ext, path in cls.fixtures.items():
            with path.open("rb") as stream:
                source = cls.store.ingest(stream, path.name)
            job = cls.store.create_job(source.id)
            run_once(cls.store, job["id"])
            state = cls.store.job(job["id"])
            if state["state"] != "succeeded":
                raise AssertionError(f"{ext} fixture did not complete: {state}")
            cls.results[ext] = cls.store.result(job["id"])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_docx_preserves_duplicate_text_table_header_and_image(self):
        r = self.results["docx"]
        self.assertEqual(r.status, "completed")
        self.assertEqual(sum(b.text == "重复段落" for b in r.blocks), 2)
        self.assertIn("合成页眉", [b.text for b in r.blocks])
        self.assertTrue(any(b.kind == "table" and any(c["text"] == "橙汁" for c in b.data["cells"]) for b in r.blocks))
        image = next(b for b in r.blocks if b.kind == "image")
        path, mime = self.store.artifact(image.data["image_artifact_id"])
        self.assertEqual(mime, "image/png")
        self.assertTrue(path.read_bytes().startswith(b"\x89PNG"))

    def test_every_derived_document_pointer_resolves_to_retained_upstream(self):
        for ext in ("docx", "pptx", "xlsx"):
            r = self.results[ext]
            for block in r.blocks:
                for loc in block.locators:
                    if loc.precision != "derived_exact":
                        continue
                    path, _ = self.store.artifact(loc.artifact_id)
                    value = json.loads(path.read_bytes())
                    for token in loc.pointer.removeprefix("#/").split("/"):
                        value = value[int(token)] if isinstance(value, list) else value[token]
                    self.assertIsInstance(value, dict)
            self.assertTrue(any(a.role == "engine_result" for a in r.artifacts))

    def test_slide_notes_are_separate_and_emu_is_not_pdf_location(self):
        r = self.results["pptx"]
        notes = next(b for b in r.blocks if b.text == "这是演讲者备注")
        self.assertEqual(notes.data["content_role"], "notes")
        self.assertEqual(notes.data["slide_indices"], [1])
        self.assertTrue(all(loc.kind == "document_node" and loc.precision == "derived_exact" for b in r.blocks for loc in b.locators))

    def test_excel_formula_cache_hidden_and_formats_survive(self):
        r = self.results["xlsx"]
        cells = {(b.data["sheet"], b.data["address"]): b for b in r.blocks if b.data.get("role") == "original_cell"}
        self.assertEqual(cells[("数据", "F4")].data["formula"], "=D4*E4")
        self.assertEqual(cells[("数据", "F4")].data["cached_value"], 25)
        self.assertIsNone(cells[("数据", "J20")].data["cached_value"])
        self.assertEqual(cells[("数据", "J20")].data["formula"], "=SUM(F4:F5)")
        self.assertEqual(cells[("数据", "H2")].data["number_format"], "0%")
        self.assertEqual(cells[("数据", "H2")].data["raw_value"], 0.1)
        self.assertEqual(cells[("数据", "H3")].data["raw_value"], "2026-01-02T00:00:00")
        self.assertTrue(cells[("数据", "E5")].data["row_hidden"])
        self.assertTrue(cells[("数据", "E5")].data["column_hidden"])
        self.assertEqual(cells[("内部", "A1")].data["sheet_state"], "hidden")
        self.assertEqual(cells[("数据", "C10")].data["merged_range"], "C10:D10")

    def test_excel_regions_map_to_original_a1_not_physical_pages(self):
        r = self.results["xlsx"]
        main = next(b for b in r.blocks if b.kind == "table" and "C3" in b.data.get("cell_addresses", []))
        self.assertTrue(any(l.kind == "sheet_range" and l.sheet == "数据" and l.a1_range == "C3:F5" for l in main.locators))
        self.assertFalse(any(l.kind == "page_region" for b in r.blocks for l in b.locators))

    def test_pdf_keeps_original_page_units_and_warns_about_order(self):
        r = self.results["pdf"]
        self.assertEqual(r.status, "completed")
        self.assertEqual([b.text for b in r.blocks], ["Native PDF evidence", "Second native page"])
        self.assertEqual([b.locators[0].page for b in r.blocks], [1, 2])
        self.assertTrue(all(b.locators[0].unit == "pt" for b in r.blocks))
        self.assertIn("reading_order_unresolved", [i.code for i in r.issues])

    def test_image_only_pdf_reports_text_gap_but_retains_image(self):
        path = self.root / "fixtures/image-only.pdf"
        source = self.store.ingest(io.BytesIO(path.read_bytes()), path.name)
        job = self.store.create_job(source.id)
        run_once(self.store, job["id"])
        result = self.store.result(job["id"])
        self.assertEqual(result.status, "partial")
        self.assertIn("external_ocr_required", [i.code for i in result.issues])
        self.assertTrue(any(b.kind == "image" and "image_artifact_id" in b.data for b in result.blocks))

    def test_blank_native_pdf_does_not_invent_text(self):
        path = self.root / "fixtures/blank.pdf"
        source = self.store.ingest(io.BytesIO(path.read_bytes()), path.name)
        job = self.store.create_job(source.id)
        run_once(self.store, job["id"])
        result = self.store.result(job["id"])
        self.assertEqual(result.blocks, [])
        self.assertIn("no_native_content", [i.code for i in result.issues])

    def test_workbook_dimensions_are_bounded_before_conversion(self):
        from openpyxl import Workbook

        path = self.root / "oversized.xlsx"
        book = Workbook()
        book.active["XFD1048576"] = "sparse but enormous dimensions"
        book.save(path)
        source = self.store.ingest(io.BytesIO(path.read_bytes()), path.name)
        job = self.store.create_job(source.id)
        run_once(self.store, job["id"])
        self.assertEqual(self.store.job(job["id"])["error"]["code"], "resource_limit")
        with self.assertRaises(ParseError):
            self.store.result(job["id"])

    def test_corrupt_documents_never_publish_success(self):
        from zipfile import ZipFile

        for ext, part in (("docx", "word/document.xml"), ("pptx", "ppt/presentation.xml"),
                          ("xlsx", "xl/workbook.xml"), ("pdf", None)):
            with self.subTest(extension=ext):
                data = io.BytesIO()
                if part:
                    with ZipFile(data, "w") as z:
                        z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
                        z.writestr(part, "<broken>")
                else:
                    data.write(b"%PDF-1.7\ncorrupt")
                data.seek(0)
                source = self.store.ingest(data, "broken." + ext)
                job = self.store.create_job(source.id)
                run_once(self.store, job["id"])
                self.assertEqual(self.store.job(job["id"])["state"], "failed")
                if self.store.job(job["id"])["result_artifact_id"]:
                    result = self.store.result(job["id"])
                    self.assertEqual(result.status, "failed")
                    self.assertFalse(result.blocks)
                    self.assertTrue(any(i.severity == "error" for i in result.issues))
                else:
                    with self.assertRaises(ParseError):
                        self.store.result(job["id"])

    def test_cli_returns_partial_result_instead_of_hiding_retained_evidence(self):
        path = self.root / "fixtures/image-only.pdf"
        result = subprocess.run([sys.executable, "-m", "knoa_parse", "--data-dir", str(self.root / "cli"),
                                 "parse", str(path)], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "partial")

    @unittest.skipUnless(importlib.util.find_spec("fastapi") is not None, "Install api for HTTP acceptance")
    def test_api_document_and_derived_artifact_share_authorization(self):
        from fastapi.testclient import TestClient
        from knoa_parse.apps.api import create_app

        client = TestClient(create_app(self.store.settings, "document-test"))
        headers = {"Authorization": "Bearer document-test"}
        path = self.fixtures["pptx"]
        uploaded = client.post("/v1/sources?filename=sample.pptx", content=path.read_bytes(), headers=headers)
        self.assertEqual(uploaded.status_code, 201)
        job = client.post("/v1/jobs", json={"source_id": uploaded.json()["id"]}, headers=headers).json()
        run_once(self.store, job["id"])
        result = client.get(f"/v1/jobs/{job['id']}/result", headers=headers).json()
        artifact_id = next(a["id"] for a in result["artifacts"] if a["role"] == "engine_result")
        self.assertEqual(client.get(f"/v1/artifacts/{artifact_id}").status_code, 401)
        upstream = client.get(f"/v1/artifacts/{artifact_id}", headers=headers)
        self.assertEqual(upstream.status_code, 200)
        self.assertEqual(upstream.json()["schema_name"], "DoclingDocument")


if __name__ == "__main__":
    unittest.main()
