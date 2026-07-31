"""Perfect Vault: global trait-combination covering on obtainable/craftable weapons.

Combinations are unordered: {perkA, perkB} is one combo regardless of which
trait column each perk sits in. (A,B) and (B,A) are the same.
"""

from __future__ import annotations

import math
import re
import sqlite3
from collections import defaultdict

PERK_TRAIT_SOCKET_ORDERS = (2, 3)
PREFERRED_PACK = 3
FALLBACK_PACK = 1


def normalize_item_hash(hash_val):
    if hash_val is None:
        return None
    return int(hash_val) & 0xFFFFFFFF


def normalize_family(name: str) -> str:
    return re.sub(r"\s*\([^)]+\)\s*$", "", name or "").strip()


def is_eligible_weapon(weapon):
    return bool(weapon.get("is_craftable") or weapon.get("is_obtainable"))


def is_preferred_weapon(weapon):
    """3x3 packing: tiered, adept, or a Zavala/Drifter/Shaxx 6-perk drop."""
    return bool(
        weapon.get("is_tiered")
        or weapon.get("is_adept")
        or weapon.get("is_vendor6")
    )


def combo_key(perk_a, perk_b):
    """Unordered trait combination (order / column does not matter).

    Same perk in both columns (A,A) is not a valid combo — returns None.
    """
    if perk_a == perk_b:
        return None
    return frozenset((perk_a, perk_b))


def combo_label(combo):
    """Stable display / JSON form for a combination."""
    return tuple(sorted(combo))


def weapon_combos(weapon):
    out = set()
    for a in weapon["col2"]:
        for b in weapon["col3"]:
            key = combo_key(a, b)
            if key is not None:
                out.add(key)
    return out


def load_weapon_trait_pools(weapon_db_path="weapon_perks.db", eligible_only=True):
    """Return list of weapon dicts with trait pools and flags."""
    conn = sqlite3.connect(weapon_db_path)
    conn.row_factory = sqlite3.Row

    cols = {row[1] for row in conn.execute("PRAGMA table_info(weapons)")}
    required = {"is_tiered", "is_adept", "is_craftable", "is_obtainable"}
    missing = required - cols
    if missing:
        conn.close()
        raise RuntimeError(
            f"weapons missing columns {sorted(missing)}. Run: python weapon_flags.py"
        )

    has_vendor6 = "is_vendor6" in cols
    vendor6_select = "is_vendor6" if has_vendor6 else "0 AS is_vendor6"

    weapons = {}
    for row in conn.execute(
        f"""
        SELECT hash, name, type, damage_type, ammo_type, icon, season,
               is_tiered, is_adept, {vendor6_select},
               is_craftable, is_obtainable
        FROM weapons
        WHERE tier = 'Legendary' AND is_current = 1
        """
    ):
        item_hash = normalize_item_hash(row["hash"])
        weapons[item_hash] = {
            "hash": item_hash,
            "name": row["name"],
            "family_name": normalize_family(row["name"]),
            "type": row["type"] or "Unknown",
            "damage_type": row["damage_type"] or "Unknown",
            "ammo_type": row["ammo_type"] or "Unknown",
            "icon": row["icon"] or "",
            "season": row["season"] or 0,
            "is_tiered": bool(row["is_tiered"]),
            "is_adept": bool(row["is_adept"]),
            "is_vendor6": bool(row["is_vendor6"]),
            "is_craftable": bool(row["is_craftable"]),
            "is_obtainable": bool(row["is_obtainable"]),
            "col2": set(),
            "col3": set(),
        }

    for row in conn.execute(
        """
        SELECT wp.weapon_hash, wp.socket_order, p.name
        FROM weapon_perks wp
        JOIN perks p ON p.hash = wp.perk_hash
        WHERE wp.socket_order IN (?, ?)
        AND p.name IS NOT NULL
        AND p.name NOT LIKE '%Shader%'
        AND p.name NOT LIKE '%Keepsake%'
        """,
        PERK_TRAIT_SOCKET_ORDERS,
    ):
        item_hash = normalize_item_hash(row["weapon_hash"])
        weapon = weapons.get(item_hash)
        if not weapon:
            continue
        name = row["name"]
        if not name:
            continue
        if row["socket_order"] == 2:
            weapon["col2"].add(name)
        elif row["socket_order"] == 3:
            weapon["col3"].add(name)

    conn.close()

    usable = [w for w in weapons.values() if w["col2"] and w["col3"]]
    if eligible_only:
        usable = [w for w in usable if is_eligible_weapon(w)]

    def _newest_pool_rank(weapon):
        pool = len(weapon["col2"]) * len(weapon["col3"])
        has_pool = 1 if pool > 0 else 0
        return (
            has_pool,
            weapon.get("season") or 0,
            pool,
            len(weapon["col2"]) + len(weapon["col3"]),
            1 if is_preferred_weapon(weapon) else 0,
            1 if weapon.get("is_adept") else 0,
            weapon.get("hash") or 0,
        )

    # Group by family + damage. Adept/Timelost supersedes craftable/base:
    # when any adept exists, drop non-adept versions entirely.
    grouped = {}
    for weapon in usable:
        key = (weapon["family_name"], weapon["damage_type"])
        grouped.setdefault(key, []).append(weapon)

    merged = {}
    for key, group in grouped.items():
        adepts = [w for w in group if w.get("is_adept")]
        candidates = adepts if adepts else group
        winner = max(candidates, key=_newest_pool_rank)
        for sibling in group:
            if sibling is winner:
                continue
            if sibling.get("is_obtainable"):
                winner["is_obtainable"] = True
            if sibling.get("is_tiered"):
                winner["is_tiered"] = True
            if sibling.get("is_vendor6"):
                winner["is_vendor6"] = True
        # Adept raid weapons are often also craftable; keep that if present on winner.
        if any(w.get("is_craftable") and w.get("is_adept") for w in group):
            winner["is_craftable"] = True
        elif not adepts and any(w.get("is_craftable") for w in group):
            winner["is_craftable"] = True
        merged[key] = winner

    return list(merged.values())


def build_pair_plane(weapons):
    """Build unordered combination plane: {perkA, perkB}."""
    plane = set()
    for weapon in weapons:
        plane |= weapon_combos(weapon)
    return plane


def _ordered_pairs_for_combos(weapon, combos):
    """Physical (col2, col3) rolls on this weapon that realize the given combos."""
    ordered = set()
    for a in weapon["col2"]:
        for b in weapon["col3"]:
            if a == b:
                continue
            key = combo_key(a, b)
            if key in combos:
                ordered.add((a, b))
    return ordered


def _pack_from_relevant(relevant_ordered, pack_size, prefer_combos=None):
    """Pack physical column perks; `relevant_ordered` is (col2, col3) tuples.

    prefer_combos: optional set of combo_keys to prioritize (e.g. exclusive leftovers).
    """
    if not relevant_ordered:
        return None

    if pack_size <= 1:
        def pair_key(pair):
            combo = combo_key(*pair)
            preferred = 1 if prefer_combos and combo in prefer_combos else 0
            return (preferred, pair[0], pair[1])

        pair = max(relevant_ordered, key=pair_key)
        covered = {combo_key(*pair)}
        return {
            "col2": [pair[0]],
            "col3": [pair[1]],
            "covered": covered,
            "score": len(covered),
        }

    score_a = defaultdict(int)
    score_b = defaultdict(int)
    for a, b in relevant_ordered:
        score_a[a] += 1
        score_b[b] += 1

    top_a = [n for n, _ in sorted(score_a.items(), key=lambda x: (-x[1], x[0]))]
    top_b = [n for n, _ in sorted(score_b.items(), key=lambda x: (-x[1], x[0]))]
    a_set = set(top_a[:pack_size])
    b_set = set(top_b[:pack_size])
    covered_ordered = {
        (a, b) for a, b in relevant_ordered if a in a_set and b in b_set
    }
    covered = {combo_key(a, b) for a, b in covered_ordered}

    if not covered:
        pair = next(iter(relevant_ordered))
        a_set = {pair[0]}
        b_set = {pair[1]}
        for perk in top_a:
            if len(a_set) >= pack_size:
                break
            a_set.add(perk)
        for perk in top_b:
            if len(b_set) >= pack_size:
                break
            b_set.add(perk)
        covered_ordered = {
            (a, b) for a, b in relevant_ordered if a in a_set and b in b_set
        }
        covered = {combo_key(a, b) for a, b in covered_ordered}

    if not covered:
        return None

    return {
        "col2": sorted(a_set),
        "col3": sorted(b_set),
        "covered": covered,
        "score": len(covered),
    }


def _best_move(weapons, remaining, pack_size, copy_counts=None):
    """Pick the best pack among weapons.

    Prefers models used the fewest times (spread-first), then max coverage.
    Unordered combos: covering {a,b} removes both column orientations globally.
    """
    if copy_counts is None:
        copy_counts = {}

    # Precompute exclusivity of remaining combos relative to this candidate set.
    covering_weapons = [
        w for w in weapons if w["all_pairs"] & remaining
    ]
    if not covering_weapons:
        return None, None

    owner_count = {}
    for weapon in covering_weapons:
        for combo in weapon["all_pairs"] & remaining:
            owner_count[combo] = owner_count.get(combo, 0) + 1

    covering = []
    for weapon in covering_weapons:
        relevant_combos = weapon["all_pairs"] & remaining
        exclusive = {c for c in relevant_combos if owner_count.get(c, 0) == 1}
        ordered = _ordered_pairs_for_combos(weapon, relevant_combos)
        move = _pack_from_relevant(
            ordered, pack_size, prefer_combos=exclusive or None
        )
        if not move or move["score"] <= 0:
            continue
        exclusive_covered = sum(1 for c in move["covered"] if c in exclusive)
        covering.append((weapon, move, exclusive_covered))

    if not covering:
        return None, None

    min_copies = min(copy_counts.get(w["hash"], 0) for w, _, _ in covering)
    tier = [
        (w, m, ex)
        for w, m, ex in covering
        if copy_counts.get(w["hash"], 0) == min_copies
    ]
    best_weapon, best_move, _ = max(
        tier, key=lambda item: (item[1]["score"], item[2], item[0]["name"])
    )
    return best_weapon, best_move


def _append_vault_entry(vault, copy_index, weapon, role, move, remaining_after):
    vault.append({
        "copy_index": copy_index,
        "role": role,
        "hash": weapon["hash"],
        "name": weapon["name"],
        "family_name": weapon["family_name"],
        "type": weapon["type"],
        "damage_type": weapon["damage_type"],
        "is_tiered": weapon["is_tiered"],
        "is_adept": weapon["is_adept"],
        "is_vendor6": weapon.get("is_vendor6", False),
        "is_craftable": weapon["is_craftable"],
        "is_obtainable": weapon["is_obtainable"],
        "icon_url": (
            f"https://www.bungie.net{weapon['icon']}" if weapon["icon"] else ""
        ),
        "col2_perks": move["col2"],
        "col3_perks": move["col3"],
        "pairs_solved": move["score"],
        "pairs_remaining_after": remaining_after,
        "sample_pairs": [
            combo_label(c) for c in sorted(move["covered"], key=combo_label)
        ][:9],
    })


def compute_perfect_vault(weapon_db_path="weapon_perks.db", mode="full"):
    """Compute Perfect Vault.

    Covers the *global* unordered combo plane (not each gun's full matrix).

    Spread-first packing: take one copy of each useful gun before duplicating
    any model. Duplicates are only added when remaining combos still need that
    model after other guns have already contributed a copy.

    mode:
      - "full": preferred 3×3 then fallback 1×1 over all eligible weapons
      - "preferred_only": only 3×3 preferred weapons (plane + covering)
    """
    if mode not in ("full", "preferred_only"):
        raise ValueError(f"Unknown perfect vault mode: {mode}")

    all_eligible = load_weapon_trait_pools(weapon_db_path, eligible_only=True)
    preferred = [w for w in all_eligible if is_preferred_weapon(w)]
    fallback = [w for w in all_eligible if not is_preferred_weapon(w)]

    if mode == "preferred_only":
        weapons = preferred
        fallback = []
    else:
        weapons = all_eligible

    for weapon in all_eligible:
        weapon["all_pairs"] = weapon_combos(weapon)

    plane = set()
    for weapon in weapons:
        plane |= weapon["all_pairs"]

    full_plane = set()
    for weapon in all_eligible:
        full_plane |= weapon["all_pairs"]
    preferred_reachable = set()
    for weapon in preferred:
        preferred_reachable |= weapon["all_pairs"]
    combos_only_on_fallback = len(full_plane - preferred_reachable)

    remaining = set(plane)
    initial_size = len(plane)
    lower_bound = (
        math.ceil(initial_size / (PREFERRED_PACK * PREFERRED_PACK))
        if initial_size else 0
    )

    vault = []
    copy_index = 0
    copy_counts = {}

    while remaining:
        weapon, move = _best_move(
            preferred, remaining, PREFERRED_PACK, copy_counts=copy_counts
        )
        role = "preferred"
        if (not move or move["score"] <= 0) and mode == "full":
            weapon, move = _best_move(
                fallback, remaining, FALLBACK_PACK, copy_counts=copy_counts
            )
            role = "fallback"
        if not move or move["score"] <= 0:
            break

        remaining -= move["covered"]
        copy_index += 1
        copy_counts[weapon["hash"]] = copy_counts.get(weapon["hash"], 0) + 1
        _append_vault_entry(
            vault, copy_index, weapon, role, move, len(remaining)
        )

    by_hash = {w["hash"]: w for w in all_eligible}
    by_weapon = {}
    for entry in vault:
        key = entry["hash"]
        if key not in by_weapon:
            model = by_hash.get(key, {})
            by_weapon[key] = {
                "hash": entry["hash"],
                "name": entry["name"],
                "family_name": entry["family_name"],
                "type": entry["type"],
                "damage_type": entry["damage_type"],
                "role": entry["role"],
                "is_tiered": entry["is_tiered"],
                "is_adept": entry["is_adept"],
                "is_vendor6": entry["is_vendor6"],
                "is_craftable": entry["is_craftable"],
                "is_obtainable": entry["is_obtainable"],
                "icon_url": entry["icon_url"],
                "capacity": (
                    PREFERRED_PACK if is_preferred_weapon(model) else FALLBACK_PACK
                ),
                "col2_pool": sorted(model.get("col2", ())),
                "col3_pool": sorted(model.get("col3", ())),
                "pool_combos": len(model.get("all_pairs", ())),
                "copies": 0,
                "pairs_solved": 0,
            }
        by_weapon[key]["copies"] += 1
        by_weapon[key]["pairs_solved"] += entry["pairs_solved"]

    summary_rows = sorted(
        by_weapon.values(),
        key=lambda r: (
            0 if r["role"] == "preferred" else 1,
            -r["copies"],
            -r["pairs_solved"],
            r["name"].lower(),
        ),
    )

    preferred_copies = sum(1 for e in vault if e["role"] == "preferred")
    fallback_copies = sum(1 for e in vault if e["role"] == "fallback")
    craftable_models = sum(1 for w in weapons if w["is_craftable"])
    obtainable_models = sum(1 for w in weapons if w["is_obtainable"])
    duplicated_models = sum(1 for row in by_weapon.values() if row["copies"] > 1)
    max_copies_one_model = max((row["copies"] for row in by_weapon.values()), default=0)

    return {
        "mode": mode,
        "plane_size": initial_size,
        "pairs_unsolved": len(remaining),
        "lower_bound": lower_bound,
        "total_copies": len(vault),
        "preferred_copies": preferred_copies,
        "fallback_copies": fallback_copies,
        "preferred_weapon_models": len(preferred),
        "fallback_weapon_models": len(fallback) if mode == "full" else 0,
        "eligible_weapon_models": len(weapons),
        "craftable_weapon_models": craftable_models,
        "obtainable_weapon_models": obtainable_models,
        "unique_models_in_vault": len(by_weapon),
        "duplicated_models": duplicated_models,
        "max_copies_one_model": max_copies_one_model,
        "combination_mode": "unordered",
        "full_plane_size": len(full_plane),
        "combos_only_on_fallback": combos_only_on_fallback,
        "weapons": summary_rows,
        "copies": vault,
    }


_cached_results = {}


def get_perfect_vault(
    force_refresh=False,
    weapon_db_path="weapon_perks.db",
    mode="full",
):
    global _cached_results
    if force_refresh or mode not in _cached_results:
        if mode == "pos_gfs":
            # Deferred: pos_gfs_vault imports helpers from this module.
            from pos_gfs_vault import solve_pos_gfs

            _cached_results[mode] = solve_pos_gfs(weapon_db_path)
        else:
            _cached_results[mode] = compute_perfect_vault(
                weapon_db_path, mode=mode
            )
    return _cached_results[mode]


if __name__ == "__main__":
    import time

    for mode in ("full", "preferred_only"):
        started = time.time()
        result = compute_perfect_vault(mode=mode)
        elapsed = time.time() - started
        print(
            f"[{mode}] plane={result['plane_size']} combos "
            f"copies={result['total_copies']} "
            f"lower_bound={result['lower_bound']} "
            f"preferred={result['preferred_copies']} "
            f"fallback={result['fallback_copies']} "
            f"unsolved={result['pairs_unsolved']} "
            f"models={result['eligible_weapon_models']} "
            f"fallback_only_combos={result['combos_only_on_fallback']} "
            f"({elapsed:.1f}s)"
        )
        for row in result["weapons"][:8]:
            print(
                f"  x{row['copies']} [{row['role']}] {row['name']} "
                f"({row['pairs_solved']} combos)"
            )
        print()
