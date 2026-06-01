import argparse
import io
import json
import os
import shutil
import time
import zipfile
from pathlib import Path

import urllib.request

from config import DEFAULT_MANIFEST_DB, get_manifest_db_path, manifest_db_exists


MANIFEST_ENDPOINT = "https://www.bungie.net/Platform/Destiny2/Manifest/"


def fetch_latest_manifest_json():
    with urllib.request.urlopen(MANIFEST_ENDPOINT) as resp:
        return json.load(resp)


def get_world_sql_content_url(manifest_json, lang: str):
    resp = manifest_json["Response"]
    paths = resp["mobileWorldContentPaths"]
    rel_path = paths[lang]
    return "https://www.bungie.net" + rel_path


def download_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "perk-calc/1.0"})
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def extract_sqlite3_from_content_bytes(content_bytes: bytes) -> bytes:
    # world_sql_content_*.content is a zip archive containing the sqlite db.
    with zipfile.ZipFile(io.BytesIO(content_bytes)) as zf:
        # Prefer a file that looks like sqlite.
        # In practice the archive contains a single .content file which is the sqlite db.
        candidates = zf.namelist()
        if not candidates:
            raise RuntimeError("Downloaded content archive was empty.")

        # Take first entry if we can't find an exact match.
        for name in candidates:
            if name.endswith(".content") or name.endswith(".sqlite3") or "world_sql_content" in name:
                with zf.open(name) as f:
                    return f.read()

        with zf.open(candidates[0]) as f:
            return f.read()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", default="en", help="Manifest language key (default: en)")
    parser.add_argument(
        "--overwrite-default",
        action="store_true",
        help="Overwrite config default manifest DB, backing it up first.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write extracted sqlite3 to this path instead of default manifest.",
    )
    args = parser.parse_args()

    manifest_json = fetch_latest_manifest_json()
    if manifest_json.get("ErrorCode") != 1:
        print("Manifest response indicates an error, continuing anyway...")

    world_url = get_world_sql_content_url(manifest_json, args.lang)
    print("Latest world_sql_content URL:")
    print(world_url)

    content_bytes = download_bytes(world_url)
    print(f"Downloaded content archive: {len(content_bytes)/1024/1024:.1f} MB")

    sqlite_bytes = extract_sqlite3_from_content_bytes(content_bytes)
    print(f"Extracted sqlite db bytes: {len(sqlite_bytes)/1024/1024:.1f} MB")

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = Path(str(DEFAULT_MANIFEST_DB))

    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.overwrite_default and out_path.exists():
        ts = int(time.time())
        backup_path = out_path.with_suffix(out_path.suffix + f".bak.{ts}")
        print(f"Backing up existing manifest: {out_path} -> {backup_path}")
        shutil.move(str(out_path), str(backup_path))

    print(f"Writing manifest sqlite3 to: {out_path}")
    with open(out_path, "wb") as f:
        f.write(sqlite_bytes)

    print("Done.")
    print(f"App will use: {get_manifest_db_path()}")
    if not manifest_db_exists():
        print("WARNING: manifest_db_exists() returned False after download.")


if __name__ == "__main__":
    main()

