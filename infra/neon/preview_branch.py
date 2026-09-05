"""Create or clean up a Neon branch for one pull request."""

import argparse
import asyncio
import os

import httpx
from pydantic import SecretStr

from kya_platform.infrastructure.neon import NeonPreviewBranchAdapter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("ensure", "cleanup"))
    parser.add_argument("--pull-request", required=True, type=int)
    parser.add_argument("--commit", default="unknown")
    return parser.parse_args()


async def run() -> None:
    args = parse_args()
    project_id = os.environ["NEON_PROJECT_ID"]
    api_key = SecretStr(os.environ["NEON_API_KEY"])
    async with httpx.AsyncClient(timeout=30.0) as client:
        adapter = NeonPreviewBranchAdapter(client, project_id, api_key)
        if args.action == "ensure":
            branch = await adapter.ensure_preview(args.pull_request, args.commit)
            print(f"branch_id={branch.id}")
            print(f"branch_name={branch.name}")
            return
        deleted = await adapter.cleanup_preview(args.pull_request)
        print(f"deleted={str(deleted).lower()}")


if __name__ == "__main__":
    asyncio.run(run())
