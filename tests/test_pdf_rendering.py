import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
from m3_fixtures import fixture

from knoa_parse.core.errors import ParseError
from knoa_parse.processors.pdf.page_inputs import PdfPageSpec, RasterPageInput
from knoa_parse.processors.pdf.rendering import PdfRenderRequest, RenderBudget, render_and_prepare


class ScriptedRenderer:
    def __init__(self, rasters=None, failure=None):
        self.rasters = rasters
        self.failure = failure
        self.requests = []

    def render(self, request: PdfRenderRequest):
        self.requests.append(request)
        if self.failure:
            raise self.failure
        return self.rasters


class PdfRenderingTests(unittest.TestCase):
    def setUp(self):
        self.native, _ = fixture()
        self.content = b"fixed synthetic PDF bytes"
        digest = hashlib.sha256(self.content).hexdigest()
        self.native.source.sha256 = digest
        self.native.source.size_bytes = len(self.content)
        self.native.artifacts[0].sha256 = digest
        self.native.artifacts[0].size_bytes = len(self.content)
        self.specs = [PdfPageSpec(page=1, width_pt=600, height_pt=800), PdfPageSpec(page=2, width_pt=600, height_pt=800)]
        self.rasters = [RasterPageInput(page=1, artifact_id="rendered-1", media_type="image/png", width_px=1200, height_px=1600, content=b"raster-one"),
                        RasterPageInput(page=2, artifact_id="rendered-2", media_type="image/png", width_px=1200, height_px=1600, content=b"raster-two")]

    def assert_code(self, code, renderer, content=None, specs=None, budget=None):
        with self.assertRaises(ParseError) as caught:
            render_and_prepare(self.native, self.content if content is None else content,
                               self.specs if specs is None else specs, renderer, budget)
        self.assertEqual(caught.exception.code, code)

    def test_valid_source_and_budget_are_passed_once_and_prepared(self):
        renderer = ScriptedRenderer(self.rasters)
        output = render_and_prepare(self.native, self.content, list(reversed(self.specs)), renderer)
        self.assertEqual([page.page for page in output], [1, 2])
        self.assertEqual(len(renderer.requests), 1)
        request = renderer.requests[0]
        self.assertEqual(request.content, self.content)
        self.assertEqual([item.page for item in request.pages], [1, 2])
        self.assertEqual(output[0].artifact.sha256, hashlib.sha256(b"raster-one").hexdigest())

    def test_source_digest_and_media_are_checked_before_renderer(self):
        renderer = ScriptedRenderer(self.rasters)
        self.assert_code("source_corrupt", renderer, content=b"wrong")
        self.assertEqual(renderer.requests, [])
        self.native.source.media_type = "text/plain"
        self.assert_code("invalid_page_input", renderer)
        self.assertEqual(renderer.requests, [])

    def test_page_and_duplicate_requests_are_preflighted(self):
        renderer = ScriptedRenderer(self.rasters)
        self.assert_code("resource_limit", renderer, specs=self.specs, budget=RenderBudget(max_pages=1))
        self.assert_code("invalid_page_input", renderer, specs=[self.specs[0], self.specs[0]])
        self.assert_code("invalid_page_input", renderer, specs=[PdfPageSpec(page=3, width_pt=600, height_pt=800)])
        self.assertEqual(renderer.requests, [])

    def test_output_page_and_total_budgets_are_atomic(self):
        renderer = ScriptedRenderer(self.rasters)
        self.assert_code("resource_limit", renderer, budget=RenderBudget(max_page_bytes=1))
        self.assert_code("resource_limit", renderer, budget=RenderBudget(max_total_bytes=1))
        huge_pixels = [self.rasters[0].model_copy(update={"width_px": 10_000, "height_px": 10_000}), self.rasters[1]]
        self.assert_code("resource_limit", ScriptedRenderer(huge_pixels), budget=RenderBudget(max_pixels=100))

    def test_renderer_shape_and_errors_are_sanitized(self):
        self.assert_code("render_failed", ScriptedRenderer(None), budget=RenderBudget())
        self.assert_code("render_failed", ScriptedRenderer(self.rasters, failure=RuntimeError("private PDF path")))
        self.assert_code("invalid_page_input", ScriptedRenderer(self.rasters[:1]))
        self.assert_code("invalid_page_input", ScriptedRenderer([self.rasters[0], self.rasters[0].model_copy(update={"page": 2})]))

    def test_renderer_receives_no_path_and_native_result_is_unchanged(self):
        before = self.native.model_dump_json()
        renderer = ScriptedRenderer(self.rasters)
        render_and_prepare(self.native, self.content, self.specs, renderer)
        self.assertFalse(hasattr(renderer.requests[0], "path"))
        self.assertEqual(self.native.model_dump_json(), before)


if __name__ == "__main__":
    unittest.main()
