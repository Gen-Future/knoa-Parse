"""Authored six-format corpus and checks that its oracle detects evidence loss."""
import importlib.util
import io
import tempfile
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "evals")]

from m2_acceptance import check_result, evaluate
from m2_fixtures import make_fixtures
from knoa_parse.core.settings import Settings
from knoa_parse.core.store import Store
from knoa_parse.parsers.structured.parser import JsonParser
from knoa_parse.parsers.text.parser import TextParser

DOCUMENTS = importlib.util.find_spec("docling") is not None


class M2AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_base_corpus_through_worker(self):
        report = evaluate(self.root / "base", base_only=True)
        self.assertEqual(report["case_count"], 4)
        self.assertTrue(report["passed"], report["cases"])

    @unittest.skipUnless(DOCUMENTS, "Install documents for the full M2 corpus")
    def test_six_format_corpus_through_worker(self):
        report = evaluate(self.root / "full")
        self.assertEqual(report["case_count"], 15)
        self.assertTrue(report["passed"], [case for case in report["cases"] if not case["passed"]])

    @unittest.skipUnless(DOCUMENTS, "Install documents for reproducible Office fixtures")
    def test_regenerated_inputs_have_identical_bytes(self):
        make_fixtures(self.root / "one")
        make_fixtures(self.root / "two")
        first = {p.name: p.read_bytes() for p in (self.root / "one").iterdir()}
        second = {p.name: p.read_bytes() for p in (self.root / "two").iterdir()}
        self.assertEqual(first.keys(), second.keys())
        for name in first:
            with self.subTest(name=name):
                self.assertEqual(first[name], second[name])

    def text_result(self):
        store = Store(Settings(self.root / "data"))
        source = store.ingest(io.BytesIO(b"authored evidence"), "source.txt")
        return store, TextParser().parse(source, store.verify_source(source))

    def test_oracle_rejects_missing_content_even_when_status_is_completed(self):
        store, result = self.text_result()
        case = {"expected": "completed", "checks": [{"type": "text_count", "value": "authored evidence", "count": 1}]}
        self.assertEqual(check_result(case, result, store), [])
        result.blocks.clear()
        self.assertTrue(any("text count" in failure for failure in check_result(case, result, store)))

    def test_oracle_rejects_out_of_bounds_source_locator(self):
        store, result = self.text_result()
        result.blocks[0].locators[0].end += 10
        self.assertTrue(any("text span" in failure for failure in check_result({"expected": "completed"}, result, store)))

    def test_oracle_rejects_boolean_changed_to_number(self):
        store = Store(Settings(self.root / "data"))
        source = store.ingest(io.BytesIO(b'{"approved":false}'), "source.json")
        result = JsonParser().parse(source, store.verify_source(source))
        case = {"expected": "completed", "checks": [{"type": "json_exact", "value": {"approved": False}}]}
        self.assertEqual(check_result(case, result, store), [])
        result.blocks[0].data["value"]["approved"] = 0
        self.assertTrue(any("native types" in failure for failure in check_result(case, result, store)))

    def test_unknown_check_cannot_silently_pass(self):
        store, result = self.text_result()
        with self.assertRaises(ValueError):
            check_result({"expected": "completed", "checks": [{"type": "misspelled_check"}]}, result, store)


if __name__ == "__main__":
    unittest.main()
