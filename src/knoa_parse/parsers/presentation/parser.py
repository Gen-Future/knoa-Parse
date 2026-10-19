from knoa_parse.core.documents import NativeDocumentParser
from knoa_parse.core.models import Issue


class PresentationParser(NativeDocumentParser):
    def finalize(self, source, document, blocks, coverage, issues):
        for block, item in zip(blocks, document.items):
            # Slide numbers are metadata; do not masquerade EMU coordinates as PDF points.
            block.data["slide_indices"] = sorted({p["page"] for p in item.locations})
        issues.append(Issue(code="derived_locations", severity="warning",
                            message="Locations refer to the retained tree; original shape IDs and precise slide regions are not exposed"))
