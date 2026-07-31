"""Detect and persist Perfect Vault weapon flags.

Flags: is_tiered, is_adept, is_vendor6, is_craftable, is_obtainable.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from config import get_manifest_db_path, manifest_db_exists

PROJECT_ROOT = Path(__file__).resolve().parent
TIER_OVERLAY_PATH = PROJECT_ROOT / "tier_flags_overlay.json"
OBTAIN_OVERLAY_PATH = PROJECT_ROOT / "obtainability_overlay.json"

# Edge of Fate / Renegades-era release traits and seasons participate in gear tiers.
TIERED_SEASON_FLOOR = 27


def normalize_item_hash(hash_val):
    if hash_val is None:
        return None
    return int(hash_val) & 0xFFFFFFFF


def load_json_overlay(path: Path):
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    out = {}
    for key, value in (raw or {}).items():
        try:
            out[normalize_item_hash(key)] = value
        except (TypeError, ValueError):
            continue
    return out


def load_tier_overlay():
    """hash -> {is_tiered?, is_adept?, is_vendor6?}"""
    raw = load_json_overlay(TIER_OVERLAY_PATH)
    out = {}
    for item_hash, value in raw.items():
        out[item_hash] = value or {}
    return out


def load_obtainability_overlay():
    """hash -> bool (currently obtainable)."""
    raw = load_json_overlay(OBTAIN_OVERLAY_PATH)
    out = {}
    for item_hash, value in raw.items():
        if isinstance(value, dict):
            if "is_obtainable" in value:
                out[item_hash] = bool(value["is_obtainable"])
            elif "obtainable" in value:
                out[item_hash] = bool(value["obtainable"])
            else:
                out[item_hash] = bool(value)
        else:
            out[item_hash] = bool(value)
    return out


def detect_is_adept(name, manifest_is_adept=False):
    if manifest_is_adept:
        return True
    return "(Adept)" in (name or "")


def detect_is_tiered(season=0, trait_ids=None, is_holofoil=False):
    """Heuristic: EoF+ release traits, season >= 27, or holofoil presentation."""
    if is_holofoil:
        return True
    if (season or 0) >= TIERED_SEASON_FLOOR:
        return True
    for trait in trait_ids or ():
        if isinstance(trait, str) and trait.startswith("releases.v9"):
            return True
    return False


def detect_is_craftable(recipe_item_hash=None):
    return recipe_item_hash is not None


def ensure_flag_columns(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(weapons)")}
    for col in (
        "is_tiered",
        "is_adept",
        "is_vendor6",
        "is_craftable",
        "is_obtainable",
    ):
        if col not in cols:
            conn.execute(
                f"ALTER TABLE weapons ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0"
            )
    conn.commit()


def enrich_weapon_flags(weapon_db_path="weapon_perks.db"):
    """Backfill tier/adept/craftable/obtainable from manifest + overlays."""
    if not manifest_db_exists():
        raise FileNotFoundError(
            f"Manifest not found at {get_manifest_db_path()}"
        )

    tier_overlay = load_tier_overlay()
    obtain_overlay = load_obtainability_overlay()
    weapon_db = sqlite3.connect(weapon_db_path)
    ensure_flag_columns(weapon_db)
    weapon_db.row_factory = sqlite3.Row

    manifest = sqlite3.connect(get_manifest_db_path())
    manifest.row_factory = sqlite3.Row
    flag_by_hash = {}
    for row in manifest.execute(
        """
        SELECT json_extract(json, '$.hash') as hash,
               json_extract(json, '$.displayProperties.name') as name,
               json_extract(json, '$.isAdept') as is_adept,
               json_extract(json, '$.isHolofoil') as is_holofoil,
               json_extract(json, '$.traitIds') as trait_ids,
               json_extract(json, '$.inventory.recipeItemHash') as recipe_item_hash
        FROM DestinyInventoryItemDefinition
        WHERE json_extract(json, '$.itemType') = 3
        AND json_extract(json, '$.inventory.tierType') = 5
        """
    ):
        item_hash = normalize_item_hash(row["hash"])
        if item_hash is None:
            continue
        trait_ids = []
        if row["trait_ids"]:
            try:
                trait_ids = json.loads(row["trait_ids"])
            except json.JSONDecodeError:
                trait_ids = []
        flag_by_hash[item_hash] = {
            "name": row["name"] or "",
            "manifest_is_adept": bool(row["is_adept"]),
            "is_holofoil": bool(row["is_holofoil"]),
            "trait_ids": trait_ids,
            "recipe_item_hash": row["recipe_item_hash"],
        }
    manifest.close()

    updates = []
    for row in weapon_db.execute("SELECT hash, name, season FROM weapons"):
        item_hash = normalize_item_hash(row["hash"])
        meta = flag_by_hash.get(item_hash, {})
        name = row["name"] or meta.get("name") or ""
        is_adept = detect_is_adept(name, meta.get("manifest_is_adept", False))
        is_tiered = detect_is_tiered(
            season=row["season"] or 0,
            trait_ids=meta.get("trait_ids"),
            is_holofoil=meta.get("is_holofoil", False),
        )
        is_craftable = detect_is_craftable(meta.get("recipe_item_hash"))
        is_obtainable = bool(obtain_overlay.get(item_hash, False))
        is_vendor6 = False

        override = tier_overlay.get(item_hash) or {}
        if "is_adept" in override:
            is_adept = bool(override["is_adept"])
        if "is_tiered" in override:
            is_tiered = bool(override["is_tiered"])
        if "is_vendor6" in override:
            is_vendor6 = bool(override["is_vendor6"])
        if "is_craftable" in override:
            is_craftable = bool(override["is_craftable"])
        if "is_obtainable" in override:
            is_obtainable = bool(override["is_obtainable"])

        updates.append((
            1 if is_tiered else 0,
            1 if is_adept else 0,
            1 if is_vendor6 else 0,
            1 if is_craftable else 0,
            1 if is_obtainable else 0,
            row["hash"],
        ))

    weapon_db.executemany(
        """
        UPDATE weapons
        SET is_tiered = ?, is_adept = ?, is_vendor6 = ?,
            is_craftable = ?, is_obtainable = ?
        WHERE hash = ?
        """,
        updates,
    )
    weapon_db.commit()

    counts = weapon_db.execute(
        """
        SELECT
          SUM(CASE WHEN is_tiered = 1 OR is_adept = 1 OR is_vendor6 = 1
                   THEN 1 ELSE 0 END),
          SUM(is_tiered),
          SUM(is_adept),
          SUM(is_vendor6),
          SUM(is_craftable),
          SUM(is_obtainable),
          SUM(CASE WHEN is_craftable = 1 OR is_obtainable = 1 THEN 1 ELSE 0 END),
          COUNT(*)
        FROM weapons
        """
    ).fetchone()
    weapon_db.close()

    preferred, tiered, adept, vendor6, craftable, obtainable, eligible, total = counts
    print(
        f"Updated flags for {total} weapons "
        f"(preferred={preferred}, is_tiered={tiered}, is_adept={adept}, "
        f"vendor6={vendor6}, craftable={craftable}, obtainable={obtainable}, "
        f"eligible={eligible})"
    )
    return {
        "total": total,
        "preferred": preferred or 0,
        "is_tiered": tiered or 0,
        "is_adept": adept or 0,
        "is_vendor6": vendor6 or 0,
        "is_craftable": craftable or 0,
        "is_obtainable": obtainable or 0,
        "eligible": eligible or 0,
    }


if __name__ == "__main__":
    enrich_weapon_flags()
