"""Recompute weapon season values from manifest watermarks (fast; no full migration).

Resolution order per weapon hash:
1. Legacy manifest watermark (older world_sql_content .bak) via the season map
2. Current manifest watermark via the season map
3. Family / family+damage inference when exactly one known season exists
"""

import re
import sqlite3
from collections import defaultdict
from pathlib import Path

from config import (
    DEFAULT_MANIFEST_DB,
    clear_watermark_season_cache,
    get_manifest_db_path,
    lookup_watermark_season_prefix,
    manifest_db_exists,
    resolve_watermark_season,
    watermark_hash_from_path,
)


def normalize_family(name: str) -> str:
    return re.sub(r"\s*\([^)]+\)\s*$", "", name or "").strip()


def convert_hash(hash_value):
    if hash_value is None:
        return None
    if isinstance(hash_value, str):
        return int(hash_value) & 0xFFFFFFFF
    return int(hash_value) & 0xFFFFFFFF


def _load_watermark_by_hash(db_path):
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        """
        SELECT json_extract(json, '$.hash'),
               json_extract(json, '$.iconWatermark')
        FROM DestinyInventoryItemDefinition
        WHERE json_extract(json, '$.itemType') = 3
        AND json_extract(json, '$.inventory.tierType') = 5
        """
    ).fetchall()
    conn.close()
    return {
        convert_hash(hash_val): watermark
        for hash_val, watermark in rows
        if hash_val is not None
    }


def _pick_best_legacy_manifest(current_wm_hashes):
    """Prefer a .bak whose watermarks are OLD-STYLE (not in the current manifest).

    Newer backups often already use the same watermark filenames as the current
    manifest, so scoring them against the expanded map is circular. We want a
    bak that still has classic watermarks we can bridge from.
    """
    candidates = sorted(
        Path(str(DEFAULT_MANIFEST_DB)).parent.glob(
            Path(str(DEFAULT_MANIFEST_DB)).name + ".bak.*"
        ),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    best_path = None
    best_hits = -1
    for path in candidates:
        try:
            wm_by_hash = _load_watermark_by_hash(path)
        except sqlite3.Error:
            continue
        old_style_hits = 0
        for wm in wm_by_hash.values():
            wh = watermark_hash_from_path(wm)
            if not wh or wh in current_wm_hashes:
                continue
            if lookup_watermark_season_prefix(wh):
                old_style_hits += 1
        print(
            f"Legacy candidate {path.name}: "
            f"{old_style_hits} old-style seasonable watermarks"
        )
        if old_style_hits > best_hits:
            best_hits = old_style_hits
            best_path = path
    return best_path, best_hits


def update_weapon_seasons():
    if not manifest_db_exists():
        raise FileNotFoundError(
            f"Manifest database not found. Set DESTINY_MANIFEST_DB.\n"
            f"Looked for: {get_manifest_db_path()}"
        )

    clear_watermark_season_cache()

    manifest_db = sqlite3.connect(get_manifest_db_path())
    weapon_db = sqlite3.connect("weapon_perks.db")

    watermark_by_weapon = _load_watermark_by_hash(get_manifest_db_path())
    current_wm_hashes = {
        watermark_hash_from_path(wm)
        for wm in watermark_by_weapon.values()
        if wm
    }

    legacy_path, legacy_hits = _pick_best_legacy_manifest(current_wm_hashes)
    legacy_wm_by_hash = {}
    if legacy_path and legacy_hits > 0:
        legacy_wm_by_hash = _load_watermark_by_hash(legacy_path)
        print(f"Using legacy manifest fallback: {legacy_path.name}")
    else:
        print("No useful legacy manifest fallback found.")

    weapons = weapon_db.execute("SELECT hash, name, damage_type FROM weapons").fetchall()

    updates = []
    source_counts = defaultdict(int)
    for weapon_hash, name, damage_type in weapons:
        item_hash = convert_hash(weapon_hash)
        season = 0
        source = "unknown"

        # Prefer the current watermark map (includes post-EoF hashes and fixes).
        icon_watermark = watermark_by_weapon.get(item_hash)
        season = resolve_watermark_season(icon_watermark, manifest_db)
        if season:
            source = "current_watermark"

        # Fall back to old-style watermarks from a legacy bak when the current
        # mark is generic/unmapped (e.g. shared dungeon/default icons).
        if not season:
            legacy_wm = legacy_wm_by_hash.get(item_hash)
            if legacy_wm:
                season = lookup_watermark_season_prefix(
                    watermark_hash_from_path(legacy_wm)
                )
                if season:
                    source = "legacy_hash"

        # Keep original DB hash for UPDATE; item_hash is only for manifest joins.
        updates.append((season, weapon_hash, name, damage_type, source))
        source_counts[source] += 1

    # Family inference for remaining unknowns.
    seasons_by_family_damage = defaultdict(set)
    seasons_by_family = defaultdict(set)
    for season, _weapon_hash, name, damage_type, _source in updates:
        if not season:
            continue
        family = normalize_family(name)
        seasons_by_family_damage[(family, damage_type)].add(season)
        seasons_by_family[family].add(season)

    inferred = 0
    refined_updates = []
    for season, weapon_hash, name, damage_type, source in updates:
        if season:
            refined_updates.append((season, weapon_hash))
            continue

        family = normalize_family(name)
        fd = seasons_by_family_damage.get((family, damage_type), set())
        f = seasons_by_family.get(family, set())

        inferred_season = 0
        if len(fd) == 1:
            inferred_season = next(iter(fd))
        elif len(f) == 1:
            inferred_season = next(iter(f))

        if inferred_season:
            inferred += 1
            source_counts["family_infer"] += 1
            source_counts["unknown"] -= 1
            refined_updates.append((inferred_season, weapon_hash))
        else:
            refined_updates.append((season, weapon_hash))

    weapon_db.executemany(
        "UPDATE weapons SET season = ? WHERE hash = ?",
        refined_updates,
    )
    weapon_db.commit()

    remaining = weapon_db.execute(
        "SELECT COUNT(*) FROM weapons WHERE season = 0 OR season IS NULL"
    ).fetchone()[0]
    dist_rows = weapon_db.execute(
        """
        SELECT season, COUNT(*)
        FROM weapons
        GROUP BY season
        ORDER BY season
        """
    ).fetchall()

    manifest_db.close()
    weapon_db.close()

    print(f"Updated season for {len(refined_updates)} weapons.")
    print(f"Sources: {dict(source_counts)}")
    print(f"Inferred seasons from family fallback: {inferred}")
    print(f"Weapons still at season 0: {remaining}")
    print("Season distribution:")
    for season, count in dist_rows:
        print(f"  S{season}: {count}")


if __name__ == "__main__":
    update_weapon_seasons()
