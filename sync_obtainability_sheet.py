"""Sync currently-obtainable weapons from the loot spreadsheet into overlays.

Reads obtainable_weapons_sheet.csv (export of the Google Sheet) and writes:
  - obtainability_overlay.json  → is_obtainable
  - merges preferred packing hints into tier_flags_overlay.json for:
      * sheet Tiered? = Yes
      * Commander Zavala / The Drifter / Lord Shaxx (6-perk drops)

Name matching:
  - exact name
  - known sheet aliases / typos
  - normalized fuzzy match
When multiple DB hashes share a name, keep the newest perk pool only
(highest season, then largest trait-column product).
"""

from __future__ import annotations

import csv
import json
import re
import sqlite3
from difflib import get_close_matches
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SHEET_PATH = PROJECT_ROOT / "obtainable_weapons_sheet.csv"
OBTAIN_OVERLAY_PATH = PROJECT_ROOT / "obtainability_overlay.json"
TIER_OVERLAY_PATH = PROJECT_ROOT / "tier_flags_overlay.json"

VENDOR_6PERK_SECTIONS = {
    "The Drifter",
    "Lord Shaxx",
    "Commander Zavala",
}

# Sheet label → canonical Destiny display name in our DB.
SHEET_NAME_ALIASES = {
    "first in first out": "First In, Last Out",
    "jian 7": "Jian 7 Rifle",
    "steel feather repeater": "Steelfeather Repeater",
    "steelfeather repeater": "Steelfeather Repeater",
    "21% delierium": "21% Delirium",
    "nightwatch": "Night Watch",
    "mida mini tool": "MIDA Mini-Tool",
    "halieatus": "Haliaetus",
    "steel sybil": "Steel Sybil Z-14",
    "fimbulwinter's stitch": "Fimbulwinter Stitch",
    "fimbulwinter stitch": "Fimbulwinter Stitch",
    "ascendency": "Ascendancy",
    "dimensional hypertrochoid": "Dimensional Hypotrochoid",
    "phylotactic spiral": "Phyllotactic Spiral",
    "no hesitations": "No Hesitation",
}


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip())


def match_key(name: str) -> str:
    """Loose key for alias / fuzzy compare."""
    text = normalize_name(name).lower()
    text = text.replace("'", "").replace(",", "").replace("-", " ")
    text = re.sub(r"[^a-z0-9%+./\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_armor_row(name: str, loot_type: str) -> bool:
    blob = f"{name} {loot_type}".lower()
    return "armor" in blob


def parse_sheet(path: Path = SHEET_PATH):
    if not path.is_file():
        raise FileNotFoundError(f"Sheet CSV not found: {path}")

    weapons = []
    section = None
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if not header:
            return weapons
        for row in reader:
            while len(row) < 8:
                row.append("")
            loot, tiered, loot_type, _elem, _acq, _craft, _updated, _notes = [
                c.strip() for c in row[:8]
            ]
            if not loot and tiered and not loot_type:
                section = tiered
                continue
            if not loot:
                continue
            if is_armor_row(loot, loot_type):
                continue
            weapons.append({
                "name": loot,
                "tiered": tiered.lower() in ("yes", "y", "true", "1"),
                "section": section,
                "vendor6": section in VENDOR_6PERK_SECTIONS,
            })
    return weapons


def load_weapon_candidates(weapon_db_path="weapon_perks.db"):
    """Return list of candidate dicts with pool scores."""
    conn = sqlite3.connect(weapon_db_path)
    conn.row_factory = sqlite3.Row
    candidates = []
    for row in conn.execute(
        """
        SELECT w.hash, w.name, w.season, w.damage_type,
               COALESCE((
                 SELECT COUNT(*) FROM weapon_perks wp
                 WHERE wp.weapon_hash = w.hash AND wp.socket_order = 2
               ), 0) AS col2,
               COALESCE((
                 SELECT COUNT(*) FROM weapon_perks wp
                 WHERE wp.weapon_hash = w.hash AND wp.socket_order = 3
               ), 0) AS col3
        FROM weapons w
        WHERE w.tier = 'Legendary' AND w.is_current = 1
        """
    ):
        item_hash = int(row["hash"]) & 0xFFFFFFFF
        col2 = int(row["col2"] or 0)
        col3 = int(row["col3"] or 0)
        candidates.append({
            "hash": item_hash,
            "name": row["name"],
            "season": int(row["season"] or 0),
            "damage_type": row["damage_type"] or "",
            "col2": col2,
            "col3": col3,
            "pool_product": col2 * col3,
            "exact_key": normalize_name(row["name"]).lower(),
            "fuzzy_key": match_key(row["name"]),
        })
    conn.close()
    return candidates


def pool_rank(candidate):
    """Prefer a real trait pool, then newest season, then largest pool."""
    has_pool = 1 if candidate["pool_product"] > 0 else 0
    return (
        has_pool,
        candidate["season"],
        candidate["pool_product"],
        candidate["col2"] + candidate["col3"],
        candidate["hash"],
    )


def pick_newest_pool(candidates):
    if not candidates:
        return None
    # Prefer versions that actually have both trait columns populated.
    with_pools = [c for c in candidates if c["col2"] > 0 and c["col3"] > 0]
    return max(with_pools or candidates, key=pool_rank)


def build_name_indexes(candidates):
    by_exact = {}
    by_fuzzy = {}
    for cand in candidates:
        by_exact.setdefault(cand["exact_key"], []).append(cand)
        by_fuzzy.setdefault(cand["fuzzy_key"], []).append(cand)
    return by_exact, by_fuzzy


def resolve_sheet_name(sheet_name, by_exact, by_fuzzy, fuzzy_keys):
    """Resolve a sheet label to DB candidates (all versions), before newest pick."""
    exact = normalize_name(sheet_name).lower()
    fuzzy = match_key(sheet_name)

    alias = SHEET_NAME_ALIASES.get(exact) or SHEET_NAME_ALIASES.get(fuzzy)
    if alias:
        alias_exact = normalize_name(alias).lower()
        alias_fuzzy = match_key(alias)
        if alias_exact in by_exact:
            return by_exact[alias_exact], f"alias:{alias}"
        if alias_fuzzy in by_fuzzy:
            return by_fuzzy[alias_fuzzy], f"alias:{alias}"

    if exact in by_exact:
        return by_exact[exact], "exact"
    if fuzzy in by_fuzzy:
        return by_fuzzy[fuzzy], "fuzzy-key"

    close = get_close_matches(fuzzy, fuzzy_keys, n=1, cutoff=0.82)
    if close:
        return by_fuzzy[close[0]], f"close:{close[0]}"

    return [], None


def sync_overlays(weapon_db_path="weapon_perks.db", sheet_path: Path = SHEET_PATH):
    sheet_weapons = parse_sheet(sheet_path)
    candidates = load_weapon_candidates(weapon_db_path)
    by_exact, by_fuzzy = build_name_indexes(candidates)
    fuzzy_keys = list(by_fuzzy.keys())

    obtain = {}
    preferred_hints = {}
    unmatched = []
    matched_rows = 0
    match_methods = {}

    for row in sheet_weapons:
        cands, method = resolve_sheet_name(row["name"], by_exact, by_fuzzy, fuzzy_keys)
        best = pick_newest_pool(cands)
        if not best or best["pool_product"] <= 0:
            # Still accept newest even if pool empty? Prefer requiring a real pool.
            if not best:
                unmatched.append(row["name"])
                continue
        matched_rows += 1
        match_methods[method or "unknown"] = match_methods.get(method or "unknown", 0) + 1
        item_hash = best["hash"]
        obtain[str(item_hash)] = True
        if row["tiered"] or row["vendor6"]:
            preferred_hints[str(item_hash)] = {"is_tiered": True}

    OBTAIN_OVERLAY_PATH.write_text(json.dumps(obtain, indent=2, sort_keys=True) + "\n")

    try:
        tier_raw = json.loads(TIER_OVERLAY_PATH.read_text()) if TIER_OVERLAY_PATH.is_file() else {}
    except (OSError, json.JSONDecodeError):
        tier_raw = {}
    if not isinstance(tier_raw, dict):
        tier_raw = {}

    # Drop prior sheet-sourced preferred hints, then re-apply current set.
    cleaned = {}
    for key, value in tier_raw.items():
        if isinstance(value, dict) and value.get("_source") == "obtainable_weapons_sheet":
            continue
        cleaned[key] = value
    tier_raw = cleaned

    for item_hash, hints in preferred_hints.items():
        entry = tier_raw.get(item_hash)
        if not isinstance(entry, dict):
            entry = {}
        entry["is_tiered"] = True
        entry["_source"] = "obtainable_weapons_sheet"
        tier_raw[item_hash] = entry

    TIER_OVERLAY_PATH.write_text(json.dumps(tier_raw, indent=2, sort_keys=True) + "\n")

    summary = {
        "sheet_weapon_rows": len(sheet_weapons),
        "matched_rows": matched_rows,
        "unmatched_rows": len(unmatched),
        "obtainable_hashes": len(obtain),
        "preferred_hint_hashes": len(preferred_hints),
        "match_methods": match_methods,
        "unmatched": unmatched,
    }
    print(
        f"Synced sheet → obtainable={summary['obtainable_hashes']} newest pools "
        f"(matched_rows={matched_rows}, unmatched={len(unmatched)}, "
        f"preferred_hints={len(preferred_hints)})"
    )
    print(f"Match methods: {match_methods}")
    if unmatched:
        print("Still unmatched:")
        for name in unmatched:
            print(f"  - {name}")
    return summary


if __name__ == "__main__":
    sync_overlays()
