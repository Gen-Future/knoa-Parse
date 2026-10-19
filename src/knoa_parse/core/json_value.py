import json
import math

from .errors import ParseError


def read_json(text: str):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate object keys are ambiguous")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("Nonfinite constants are not JSON")

    try:
        value = json.loads(text.lstrip("\ufeff"), object_pairs_hook=pairs, parse_constant=constant)
        stack = [(value, 0)]
        count = 0
        while stack:
            item, depth = stack.pop()
            count += 1
            if depth > 64 or count > 100000:
                raise ParseError("resource_limit", "JSON exceeds the structure budget", 413)
            if isinstance(item, dict):
                stack.extend((v, depth + 1) for v in item.values())
            elif isinstance(item, list):
                stack.extend((v, depth + 1) for v in item)
            elif isinstance(item, float) and not math.isfinite(item):
                raise ValueError("Number is outside finite representation")
        return value
    except (ValueError, RecursionError) as exc:
        raise ParseError("invalid_json", "Invalid or ambiguous JSON document") from exc
