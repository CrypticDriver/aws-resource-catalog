"""Validate every yaml under knowledge/ against schemas/resource.v1.json."""
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schemas" / "resource.v1.json").read_text())
VALIDATOR = Draft7Validator(SCHEMA)
KNOWLEDGE = ROOT / "knowledge"


def yaml_files():
    return sorted(KNOWLEDGE.rglob("*.yaml"))


@pytest.mark.parametrize("path", yaml_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_yaml_valid(path: Path):
    data = yaml.safe_load(path.read_text())
    errors = sorted(VALIDATOR.iter_errors(data), key=lambda e: e.path)
    assert not errors, "\n".join(f"{list(e.path)}: {e.message}" for e in errors)


def test_resource_id_unique():
    seen = set()
    for path in yaml_files():
        data = yaml.safe_load(path.read_text())
        if not data or "resource_type" not in data:
            continue
        rid = f"{data['service']}/{data['resource_type']['name']}"
        assert rid not in seen, f"duplicate id {rid} in {path}"
        seen.add(rid)


def test_loader_works():
    """Smoke test the Python API."""
    import sys
    sys.path.insert(0, str(ROOT))
    from aws_resource_catalog import Catalog
    cat = Catalog.load(KNOWLEDGE)
    assert len(cat) >= 5
    stats = cat.stats()
    assert stats["orphan_prone"] >= 5
