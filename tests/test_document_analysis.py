import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
from m3_fixtures import ScriptedDocumentProvider, fixture

from knoa_parse.core.document_analysis import PageAnalysis, RecognizedElement
from knoa_parse.core.errors import ParseError
from knoa_parse.core.text_model import ProviderError
from knoa_parse.enrichment.document import AnalysisBudget, analyze_pages, select_context


class DocumentAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.native, self.pages = fixture()
        self.provider = ScriptedDocumentProvider()

    def run_analysis(self, **kwargs):
        return analyze_pages(self.native, self.pages, self.provider, dry_run=True, **kwargs)

    def error_before_call(self, code, **kwargs):
        with self.assertRaises(ParseError) as caught:
            self.run_analysis(**kwargs)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.provider.calls, [])

    def test_missing_and_mock_cannot_be_live(self):
        for provider, code in ((None, "missing_capability"), (self.provider, "mock_not_allowed")):
            with self.subTest(code=code), self.assertRaises(ParseError) as caught:
                analyze_pages(self.native, self.pages, provider)
            self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.provider.calls, [])

    def test_full_preflight_before_sending_any_page(self):
        self.pages[1].source_id = "another-source"
        self.error_before_call("invalid_page_input")

    def test_digest_size_role_type_and_source_binding(self):
        mutations = [lambda p: setattr(p, "content", b"tampered"),
                     lambda p: setattr(p.artifact, "size_bytes", 1),
                     lambda p: setattr(p.artifact, "role", "source"),
                     lambda p: setattr(p.artifact, "media_type", "image/jpeg"),
                     lambda p: setattr(p, "source_sha256", "b" * 64),
                     lambda p: setattr(p, "source_artifact_id", "other")]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.setUp()
                mutation(self.pages[1])
                self.error_before_call("invalid_page_input")

    def test_unknown_duplicate_pages_and_artifacts(self):
        for field, value in (("page", 3), ("page", 1)):
            self.setUp()
            setattr(self.pages[1], field, value)
            self.error_before_call("invalid_page_input")
        self.setUp()
        self.pages[1].artifact.id = self.pages[0].artifact.id
        self.error_before_call("invalid_page_input")

    def test_input_budgets_and_service_limits(self):
        for budget in (AnalysisBudget(max_pages=1), AnalysisBudget(max_input_bytes=1)):
            self.error_before_call("resource_limit", budget=budget)
        capability = self.provider.describe()
        for field, value in (("max_pixels", 1), ("max_page_bytes", 1)):
            cap = capability.model_copy(update={field: value})
            with patch.object(self.provider, "describe", return_value=cap):
                self.error_before_call("resource_limit")

    def test_upright_mapping_and_finite_geometry_required(self):
        for field, value in (("mapping", "cropped"), ("width_pt", float("nan")), ("height_px", 0), ("content", b"")):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.pages[0].__class__.model_validate(self.pages[0].model_dump() | {"content": self.pages[0].content, field: value})

    def test_partial_merge_is_ordered_and_native_unchanged(self):
        before = self.native.model_dump_json()
        self.pages.reverse()
        report = self.run_analysis()
        self.assertEqual(report.status, "partial")
        self.assertEqual([p.page for p in report.outcomes], [1, 2])
        self.assertEqual(report.blocks[0].locators[0].bbox, [60.0, 160.0, 300.0, 320.0])
        self.assertEqual(report.blocks[0].acquisition, "ocr")
        self.assertEqual(report.blocks[0].context_block_ids, ["heading"])
        self.assertEqual(report.blocks[0].locators[0].precision, "estimated")
        self.assertNotIn(report.blocks[0].id, [b.id for b in self.native.blocks])
        self.assertEqual(before, self.native.model_dump_json())

    def test_pixel_bottom_left_transform_and_description(self):
        self.pages = self.pages[:1]
        self.provider.responses[1] = PageAnalysis(page=1, model="mock", total_tokens=0, elements=[RecognizedElement(
            kind="description", text="图像描述", bbox=[120.0, 1280.0, 600.0, 960.0], unit="px", origin="bottom_left")])
        report = self.run_analysis()
        self.assertEqual(report.status, "completed")
        self.assertEqual(report.blocks[0].locators[0].bbox, [60.0, 160.0, 300.0, 320.0])
        self.assertEqual(report.blocks[0].acquisition, "inferred")
        self.assertEqual(report.total_tokens, 0)

    def test_context_limits_and_ambiguous_page_exclusion(self):
        block = self.native.blocks[0]
        other = block.model_copy(deep=True)
        other.id = "other-page"
        other.locators[0].page = 2
        ambiguous = block.model_copy(deep=True)
        ambiguous.id = "ambiguous"
        ambiguous.locators.append(other.locators[0])
        repeated = block.model_copy(deep=True)
        repeated.id = "repeated-heading"
        self.native.blocks.extend([other, ambiguous, repeated])
        selected = select_context(self.native, 1, AnalysisBudget(max_context_chars=3))
        self.assertEqual([c.block_id for c in selected], ["heading"])
        self.assertEqual(selected[0].text, "已有中")
        self.assertTrue(selected[0].truncated)
        self.assertEqual(select_context(self.native, 1, AnalysisBudget(max_context_chars=0)), [])
        selected = select_context(self.native, 1, AnalysisBudget(max_context_blocks=1))
        self.assertEqual(len(selected), 1)
        self.assertFalse(selected[0].truncated)
        self.assertEqual([c.block_id for c in select_context(self.native, 1, AnalysisBudget())], ["heading", "repeated-heading"])

    def test_bad_coordinates_reject_whole_page(self):
        self.pages = self.pages[:1]
        good = self.provider.responses[1].elements[0]
        bad = RecognizedElement(text="bad", bbox=[1.0, 1.0, 2000.0, 3000.0], unit="px", origin="top_left")
        self.provider.responses[1] = PageAnalysis(page=1, model="mock", elements=[good, bad])
        report = self.run_analysis()
        self.assertEqual(report.status, "failed")
        self.assertEqual(report.blocks, [])
        self.assertEqual(report.outcomes[0].code, "invalid_provider_response")

    def test_response_validation_missing_bounds_nonfinite_and_whitespace(self):
        for changes in ({"bbox": None}, {"bbox": [-0.1, 0.0, 0.5, 0.5]},
                        {"bbox": [0.0, 0.0, float("inf"), 0.5]}, {"text": "  "}, {"bbox": [0.5, 0.5, 0.1, 0.1]}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                RecognizedElement.model_validate(dict(text="text", bbox=[0.0, 0.0, 0.5, 0.5], unit="normalized", origin="top_left") | changes)
        with self.assertRaises(ValidationError):
            PageAnalysis(page=1, model="mock", elements=[])

    def test_wrong_page_and_undeclared_units(self):
        self.pages = self.pages[:1]
        self.provider.responses[1].page = 2
        self.assertEqual(self.run_analysis().status, "failed")
        self.provider.responses[1].page = 1
        cap = self.provider.describe().model_copy(update={"coordinate_units": ["px"]})
        with patch.object(self.provider, "describe", return_value=cap):
            self.assertEqual(self.run_analysis().status, "failed")

    def test_blank_is_explicit_and_not_native_coverage_repair(self):
        self.provider.responses = {n: PageAnalysis(page=n, model="mock", elements=[], blank=True) for n in (1, 2)}
        report = self.run_analysis()
        self.assertEqual(report.status, "completed")
        self.assertEqual(report.blocks, [])
        self.assertEqual(self.native.coverage[0].status, "failed")
        self.assertEqual(self.native.status, "partial")

    def test_errors_are_sanitized_and_never_retried(self):
        for failure in (ProviderError("private-key-code", "private-key-message", retryable=True), RuntimeError("private-key-stack")):
            self.setUp()
            self.provider.responses[1] = failure
            report = self.run_analysis()
            self.assertEqual(len(self.provider.calls), 2)
            self.assertEqual(report.status, "failed")
            self.assertNotIn("private-key", report.model_dump_json())
            self.assertIsNone(report.total_tokens)
            self.assertEqual(report.invocations[0].status, "unknown")

    def test_cancel_before_and_after_send(self):
        report = self.run_analysis(cancelled=lambda: True)
        self.assertEqual(report.status, "failed")
        self.assertEqual(self.provider.calls, [])
        self.assertTrue(all(o.status == "not_sent" for o in report.outcomes))
        self.setUp()
        report = self.run_analysis(cancelled=lambda: bool(self.provider.calls))
        self.assertEqual(len(self.provider.calls), 1)
        self.assertEqual(report.blocks, [])
        self.assertEqual(report.invocations[0].status, "discarded")
        self.assertEqual(report.invocations[0].code, "cancelled")
        self.assertIsNone(report.invocations[0].cost)

    def test_deadline_before_and_after_send(self):
        moments = iter([0.0, 61.0, 62.0])
        report = self.run_analysis(clock=lambda: next(moments))
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(report.outcomes[0].code, "deadline_exceeded")
        self.setUp()
        moments = iter([0.0, 1.0, 61.0, 62.0])
        report = self.run_analysis(clock=lambda: next(moments))
        self.assertEqual(len(self.provider.calls), 1)
        self.assertEqual(report.blocks, [])
        self.assertEqual(report.invocations[0].code, "deadline_exceeded")

    def test_call_and_output_budgets(self):
        report = self.run_analysis(budget=AnalysisBudget(max_calls=1))
        self.assertEqual(len(self.provider.calls), 1)
        self.assertEqual(report.outcomes[1].code, "call_budget_exceeded")
        self.setUp()
        report = self.run_analysis(budget=AnalysisBudget(max_text_chars=1))
        self.assertEqual(report.outcomes[0].code, "output_budget_exceeded")
        self.assertEqual(report.blocks, [])
        self.setUp()
        self.provider.responses[1].elements *= 2
        report = self.run_analysis(budget=AnalysisBudget(max_blocks=1))
        self.assertEqual(report.outcomes[0].code, "output_budget_exceeded")

    def test_json_keeps_refs_not_bytes_and_mock_marker(self):
        report = self.run_analysis()
        encoded = report.model_dump_json()
        value = json.loads(encoded)
        self.assertTrue(value["dry_run"])
        self.assertEqual(value["invocations"][0]["execution"], "mock")
        self.assertNotIn("content", value["pages"][0])
        self.assertNotIn("not raster bytes", encoded)
        self.assertEqual(value["pages"][0]["artifact"]["sha256"], self.pages[0].artifact.sha256)
        self.assertIsNone(value["total_tokens"])

    def test_cumulative_output_and_known_usage_include_discarded_call(self):
        self.provider.responses = {n: PageAnalysis(page=n, model="mock", total_tokens=n, elements=[RecognizedElement(
            text="中文", bbox=[0.1, 0.2, 0.5, 0.4], unit="normalized", origin="top_left")]) for n in (1, 2)}
        report = self.run_analysis(budget=AnalysisBudget(max_text_chars=3))
        self.assertEqual(report.status, "partial")
        self.assertEqual([b.text for b in report.blocks], ["中文"])
        self.assertEqual(report.outcomes[1].code, "output_budget_exceeded")
        self.assertEqual(report.total_tokens, 3)
        self.assertEqual(len(self.provider.calls), 2)

    def test_provider_cannot_mutate_retained_input_or_context(self):
        before = self.native.model_dump_json()

        def mutate(request):
            request.context[0].text = "mutated"
            request.page.artifact.id = "mutated"
            return self.provider.responses[1]

        self.pages = self.pages[:1]
        with patch.object(self.provider, "analyze_page", side_effect=mutate):
            report = self.run_analysis()
        self.assertEqual(report.invocations[0].context[0].text, "已有中文页眉")
        self.assertEqual(report.pages[0].artifact.id, "page-image-1")
        self.assertEqual(self.pages[0].artifact.id, "page-image-1")
        self.assertEqual(self.native.model_dump_json(), before)


if __name__ == "__main__":
    unittest.main()
