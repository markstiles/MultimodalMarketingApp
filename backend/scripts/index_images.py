#!/usr/bin/env python
"""Standalone script to crawl and index images from the Sitecore media library.

Embeds images with Cohere multimodal embeddings and stores vectors in pgvector
so the chat assistant can search them with search_site_images.

Usage:
    python -m scripts.index_images --site-id <SITE_ID> [options]

Examples:
    # Index up to 50 images from the full media library
    python -m scripts.index_images --site-id my-site-id --batch-limit 50

    # Index a specific media folder
    python -m scripts.index_images --site-id my-site-id --folder "/sitecore/media library/Project/acme-corp"

    # Full crawl (no batch limit)
    python -m scripts.index_images --site-id my-site-id --no-limit

    # Dry run: show how many images exist without indexing
    python -m scripts.index_images --site-id my-site-id --dry-run

Required environment variables:
    DATABASE_URL                    PostgreSQL connection string
    COHERE_API_KEY                  Cohere API key for embeddings
    SITECORE_CM_HOST                Sitecore CM host (e.g. https://xmcloud.example.com)
    AUTHOR_APP_ID                   Sitecore automation app client ID
    AUTHOR_APP_CLIENT_CREDENTIALS   Sitecore automation app client secret

Note: Run the database migration first:
    python -m alembic -c backend/alembic.ini upgrade head   (from project root)
"""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

_here = Path(__file__).resolve().parent.parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

from dotenv import load_dotenv
load_dotenv()


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Crawl and index Sitecore media library images for semantic search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--site-id",
        required=True,
        metavar="ID",
        help="Sitecore site ID (from HEADLESS_SITE_ID or the XM Cloud dashboard)",
    )
    p.add_argument(
        "--folder",
        default=None,
        metavar="PATH",
        help=(
            "Sitecore media library path to scope the crawl "
            "(default: full /sitecore/media library)"
        ),
    )
    p.add_argument(
        "--environment",
        default="master",
        choices=["master", "web"],
        help="Sitecore environment to tag embeddings against (default: master)",
    )
    p.add_argument(
        "--batch-limit",
        type=int,
        default=100,
        metavar="N",
        help="Max images to process per run (default: 100). Use --no-limit for full crawl.",
    )
    p.add_argument(
        "--no-limit",
        action="store_true",
        help="Remove the batch limit — index all images found (may take several minutes)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Query the media library count without embedding or storing anything",
    )
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO)",
    )
    return p


async def _dry_run(folder: str, auth_token: str) -> None:
    """Count image items under the folder via SSC REST without indexing."""
    import os
    import urllib.parse
    import httpx

    cm_host = os.environ.get("SITECORE_CM_HOST", "").rstrip("/")
    if not cm_host:
        print("ERROR: SITECORE_CM_HOST is not set", file=sys.stderr)
        sys.exit(1)

    ssc_base = f"{cm_host}/sitecore/api/ssc/item"
    headers = {"Authorization": f"Bearer {auth_token}"}
    _IMAGE_TEMPLATES = {
        # Versioned
        "F6F72B6B-F5D5-4ED0-8701-45266461F77B",  # webp
        "EB3FB96C-D56B-4AC9-97F8-F07B24BB9BF7",  # jpeg
        "C97BA923-8009-4858-BDD5-D8BE5FCCECF7",  # image
        # Unversioned
        "309EB383-99B6-4722-9FAB-58D8AE802D72",  # webp
        "DAF085E8-602E-43A6-8299-038FF171349F",  # jpeg
        "F1828A2C-7E5D-4BBD-98CA-320474871548",  # image
    }

    async with httpx.AsyncClient(timeout=20) as http:
        # Resolve the folder to an item ID
        url = f"{ssc_base}/?path={urllib.parse.quote(folder)}&database=master"
        r = await http.get(url, headers=headers)
        if r.status_code == 404:
            print(f"Folder not found: {folder!r}", file=sys.stderr)
            return
        r.raise_for_status()
        root_id = r.json().get("ItemID")
        if not root_id:
            print("Could not resolve folder item ID", file=sys.stderr)
            return

        # BFS count — don't embed, just count
        image_count = 0
        folder_count = 0
        queue = [root_id]
        while queue:
            fid = queue.pop(0)
            skip = 0
            while True:
                children_url = f"{ssc_base}/{fid}/children?database=master&skip={skip}&take=50"
                cr = await http.get(children_url, headers=headers)
                if cr.status_code != 200:
                    break
                children = cr.json() if isinstance(cr.json(), list) else []
                for child in children:
                    tid = child.get("TemplateID", "").upper()
                    tname = child.get("TemplateName", "").lower()
                    if tid in _IMAGE_TEMPLATES or tname == "image":
                        image_count += 1
                    else:
                        folder_count += 1
                        queue.append(child["ItemID"])
                if len(children) < 50:
                    break
                skip += 50

    print(f"Dry run — found {image_count} images under {folder!r}")
    print(f"  ({folder_count} non-image items traversed)")
    print("Run without --dry-run to index them.")


async def _run(args: argparse.Namespace) -> int:
    from app.resources.database import _get_session_factory
    from app.services.image_search_service import crawl_and_index_media_library
    from app.services.sites_service import get_site_info
    from app.services.sitecore_auth import get_sitecore_automation_token

    print(f"Authenticating with Sitecore...")
    try:
        auth_token = await get_sitecore_automation_token()
    except Exception as exc:
        print(f"ERROR: Auth failed — {exc}", file=sys.stderr)
        print("Check AUTHOR_APP_ID and AUTHOR_APP_CLIENT_CREDENTIALS are set.", file=sys.stderr)
        return 1

    print(f"Resolving site {args.site_id!r}...")
    site_info = await get_site_info(args.site_id, auth_token)
    if not site_info.get("success"):
        print(f"ERROR: {site_info.get('error', 'Could not resolve site')}", file=sys.stderr)
        return 1
    collection = site_info["collection"]
    site_name = site_info.get("name", "")
    print(f"Site collection: {collection!r}")

    # Resolve the folder to crawl — explicit arg wins; otherwise scope to the site's
    # media folder so we don't crawl unrelated projects' images.
    folder = args.folder
    if not folder and collection and site_name:
        folder = f"/sitecore/media library/Project/{collection}/{site_name}"
        print(f"Defaulting to site media folder: {folder!r}")

    if args.dry_run:
        await _dry_run(folder or "/sitecore/media library", auth_token)
        return 0

    batch_limit = 999_999 if args.no_limit else args.batch_limit
    print(
        f"Crawling {'all' if args.no_limit else f'up to {batch_limit}'} images "
        f"from {folder or '/sitecore/media library'!r} ..."
    )

    async with _get_session_factory()() as db:
        result = await crawl_and_index_media_library(
            site_id=args.site_id,
            collection=collection,
            environment=args.environment,
            folder_path=folder,
            auth_token=auth_token,
            db=db,
            batch_limit=batch_limit,
            site_name=site_name,
        )

    print(json.dumps(result, indent=2))

    if result["success"]:
        print(
            f"\nIndexed {result['indexed_count']} images "
            f"({result['failed_count']} failed, "
            f"{result['total_found']} found total)"
        )
        if result.get("batch_limited"):
            print(f"Batch limit reached — run again to continue (upsert is safe to re-run).")
        return 0
    else:
        print(f"\nERROR: {result.get('error')}", file=sys.stderr)
        return 1


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s  %(message)s",
    )
    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
