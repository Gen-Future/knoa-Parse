"""Draft contract regressions, not tests of an implemented parser."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check import check_contract, contract_dir, validate_result


class ParseContractTests(unittest.TestCase):
    def setUp(self):
        directory = contract_dir()
        self.schema = json.loads((directory / "parse-result.schema.json").read_text())
        self.success = json.loads((directory / "examples/success.json").read_text())
        self.failed = json.loads((directory / "examples/failed.json").read_text())

    def validate(self, result):
        validate_result(result, self.schema)

    def test_fixtures_and_snapshot(self):
        check_contract()

    def test_empty_document_can_complete(self):
        self.success["evidence"] = []
        self.validate(self.success)

    def test_partial_requires_both_evidence_and_error(self):
        self.success["status"] = "partial"
        with self.assertRaises(ValueError):
            self.validate(self.success)
        self.success["errors"] = self.failed["errors"]
        self.validate(self.success)
        self.success["evidence"] = []
        with self.assertRaises(ValueError):
            self.validate(self.success)

    def test_failed_cannot_include_evidence(self):
        self.failed["evidence"] = self.success["evidence"]
        with self.assertRaises(ValueError):
            self.validate(self.failed)

    def test_completed_cannot_hide_errors(self):
        self.success["errors"] = self.failed["errors"]
        with self.assertRaises(ValueError):
            self.validate(self.success)

    def test_missing_source_revision_is_rejected(self):
        del self.success["source"]["revision"]
        with self.assertRaises(ValueError):
            self.validate(self.success)

    def test_unsupported_version_is_rejected(self):
        self.success["schema_version"] = "99.0.0"
        with self.assertRaises(ValueError):
            self.validate(self.success)

    def test_extra_field_is_rejected(self):
        self.success["workspace_id"] = "untrusted-space"
        with self.assertRaises(ValueError):
            self.validate(self.success)

    def test_duplicate_evidence_id_is_rejected(self):
        self.success["evidence"].append(copy.deepcopy(self.success["evidence"][0]))
        with self.assertRaises(ValueError):
            self.validate(self.success)

    def test_text_range_must_be_forward(self):
        location = self.success["evidence"][0]["location"]
        location["end"] = location["start"]
        with self.assertRaises(ValueError):
            self.validate(self.success)

    def test_pages_are_one_based(self):
        self.success["evidence"][0]["location"] = {"kind": "page", "page": 1}
        self.validate(self.success)
        self.success["evidence"][0]["location"]["page"] = 0
        with self.assertRaises(ValueError):
            self.validate(self.success)

    def test_time_range_must_be_forward(self):
        location = {"kind": "time", "start_ms": 0, "end_ms": 1000}
        self.success["evidence"][0]["location"] = location
        self.validate(self.success)
        location["end_ms"] = 0
        with self.assertRaises(ValueError):
            self.validate(self.success)


if __name__ == "__main__":
    unittest.main()
