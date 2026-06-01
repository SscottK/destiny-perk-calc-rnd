"""Recompute weapon season values from manifest watermarks (fast; no full migration)."""

import sqlite3
from pathlib import Path
import re

from config import (
    DEFAULT_MANIFEST_DB,
    get_manifest_db_path,
    manifest_db_exists,
    lookup_watermark_season_prefix,
    resolve_watermark_season,
    watermark_hash_from_path,
)

def normalize_family(name: str) -> str:
    return re.sub(r"\s*\([^)]+\)\s*$", "", name or "").strip()


def update_weapon_seasons():
    if not manifest_db_exists():
        raise FileNotFoundError(
            f"Manifest database not found. Set DESTINY_MANIFEST_DB.\n"
            f"Looked for: {get_manifest_db_path()}"
        )

    manifest_db = sqlite3.connect(get_manifest_db_path())
    weapon_db = sqlite3.connect("weapon_perks.db")

    # Optional fallback: previous manifest backup often has watermark hashes that
    # still match our hardcoded season map much better than the newest manifest.
    legacy_manifest_map = {}
    legacy_candidates = sorted(
        Path(str(DEFAULT_MANIFEST_DB)).parent.glob(
            Path(str(DEFAULT_MANIFEST_DB)).name + ".bak.*"
        ),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if legacy_candidates:
        legacy_db_path = legacy_candidates[0]
        try:
            legacy_db = sqlite3.connect(str(legacy_db_path))
            legacy_manifest_map = {
                convert_hash(row[0]): row[1]
                for row in legacy_db.execute(
                    """
                    SELECT json_extract(json, '$.hash'),
                           json_extract(json, '$.iconWatermark')
                    FROM DestinyInventoryItemDefinition
                    WHERE json_extract(json, '$.itemType') = 3
                    AND json_extract(json, '$.inventory.tierType') = 5
                    """
                )
                if row[0]
            }
            legacy_db.close()
            print(f"Using legacy manifest fallback: {legacy_db_path.name}")
        except sqlite3.Error:
            legacy_manifest_map = {}

    watermark_by_weapon = {
        convert_hash(row[0]): row[1]
        for row in manifest_db.execute(
            """
            SELECT json_extract(json, '$.hash'),
                   json_extract(json, '$.iconWatermark')
            FROM DestinyInventoryItemDefinition
            WHERE json_extract(json, '$.itemType') = 3
            AND json_extract(json, '$.inventory.tierType') = 5
            """
        )
        if row[0]
    }

    weapons = weapon_db.execute("SELECT hash FROM weapons").fetchall()
    updates = []

    for (weapon_hash,) in weapons:
        icon_watermark = watermark_by_weapon.get(weapon_hash)
        season = resolve_watermark_season(icon_watermark, manifest_db)

        if not season and legacy_manifest_map:
            legacy_wm = legacy_manifest_map.get(weapon_hash)
            legacy_hash = watermark_hash_from_path(legacy_wm)
            if legacy_hash:
                season = lookup_watermark_season_prefix(legacy_hash)

        updates.append((season, weapon_hash))

    # Conservative second-pass inference:
    # If a weapon family (or family+damage) has exactly one known season, apply it
    # to sibling rows that are still unknown.
    by_hash = {h: s for s, h in updates}
    weapon_meta = weapon_db.execute(
        "SELECT hash, name, damage_type FROM weapons"
    ).fetchall()
    meta_by_hash = {row[0]: row for row in weapon_meta}

    seasons_by_family_damage = {}
    seasons_by_family = {}
    for row in weapon_meta:
        h, name, dmg = row
        season = by_hash.get(h, 0) or 0
        if not season:
            continue
        family = normalize_family(name)
        seasons_by_family_damage.setdefault((family, dmg), set()).add(season)
        seasons_by_family.setdefault(family, set()).add(season)

    inferred = 0
    refined_updates = []
    for season, h in updates:
        if season:
            refined_updates.append((season, h))
            continue
        meta = meta_by_hash.get(h)
        if not meta:
            refined_updates.append((season, h))
            continue
        _, name, dmg = meta
        family = normalize_family(name)
        fd = seasons_by_family_damage.get((family, dmg), set())
        f = seasons_by_family.get(family, set())

        inferred_season = 0
        if len(fd) == 1:
            inferred_season = next(iter(fd))
        elif len(f) == 1:
            inferred_season = next(iter(f))

        if inferred_season:
            inferred += 1
            refined_updates.append((inferred_season, h))
        else:
            refined_updates.append((season, h))

    weapon_db.executemany("UPDATE weapons SET season = ? WHERE hash = ?", refined_updates)
    weapon_db.commit()

    remaining = weapon_db.execute(
        "SELECT COUNT(*) FROM weapons WHERE season = 0"
    ).fetchone()[0]

    manifest_db.close()
    weapon_db.close()

    print(f"Updated season for {len(refined_updates)} weapons.")
    print(f"Inferred seasons from family fallback: {inferred}")
    print(f"Weapons still at season 0: {remaining}")


def convert_hash(hash_value):
    if isinstance(hash_value, str):
        return int(hash_value) & 0xFFFFFFFF
    return hash_value


if __name__ == "__main__":
    update_weapon_seasons()
