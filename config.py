import os
import re
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# Default matches the Bungie world content export in this project folder.
DEFAULT_MANIFEST_DB = PROJECT_ROOT / (
    "world_sql_content_4bc957fe614b9ca05b3a93fc27458ae4 - Copy.sqlite3"
)

# Watermark filename hash prefix (lowercase) -> season number.
# Keys may be truncated; lookup uses longest matching prefix.
WATERMARK_SEASON_PREFIXES = {
    # Full hashes from manifest / migration
    "31445f1891ce9eb464ed1dcf28f43613": 1,
    "b12630659223b53634e9f97c0a0a8305": 2,
    "2c024f088557ca6cceae1e8030c67169": 3,
    "e775dcb3d47e3d54e0e24fbdb64b5763": 4,
    "0337ec21962f67c7c493fedb447c4a9b": 5,
    "1b6c8b94cec61ea42edb1e2cb6b45a31": 6,
    "2352f9d04dc842cfcdda77636335ded9": 7,
    "fb50cd68a9850bd323872be4f6be115c": 8,
    "ed6c4762c48bd132d538ced83c1699a6": 9,
    "23968435c2095c0f8119d82ee222c672": 10,
    "a3923ae7d2376a1c4eb0f1f154da7565": 11,
    "448f071a7637fcefb2fccf76902dcf7d": 12,
    "5ac4a1d48a5221993a41a5bb524eda1b": 13,
    "af00bdcd3e3b89e6e85c1f63ebc0b4e4": 13,
    "a2fb48090c8bc0e5785975fab9596ab5": 14,
    "671a19eca92ad9dcf39d4e9c92fcdf75": 15,
    "ab075a3679d69f40b8c2a319635d60a9": 15,
    "1448dde4efdb57b07f5473f87c4fccd7": 16,
    "04de56db6d59127239ed51e82d16c06c": 16,
    "6e4fdb4800c34ccac313dd1598bd7589": 16,
    "5586f6a4193e34acc035209b5e9204d8": 17,
    "3543d23d9063fbf7332c7f129a74ada2": 18,
    "5364cc3900dc3615cb0c4b03c6221942": 18,
    "be3c0a95a8d1abc6e7c875d4294ba233": 19,
    "ad7fdb049d430c1fac1d20cf39059702": 19,
    "d92e077d544925c4f37e564158f8f76a": 19,
    "4c25426263cacf963777cd4988340838": 20,
    "6026e9d64e8c2b19f302dafb0286897b": 20,
    "e3ea0bd2e889b605614276876667759c": 20,
    "428c962c15612ea89693349d1b84531a": 21,
    "d5a3f4d7d20fefc781fea3c60bde9434": 22,
    "b973f89ecd631a3e3d294e98268f7134": 23,
    "efdb35540cd169fa6e334995c2ce87b6": 22,
    "f80e39c767f309f0b2be625dae0e3744": 24,
    "3de52d90db7ee2feb086ef6665b736b6": 25,
    "e8fe681196baf74917fa3e6f125349b0": 26,
    "52523b49e5965f6f33ab86710215c676": 27,
    # Truncated hashes (Bungie watermark filenames are often shortened on disk)
    "1f9f59c8cb44": 21,
    "0aa66ed6af2fe3519b7bd656e760b243": 22,
    "0d9992493b70af4a882bad79f60ead63": 23,
    "0e396ee456b82fd189ddecef1c7c9b41": 24,
    "5586fea4193e34acc835209": 17,
    "af00bdcd3e3b896e85c1f6": 17,
    "fb58cd68a9858bd323872be": 17,
    "5364cc3908dc3615cb0c4b0": 18,
    "e775dcb3d47e3d54ede24fb": 18,
    "f80e39c767f399f0b2be625": 18,
    "b973f89ecd631a3e3d294e9": 19,
    "525230d9e59656f633ab867": 19,
    "428c962c15612ea89693349": 20,
    "4c25426263cacf963777cd4": 20,
    "448f871a7637fcefb2fccf7": 21,
    "a3923ae7d2376a1c4eb0f1f": 21,
    "efdb35540cd169fa6e33499": 22,
    "ab075a3679d69f40b8c2a31": 22,
    "23968435c2095c0f81119d82": 23,
    "ed6c4762c48bd132d538ced": 23,
    "2352f9d04dc842cfcdda776": 24,
}


def get_manifest_db_path():
    """Path to the Destiny manifest SQLite DB (override with DESTINY_MANIFEST_DB)."""
    env_path = os.environ.get("DESTINY_MANIFEST_DB")
    if env_path:
        return str(Path(env_path).expanduser().resolve())
    return str(DEFAULT_MANIFEST_DB)


def manifest_db_exists():
    return Path(get_manifest_db_path()).is_file()


def watermark_hash_from_path(icon_watermark):
    if not icon_watermark:
        return None
    return icon_watermark.split("/")[-1].split(".")[0].lower()


def lookup_watermark_season_prefix(watermark_hash):
    """Match season by longest prefix hit on the watermark filename hash."""
    best_len = 0
    best_season = 0
    for prefix, season in WATERMARK_SEASON_PREFIXES.items():
        prefix = prefix.lower()
        if watermark_hash.startswith(prefix) and len(prefix) > best_len:
            best_len = len(prefix)
            best_season = season
    return best_season


def season_from_manifest_descriptions(manifest_db, watermark_hash):
    """Try to read 'Season N' from any manifest item sharing this watermark."""
    rows = manifest_db.execute(
        """
        SELECT json_extract(json, '$.displayProperties.description')
        FROM DestinyInventoryItemDefinition
        WHERE json_extract(json, '$.iconWatermark') LIKE ?
        """,
        (f"%{watermark_hash}%",),
    ).fetchall()
    for row in rows:
        description = row[0]
        if not description:
            continue
        match = re.search(r"Season (\d+)", description)
        if match:
            return int(match.group(1))
    return 0


def resolve_watermark_season(icon_watermark, manifest_db=None):
    """Resolve season number from weapon iconWatermark path."""
    watermark_hash = watermark_hash_from_path(icon_watermark)
    if not watermark_hash:
        return 0

    # Cache because watermark hashes repeat heavily across weapons,
    # and the fallback scan is expensive.
    global _watermark_season_cache
    if watermark_hash in _watermark_season_cache:
        return _watermark_season_cache[watermark_hash]

    season = lookup_watermark_season_prefix(watermark_hash)
    if season:
        _watermark_season_cache[watermark_hash] = season
        return season

    if manifest_db is not None:
        season = season_from_manifest_descriptions(manifest_db, watermark_hash)
        _watermark_season_cache[watermark_hash] = season
        return season

    _watermark_season_cache[watermark_hash] = 0
    return 0


_stat_name_cache = None

# watermark_hash (filename hash) -> resolved season number
_watermark_season_cache = {}


def get_stat_name_cache():
    """Load Destiny stat hash -> display name from manifest (cached)."""
    global _stat_name_cache
    if _stat_name_cache is not None:
        return _stat_name_cache

    _stat_name_cache = {}
    if not manifest_db_exists():
        return _stat_name_cache

    conn = sqlite3.connect(get_manifest_db_path())
    rows = conn.execute(
        """
        SELECT json_extract(json, '$.hash'),
               json_extract(json, '$.displayProperties.name')
        FROM DestinyStatDefinition
        """
    ).fetchall()
    conn.close()

    for stat_hash, name in rows:
        if stat_hash is None:
            continue
        key = str(int(stat_hash))
        if name:
            _stat_name_cache[key] = name

    return _stat_name_cache


def stat_display_name(stat_hash):
    """Human-readable stat label for a manifest stat hash."""
    key = str(stat_hash).replace("Stat_", "")
    return get_stat_name_cache().get(key, f"Stat {key}")
