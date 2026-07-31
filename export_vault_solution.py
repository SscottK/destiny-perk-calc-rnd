"""Dump a vault solution (CSV + TXT roll plan) for any solver mode.

Usage:
    python export_vault_solution.py                 # every mode
    python export_vault_solution.py pos_gfs         # one mode
    python export_vault_solution.py full pos_gfs    # a few modes

Writes vault_solution_<mode>.csv and vault_solution_<mode>.txt.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from perfect_vault import get_perfect_vault

MODES = ("full", "preferred_only", "pos_gfs")

CSV_FIELDS = (
    "copy_index",
    "weapon",
    "role",
    "type",
    "damage_type",
    "is_tiered",
    "is_adept",
    "is_vendor6",
    "is_craftable",
    "is_obtainable",
    "col2_perks",
    "col3_perks",
    "combos_solved",
    "best_pos",
    "gfs",
    "sample_combos",
    "hash",
)


def _sample_text(copy):
    return " | ".join(
        "+".join(pair) for pair in copy.get("sample_pairs", [])
    )


def write_csv(result, path: Path):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for copy in result["copies"]:
            writer.writerow({
                "copy_index": copy["copy_index"],
                "weapon": copy["name"],
                "role": copy["role"],
                "type": copy["type"],
                "damage_type": copy["damage_type"],
                "is_tiered": int(bool(copy["is_tiered"])),
                "is_adept": int(bool(copy["is_adept"])),
                "is_vendor6": int(bool(copy.get("is_vendor6"))),
                "is_craftable": int(bool(copy["is_craftable"])),
                "is_obtainable": int(bool(copy["is_obtainable"])),
                "col2_perks": ", ".join(copy["col2_perks"]),
                "col3_perks": ", ".join(copy["col3_perks"]),
                "combos_solved": copy["pairs_solved"],
                "best_pos": copy.get("best_pos", ""),
                "gfs": copy.get("gfs", ""),
                "sample_combos": _sample_text(copy),
                "hash": copy["hash"],
            })


def _header_lines(result):
    mode = result["mode"]
    lines = [
        f"PERFECT VAULT SOLUTION ({mode} mode)",
        f"Unordered trait combos in plane: {result['plane_size']}",
        f"Total physical copies: {result['total_copies']}",
        f"Preferred 3x3 copies: {result['preferred_copies']}",
        f"Gap-fill 1x1 copies: {result['fallback_copies']}",
        f"Distinct weapon models: {result['unique_models_in_vault']}",
        f"Models needing duplicates: {result.get('duplicated_models', 0)}",
        f"Most copies of one model: {result.get('max_copies_one_model', 0)}",
        f"Unsolved: {result['pairs_unsolved']}",
    ]
    if mode == "pos_gfs":
        hist = result.get("pos_histogram") or {}
        lines += [
            f"Combos placed directly: {result.get('combos_explicit', 0)}",
            f"Combos credited from filled grids: {result.get('combos_credited', 0)}",
            "POS histogram (combos by how many models can roll them): "
            f"POS 1={hist.get('1', 0)}, 2={hist.get('2', 0)}, "
            f"3-5={hist.get('3_5', 0)}, 6+={hist.get('6_plus', 0)}",
        ]
    lines += [
        "",
        "Each entry is one physical vault gun.",
        "Preferred: roll the listed perks in trait column 2 and column 3 "
        "(up to 3 each = 3x3).",
        "Gap-fill: roll exactly that one combo (1x1).",
        "Combinations are unordered: A+B is the same as B+A globally.",
    ]
    return lines


def write_txt(result, path: Path):
    lines = _header_lines(result)
    bar = "=" * 72

    lines += ["", bar, "SUMMARY BY WEAPON (copies needed)", bar]
    for row in result["weapons"]:
        gfs = f"  GFS {row['gfs']}" if "gfs" in row else ""
        lines.append(
            f"x{row['copies']:>3}  [{row['role']:<9}]  {row['name']}  "
            f"({row['pairs_solved']} combos covered){gfs}"
        )

    if result["mode"] == "pos_gfs" and result.get("top_gfs"):
        lines += ["", bar, "MOST FLEXIBLE GUNS (highest GFS)", bar]
        for row in result["top_gfs"]:
            lines.append(
                f"GFS {row['gfs']:>8}  {row['name']}  "
                f"({row['combos']} combos, {row['capacity']}x{row['capacity']})"
            )

    lines += ["", bar, "COPY-BY-COPY ROLL PLAN", bar]
    for copy in result["copies"]:
        lines.append(
            f"#{copy['copy_index']}  {copy['name']}  [{copy['role']}]  "
            f"{copy['type']} / {copy['damage_type']}"
        )
        lines.append(f"    Column 2: {', '.join(copy['col2_perks'])}")
        lines.append(f"    Column 3: {', '.join(copy['col3_perks'])}")
        detail = f"    Solves {copy['pairs_solved']} combo(s)"
        if copy.get("best_pos") is not None:
            detail += f", rarest POS {copy['best_pos']}"
        lines.append(detail)
        sample = _sample_text(copy)
        if sample:
            lines.append(f"    {sample}")
        lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_mode(mode, out_dir: Path = Path(".")):
    result = get_perfect_vault(mode=mode)
    csv_path = out_dir / f"vault_solution_{mode}.csv"
    txt_path = out_dir / f"vault_solution_{mode}.txt"
    write_csv(result, csv_path)
    write_txt(result, txt_path)
    print(
        f"[{mode}] {result['total_copies']} copies, "
        f"{result['unique_models_in_vault']} models -> {csv_path}, {txt_path}"
    )
    return csv_path, txt_path


def main(argv):
    modes = argv[1:] or list(MODES)
    for mode in modes:
        if mode not in MODES:
            raise SystemExit(f"Unknown mode {mode!r}; pick from {', '.join(MODES)}")
        export_mode(mode)


if __name__ == "__main__":
    main(sys.argv)
