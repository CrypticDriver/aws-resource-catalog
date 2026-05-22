#!/usr/bin/env python3
"""Pull AWS service / pricing / boto3 metadata into catalog/.

Sources:
  1. AWS Pricing API service codes (offers index).
  2. boto3 service models (client list + endpoint metadata).
  3. CloudFormation resource specification (resource types per region).

Run weekly. Output is committed so consumers can use without AWS creds.
"""
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog"
CATALOG.mkdir(parents=True, exist_ok=True)

PRICING_INDEX = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/index.json"
CFN_SPEC = "https://d1uauaxba7bl26.cloudfront.net/latest/CloudFormationResourceSpecification.json"


def fetch(url):
    print(f"  fetching {url}")
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read())


def pull_pricing_index():
    print("[1/3] AWS Pricing offers index")
    data = fetch(PRICING_INDEX)
    out = CATALOG / "pricing_offers_index.json"
    services = []
    for code, entry in (data.get("offers") or {}).items():
        services.append({
            "service_code": code,
            "name": entry.get("offerCode"),
            "version": entry.get("versionIndexUrl", "").split("/")[-1] if entry.get("versionIndexUrl") else None,
            "current_offer_url": entry.get("currentVersionUrl"),
            "current_region_index": entry.get("currentRegionIndexUrl"),
        })
    services.sort(key=lambda s: s["service_code"])
    out.write_text(json.dumps({
        "publication_date": data.get("publicationDate"),
        "format_version": data.get("formatVersion"),
        "service_count": len(services),
        "services": services,
    }, indent=2))
    print(f"  -> {out} ({len(services)} services)")


def pull_boto3_services():
    print("[2/3] boto3 service catalog")
    try:
        import boto3
        import botocore
    except ImportError:
        print("  ! boto3 not installed, skip")
        return

    session = boto3.Session()
    services = []
    for name in sorted(session.get_available_services()):
        try:
            model = session._loader.load_service_model(name, "service-2")
            metadata = model.get("metadata", {})
            services.append({
                "service": name,
                "endpoint_prefix": metadata.get("endpointPrefix"),
                "service_id": metadata.get("serviceId"),
                "api_version": metadata.get("apiVersion"),
                "protocol": metadata.get("protocol"),
                "signing_name": metadata.get("signingName"),
                "operation_count": len(model.get("operations") or {}),
            })
        except Exception as e:
            services.append({"service": name, "error": str(e)})
    out = CATALOG / "boto3_services.json"
    out.write_text(json.dumps({
        "boto3_version": boto3.__version__,
        "botocore_version": botocore.__version__,
        "service_count": len(services),
        "services": services,
    }, indent=2))
    print(f"  -> {out} ({len(services)} services)")


def pull_cfn_spec():
    print("[3/3] CloudFormation resource specification")
    data = fetch(CFN_SPEC)
    resources = []
    for type_name, body in (data.get("ResourceTypes") or {}).items():
        resources.append({
            "type": type_name,
            "documentation": body.get("Documentation"),
            "property_count": len(body.get("Properties") or {}),
        })
    resources.sort(key=lambda r: r["type"])
    out = CATALOG / "cfn_resource_types.json"
    out.write_text(json.dumps({
        "resource_specification_version": data.get("ResourceSpecificationVersion"),
        "resource_count": len(resources),
        "resources": resources,
    }, indent=2))
    print(f"  -> {out} ({len(resources)} types)")


if __name__ == "__main__":
    pull_pricing_index()
    pull_boto3_services()
    pull_cfn_spec()
    print("done")
