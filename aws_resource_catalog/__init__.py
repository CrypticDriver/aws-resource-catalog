"""aws_resource_catalog — load + query resource yaml definitions.

Usage:
    from aws_resource_catalog import Catalog

    cat = Catalog.load_default()  # finds knowledge/ next to package
    eip = cat.get("ec2/elastic_ip")
    for r in cat.filter(orphan_prone=True, severity="high"):
        print(r.service, r.resource_type["human_name"])
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml  # PyYAML
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "aws_resource_catalog requires PyYAML. Install with `pip install pyyaml`."
    ) from e


@dataclass
class Resource:
    """One catalog entry."""

    raw: dict[str, Any]
    path: Path

    @property
    def id(self) -> str:
        return f"{self.service}/{self.raw['resource_type']['name']}"

    @property
    def service(self) -> str:
        return self.raw["service"]

    @property
    def resource_type(self) -> dict[str, Any]:
        return self.raw["resource_type"]

    @property
    def billing(self) -> dict[str, Any]:
        return self.raw.get("billing") or {}

    @property
    def lifecycle(self) -> dict[str, Any]:
        return self.raw.get("lifecycle") or {}

    @property
    def orphan(self) -> dict[str, Any]:
        return self.raw.get("orphan_detection") or {}

    @property
    def tags(self) -> list[str]:
        return list(self.raw.get("tags") or [])

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    def to_json(self) -> str:
        return json.dumps(self.raw, indent=2, ensure_ascii=False)

    def __repr__(self) -> str:
        return f"<Resource id={self.id} severity={self.orphan.get('severity')}>"


@dataclass
class Catalog:
    """Loaded resource catalog. Indexed by id (`service/name`)."""

    knowledge_dir: Path
    resources: dict[str, Resource] = field(default_factory=dict)

    # ---------------- loaders ----------------
    @classmethod
    def load(cls, knowledge_dir: str | Path) -> "Catalog":
        kd = Path(knowledge_dir).resolve()
        if not kd.exists():
            raise FileNotFoundError(f"knowledge dir not found: {kd}")
        cat = cls(knowledge_dir=kd)
        for yaml_path in sorted(kd.rglob("*.yaml")):
            try:
                raw = yaml.safe_load(yaml_path.read_text())
            except yaml.YAMLError as e:
                raise RuntimeError(f"YAML parse failed: {yaml_path}: {e}") from e
            if not raw or "resource_type" not in raw:
                continue
            res = Resource(raw=raw, path=yaml_path)
            cat.resources[res.id] = res
        return cat

    @classmethod
    def load_default(cls) -> "Catalog":
        """Find knowledge/ relative to this package (sibling directory)."""
        # Try git root first (when used as submodule).
        here = Path(__file__).resolve()
        for parent in [here.parent, *here.parents]:
            cand = parent / "knowledge"
            if cand.is_dir():
                return cls.load(cand)
        raise FileNotFoundError(
            "no knowledge/ directory found relative to package; "
            "pass knowledge_dir explicitly."
        )

    # ---------------- queries ----------------
    def get(self, resource_id: str) -> Resource:
        return self.resources[resource_id]

    def __contains__(self, resource_id: str) -> bool:
        return resource_id in self.resources

    def __iter__(self) -> Iterable[Resource]:
        return iter(self.resources.values())

    def __len__(self) -> int:
        return len(self.resources)

    def filter(
        self,
        *,
        service: str | None = None,
        orphan_prone: bool | None = None,
        severity: str | None = None,
        tag: str | None = None,
        billable: bool | None = None,
    ) -> list[Resource]:
        out = []
        for r in self.resources.values():
            if service is not None and r.service != service:
                continue
            if orphan_prone is not None and r.orphan.get("orphan_prone") != orphan_prone:
                continue
            if severity is not None and r.orphan.get("severity") != severity:
                continue
            if tag is not None and tag not in r.tags:
                continue
            if billable is not None and r.billing.get("billable") != billable:
                continue
            out.append(r)
        return out

    def services(self) -> list[str]:
        return sorted({r.service for r in self.resources.values()})

    def stats(self) -> dict[str, Any]:
        """High-level counts for sanity checks."""
        total = len(self.resources)
        return {
            "total": total,
            "services": len(self.services()),
            "orphan_prone": len(self.filter(orphan_prone=True)),
            "by_severity": {
                sev: len(self.filter(severity=sev))
                for sev in ("high", "medium", "low")
            },
        }


__all__ = ["Catalog", "Resource"]
__version__ = "0.1.0"
