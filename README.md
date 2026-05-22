# aws-resource-catalog

A machine-readable catalog of billable AWS resource types, their lifecycle, and orphan-detection rules.

This repo answers two questions that AWS does not document in one place:

1. **What is this billing line item really?** (e.g. `USE1-EMRWAL-WALHours` → Amazon EMR WAL workspace storage)
2. **When does this resource become an orphan that keeps charging after its parent is gone?**

It is the knowledge source for downstream tools (idle-detector, MCP servers, FinOps reports, AI agents).

## Layout

```
aws-resource-catalog/
├── schemas/                 # JSON Schemas (resource.v1.json)
├── catalog/                 # auto-pulled (refresh_catalog.py)
│   ├── pricing_offers_index.json
│   ├── boto3_services.json
│   └── cfn_resource_types.json
├── knowledge/               # human-curated resource definitions (yaml)
│   ├── ec2/
│   ├── emr/
│   ├── vpc/
│   └── ...
├── aws_resource_catalog/    # Python loader package
│   └── __init__.py
├── scripts/
│   └── refresh_catalog.py
└── tests/
    └── test_yaml_valid.py
```

## Quick start

```bash
pip install pyyaml jsonschema

python -c "
from aws_resource_catalog import Catalog
cat = Catalog.load('knowledge/')
for r in cat.filter(orphan_prone=True, severity='high'):
    print(r.id, '-', r.resource_type['human_name'])
print(cat.stats())
"
```

## Schema (v1)

Each resource is a single yaml file under `knowledge/<service>/<name>.yaml`. See `schemas/resource.v1.json` for the full schema. Required fields:

- `service` — short service name
- `resource_type.name` / `resource_type.human_name`
- `billing.billable` / `billing.model` / `billing.summary`
- `lifecycle.parent_resource` / `lifecycle.auto_delete_on_parent_delete`

Optional but recommended:

- `orphan_detection.*` — judgment rule + cleanup command + IAM
- `verification.last_verified` + `contributor`
- `tags` — free-form labels

## Adding a new resource type

```bash
# 1. Find the right service folder
mkdir -p knowledge/<service>
# 2. Copy an existing yaml as a starting point
cp knowledge/vpc/elastic_ip.yaml knowledge/<service>/<name>.yaml
# 3. Fill in fields (always cite an official AWS doc anchor)
# 4. Validate
pip install pytest
pytest tests/test_yaml_valid.py
```

## Refreshing the auto-pulled catalog

```bash
python scripts/refresh_catalog.py
git add catalog/
git commit -m "refresh catalog YYYY-MM-DD"
```

## Consumers

This repo is meant to be consumed as a git submodule or pip install:

```bash
# As submodule (pinned commit)
git submodule add https://github.com/CrypticDriver/aws-resource-catalog shared/catalog

# Or as pip package (when published)
pip install aws-resource-catalog
```

Then in code:

```python
from aws_resource_catalog import Catalog
cat = Catalog.load_default()  # finds knowledge/ next to package
```

## License

MIT.
