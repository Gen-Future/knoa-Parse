from knoa_parse.core.documents import NativeDocumentParser
from knoa_parse.core.models import Issue


class WordParser(NativeDocumentParser):
    def finalize(self, source, document, blocks, coverage, issues):
        issues.append(Issue(code="derived_locations", severity="warning",
                            message="Locations refer to the retained document tree, not Word pagination or original XML nodes"))
