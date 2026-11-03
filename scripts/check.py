"""Repository, versioned contract and capability planning checks."""
import hashlib
import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

if sys.version_info < (3, 11):
    raise SystemExit("Repository checks require Python 3.11+; select that interpreter before creating .venv")

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def contract_dir(version="0.1.0-draft.1"):
    # Default is the legacy fixture version, so its regression suite remains unchanged.
    return ROOT / "contracts" / ("v" + version)


def validate_result(result, schema):
    errors = [error.message for error in Draft202012Validator(schema).iter_errors(result)]
    if errors:
        raise ValueError("; ".join(errors))
    if result.get("schema_version") == "0.2.0-draft.1":
        from knoa_parse.core.models import ParseResult

        ParseResult.model_validate(result)
        return
    ids = set()
    for item in result["evidence"]:
        if item["id"] in ids:
            raise ValueError("Duplicate evidence ID")
        ids.add(item["id"])
        location = item["location"]
        if location["kind"] == "text" and location["end"] <= location["start"]:
            raise ValueError("Text range must be non-empty and forward")
        if location["kind"] == "time" and location["end_ms"] <= location["start_ms"]:
            raise ValueError("Time range must be non-empty and forward")


def check_contract():
    index = json.loads((ROOT / "contracts/index.json").read_text(encoding="utf-8"))
    directories = {p.parent.name for p in ROOT.glob("contracts/*/parse-result.schema.json")}
    if directories != {"v" + version for version in index["versions"]}:
        raise ValueError("Contract version index must cover every schema")
    if index["active"] not in index["versions"]:
        raise ValueError("Active contract must be indexed")
    from export_schema import schema as generated_schema

    current = contract_dir(index["active"])
    current_schema = json.loads((current / "parse-result.schema.json").read_text(encoding="utf-8"))
    if current_schema != generated_schema():
        raise ValueError("Runtime model/schema drift; run scripts/export_schema.py")
    Draft202012Validator.check_schema(current_schema)
    for path in (current / "examples").glob("*.json"):
        validate_result(json.loads(path.read_text(encoding="utf-8")), current_schema)
    directory = contract_dir()
    schema = json.loads((directory / "parse-result.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    source = (directory / "examples/source.txt").read_bytes()
    original = source.decode("utf-8")
    for name in ("success", "failed"):
        result = json.loads((directory / f"examples/{name}.json").read_text(encoding="utf-8"))
        validate_result(result, schema)
        if result["source"]["content_sha256"] != hashlib.sha256(source).hexdigest():
            raise ValueError(f"{name}: source digest mismatch")
        for item in result["evidence"]:
            location = item["location"]
            if location["kind"] == "text":
                start, end = location["start"], location["end"]
                if end > len(original) or original[start:end] != item["text"]:
                    raise ValueError(f"{name}: source text/location mismatch")

    manifest_file = ROOT / "contracts/knoa-parse/UPSTREAM.json"
    if manifest_file.exists():
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        if manifest["version"] != schema["properties"]["schema_version"]["const"]:
            raise ValueError("Snapshot version mismatch")
        actual_files = {
            path.relative_to(directory).as_posix()
            for path in directory.rglob("*") if path.is_file()
        }
        if set(manifest["files"]) != actual_files:
            raise ValueError("Snapshot manifest must cover every contract file exactly")
        for relative, expected in manifest["files"].items():
            actual = hashlib.sha256((directory / relative).read_bytes()).hexdigest()
            if actual != expected:
                raise ValueError(f"Snapshot drift: {relative}; update through Parse")


def repository_files():
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
    )
    return sorted({
        ROOT / name.decode("utf-8") for name in output.split(b"\0") if name
    })


def validate_catalog(catalog):
    """Check planned ownership separately from accepted extension support."""
    if catalog.get("schema_version") != 2 or catalog.get("status") != "initial-runtime":
        raise ValueError("Unsupported catalog version or lifecycle")
    if catalog.get("model_policy") != {
        "local_model_inference": False, "model_weight_downloads": False
    }:
        raise ValueError("Local model inference and weight downloads must remain disabled")
    capabilities = catalog.get("provider_capabilities", [])
    provider_dirs = {
        path.name for path in (ROOT / "src/knoa_parse/providers").iterdir() if path.is_dir() and not path.name.startswith("_")
    }
    if len(capabilities) != len(set(capabilities)) or set(capabilities) != provider_dirs:
        raise ValueError("Provider capability declarations must match provider directories")
    processor_dirs = {
        path.name for path in (ROOT / "src/knoa_parse/processors").iterdir() if path.is_dir() and not path.name.startswith("_")
    }
    parser_dirs = {
        path.name for path in (ROOT / "src/knoa_parse/parsers").iterdir() if path.is_dir() and not path.name.startswith("_")
    }
    families = catalog.get("families", [])
    if not families:
        raise ValueError("At least one planned family is required")
    identifiers = set()
    extensions = set()
    for family in families:
        identifier = family["id"]
        if not re.fullmatch(r"[a-z][a-z_]*", identifier) or identifier in identifiers:
            raise ValueError(f"Invalid or duplicate family: {identifier}")
        identifiers.add(identifier)
        expected_dir = f"src/knoa_parse/parsers/{identifier}"
        if family["directory"] != expected_dir or not (ROOT / expected_dir / "README.md").is_file():
            raise ValueError(f"Missing or mismatched family directory: {identifier}")
        enabled = family.get("enabled_extensions", [])
        if len(enabled) != len(set(enabled)) or not set(enabled) <= set(family["initial_extensions"]):
            raise ValueError("Enabled extensions must be unique members of the family")
        if family["enabled"] != bool(enabled) or family["status"] != ("partially_implemented" if enabled else "planned"):
            raise ValueError("Family lifecycle must reflect accepted extensions only")
        if family["priority"] not in {"P0", "P1", "P2"}:
            raise ValueError(f"Invalid priority: {identifier}")
        if not family["initial_extensions"]:
            raise ValueError(f"No initial formats: {identifier}")
        for extension in family["initial_extensions"] + family["deferred_extensions"]:
            if not re.fullmatch(r"\.[a-z0-9]+(?:\.[a-z0-9]+)*", extension) or extension in extensions:
                raise ValueError(f"Invalid or duplicate extension ownership: {extension}")
            extensions.add(extension)
        if not set(family["optional_external_capabilities"]) <= set(capabilities):
            raise ValueError(f"Unknown external capability: {identifier}")
        if not set(family["processors"]) <= processor_dirs:
            raise ValueError(f"Unknown processor group: {identifier}")
    if identifiers != parser_dirs:
        raise ValueError("Every parser directory must have exactly one catalog entry")
    from knoa_parse.apps.runtime import ACCEPTED_EXTENSIONS

    accepted = {ext for f in families for ext in f["enabled_extensions"]}
    if accepted != ACCEPTED_EXTENSIONS:
        raise ValueError("Catalog and runtime capability declarations disagree")
    for parent, names in (("providers", provider_dirs), ("processors", processor_dirs)):
        for name in names:
            if not (ROOT / "src/knoa_parse" / parent / name / "README.md").is_file():
                raise ValueError(f"Missing module boundary documentation: {parent}/{name}")


def check_import_boundaries():
    source = ROOT / "src/knoa_parse"
    for path in source.rglob("*.py"):
        parts = path.relative_to(source).parts
        layer = parts[0]
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imports = [name.name for name in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    package = ["knoa_parse", *parts[:-1]]
                    prefix = package[:len(package) - node.level + 1]
                    imports = [".".join(prefix + node.module.split("."))] if node.module else [
                        ".".join(prefix + [alias.name]) for alias in node.names
                    ]
                else:
                    imports = [node.module or ""]
            else:
                continue
            for name in imports:
                if not name.startswith("knoa_parse."):
                    continue
                target = name.split(".")[1]
                if layer == "core" and target != "core":
                    raise ValueError(f"Core imports implementation: {path.name}: {name}")
                if layer == "parsers" and target not in {"core", "parsers"}:
                    raise ValueError(f"Parser bypasses core interfaces: {path.name}: {name}")
                if layer == "parsers" and target == "parsers" and name.split(".")[2] != parts[1]:
                    raise ValueError(f"Parser imports another family: {path.name}: {name}")
                if layer in {"processors", "providers", "engines", "enrichment"} and target not in {"core", layer}:
                    raise ValueError(f"Implementation imports another layer: {path.name}: {name}")


def main():
    failures = []
    paths = repository_files()
    for path in paths:
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if path.suffix not in {".md", ".json", ".yml", ".yaml", ".txt", ".py", ".toml"} and path.name not in {
            ".gitignore", ".gitattributes", ".editorconfig"
        }:
            continue
        try:
            raw = path.read_bytes()
            content = raw.decode("utf-8")
            if b"\r" in raw or (raw and not raw.endswith(b"\n")):
                failures.append(f"{relative}: require LF and final newline")
            if any(line.rstrip(" \t") != line for line in content.splitlines()):
                failures.append(f"{relative}: trailing whitespace")
            if path.suffix == ".json":
                json.loads(content)
            if path.suffix == ".toml":
                import tomllib

                tomllib.loads(content)
            if path.suffix in {".yaml", ".yml"}:
                yaml.load(content, Loader=yaml.BaseLoader)
            if path.suffix == ".md":
                prose = re.sub(r"\x60{3}.*?\x60{3}", "", content, flags=re.DOTALL)
                for target in re.findall(r"\[[^\]]*\]\(([^)\s]+)\)", prose):
                    parsed = urlsplit(target.strip("<>"))
                    if parsed.scheme or parsed.netloc or not parsed.path:
                        continue
                    destination = (path.parent / unquote(parsed.path)).resolve()
                    if not destination.is_relative_to(ROOT) or not destination.exists():
                        failures.append(f"{relative}: missing/outside-repo link {target}")
        except (ValueError, UnicodeError, yaml.YAMLError) as error:
            failures.append(f"{relative}: {error}")

    try:
        check_contract()
    except (ValueError, KeyError, OSError) as error:
        failures.append(f"Contract: {error}")
    try:
        catalog = json.loads((ROOT / "src/knoa_parse/parsers/catalog.json").read_text(encoding="utf-8"))
        validate_catalog(catalog)
        check_import_boundaries()
    except (ValueError, KeyError, TypeError, OSError) as error:
        failures.append(f"Catalog: {error}")
    if failures:
        raise SystemExit("\n".join(failures))
    print(f"PASS: {len(paths)} files; links, syntax, draft contracts, fixtures and format catalog")


if __name__ == "__main__":
    main()
