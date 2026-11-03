import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
from m3_fixtures import fixture

from knoa_parse.core.errors import ParseError
from knoa_parse.processors.pdf.page_inputs import PdfPageSpec, RasterPageInput, prepare_pages


class PdfPageInputTests(unittest.TestCase):
    def setUp(self):
        self.native, self.pages = fixture()
        self.specs = [PdfPageSpec(page=1, width_pt=600, height_pt=800),
                      PdfPageSpec(page=2, width_pt=600, height_pt=800)]
        self.rasters = [RasterPageInput(page=1, artifact_id="prepared-1", media_type="image/png",
                                        width_px=1200, height_px=1600, content=b"page-one"),
                        RasterPageInput(page=2, artifact_id="prepared-2", media_type="image/jpeg",
                                        width_px=1200, height_px=1600, content=b"page-two")]

    def assert_code(self, code, specs=None, rasters=None):
        with self.assertRaises(ParseError) as caught:
            prepare_pages(self.native, self.specs if specs is None else specs,
                          self.rasters if rasters is None else rasters)
        self.assertEqual(caught.exception.code, code)

    def test_binds_digest_media_and_source_without_mutating_native(self):
        before = self.native.model_dump_json()
        output = prepare_pages(self.native, self.specs, self.rasters)
        self.assertEqual([page.page for page in output], [1, 2])
        self.assertEqual(output[0].artifact.role, "derived")
        self.assertEqual(output[0].artifact.media_type, "image/png")
        self.assertEqual(output[0].artifact.size_bytes, len(b"page-one"))
        self.assertEqual(output[0].source_id, self.native.source.id)
        self.assertEqual(output[0].source_artifact_id, self.native.source.id)
        self.assertEqual(output[0].width_pt, 600)
        self.assertEqual(output[0].height_pt, 800)
        self.assertEqual(output[0].content, b"page-one")
        self.assertEqual(self.native.model_dump_json(), before)

    def test_rotation_swaps_upright_dimensions_but_preserves_source_media_box(self):
        specs = [PdfPageSpec(page=1, width_pt=600, height_pt=800, rotation_degrees=90),
                 PdfPageSpec(page=2, width_pt=600, height_pt=800, rotation_degrees=270)]
        rasters = [r.model_copy(update={"width_px": 1600, "height_px": 1200}) for r in self.rasters]
        output = prepare_pages(self.native, specs, rasters)
        self.assertEqual([(p.width_pt, p.height_pt, p.source_width_pt, p.source_height_pt, p.rotation_degrees)
                          for p in output], [(800, 600, 600, 800, 90), (800, 600, 600, 800, 270)])

    def test_aspect_ratio_has_small_rounding_tolerance(self):
        output = prepare_pages(self.native, self.specs,
                               [self.rasters[0].model_copy(update={"width_px": 1210}), self.rasters[1]])
        self.assertEqual(output[0].page, 1)
        self.assert_code("invalid_page_input", rasters=[self.rasters[0].model_copy(update={"width_px": 1400}), self.rasters[1]])

    def test_all_pages_are_preflighted_before_returning(self):
        bad = self.rasters[1].model_copy(update={"artifact_id": self.native.source.id})
        self.assert_code("invalid_page_input", rasters=[self.rasters[0], bad])

    def test_source_and_page_ownership(self):
        self.native.source.media_type = "text/plain"
        self.assert_code("invalid_page_input")
        self.setUp()
        self.specs[1].page = 3
        self.rasters[1].page = 3
        self.assert_code("invalid_page_input")

    def test_duplicate_missing_and_unknown_sets_rejected(self):
        self.assert_code("invalid_page_input", specs=[self.specs[0], self.specs[0]])
        self.assert_code("invalid_page_input", rasters=[self.rasters[0]])
        self.assert_code("invalid_page_input", specs=[self.specs[0], PdfPageSpec(page=3, width_pt=600, height_pt=800)],
                         rasters=self.rasters)

    def test_invalid_raster_media_dimensions_and_crop_rejected(self):
        with self.assertRaises(ValueError):
            RasterPageInput(page=1, artifact_id="bad", media_type="image/gif", width_px=1200, height_px=1600, content=b"x")
        with self.assertRaises(ValueError):
            RasterPageInput(page=1, artifact_id="bad", media_type="image/png", width_px=0, height_px=1600, content=b"x")
        with self.assertRaises(ValueError):
            PdfPageSpec(page=1, width_pt=600, height_pt=800, rotation_degrees=45)
        with self.assertRaises(ValueError):
            PdfPageSpec(page=1, width_pt=float("inf"), height_pt=800)
        with self.assertRaises(ValueError):
            PdfPageSpec(page=1, width_pt=600, height_pt=800, crop="crop")

    def test_zero_bytes_and_artifact_id_collisions_rejected(self):
        with self.assertRaises(ValueError):
            RasterPageInput(page=1, artifact_id="empty", media_type="image/png", width_px=1200, height_px=1600, content=b"")
        self.assert_code("invalid_page_input", rasters=[self.rasters[0], self.rasters[0].model_copy(update={"page": 2})])

    def test_output_is_sorted_and_keeps_page_specific_bytes(self):
        output = prepare_pages(self.native, list(reversed(self.specs)), list(reversed(self.rasters)))
        self.assertEqual([p.page for p in output], [1, 2])
        self.assertEqual([p.content for p in output], [b"page-one", b"page-two"])


if __name__ == "__main__":
    unittest.main()
