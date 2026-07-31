"""Lightweight tests for the POS / GFS vault solver."""

from perfect_vault import combo_key, weapon_combos
from pos_gfs_vault import (
    column_capacity,
    compute_gfs,
    compute_pos,
    rank_combos,
    rank_weapons,
    solve_pos_gfs,
)


def make_weapon(name, col2, col3, item_hash=None, **flags):
    weapon = {
        "hash": item_hash if item_hash is not None else abs(hash(name)) % 100000,
        "name": name,
        "family_name": name,
        "type": "Hand Cannon",
        "damage_type": "Solar",
        "ammo_type": "Primary",
        "icon": "",
        "season": 25,
        "is_tiered": flags.get("is_tiered", False),
        "is_adept": flags.get("is_adept", False),
        "is_vendor6": flags.get("is_vendor6", False),
        "is_craftable": flags.get("is_craftable", False),
        "is_obtainable": flags.get("is_obtainable", True),
        "col2": set(col2),
        "col3": set(col3),
    }
    weapon["all_pairs"] = weapon_combos(weapon)
    return weapon


def test_capacity_follows_flags():
    assert column_capacity(make_weapon("T", "a", "b", is_tiered=True)) == 3
    assert column_capacity(make_weapon("A", "a", "b", is_adept=True)) == 3
    assert column_capacity(make_weapon("V", "a", "b", is_vendor6=True)) == 3
    assert column_capacity(make_weapon("Plain", "a", "b")) == 1


def test_pos_counts_models_that_can_roll_each_combo():
    weapons = [
        make_weapon("Alpha", ["a1"], ["b1", "b2"]),
        make_weapon("Bravo", ["a1"], ["b1"]),
    ]
    pos = compute_pos(weapons)
    assert pos[combo_key("a1", "b1")] == 2
    assert pos[combo_key("a1", "b2")] == 1


def test_gfs_sums_pos_over_a_guns_combos():
    weapons = [
        make_weapon("Alpha", ["a1"], ["b1", "b2"]),
        make_weapon("Bravo", ["a1"], ["b1"]),
    ]
    pos = compute_pos(weapons)
    gfs = compute_gfs(weapons, pos)
    # Alpha rolls a1+b1 (POS 2) and a1+b2 (POS 1); Bravo rolls only a1+b1.
    assert gfs[weapons[0]["hash"]] == 3
    assert gfs[weapons[1]["hash"]] == 2


def test_rankings_put_rarest_combo_and_most_flexible_gun_first():
    weapons = [
        make_weapon("Alpha", ["a1"], ["b1", "b2"]),
        make_weapon("Bravo", ["a1"], ["b1"]),
    ]
    pos = compute_pos(weapons)
    gfs = compute_gfs(weapons, pos)
    assert rank_combos(pos)[0] == combo_key("a1", "b2")
    assert rank_weapons(weapons, gfs)[0]["name"] == "Alpha"


def test_open_copy_is_filled_before_a_second_model_is_used():
    # Two identical 3x3 guns: one copy of the first should absorb everything.
    weapons = [
        make_weapon("Alpha", ["a1", "a2"], ["b1", "b2"], is_tiered=True),
        make_weapon("Bravo", ["a1", "a2"], ["b1", "b2"], is_tiered=True),
    ]
    result = solve_pos_gfs(weapons=weapons)
    assert result["total_copies"] == 1
    assert result["unique_models_in_vault"] == 1
    assert result["pairs_unsolved"] == 0


def test_unused_model_is_used_before_a_duplicate():
    # 1x1 guns hold one combo per copy, so the ladder is visible copy by copy.
    weapons = [
        make_weapon("Alpha", ["a1", "a2"], ["b1", "b2"]),
        make_weapon("Bravo", ["a1", "a2"], ["b1", "b2"]),
    ]
    result = solve_pos_gfs(weapons=weapons)
    names = [copy["name"] for copy in result["copies"]]
    assert result["total_copies"] == 4
    assert names[0] == "Alpha"
    # Second combo starts Bravo's first copy rather than duplicating Alpha.
    assert names[1] == "Bravo"
    # Only once both models are in use do duplicates appear.
    assert result["duplicate_copies"] == 2
    assert result["pairs_unsolved"] == 0


def test_full_grid_credits_every_combo_it_rolls():
    weapons = [
        make_weapon(
            "Alpha", ["a1", "a2", "a3"], ["b1", "b2", "b3"], is_tiered=True
        )
    ]
    result = solve_pos_gfs(weapons=weapons)
    assert result["total_copies"] == 1
    copy = result["copies"][0]
    assert copy["pairs_solved"] == 9
    assert len(copy["col2_perks"]) == 3 and len(copy["col3_perks"]) == 3
    # Fewer explicit placements than combos solved: the rest come free.
    assert result["combos_explicit"] < 9
    assert result["combos_explicit"] + result["combos_credited"] == 9


def test_capacity_one_gun_gets_one_combo_per_copy():
    weapons = [make_weapon("Alpha", ["a1", "a2"], ["b1", "b2"])]
    result = solve_pos_gfs(weapons=weapons)
    assert result["total_copies"] == 4
    assert all(len(c["col2_perks"]) == 1 for c in result["copies"])
    assert all(c["pairs_solved"] == 1 for c in result["copies"])


def test_same_perk_in_both_columns_is_never_a_combo():
    weapons = [
        make_weapon("Alpha", ["Rampage", "Outlaw"], ["Rampage", "Kill Clip"],
                    is_tiered=True)
    ]
    result = solve_pos_gfs(weapons=weapons)
    assert result["plane_size"] == 3
    assert result["pairs_unsolved"] == 0
    for copy in result["copies"]:
        for pair in copy["sample_pairs"]:
            assert pair[0] != pair[1]


def test_3x3_guns_are_filled_before_any_1x1_gun_is_used():
    # Both guns roll a1+b1; only the 1x1 gun rolls a1+solo.
    weapons = [
        make_weapon("Grid", ["a1"], ["b1"], is_tiered=True),
        make_weapon("Single", ["a1"], ["b1", "solo"]),
    ]
    result = solve_pos_gfs(weapons=weapons)
    # The shared combo goes to the 3x3 gun even though the 1x1 gun has higher GFS.
    shared = [c for c in result["copies"] if "b1" in c["col3_perks"]]
    assert [c["name"] for c in shared] == ["Grid"]
    # The 1x1 gun is bought once, only for the combo nothing else can roll.
    gap_fill = [c for c in result["copies"] if c["role"] == "fallback"]
    assert len(gap_fill) == 1
    assert gap_fill[0]["col3_perks"] == ["solo"]
    assert result["pairs_unsolved"] == 0


def test_gap_fill_copies_match_combos_only_1x1_guns_can_roll():
    weapons = [
        make_weapon("Grid", ["a1", "a2"], ["b1", "b2"], is_tiered=True),
        make_weapon("Single", ["a1", "a2"], ["b1", "x1", "x2"]),
    ]
    result = solve_pos_gfs(weapons=weapons)
    # a1+x1, a1+x2, a2+x1, a2+x2 exist only on the 1x1 gun.
    assert result["combos_only_on_fallback"] == 4
    assert result["fallback_copies"] == 4
    assert result["pairs_unsolved"] == 0


def test_rare_combo_lands_on_the_most_flexible_gun():
    # Both guns roll the rare combo; Alpha has the wider pool, so higher GFS.
    weapons = [
        make_weapon("Alpha", ["a1"], ["rare", "b1", "b2"], is_tiered=True),
        make_weapon("Bravo", ["a1"], ["rare"], is_tiered=True),
    ]
    result = solve_pos_gfs(weapons=weapons)
    assert result["copies"][0]["name"] == "Alpha"
    assert result["unique_models_in_vault"] == 1


def test_pos_histogram_buckets_by_rarity():
    weapons = [
        make_weapon("Alpha", ["a1"], ["b1", "b2"]),
        make_weapon("Bravo", ["a1"], ["b1"]),
    ]
    result = solve_pos_gfs(weapons=weapons)
    assert result["pos_histogram"]["1"] == 1
    assert result["pos_histogram"]["2"] == 1


if __name__ == "__main__":
    test_capacity_follows_flags()
    test_pos_counts_models_that_can_roll_each_combo()
    test_gfs_sums_pos_over_a_guns_combos()
    test_rankings_put_rarest_combo_and_most_flexible_gun_first()
    test_open_copy_is_filled_before_a_second_model_is_used()
    test_unused_model_is_used_before_a_duplicate()
    test_full_grid_credits_every_combo_it_rolls()
    test_capacity_one_gun_gets_one_combo_per_copy()
    test_same_perk_in_both_columns_is_never_a_combo()
    test_3x3_guns_are_filled_before_any_1x1_gun_is_used()
    test_gap_fill_copies_match_combos_only_1x1_guns_can_roll()
    test_rare_combo_lands_on_the_most_flexible_gun()
    test_pos_histogram_buckets_by_rarity()
    print("All pos_gfs_vault tests passed.")
