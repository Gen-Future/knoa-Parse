from knoa_parse.core.documents import NativeDocumentParser
from knoa_parse.core.models import Coverage, Issue, PageRegion


class PdfParser(NativeDocumentParser):
    def locations(self, source, item, raw_artifact, document):
        return [PageRegion(artifact_id=source.id, precision="source_exact", page=p["page"],
                           bbox=p["bbox"], unit="pt", origin=p["origin"]) for p in item.locations] or super().locations(source, item, raw_artifact, document)

    def finalize(self, source, document, blocks, coverage, issues):
        if document.successful:
            coverage.clear()
        for page in document.pages:
            unit = f"page-{page}"
            items = [i for i in document.items if any(p["page"] == page for p in i.locations)]
            has_text = any(i.text and i.text.strip() for i in items)
            has_image = any(i.kind == "image" for i in items)
            if has_image and not has_text:
                issues.append(Issue(code="external_ocr_required", severity="error", unit_id=unit,
                                    message="Image-only page has no native text; external OCR is not configured"))
                coverage.append(Coverage(unit_id=unit, status="failed", issue_codes=["external_ocr_required"]))
            else:
                coverage.append(Coverage(unit_id=unit, status="completed"))
                if has_image:
                    issues.append(Issue(code="image_text_unread", severity="warning", unit_id=unit,
                                        message="Embedded images retained; their text has not been recognized"))
                elif not has_text:
                    issues.append(Issue(code="no_native_content", severity="warning", unit_id=unit,
                                        message="No native text or bitmap found; this does not prove the page is visually empty"))
        if not coverage:
            coverage.append(Coverage(unit_id="document", status="completed"))
        issues.append(Issue(code="reading_order_unresolved", severity="warning",
                            message="Native PDF reads text and bitmaps in backend order; layout, tables and vector drawings are not reconstructed"))
