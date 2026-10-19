def cell_address(column: int, row: int) -> str:
    """A1 label from 1-based source coordinates; never a physical page position."""
    if not (1 <= column <= 16384 and 1 <= row <= 1048576):
        raise ValueError("Cell position is outside workbook bounds")
    label = ""
    while column:
        column, remainder = divmod(column - 1, 26)
        label = chr(65 + remainder) + label
    return f"{label}{row}"
