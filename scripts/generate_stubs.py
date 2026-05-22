#!/usr/bin/env python3
"""Generate stub yaml entries for every AWS::*::* CloudFormation resource type.

Strategy:
  - Parse catalog/cfn_resource_types.json (1500+ types).
  - For each type, emit a minimal yaml under knowledge/<service>/<resource>.yaml
    with status="stub".
  - DO NOT overwrite any file that is missing the "status: stub" marker
    (i.e. preserve human-curated entries).
  - Fill in best-guess ARN pattern from CFN doc URL when possible.

Goal: 100% coverage with sensible scaffolding. Human authors then
upgrade individual stubs to "verified" by editing the file and removing
the status field (or setting status="verified").
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFN_INDEX = ROOT / "catalog" / "cfn_resource_types.json"
KNOWLEDGE = ROOT / "knowledge"

# Subset of CFN types that aren't billable in any meaningful way.
# We still scaffold them; downstream consumers can ignore via tag=infrastructure_only.
NON_BILLABLE_HINTS = {
    "AWS::IAM::",        # IAM roles/policies/users - mostly free
    "AWS::CloudFormation::",
    "AWS::Events::",     # EventBridge rules - free
    "AWS::SSM::Parameter",
    "AWS::SecretsManager::ResourcePolicy",
}


def slug(s: str) -> str:
    """Lowercase + replace non-alnum with '_'."""
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def build_stub(cfn_type: str, doc_url: str | None) -> dict:
    """Construct a minimal but schema-valid yaml dict."""
    # AWS::EMR::Cluster -> ['AWS', 'EMR', 'Cluster']
    parts = cfn_type.split("::")
    service_raw = parts[1] if len(parts) >= 2 else "Unknown"
    resource_raw = "::".join(parts[2:]) if len(parts) >= 3 else "Unknown"

    service = slug(service_raw)
    resource_name = slug(resource_raw)

    is_likely_non_billable = any(cfn_type.startswith(p) for p in NON_BILLABLE_HINTS)

    return {
        "schema_version": "v1",
        "status": "stub",
        "service": service,
        "service_code_arn_namespace": service.replace("_", ""),
        "resource_type": {
            "name": resource_name,
            "human_name": cfn_type,
            "cfn": cfn_type,
            "config": cfn_type,  # most CFN types are also Config types; verify per-resource later
            "resource_explorer": cfn_type,
        },
        "billing": {
            "billable": not is_likely_non_billable,
            "model": "complex" if not is_likely_non_billable else "free",
            "summary": "TODO — verify pricing model and CUR usage type from official docs.",
            "free_tier": False,
        },
        "lifecycle": {
            "parent_resource": None,
            "auto_delete_on_parent_delete": False,
        },
        "orphan_detection": {
            "orphan_prone": False,  # default false; promote when verified
        },
        "tags": ["stub"] + (["infrastructure_only"] if is_likely_non_billable else []),
        "verification": {
            "last_verified": "",
            "source_doc_version": "",
            "contributor": "auto-generated",
            "doc_url": doc_url or "",
        },
    }


def write_yaml(path: Path, data: dict) -> bool:
    """Write yaml; skip if file exists and is already curated.

    A file is 'curated' if it does NOT have ``status: stub`` at the top.
    Returns True if written, False if skipped.
    """
    if path.exists():
        try:
            head = path.read_text().splitlines()
            curated = not any(
                line.strip().startswith("status:") and line.strip().endswith("stub")
                for line in head[:10]
            )
            if curated:
                return False
        except Exception:
            pass

    path.parent.mkdir(parents=True, exist_ok=True)
    # Manual yaml dump to keep deterministic key order.
    lines = [
        f'schema_version: {data["schema_version"]}',
        f'status: {data["status"]}',
        f'service: {data["service"]}',
        f'service_code_arn_namespace: {data["service_code_arn_namespace"]}',
        "",
        "resource_type:",
        f'  name: {data["resource_type"]["name"]}',
        f'  human_name: {data["resource_type"]["human_name"]}',
        f'  cfn: {data["resource_type"]["cfn"]}',
        f'  config: {data["resource_type"]["config"]}',
        f'  resource_explorer: {data["resource_type"]["resource_explorer"]}',
        "",
        "billing:",
        f'  billable: {str(data["billing"]["billable"]).lower()}',
        f'  model: {data["billing"]["model"]}',
        f'  summary: |',
        f'    {data["billing"]["summary"]}',
        f'  free_tier: false',
        "",
        "lifecycle:",
        "  parent_resource: null",
        "  auto_delete_on_parent_delete: false",
        "",
        "orphan_detection:",
        f'  orphan_prone: {str(data["orphan_detection"]["orphan_prone"]).lower()}',
        "",
        f'tags: [{", ".join(data["tags"])}]',
        "",
        "verification:",
        f'  contributor: auto-generated',
    ]
    if data["verification"].get("doc_url"):
        lines.append(f'  doc_url: {data["verification"]["doc_url"]}')
    path.write_text("\n".join(lines) + "\n")
    return True


def main():
    cfn = json.loads(CFN_INDEX.read_text())
    resources = cfn.get("resources") or []

    written = 0
    skipped_curated = 0
    for entry in resources:
        cfn_type = entry["type"]
        doc_url = entry.get("documentation")

        parts = cfn_type.split("::")
        if len(parts) < 3:
            continue
        service_dir = slug(parts[1])
        resource_name = slug("::".join(parts[2:]))

        target = KNOWLEDGE / service_dir / f"{resource_name}.yaml"
        stub = build_stub(cfn_type, doc_url)

        if write_yaml(target, stub):
            written += 1
        else:
            skipped_curated += 1

    total = written + skipped_curated
    print(f"CFN types scanned:   {len(resources)}")
    print(f"  stub yaml written: {written}")
    print(f"  curated preserved: {skipped_curated}")
    print(f"  total in repo:     {total}")


if __name__ == "__main__":
    main()
