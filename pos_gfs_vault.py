"""POS / GFS vault solver.

Instead of greedy set cover, rank the work by rarity and the tools by
flexibility:

- POS (Perk Occurance Score) = how many eligible models can roll a combo.
  Lower means rarer, so it gets solved first.
- GFS (Gun Flexibility Score) = sum of POS over every combo a gun can roll.
  Higher means the gun sits on more of the popular plane, so it is the
  preferred home for a rare combo.

Rare combos are then assigned to the most flexible gun that can take them,
filling copies that are already in the vault before ever adding a new one.

Solving runs in two phases so the 3x3 guns do as much work as possible:
first every combo any 3x3 gun can roll is placed on 3x3 guns, then the 1x1
guns only mop up the combos that exist nowhere else.
"""

from __future__ import annotations

import math
from collections import defaultdict

from perfect_vault import (
    FALLBACK_PACK,
    PREFERRED_PACK,
    combo_label,
    is_preferred_weapon,
    load_weapon_trait_pools,
    weapon_combos,
)


def column_capacity(weapon):
    """Perks allowed per trait column on one copy of this model."""
    return PREFERRED_PACK if is_preferred_weapon(weapon) else FALLBACK_PACK


def compute_pos(weapons):
    """combo -> number of eligible models that can roll it."""
    pos = defaultdict(int)
    for weapon in weapons:
        for combo in weapon["all_pairs"]:
            pos[combo] += 1
    return dict(pos)


def compute_gfs(weapons, pos):
    """weapon hash -> sum of POS across every combo the gun can roll."""
    return {
        weapon["hash"]: sum(pos.get(c, 0) for c in weapon["all_pairs"])
        for weapon in weapons
    }


def rank_combos(pos):
    """Combos sorted rarest first; ties broken on the label for determinism."""
    return sorted(pos, key=lambda c: (pos[c], combo_label(c)))


def rank_weapons(weapons, gfs):
    """Weapons sorted most flexible first."""
    return sorted(
        weapons,
        key=lambda w: (-gfs.get(w["hash"], 0), w["name"].lower(), w["hash"]),
    )


def _realized_combos(col2, col3):
    """Every combo a filled grid actually rolls (A != B)."""
    out = set()
    for a in col2:
        for b in col3:
            if a != b:
                out.add(frozenset((a, b)))
    return out


def _fit_cost(copy, combo):
    """Cheapest way to place `combo` on `copy`, or None.

    Returns (new_perks_added, col2_perk, col3_perk). A perk already sitting
    in the column is free; otherwise that column must be under capacity.
    """
    weapon = copy["weapon"]
    cap = copy["capacity"]
    best = None
    for x, y in _orientations(combo):
        if x not in weapon["col2"] or y not in weapon["col3"]:
            continue
        cost = 0
        if x not in copy["col2"]:
            if len(copy["col2"]) >= cap:
                continue
            cost += 1
        if y not in copy["col3"]:
            if len(copy["col3"]) >= cap:
                continue
            cost += 1
        if best is None or cost < best[0]:
            best = (cost, x, y)
    return best


def _orientations(combo):
    a, b = combo_label(combo)
    return ((a, b), (b, a))


def _can_roll(weapon, combo):
    return _fit_cost(
        {"weapon": weapon, "capacity": column_capacity(weapon),
         "col2": set(), "col3": set()},
        combo,
    ) is not None


def _new_copy(weapon, copy_index):
    return {
        "copy_index": copy_index,
        "weapon": weapon,
        "capacity": column_capacity(weapon),
        "col2": set(),
        "col3": set(),
        "solved": set(),
        "requested": [],
    }


def _is_full(copy):
    cap = copy["capacity"]
    return len(copy["col2"]) >= cap and len(copy["col3"]) >= cap


def _candidate_index(models, gfs):
    """combo -> candidate models that can roll it, most flexible first."""
    index = defaultdict(list)
    for weapon in rank_weapons(models, gfs):
        for combo in weapon["all_pairs"]:
            index[combo].append(weapon)
    return index


def _start_copy(weapon, combo, state):
    copy = _new_copy(weapon, len(state["copies"]) + 1)
    fit = _fit_cost(copy, combo)
    if fit is None:
        return None, None
    state["copies"].append(copy)
    state["copy_counts"][weapon["hash"]] += 1
    state["open_copies"][weapon["hash"]].append(copy)
    return copy, fit


def _allocate(combos, candidates_by_combo, state):
    """Place each unsolved combo using the open-copy / new-model / duplicate ladder."""
    for combo in combos:
        if combo in state["solved"]:
            continue

        candidates = candidates_by_combo.get(combo) or []
        target = None
        placement = None

        # 1) reuse an open copy: fewest new perks first, then highest GFS
        for weapon in candidates:
            for copy in state["open_copies"][weapon["hash"]]:
                fit = _fit_cost(copy, combo)
                if fit is None:
                    continue
                if placement is None or fit[0] < placement[0]:
                    target, placement = copy, fit
                if placement[0] <= 1:
                    break
            if placement is not None and placement[0] <= 1:
                break

        # 2) otherwise start the first copy of an unused model
        if target is None:
            for weapon in candidates:
                if state["copy_counts"][weapon["hash"]]:
                    continue
                target, placement = _start_copy(weapon, combo, state)
                if target is not None:
                    break

        # 3) last resort: duplicate the most flexible candidate
        if target is None:
            for weapon in candidates:
                target, placement = _start_copy(weapon, combo, state)
                if target is not None:
                    break

        if target is None:
            continue

        _, col2_perk, col3_perk = placement
        target["col2"].add(col2_perk)
        target["col3"].add(col3_perk)
        target["requested"].append(combo)

        # Credit every combo this grid now rolls, not just the requested one.
        newly = _realized_combos(target["col2"], target["col3"]) & state["plane"]
        newly -= state["solved"]
        state["solved"] |= newly
        target["solved"] |= newly
        state["explicit"] += 1
        state["credited"] += len(newly) - 1

        if _is_full(target):
            state["open_copies"][target["weapon"]["hash"]].remove(target)


def solve_pos_gfs(weapon_db_path="weapon_perks.db", weapons=None):
    """Assign the rarest combos to the most flexible guns, 3x3 guns first.

    Phase 1 solves every combo a 3x3 gun can roll using only 3x3 guns.
    Phase 2 gap-fills what is left — combos that exist on no 3x3 gun — with
    1x1 guns, so a 1x1 copy is only ever bought when nothing else can roll it.

    Ladder within a phase, for each unsolved combo rarest first:
      1. an open copy already in the vault (fewest new perks, then best GFS)
      2. the first copy of a candidate model that has no copy yet
      3. a duplicate copy of the highest-GFS candidate

    `weapons` overrides the database load (used by tests).
    """
    if weapons is None:
        weapons = load_weapon_trait_pools(weapon_db_path, eligible_only=True)
    for weapon in weapons:
        weapon["all_pairs"] = weapon_combos(weapon)

    pos = compute_pos(weapons)
    gfs = compute_gfs(weapons, pos)

    preferred = [w for w in weapons if is_preferred_weapon(w)]
    fallback = [w for w in weapons if not is_preferred_weapon(w)]

    state = {
        "plane": set(pos),
        "solved": set(),
        "copies": [],
        "open_copies": defaultdict(list),
        "copy_counts": defaultdict(int),
        "explicit": 0,
        "credited": 0,
    }

    ordered = rank_combos(pos)
    preferred_reachable = set()
    for weapon in preferred:
        preferred_reachable |= weapon["all_pairs"]

    _allocate(
        [c for c in ordered if c in preferred_reachable],
        _candidate_index(preferred, gfs),
        state,
    )
    _allocate(
        [c for c in ordered if c not in preferred_reachable],
        _candidate_index(fallback, gfs),
        state,
    )

    return _build_result(
        weapons=weapons,
        plane=state["plane"],
        solved=state["solved"],
        copies=state["copies"],
        pos=pos,
        gfs=gfs,
        explicit_solved=state["explicit"],
        credited_solved=state["credited"],
    )


def _copy_entry(copy, gfs, pos, remaining_after):
    weapon = copy["weapon"]
    solved_labels = sorted(
        (combo_label(c) for c in copy["solved"]), key=lambda label: label
    )
    return {
        "copy_index": copy["copy_index"],
        "role": "preferred" if copy["capacity"] > 1 else "fallback",
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
        "col2_perks": sorted(copy["col2"]),
        "col3_perks": sorted(copy["col3"]),
        "pairs_solved": len(copy["solved"]),
        "pairs_remaining_after": remaining_after,
        "gfs": gfs.get(weapon["hash"], 0),
        "best_pos": min(
            (pos[c] for c in copy["requested"]), default=None
        ),
        "sample_pairs": solved_labels[:9],
    }


def _pos_histogram(pos):
    buckets = {"1": 0, "2": 0, "3_5": 0, "6_plus": 0}
    for count in pos.values():
        if count <= 1:
            buckets["1"] += 1
        elif count == 2:
            buckets["2"] += 1
        elif count <= 5:
            buckets["3_5"] += 1
        else:
            buckets["6_plus"] += 1
    return buckets


def _build_result(
    weapons, plane, solved, copies, pos, gfs, explicit_solved, credited_solved
):
    remaining = len(plane - solved)
    entries = []
    running_unsolved = len(plane)
    for copy in copies:
        running_unsolved -= len(copy["solved"])
        entries.append(_copy_entry(copy, gfs, pos, running_unsolved))

    by_hash = {w["hash"]: w for w in weapons}
    by_weapon = {}
    for entry in entries:
        row = by_weapon.get(entry["hash"])
        if row is None:
            model = by_hash.get(entry["hash"], {})
            row = {
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
                "gfs": entry["gfs"],
                "capacity": column_capacity(model) if model else 1,
                "col2_pool": sorted(model.get("col2", ())),
                "col3_pool": sorted(model.get("col3", ())),
                "pool_combos": len(model.get("all_pairs", ())),
                "copies": 0,
                "pairs_solved": 0,
            }
            by_weapon[entry["hash"]] = row
        row["copies"] += 1
        row["pairs_solved"] += entry["pairs_solved"]

    summary_rows = sorted(
        by_weapon.values(),
        key=lambda r: (
            0 if r["role"] == "preferred" else 1,
            -r["copies"],
            -r["pairs_solved"],
            r["name"].lower(),
        ),
    )

    preferred = [w for w in weapons if is_preferred_weapon(w)]
    fallback = [w for w in weapons if not is_preferred_weapon(w)]
    preferred_reachable = set()
    for weapon in preferred:
        preferred_reachable |= weapon["all_pairs"]

    top_gfs = [
        {
            "hash": w["hash"],
            "name": w["name"],
            "gfs": gfs.get(w["hash"], 0),
            "combos": len(w["all_pairs"]),
            "capacity": column_capacity(w),
        }
        for w in rank_weapons(weapons, gfs)[:15]
    ]

    plane_size = len(plane)
    return {
        "mode": "pos_gfs",
        "plane_size": plane_size,
        "pairs_unsolved": remaining,
        "lower_bound": (
            math.ceil(plane_size / (PREFERRED_PACK * PREFERRED_PACK))
            if plane_size else 0
        ),
        "total_copies": len(entries),
        "preferred_copies": sum(1 for e in entries if e["role"] == "preferred"),
        "fallback_copies": sum(1 for e in entries if e["role"] == "fallback"),
        "preferred_weapon_models": len(preferred),
        "fallback_weapon_models": len(fallback),
        "eligible_weapon_models": len(weapons),
        "craftable_weapon_models": sum(1 for w in weapons if w["is_craftable"]),
        "obtainable_weapon_models": sum(1 for w in weapons if w["is_obtainable"]),
        "unique_models_in_vault": len(by_weapon),
        "duplicated_models": sum(1 for r in by_weapon.values() if r["copies"] > 1),
        "duplicate_copies": sum(
            r["copies"] - 1 for r in by_weapon.values() if r["copies"] > 1
        ),
        "max_copies_one_model": max(
            (r["copies"] for r in by_weapon.values()), default=0
        ),
        "combination_mode": "unordered",
        "full_plane_size": plane_size,
        "combos_only_on_fallback": len(plane - preferred_reachable),
        "combos_explicit": explicit_solved,
        "combos_credited": credited_solved,
        "pos_histogram": _pos_histogram(pos),
        "top_gfs": top_gfs,
        "weapons": summary_rows,
        "copies": entries,
    }


if __name__ == "__main__":
    import time

    started = time.time()
    result = solve_pos_gfs()
    elapsed = time.time() - started
    print(
        f"[pos_gfs] plane={result['plane_size']} "
        f"copies={result['total_copies']} "
        f"models={result['unique_models_in_vault']}/"
        f"{result['eligible_weapon_models']} "
        f"duplicate_copies={result['duplicate_copies']} "
        f"max_copies={result['max_copies_one_model']} "
        f"unsolved={result['pairs_unsolved']} "
        f"explicit={result['combos_explicit']} "
        f"credited={result['combos_credited']} "
        f"({elapsed:.1f}s)"
    )
    print(f"POS histogram: {result['pos_histogram']}")
    print("Top GFS guns:")
    for row in result["top_gfs"][:8]:
        print(f"  {row['gfs']:>8}  {row['name']} ({row['combos']} combos)")
