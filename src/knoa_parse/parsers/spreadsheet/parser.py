from knoa_parse.core.coordinates import cell_address
from knoa_parse.core.documents import NativeDocumentParser, WorkbookInspector
from knoa_parse.core.models import Block, Coverage, DocumentNode, SheetRange


class SpreadsheetParser(NativeDocumentParser):
    def __init__(self, engine, sink, inspector: WorkbookInspector):
        super().__init__(engine, sink)
        self.inspector = inspector

    def parse(self, source, path):
        self.workbook = self.inspector.inspect(path)
        return super().parse(source, path)

    def locations(self, source, item, raw_artifact, document):
        locations = super().locations(source, item, raw_artifact, document)
        if item.kind not in {"table", "text"} or item.data.get("role") == "native_chart":
            return locations
        for pos in item.locations:
            page = pos["page"]
            left, top, right, bottom = pos["bbox"]
            if not (1 <= page <= len(self.workbook["sheets"])) or pos["origin"] != "top_left":
                continue
            if any(v != int(v) for v in (left, top, right, bottom)) or left < 0 or top < 0 or right <= left or bottom <= top:
                continue
            name = self.workbook["sheets"][page - 1]["name"]
            locations.append(SheetRange(artifact_id=source.id, precision="source_exact", sheet=name,
                                        a1_range=f"{cell_address(int(left)+1, int(top)+1)}:{cell_address(int(right), int(bottom))}"))
            if item.kind == "table":
                item.data["cell_addresses"] = [cell_address(int(left) + c["column"] + 1,
                                                           int(top) + c["row"] + 1) for c in item.data["cells"]]
        return locations

    def finalize(self, source, document, blocks, coverage, issues):
        if document.successful:
            coverage.clear()
        for sheet in self.workbook["sheets"]:
            coverage.append(Coverage(unit_id="sheet:" + sheet["name"], status="completed"))
        # Original records are independent evidence, including formulas omitted by upstream regions.
        for index, cell in enumerate(self.workbook["cells"]):
            blocks.append(Block(id=f"cell-{index}", kind="structured", data={"role": "original_cell", **cell},
                                locators=[SheetRange(artifact_id=source.id, precision="source_exact",
                                                     sheet=cell["sheet"], a1_range=cell["address"])]))
        blocks.append(Block(id="workbook-metadata", kind="structured", data={"sheets": self.workbook["sheets"]},
                            locators=[DocumentNode(artifact_id=source.id, precision="source_exact", pointer="")]))
