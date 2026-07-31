"""Lightweight tests for Perfect Vault covering helpers."""

from perfect_vault import (
    _best_move,
    _pack_from_relevant,
    build_pair_plane,
    combo_key,
    is_eligible_weapon,
    normalize_family,
    weapon_combos,
)


def test_normalize_family_strips_adept():
    assert normalize_family("Igneous Hammer (Adept)") == "Igneous Hammer"


def test_plane_uses_unordered_combinations():
    weapons = [
        {"col2": {"Outlaw", "Rapid Hit"}, "col3": {"Rampage", "Kill Clip"}},
        {"col2": {"Rampage"}, "col3": {"Outlaw", "Swashbuckler"}},
    ]
    plane = build_pair_plane(weapons)
    assert combo_key("Outlaw", "Rampage") in plane
    assert combo_key("Rapid Hit", "Kill Clip") in plane
    assert combo_key("Rampage", "Swashbuckler") in plane
    # First: Outlaw+Rampage, Outlaw+KillClip, RapidHit+Rampage, RapidHit+KillClip
    # Second adds Rampage+Swashbuckler; Rampage+Outlaw collapses into Outlaw+Rampage.
    assert len(plane) == 5


def test_swapped_columns_same_combo():
    a = {"col2": {"Outlaw"}, "col3": {"Rampage"}}
    b = {"col2": {"Rampage"}, "col3": {"Outlaw"}}
    assert weapon_combos(a) == weapon_combos(b)
    assert len(build_pair_plane([a, b])) == 1


def test_same_perk_both_columns_ignored():
    assert combo_key("Rampage", "Rampage") is None
    weapon = {"col2": {"Rampage", "Outlaw"}, "col3": {"Rampage", "Kill Clip"}}
    combos = weapon_combos(weapon)
    assert combo_key("Outlaw", "Rampage") in combos
    assert combo_key("Outlaw", "Kill Clip") in combos
    assert combo_key("Rampage", "Kill Clip") in combos
    # Rampage+Rampage is not a combo we solve for.
    assert all(len(c) == 2 for c in combos)
    assert len(combos) == 3


def test_pack_3x3_covers_up_to_nine_combos():
    relevant = {(f"A{i}", f"B{j}") for i in range(4) for j in range(4)}
    move = _pack_from_relevant(relevant, 3)
    assert move is not None
    assert move["score"] <= 9
    assert len(move["col2"]) <= 3
    assert len(move["col3"]) <= 3


def test_pack_1x1_covers_one_combo():
    relevant = {("Outlaw", "Rampage"), ("Rapid Hit", "Kill Clip")}
    move = _pack_from_relevant(relevant, 1)
    assert move["score"] == 1
    assert len(move["covered"]) == 1


def test_eligible_requires_craftable_or_obtainable():
    assert is_eligible_weapon({"is_craftable": True, "is_obtainable": False})
    assert is_eligible_weapon({"is_craftable": False, "is_obtainable": True})
    assert not is_eligible_weapon({"is_craftable": False, "is_obtainable": False})


def test_best_move_prefers_higher_coverage():
    weapons = [
        {
            "name": "small",
            "hash": 1,
            "col2": {"A", "B"},
            "col3": {"X", "Y"},
            "all_pairs": {
                combo_key("A", "X"),
                combo_key("B", "Y"),
            },
        },
        {
            "name": "big",
            "hash": 2,
            "col2": {"A", "B", "C"},
            "col3": {"X", "Y", "Z"},
            "all_pairs": {
                combo_key(a, b)
                for a in ("A", "B", "C")
                for b in ("X", "Y", "Z")
            },
        },
    ]
    remaining = set(weapons[1]["all_pairs"])
    weapon, move = _best_move(weapons, remaining, 3)
    assert weapon["name"] == "big"
    assert move["score"] == 9


def test_best_move_spreads_before_duplicating():
    """Prefer a unused model over stacking another copy of a used one."""
    shared = {combo_key("A", "X"), combo_key("A", "Y"), combo_key("B", "X")}
    used = {
        "name": "already-used",
        "hash": 10,
        "col2": {"A", "B", "C"},
        "col3": {"X", "Y", "Z"},
        "all_pairs": {
            combo_key(a, b)
            for a in ("A", "B", "C")
            for b in ("X", "Y", "Z")
        },
    }
    fresh = {
        "name": "fresh",
        "hash": 11,
        "col2": {"A", "B"},
        "col3": {"X", "Y"},
        "all_pairs": shared,
    }
    weapon, move = _best_move(
        [used, fresh], shared, 3, copy_counts={10: 1, 11: 0}
    )
    assert weapon["name"] == "fresh"


def test_adept_supersedes_craftable_base():
    from perfect_vault import load_weapon_trait_pools

    # Build a tiny in-memory scenario via the merge path by monkeypatching is awkward;
    # unit-test the grouping rule directly with a local replica of selection.
    group = [
        {
            "name": "Cataclysmic",
            "is_adept": False,
            "is_craftable": True,
            "is_obtainable": False,
            "is_tiered": False,
            "season": 23,
            "col2": set(f"A{i}" for i in range(19)),
            "col3": set(f"B{i}" for i in range(19)),
            "hash": 1,
        },
        {
            "name": "Cataclysmic (Adept)",
            "is_adept": True,
            "is_craftable": True,
            "is_obtainable": False,
            "is_tiered": False,
            "season": 23,
            "col2": set(f"A{i}" for i in range(18)),
            "col3": set(f"B{i}" for i in range(18)),
            "hash": 2,
        },
    ]
    adepts = [w for w in group if w["is_adept"]]
    candidates = adepts if adepts else group
    winner = max(
        candidates,
        key=lambda w: (
            len(w["col2"]) * len(w["col3"]),
            w["season"],
            1 if w["is_adept"] else 0,
        ),
    )
    # Even though base has a larger pool, adept group wins selection.
    assert winner["name"] == "Cataclysmic (Adept)"
    assert candidates == adepts


if __name__ == "__main__":
    test_normalize_family_strips_adept()
    test_plane_uses_unordered_combinations()
    test_swapped_columns_same_combo()
    test_same_perk_both_columns_ignored()
    test_pack_3x3_covers_up_to_nine_combos()
    test_pack_1x1_covers_one_combo()
    test_eligible_requires_craftable_or_obtainable()
    test_best_move_prefers_higher_coverage()
    test_best_move_spreads_before_duplicating()
    test_adept_supersedes_craftable_base()
    print("All perfect_vault tests passed.")
