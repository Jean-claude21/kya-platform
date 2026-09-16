"""Export Infisical metadata recursively without requesting secret values."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

from kya_platform.infrastructure.backup import sanitize_infisical_metadata


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def export_metadata(output: Path) -> None:
    base_url = _required("KYA_INFISICAL_API_URL").rstrip("/")
    client_id = _required("KYA_INFISICAL_CLIENT_ID")
    client_secret = _required("KYA_INFISICAL_CLIENT_SECRET")
    project_id = _required("KYA_INFISICAL_PROJECT_ID")
    environment = os.environ.get("KYA_INFISICAL_ENVIRONMENT", "staging")
    secret_path = os.environ.get("KYA_INFISICAL_SECRET_PATH", "/")
    organization_slug = os.environ.get("KYA_INFISICAL_ORGANIZATION_SLUG")
    login: dict[str, str] = {"clientId": client_id, "clientSecret": client_secret}
    if organization_slug:
        login["organizationSlug"] = organization_slug

    with httpx.Client(timeout=30) as client:
        session = client.post(f"{base_url}/api/v1/auth/universal-auth/login", json=login)
        session.raise_for_status()
        token = session.json()["accessToken"]
        response = client.get(
            f"{base_url}/api/v4/secrets",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "projectId": project_id,
                "environment": environment,
                "secretPath": secret_path,
                "viewSecretValue": "false",
                "expandSecretReferences": "false",
                "recursive": "true",
                "includePersonalOverrides": "false",
            },
        )
        response.raise_for_status()
    metadata = sanitize_infisical_metadata(response.json())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(metadata, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args(argv)
    export_metadata(arguments.output)
    print(json.dumps({"output": str(arguments.output), "contains_secret_values": False}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
