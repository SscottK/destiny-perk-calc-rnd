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
    # Post-Edge-of-Fate / Renegades manifest watermark hashes (bridged from
    # older manifest via shared weapon hashes, plus collectible-source checks).
    "a0556509f8825756b6b89f59f90528ec": 1,
    "247715dd42abef457b52ef37280c0e42": 2,
    "7ba9d804508dd083ec20fcdb8ba0869d": 3,
    "41d05b7cb5cc0a384af07ee9b7d36dd2": 4,
    "9bfaa5536772e2f3ef1252813a21c4d1": 5,
    "aeb95eb1abe8e45e1fe2573d6b3ab3c5": 6,
    "a15754752f40aaf7b1b00aadb70a8f35": 7,
    "4f28dc0f39238fe25d298a894ea71389": 8,
    "da5f961ef97b78293cc498978c10e178": 9,
    "ede19a0e1a54564243b0e5e8a18bde84": 9,   # Sundial / Dawn-era
    # 36418dde751148bd3b95a023d491ea73 intentionally omitted — shared VoG/playlist mark
    "7d815c943977fe71bbf00caf1bd9c514": 11,
    "e0c16042274fd7d9cbffc4489e340c5d": 12,
    "bce51cf90464e28026140df77c4eb6ce": 12,  # DSC / Europa / Beyond Light
    "7b48b09fbb50634680168d5880b16bc9": 13,
    "fc02418ad2002351a3f88faa5b14eb88": 13,
    "6f17d323d81dd683086d88a9268f8106": 14,
    "75adde12e4e9c9fb237e492d8258eb73": 15,
    "bcc26708e314306fb2fc8cb98fcbf47e": 15,
    "2c022e452f395db7b1daec1cb44631fc": 16,
    "7b41678824a620d4f295984862702179": 16,
    "fe8bcc20fbfaf4cac69dfb640bb0b84e": 16,
    "5232219633cc4d90570bffda36caccf4": 17,
    "0d6c3365022ed3b059eac467b076978f": 18,
    "58d3ec8338cc9746a2e0cf901fbcec0e": 18,
    "914322d11262322c839a5388db2a4943": 19,
    "83fbcacd223402c09af4b7ab067f8cce": 19,
    "a5e27dc822aa72787f388bd1fc115803": 19,
    "ae5c7f708a36f754c2f68c65c88ab9aa": 20,
    "661c84a377389a3b8a1fc38b44189b41": 24,  # Final Shape / Pale Heart / SE
    "d105aa342f2d0c53a90a28477552f61f": 12,  # Beyond Light year world drops
    "0ac354c1c326441716ddb15d2c158c59": 21,
    "60d34bc853c51063b79592233c3661d4": 22,
    "9c091ec0e22c01dacc25efb63b46eb9b": 22,
    "0b441021fbc328e6d0e2abc895f5c96e": 23,
    "53dc0b02306726ff1517af33ac908cef": 24,
    "2dc17f123b7449b14144e76cfbeb2309": 25,
    "0b212b58a961f150708bca95095e0ecb": 26,
    "50c3ebe414c6946429934d79504922fa": 27,
    "249813e647271a8227bae0d8a39ed505": 27,  # Edge of Fate activities
    "6129365b4fad6754f2b8c4478fc3c4ac": 27,  # Kepler / Desert Perpetual
    "95f7754d52d6016fdc445fb62aa7a31e": 28,  # Renegades / Equilibrium
    "6eeb62a30439cecc7699c22f3e1fb3cf": 28,  # Renegades-era companion marks
    # Intentionally unmapped (not a single season):
    # e78fd9419f99464816ac8f628bc3c4af — generic/shared mark across many eras
    # 4376a7d734583ae347acf9732aa3bb43 — Trials/events activity mark
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
    if not watermark_hash:
        return 0
    best_len = 0
    best_season = 0
    for prefix, season in WATERMARK_SEASON_PREFIXES.items():
        prefix = prefix.lower()
        if watermark_hash.startswith(prefix) and len(prefix) > best_len:
            best_len = len(prefix)
            best_season = season
    return best_season


def clear_watermark_season_cache():
    """Clear resolver cache (call after updating watermark maps)."""
    global _watermark_season_cache
    _watermark_season_cache = {}


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
