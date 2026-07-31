# The Perfect Vault — snapshot, 2026-07-30

This is a frozen write-up of where the Perfect Vault project stands right now.
It is a reference document only; nothing in the app reads it. It covers what the
solver does, why, what it currently produces, and then lists the complete
solution: every gun to keep and the exact perks each copy should roll.

---

## 1. The question

Destiny weapons roll two trait columns. A "combo" is one perk from each column,
and order does not matter: A+B and B+A are the same roll, and A+A is not a combo
at all. Across every gun you can currently earn, there are **9,423 distinct
trait combinations**. The question the app answers is: what is the smallest set
of physical guns — and the exact perks on each — that puts every one of those
combinations in your vault?

## 2. Which guns count

The universe is built from the local weapon database, restricted to Legendary
weapons that are current, and then filtered to guns that are actually reachable:

- **Obtainable** — driven by a Google Sheet of currently-farmable weapons, synced
  by `sync_obtainability_sheet.py`. Sheet names are matched to database names by
  exact match, a small alias table, and fuzzy fallback; all 601 rows match today.
- **Craftable** — taken from the manifest (`inventory.recipeItemHash`).

A gun is eligible if it is obtainable **or** craftable. Duplicates are then
collapsed: weapons are grouped by family name plus damage type, an adept version
supersedes the base/craftable version of the same raid gun, and otherwise the
newest and largest real perk pool wins. That leaves **580 distinct models**,
of which 375 pack 3x3 and 205 pack 1x1.

## 3. How many perks one copy can hold

A single physical gun can only hold what it drops with:

- **3x3 (called "preferred")** — up to three perks in each column, so one copy
  covers up to nine combos at once. This applies to tiered weapons, adept
  weapons, and the Zavala / Drifter / Shaxx vendor guns that drop with six perks
  regardless of tier.
- **1x1 (called "gap-fill")** — one perk per column, so one copy is worth exactly
  one combo.

The vendor 6-perk case used to be smuggled into the `is_tiered` flag. It is now
its own `is_vendor6` column in the schema, the migration, `weapon_flags.py`, and
the sheet sync, so the capacity rule is auditable: capacity is 3 when a gun is
tiered, adept, or vendor6, and 1 otherwise. 141 guns in the current
solution carry the vendor6 flag.

## 4. The scoring: POS and GFS

Two numbers drive the whole solve.

- **POS — Perk Occurance Score.** For a combo, the number of eligible models that
  can roll it. Low POS means rare, and rare combos are the constraint, so they
  get solved first. Today: 3,598 combos have POS 1, 1,813 have POS 2,
  2,374 have POS 3-5, and 1,638 have POS 6 or more.
- **GFS — Gun Flexibility Score.** For a gun, the sum of POS across every combo it
  can roll. High GFS means the gun sits on a lot of the plane, so it is the
  preferred home for a rare combo. It is a reach score, not a quality score: a
  1x1 gun with a big pool of popular perks can score high while still only
  holding one combo per copy.

Both are computed once, up front, over the whole eligible universe.

## 5. The allocation

Solving runs in **two phases so the 3x3 guns do as much work as possible**:

1. **Phase one** solves every combo that any 3x3 gun can reach, using only 3x3
   guns.
2. **Phase two** gap-fills what is left — combos that exist on no 3x3 gun — with
   1x1 guns.

That ordering matters: it guarantees a 1x1 copy is never bought for a combo a
3x3 gun could have absorbed, and it drops the gap-fill count to its theoretical
floor.

Within a phase, combos are walked rarest-first (lowest POS). For each one, the
guns that can roll it are considered highest-GFS first, and the solver climbs a
three-rung ladder:

1. **Top up a copy already in the vault**, preferring the fit that adds the
   fewest new perks, then the higher GFS gun.
2. Otherwise **start the first copy of a model that has no copy yet**.
3. Only if neither works, **duplicate** the highest-GFS candidate.

After each placement, every combo the copy's grid now rolls is credited as
solved, not just the one that was asked for. A 3x3 grid filled to 3+3 realizes
nine combos, so filling grids pays for itself: 6,352 combos were placed
deliberately and another 3,071 came free from completed grids.

## 6. What it produces

| Measure | Value |
|---|---|
| Distinct trait combos to cover | 9,423 |
| Total physical copies to keep | **2,547** |
| Distinct guns | 551 |
| 3x3 preferred copies | 1,282 |
| 1x1 gap-fill copies | 1,265 |
| Guns needing more than one copy | 471 |
| Most copies of a single gun | 32 |
| Combos left unsolved | 0 |
| Theoretical lower bound (plane / 9) | 1,047 |

Against the earlier greedy set-cover solvers, on the identical universe:

| Solver | Copies | Distinct guns | 3x3 copies | 1x1 copies | Runtime |
|---|---|---|---|---|---|
| Greedy, all guns | 2,883 | 559 | 1,619 | 1,264 | ~31s |
| Greedy, 3x3 only (covers 8,158 of the plane) | 1,618 | 373 | 1,618 | 0 | ~25s |
| **POS / GFS, 3x3 first** | **2,547** | **551** | **1,282** | **1,265** | **~0.3s** |

Two things worth noticing:

- The gap-fill number, 1,265, is exactly the number of combos that exist on
  no 3x3 gun. Since a 1x1 copy is worth one combo, that part of the answer is
  provably minimal — it cannot be improved without new guns entering the game.
- The 3x3 side covers 8,158 combos in 1,282 copies. The absolute floor there
  is 1,047 (nine combos per copy with zero waste), so the remaining headroom
  in the whole problem lives here.

## 7. Where the count comes from

The vault is large not because any single combo is hard, but because the plane is
large and lopsided. 3,598 of the 9,423 combos can be rolled on exactly one gun in
the game, so they can never be shared or consolidated. On top of that, 1,265
combos only exist on guns that drop with one perk per column, and each of those
costs a full copy on its own.

## 8. The code

| File | Role |
|---|---|
| `pos_gfs_vault.py` | POS, GFS, capacity, the two-phase allocator, metrics |
| `perfect_vault.py` | Universe loading, eligibility, combo helpers, the two older greedy solvers |
| `weapon_flags.py` | Detects and persists is_tiered / is_adept / is_vendor6 / is_craftable / is_obtainable |
| `sync_obtainability_sheet.py` | Parses the obtainable-weapons sheet into the overlays |
| `export_vault_solution.py` | Writes `vault_solution_<mode>.csv` and `.txt` for any solver |
| `test_pos_gfs_vault.py` | POS/GFS math, capacity by flag, ladder order, phase order, grid crediting, A != A |
| `app.py`, `templates/index.html` | The web view: solution first, older solvers and reference lists behind secondary controls |

## 9. Open threads

- The 3x3 phase spends 1,282 copies against a floor of 1,047. Choosing which
  3x3 gun takes a combo purely by GFS is a heuristic; a smarter rule, or a
  clean-up pass that merges under-filled grids, is the obvious next lever.
- Guns are still duplicated heavily (471 models need more than one copy, up to
  32). Some of that is forced by 1x1 capacity, some is not.
- Nothing here weighs whether a combo is worth owning. Every combination counts
  the same, including ones nobody would ever chase.

---

# The current solution

Below is the full plan: every gun to keep, its complete perk pool, and the exact
perks each copy should roll. 3x3 preferred guns come first, then 1x1 gap-fill
guns; within each group, guns needing the most copies come first.

How to read an entry: `Pool` is everything the gun can roll in each column.
`Copy N` lines are the physical guns to keep and the perks to roll on them —
for a 3x3 gun, every pairing of its column 2 and column 3 perks is covered.

Totals: 366 preferred guns / 1,282 copies, 185 gap-fill guns / 1,265 copies.


## 3x3 preferred guns

Each copy carries up to three perks per column, covering up to nine combinations at once.


### Blowout
Rocket Launcher · Arc · vendor 6-perk, obtainable · GFS 1,083 · pool 156 combos · 14 copies · 87 combos covered
- Pool col 2 (12): Ambitious Assassin, Danger Zone, Demolitionist, Ensemble, Field Prep, Genesis, Impulse Amplifier, Stats for All, Sympathetic Arsenal, Thresh, Tracking Module, Turnabout
- Pool col 3 (13): Adrenaline Junkie, Chain Reaction, Cluster Bomb, Disruption Break, Explosive Light, Frenzy, Golden Tricorn, Golden Tricorn Enhanced, Harmony, Lasting Impression, Multikill Clip, Swashbuckler, Vorpal Weapon
- Copy 1: [Ensemble, Stats for All, Thresh] x [Cluster Bomb, Golden Tricorn, Golden Tricorn Enhanced] — 9 combos
- Copy 2: [Danger Zone, Sympathetic Arsenal, Tracking Module] x [Disruption Break, Golden Tricorn, Golden Tricorn Enhanced] — 9 combos
- Copy 3: [Stats for All, Sympathetic Arsenal, Tracking Module] x [Frenzy, Harmony, Lasting Impression] — 8 combos
- Copy 4: [Sympathetic Arsenal, Thresh, Turnabout] x [Lasting Impression, Multikill Clip, Swashbuckler] — 8 combos
- Copy 5: [Danger Zone, Sympathetic Arsenal, Tracking Module] x [Multikill Clip, Swashbuckler, Vorpal Weapon] — 6 combos
- Copy 6: [Genesis, Sympathetic Arsenal, Turnabout] x [Chain Reaction, Cluster Bomb, Disruption Break] — 4 combos
- Copy 7: [Genesis, Sympathetic Arsenal, Thresh] x [Adrenaline Junkie, Explosive Light, Lasting Impression] — 6 combos
- Copy 8: [Ensemble, Impulse Amplifier, Turnabout] x [Explosive Light, Golden Tricorn, Golden Tricorn Enhanced] — 5 combos
- Copy 9: [Danger Zone, Ensemble, Thresh] x [Chain Reaction, Cluster Bomb, Disruption Break] — 4 combos
- Copy 10: [Demolitionist, Impulse Amplifier, Turnabout] x [Cluster Bomb, Disruption Break, Harmony] — 6 combos
- Copy 11: [Ambitious Assassin, Genesis, Thresh] x [Frenzy, Harmony, Multikill Clip] — 7 combos
- Copy 12: [Ambitious Assassin, Demolitionist] x [Cluster Bomb, Golden Tricorn, Golden Tricorn Enhanced] — 5 combos
- Copy 13: [Danger Zone, Demolitionist, Tracking Module] x [Explosive Light, Frenzy, Multikill Clip] — 5 combos
- Copy 14: [Ambitious Assassin, Ensemble, Thresh] x [Adrenaline Junkie, Chain Reaction, Vorpal Weapon] — 5 combos

### Albruna-D
Sniper Rifle · Arc · vendor 6-perk, obtainable · GFS 1,169 · pool 156 combos · 12 copies · 74 combos covered
- Pool col 2 (12): Air Assault, Clown Cartridge, Elemental Capacitor, Ensemble, Explosive Payload, Field Prep, Moving Target, No Distractions, Perpetual Motion, Surplus, Triple Tap, Wellspring
- Pool col 3 (13): Cascade Point, Eye of the Storm, Firing Line, Frenzy, Golden Tricorn, Golden Tricorn Enhanced, Harmony, High-Impact Reserves, Opening Shot, Slickdraw, Snapshot Sights, Under-Over, Vorpal Weapon
- Copy 1: [Air Assault, Explosive Payload, Wellspring] x [Cascade Point, Firing Line, High-Impact Reserves] — 9 combos
- Copy 2: [Air Assault, Clown Cartridge, Explosive Payload] x [Slickdraw, Snapshot Sights, Under-Over] — 8 combos
- Copy 3: [Air Assault, Elemental Capacitor, Explosive Payload] x [Firing Line, Golden Tricorn, Golden Tricorn Enhanced] — 7 combos
- Copy 4: [Elemental Capacitor, Field Prep, Triple Tap] x [Harmony, Slickdraw, Under-Over] — 8 combos
- Copy 5: [Elemental Capacitor, Explosive Payload, Triple Tap] x [Harmony, High-Impact Reserves, Vorpal Weapon] — 5 combos
- Copy 6: [Moving Target, No Distractions, Perpetual Motion] x [Cascade Point, Slickdraw, Under-Over] — 8 combos
- Copy 7: [Air Assault, Surplus, Wellspring] x [Slickdraw, Snapshot Sights, Vorpal Weapon] — 6 combos
- Copy 8: [Air Assault, Ensemble, Wellspring] x [Cascade Point, Harmony, Opening Shot] — 4 combos
- Copy 9: [Ensemble, Surplus, Triple Tap] x [Eye of the Storm, Golden Tricorn, Under-Over] — 5 combos
- Copy 10: [Elemental Capacitor, No Distractions, Wellspring] x [Eye of the Storm, Frenzy, Snapshot Sights] — 4 combos
- Copy 11: [Clown Cartridge, Field Prep, Moving Target] x [Frenzy, Golden Tricorn Enhanced, Vorpal Weapon] — 6 combos
- Copy 12: [Perpetual Motion, Surplus, Triple Tap] x [Eye of the Storm, Frenzy, Golden Tricorn] — 4 combos

### Joxer's Longsword
Pulse Rifle · Void · tiered, vendor 6-perk, obtainable · GFS 923 · pool 144 combos · 11 copies · 69 combos covered
- Pool col 2 (12): Closing Time, Demolitionist, Dragonfly, Enlightened Action, Gutshot Straight, Killing Wind, Lone Wolf, Pugilist, Repulsor Brace, Rewind Rounds, Shoot to Loot, Strategist
- Pool col 3 (12): Adrenaline Junkie, Demoralize, Desperado, Desperate Measures, Destabilizing Rounds, Headseeker, High-Impact Reserves, One for All, Swashbuckler, Under Pressure, Withering Gaze, Zen Moment
- Copy 1: [Closing Time, Enlightened Action, Gutshot Straight] x [Demoralize, Destabilizing Rounds, Withering Gaze] — 8 combos
- Copy 2: [Pugilist, Rewind Rounds, Strategist] x [Demoralize, Desperado, Headseeker] — 8 combos
- Copy 3: [Enlightened Action, Gutshot Straight, Repulsor Brace] x [Desperado, High-Impact Reserves, Under Pressure] — 8 combos
- Copy 4: [Killing Wind, Rewind Rounds, Strategist] x [High-Impact Reserves, Under Pressure, Withering Gaze] — 8 combos
- Copy 5: [Closing Time, Dragonfly, Gutshot Straight] x [Desperado, Desperate Measures, Withering Gaze] — 4 combos
- Copy 6: [Lone Wolf, Pugilist, Shoot to Loot] x [High-Impact Reserves, Under Pressure, Withering Gaze] — 9 combos
- Copy 7: [Closing Time, Shoot to Loot, Strategist] x [Adrenaline Junkie, Headseeker, Zen Moment] — 8 combos
- Copy 8: [Closing Time, Demolitionist, Killing Wind] x [Desperado, One for All, Withering Gaze] — 5 combos
- Copy 9: [Dragonfly, Gutshot Straight, Killing Wind] x [Demoralize, Swashbuckler, Zen Moment] — 4 combos
- Copy 10: [Closing Time, Killing Wind, Pugilist] x [Desperate Measures, Destabilizing Rounds, Swashbuckler] — 3 combos
- Copy 11: [Demolitionist, Lone Wolf, Repulsor Brace] x [Headseeker, One for All, Swashbuckler] — 4 combos

### Strident Whistle
Combat Bow · Solar · vendor 6-perk, obtainable · GFS 1,101 · pool 144 combos · 10 copies · 68 combos covered
- Pool col 2 (12): Archer's Tempo, Ensemble, Killing Wind, Moving Target, No Distractions, Perpetual Motion, Quickdraw, Rangefinder, Shoot to Loot, Sneak Bow, Surplus, Well-Rounded
- Pool col 3 (12): Adrenaline Junkie, Cornered, Dragonfly, Explosive Head, Harmony, Incandescent, Opening Shot, Rampage, Successful Warm-Up, Turnabout, Vorpal Weapon, Wellspring
- Copy 1: [Moving Target, No Distractions, Sneak Bow] x [Adrenaline Junkie, Cornered, Explosive Head] — 9 combos
- Copy 2: [Ensemble, Sneak Bow, Well-Rounded] x [Explosive Head, Incandescent, Turnabout] — 8 combos
- Copy 3: [Archer's Tempo, Quickdraw, Sneak Bow] x [Incandescent, Successful Warm-Up, Vorpal Weapon] — 8 combos
- Copy 4: [Archer's Tempo, Killing Wind, Quickdraw] x [Cornered, Turnabout, Wellspring] — 9 combos
- Copy 5: [Quickdraw, Rangefinder, Surplus] x [Cornered, Explosive Head, Turnabout] — 5 combos
- Copy 6: [Killing Wind, Moving Target, No Distractions] x [Explosive Head, Successful Warm-Up, Turnabout] — 6 combos
- Copy 7: [Archer's Tempo, Shoot to Loot, Sneak Bow] x [Harmony, Rampage, Wellspring] — 7 combos
- Copy 8: [Perpetual Motion, Shoot to Loot, Sneak Bow] x [Cornered, Dragonfly, Explosive Head] — 4 combos
- Copy 9: [Archer's Tempo, Sneak Bow, Well-Rounded] x [Adrenaline Junkie, Dragonfly, Opening Shot] — 6 combos
- Copy 10: [Rangefinder, Shoot to Loot, Surplus] x [Harmony, Incandescent, Successful Warm-Up] — 6 combos

### Embraced Identity
Sniper Rifle · Void · tiered, craftable, obtainable · GFS 594 · pool 99 combos · 10 copies · 67 combos covered
- Pool col 2 (10): Attrition Orbs, Demolitionist, Destabilizing Rounds, Empty Traits Socket, Opening Shot, Permeability, Reconstruction, Rewind Rounds, Vorpal Weapon, Withering Gaze
- Pool col 3 (10): Aggregate Charge, Box Breathing, Elemental Capacitor, Elemental Honing, Empty Traits Socket, Fourth Time's the Charm, High Ground, Moving Target, Precision Instrument, Redirection
- Copy 1: [Attrition Orbs, Permeability, Vorpal Weapon] x [Aggregate Charge, Box Breathing, Elemental Capacitor] — 9 combos
- Copy 2: [Destabilizing Rounds, Opening Shot, Withering Gaze] x [Box Breathing, Elemental Capacitor, Redirection] — 9 combos
- Copy 3: [Permeability, Vorpal Weapon, Withering Gaze] x [Elemental Honing, Fourth Time's the Charm, High Ground] — 9 combos
- Copy 4: [Empty Traits Socket, Opening Shot, Reconstruction] x [Fourth Time's the Charm, High Ground, Redirection] — 8 combos
- Copy 5: [Permeability, Vorpal Weapon, Withering Gaze] x [Moving Target, Precision Instrument, Redirection] — 7 combos
- Copy 6: [Destabilizing Rounds, Opening Shot, Rewind Rounds] x [Aggregate Charge, Box Breathing, High Ground] — 5 combos
- Copy 7: [Attrition Orbs, Demolitionist, Rewind Rounds] x [Box Breathing, Fourth Time's the Charm, Redirection] — 7 combos
- Copy 8: [Destabilizing Rounds, Rewind Rounds, Withering Gaze] x [Empty Traits Socket, Moving Target, Precision Instrument] — 7 combos
- Copy 9: [Empty Traits Socket, Reconstruction] x [Box Breathing, Moving Target, Precision Instrument] — 3 combos
- Copy 10: [Demolitionist, Permeability] x [Empty Traits Socket, High Ground] — 3 combos

### Retrofuturist
Shotgun · Void · tiered, vendor 6-perk, obtainable · GFS 1,011 · pool 144 combos · 10 copies · 66 combos covered
- Pool col 2 (12): Auto-Loading Holster, Dual Loader, Feeding Frenzy, Hip-Fire Grip, Loose Change, Pugilist, Pulse Monitor, Quickdraw, Shot Swap, Slickdraw, Stats for All, Unrelenting
- Pool col 3 (12): Barrel Constrictor, Deconstruct, Destabilizing Rounds, Envious Assassin, Frenzy, High Ground, One for All, Snapshot Sights, Swashbuckler, Thresh, Trench Barrel, Vorpal Weapon
- Copy 1: [Auto-Loading Holster, Feeding Frenzy, Hip-Fire Grip] x [Barrel Constrictor, Deconstruct, Envious Assassin] — 8 combos
- Copy 2: [Pulse Monitor, Quickdraw, Shot Swap] x [Barrel Constrictor, Envious Assassin, Trench Barrel] — 9 combos
- Copy 3: [Dual Loader, Stats for All, Unrelenting] x [Barrel Constrictor, Deconstruct, Envious Assassin] — 9 combos
- Copy 4: [Dual Loader, Loose Change, Unrelenting] x [One for All, Snapshot Sights, Trench Barrel] — 6 combos
- Copy 5: [Dual Loader, Quickdraw, Stats for All] x [Destabilizing Rounds, High Ground, Trench Barrel] — 7 combos
- Copy 6: [Loose Change, Pulse Monitor, Slickdraw] x [Envious Assassin, High Ground, Thresh] — 8 combos
- Copy 7: [Pugilist, Shot Swap, Unrelenting] x [Barrel Constrictor, One for All, Swashbuckler] — 3 combos
- Copy 8: [Auto-Loading Holster, Dual Loader, Slickdraw] x [Barrel Constrictor, Destabilizing Rounds, Frenzy] — 6 combos
- Copy 9: [Auto-Loading Holster, Pugilist, Slickdraw] x [High Ground, Snapshot Sights, Trench Barrel] — 6 combos
- Copy 10: [Hip-Fire Grip, Loose Change, Quickdraw] x [Deconstruct, Frenzy, High Ground] — 4 combos

### Double-Edged Answer
Sword · Void · vendor 6-perk, obtainable · GFS 1,022 · pool 144 combos · 10 copies · 65 combos covered
- Pool col 2 (12): Demolitionist, Duelist's Trance, En Garde, Energy Transfer, Flash Counter, Pugilist, Relentless Strikes, Repulsor Brace, Thresh, Tireless Blade, Unrelenting, Wellspring
- Pool col 3 (12): Adrenaline Junkie, Assassin's Blade, Attrition Orbs, Collective Action, Counterattack, Destabilizing Rounds, Harmony, One for All, Surrounded, Valiant Charge, Vorpal Weapon, Whirlwind Blade
- Copy 1: [En Garde, Energy Transfer, Pugilist] x [Adrenaline Junkie, Assassin's Blade, Attrition Orbs] — 8 combos
- Copy 2: [En Garde, Pugilist, Repulsor Brace] x [Collective Action, Counterattack, Destabilizing Rounds] — 9 combos
- Copy 3: [En Garde, Energy Transfer, Flash Counter] x [Harmony, One for All, Vorpal Weapon] — 9 combos
- Copy 4: [Demolitionist, Pugilist, Repulsor Brace] x [Assassin's Blade, Valiant Charge, Whirlwind Blade] — 8 combos
- Copy 5: [Demolitionist, Flash Counter, Tireless Blade] x [Attrition Orbs, Counterattack, Destabilizing Rounds] — 6 combos
- Copy 6: [Relentless Strikes, Thresh, Wellspring] x [Adrenaline Junkie, Attrition Orbs, Counterattack] — 4 combos
- Copy 7: [Energy Transfer, Thresh, Wellspring] x [Collective Action, Destabilizing Rounds, Valiant Charge] — 8 combos
- Copy 8: [Duelist's Trance, Repulsor Brace, Unrelenting] x [Attrition Orbs, Harmony, Valiant Charge] — 5 combos
- Copy 9: [Flash Counter, Relentless Strikes, Wellspring] x [One for All, Valiant Charge, Whirlwind Blade] — 4 combos
- Copy 10: [Energy Transfer, Relentless Strikes, Unrelenting] x [Collective Action, Counterattack, Whirlwind Blade] — 4 combos

### Laser Painter
Linear Fusion Rifle · Strand · tiered, vendor 6-perk, obtainable · GFS 1,119 · pool 156 combos · 10 copies · 63 combos covered
- Pool col 2 (12): Auto-Loading Holster, Clown Cartridge, Compulsive Reloader, Encore, Ensemble, Fragile Focus, Invisible Hand, Moving Target, No Distractions, Outlaw, Rapid Hit, Stats for All
- Pool col 3 (13): Box Breathing, Demolitionist, Focused Fury, Golden Tricorn, Golden Tricorn Enhanced, Harmony, Hatchling, High-Impact Reserves, Hip-Fire Grip, Thresh, Unrelenting, Vorpal Weapon, Wellspring
- Copy 1: [Clown Cartridge, Encore, Invisible Hand] x [Box Breathing, Demolitionist, Hip-Fire Grip] — 8 combos
- Copy 2: [Compulsive Reloader, Ensemble, Fragile Focus] x [Hip-Fire Grip, Thresh, Unrelenting] — 9 combos
- Copy 3: [Invisible Hand, No Distractions, Rapid Hit] x [High-Impact Reserves, Hip-Fire Grip, Unrelenting] — 8 combos
- Copy 4: [Auto-Loading Holster, Invisible Hand, Stats for All] x [Box Breathing, Hip-Fire Grip, Wellspring] — 6 combos
- Copy 5: [Compulsive Reloader, Encore, Ensemble] x [Hatchling, High-Impact Reserves, Unrelenting] — 6 combos
- Copy 6: [Fragile Focus, Invisible Hand, No Distractions] x [Hatchling, High-Impact Reserves, Thresh] — 5 combos
- Copy 7: [Encore, Fragile Focus, Invisible Hand] x [Focused Fury, Harmony, Vorpal Weapon] — 6 combos
- Copy 8: [Auto-Loading Holster, Moving Target, Stats for All] x [Box Breathing, Golden Tricorn, High-Impact Reserves] — 6 combos
- Copy 9: [Encore, No Distractions, Outlaw] x [Golden Tricorn, Harmony, Wellspring] — 6 combos
- Copy 10: [Moving Target, Rapid Hit, Stats for All] x [Golden Tricorn Enhanced, Unrelenting, Wellspring] — 3 combos

### Origin Story
Auto Rifle · Kinetic · tiered, vendor 6-perk, obtainable · GFS 1,056 · pool 144 combos · 10 copies · 62 combos covered
- Pool col 2 (12): Attrition Orbs, Demolitionist, Discord, Dynamic Sway Reduction, Feeding Frenzy, Fragile Focus, Hip-Fire Grip, Keep Away, Slideways, Strategist, Threat Detector, Zen Moment
- Pool col 3 (12): Eye of the Storm, Gutshot Straight, Harmony, High Ground, Kinetic Tremors, Onslaught, Pugilist, Rampage, Snapshot Sights, Surrounded, Swashbuckler, Target Lock
- Copy 1: [Attrition Orbs, Discord, Fragile Focus] x [Gutshot Straight, Kinetic Tremors, Snapshot Sights] — 9 combos
- Copy 2: [Fragile Focus, Slideways, Strategist] x [High Ground, Kinetic Tremors, Onslaught] — 8 combos
- Copy 3: [Attrition Orbs, Demolitionist, Discord] x [Onslaught, Pugilist, Swashbuckler] — 8 combos
- Copy 4: [Hip-Fire Grip, Keep Away, Slideways] x [Gutshot Straight, Kinetic Tremors, Onslaught] — 6 combos
- Copy 5: [Slideways, Threat Detector, Zen Moment] x [Kinetic Tremors, Onslaught, Pugilist] — 6 combos
- Copy 6: [Dynamic Sway Reduction, Strategist, Threat Detector] x [High Ground, Pugilist, Rampage] — 6 combos
- Copy 7: [Fragile Focus, Hip-Fire Grip, Slideways] x [Pugilist, Snapshot Sights, Target Lock] — 5 combos
- Copy 8: [Fragile Focus, Strategist, Threat Detector] x [Eye of the Storm, Harmony, Target Lock] — 4 combos
- Copy 9: [Attrition Orbs, Keep Away, Slideways] x [Harmony, Surrounded, Swashbuckler] — 6 combos
- Copy 10: [Feeding Frenzy, Keep Away, Slideways] x [Rampage, Swashbuckler, Target Lock] — 4 combos

### Cynosure
Rocket Launcher · Strand · tiered, vendor 6-perk, obtainable · GFS 773 · pool 144 combos · 9 copies · 62 combos covered
- Pool col 2 (12): Ambitious Assassin, Clown Cartridge, Danger Zone, Demolitionist, Envious Arsenal, Field Prep, Impulse Amplifier, Overflow, Reconstruction, Slice, Sympathetic Arsenal, Tracking Module
- Pool col 3 (12): Adrenaline Junkie, Bipod, Chain Reaction, Cluster Bomb, Desperate Measures, Elemental Honing, Explosive Light, Hatchling, High Ground, Lasting Impression, Quickdraw, Reverberation
- Copy 1: [Clown Cartridge, Slice, Sympathetic Arsenal] x [Bipod, Cluster Bomb, Desperate Measures] — 9 combos
- Copy 2: [Danger Zone, Field Prep, Tracking Module] x [Desperate Measures, Hatchling, High Ground] — 9 combos
- Copy 3: [Ambitious Assassin, Clown Cartridge, Sympathetic Arsenal] x [Elemental Honing, Hatchling, High Ground] — 9 combos
- Copy 4: [Impulse Amplifier, Overflow, Slice] x [Lasting Impression, Quickdraw, Reverberation] — 9 combos
- Copy 5: [Ambitious Assassin, Sympathetic Arsenal, Tracking Module] x [Adrenaline Junkie, Desperate Measures, Reverberation] — 7 combos
- Copy 6: [Demolitionist, Envious Arsenal, Reconstruction] x [Lasting Impression, Quickdraw, Reverberation] — 8 combos
- Copy 7: [Overflow, Reconstruction, Tracking Module] x [Adrenaline Junkie, Elemental Honing, Hatchling] — 3 combos
- Copy 8: [Field Prep, Slice, Tracking Module] x [Bipod, Chain Reaction, Quickdraw] — 5 combos
- Copy 9: [Impulse Amplifier, Reconstruction] x [Bipod, Elemental Honing, Hatchling] — 3 combos

### Positive Outlook
Auto Rifle · Void · tiered, vendor 6-perk, obtainable · GFS 963 · pool 156 combos · 9 copies · 59 combos covered
- Pool col 2 (12): Ambitious Assassin, Dynamic Sway Reduction, Invisible Hand, Perfect Float, Perpetual Motion, Shot Swap, Stats for All, Steady Hands, Surplus, Tap the Trigger, Tunnel Vision, Zen Moment
- Pool col 3 (13): Adaptive Munitions, Cascade Point, Destabilizing Rounds, Dragonfly, Elemental Capacitor, Eye of the Storm, Golden Tricorn, Golden Tricorn Enhanced, Gutshot Straight, Kill Clip, Pugilist, Repulsor Brace, Vorpal Weapon
- Copy 1: [Invisible Hand, Perfect Float, Shot Swap] x [Adaptive Munitions, Dragonfly, Elemental Capacitor] — 9 combos
- Copy 2: [Invisible Hand, Steady Hands, Tap the Trigger] x [Cascade Point, Destabilizing Rounds, Kill Clip] — 9 combos
- Copy 3: [Invisible Hand, Perfect Float, Tap the Trigger] x [Adaptive Munitions, Repulsor Brace, Vorpal Weapon] — 7 combos
- Copy 4: [Dynamic Sway Reduction, Tunnel Vision, Zen Moment] x [Adaptive Munitions, Cascade Point, Destabilizing Rounds] — 7 combos
- Copy 5: [Invisible Hand, Shot Swap, Tap the Trigger] x [Golden Tricorn, Golden Tricorn Enhanced, Kill Clip] — 7 combos
- Copy 6: [Perpetual Motion, Shot Swap, Surplus] x [Adaptive Munitions, Pugilist, Repulsor Brace] — 7 combos
- Copy 7: [Ambitious Assassin, Dynamic Sway Reduction, Stats for All] x [Cascade Point, Eye of the Storm, Repulsor Brace] — 5 combos
- Copy 8: [Dynamic Sway Reduction, Shot Swap, Tunnel Vision] x [Cascade Point, Destabilizing Rounds, Gutshot Straight] — 5 combos
- Copy 9: [Perfect Float, Stats for All] x [Dragonfly, Kill Clip, Pugilist] — 3 combos

### Someday
Shotgun · Kinetic · tiered, craftable, obtainable · GFS 697 · pool 99 combos · 9 copies · 59 combos covered
- Pool col 2 (10): Dual Loader, Elemental Capacitor, Empty Traits Socket, Lead from Gold, Loose Change, One-Two Punch, Slickdraw, Strategist, Threat Detector, Threat Remover
- Pool col 3 (10): Barrel Constrictor, Cascade Point, Closing Time, Collective Action, Empty Traits Socket, Frenzy, Opening Shot, Recombination, Swashbuckler, Vorpal Weapon
- Copy 1: [Lead from Gold, One-Two Punch, Strategist] x [Barrel Constrictor, Closing Time, Collective Action] — 8 combos
- Copy 2: [Dual Loader, Elemental Capacitor, Threat Remover] x [Collective Action, Empty Traits Socket, Recombination] — 9 combos
- Copy 3: [Empty Traits Socket, Loose Change, One-Two Punch] x [Barrel Constrictor, Frenzy, Recombination] — 8 combos
- Copy 4: [Loose Change, Slickdraw, Strategist] x [Closing Time, Collective Action, Recombination] — 5 combos
- Copy 5: [One-Two Punch, Threat Detector, Threat Remover] x [Recombination, Swashbuckler, Vorpal Weapon] — 7 combos
- Copy 6: [Dual Loader, Elemental Capacitor, Lead from Gold] x [Cascade Point, Closing Time, Swashbuckler] — 7 combos
- Copy 7: [Lead from Gold, One-Two Punch, Strategist] x [Empty Traits Socket, Opening Shot, Recombination] — 6 combos
- Copy 8: [Loose Change, Slickdraw, Threat Detector] x [Barrel Constrictor, Cascade Point, Swashbuckler] — 4 combos
- Copy 9: [Empty Traits Socket, Slickdraw, Strategist] x [Cascade Point, Opening Shot, Vorpal Weapon] — 5 combos

### Bold Endings
Hand Cannon · Stasis · tiered, craftable, obtainable · GFS 799 · pool 109 combos · 9 copies · 56 combos covered
- Pool col 2 (10): Air Trigger, Attrition Orbs, Empty Traits Socket, Headstone, Loose Change, Opening Shot, Rapid Hit, Rimestealer, Strategist, To the Pain
- Pool col 3 (11): Collective Action, Crystalline Corpsebloom, Demolitionist, Desperate Measures, Dragonfly, Empty Traits Socket, Eye of the Storm, Frenzy, Golden Tricorn, Golden Tricorn Enhanced, Moving Target
- Copy 1: [Air Trigger, Attrition Orbs, Loose Change] x [Demolitionist, Dragonfly, Golden Tricorn] — 8 combos
- Copy 2: [Air Trigger, Headstone, Rimestealer] x [Collective Action, Eye of the Storm, Golden Tricorn Enhanced] — 9 combos
- Copy 3: [Loose Change, Rapid Hit, Strategist] x [Collective Action, Crystalline Corpsebloom, Dragonfly] — 5 combos
- Copy 4: [Attrition Orbs, Opening Shot, To the Pain] x [Collective Action, Crystalline Corpsebloom, Demolitionist] — 8 combos
- Copy 5: [Opening Shot, Rimestealer, To the Pain] x [Dragonfly, Frenzy, Golden Tricorn] — 9 combos
- Copy 6: [Empty Traits Socket, Opening Shot, Strategist] x [Crystalline Corpsebloom, Golden Tricorn Enhanced, Moving Target] — 6 combos
- Copy 7: [Air Trigger, Attrition Orbs, Loose Change] x [Empty Traits Socket, Golden Tricorn Enhanced, Moving Target] — 7 combos
- Copy 8: [Air Trigger, Empty Traits Socket, Opening Shot] x [Eye of the Storm, Frenzy] — 3 combos
- Copy 9: [Rapid Hit] x [Empty Traits Socket] — 1 combo

### Prolonged Engagement
Submachine Gun · Stasis · tiered, vendor 6-perk, obtainable · GFS 1,028 · pool 144 combos · 9 copies · 56 combos covered
- Pool col 2 (12): Air Assault, Dynamic Sway Reduction, Eye of the Storm, Feeding Frenzy, Fourth Time's the Charm, Grave Robber, Heating Up, Killing Wind, Offhand Strike, Outlaw, Perfect Float, Subsistence
- Pool col 3 (12): Adagio, Encore, Frenzy, Gutshot Straight, Headstone, Multikill Clip, One for All, Pugilist, Rangefinder, Surrounded, Target Lock, Thresh
- Copy 1: [Air Assault, Dynamic Sway Reduction, Fourth Time's the Charm] x [Encore, Headstone, Target Lock] — 9 combos
- Copy 2: [Grave Robber, Heating Up, Perfect Float] x [Encore, Gutshot Straight, Rangefinder] — 9 combos
- Copy 3: [Air Assault, Eye of the Storm, Fourth Time's the Charm] x [One for All, Rangefinder, Thresh] — 9 combos
- Copy 4: [Eye of the Storm, Outlaw, Subsistence] x [Encore, Surrounded, Target Lock] — 6 combos
- Copy 5: [Air Assault, Offhand Strike, Perfect Float] x [Gutshot Straight, Surrounded, Thresh] — 5 combos
- Copy 6: [Eye of the Storm, Fourth Time's the Charm, Grave Robber] x [Gutshot Straight, Multikill Clip, Target Lock] — 3 combos
- Copy 7: [Eye of the Storm, Grave Robber, Perfect Float] x [Frenzy, Headstone, Target Lock] — 6 combos
- Copy 8: [Feeding Frenzy, Perfect Float, Subsistence] x [Gutshot Straight, One for All, Pugilist] — 5 combos
- Copy 9: [Killing Wind, Offhand Strike, Outlaw] x [One for All, Target Lock, Thresh] — 4 combos

### Breakneck
Auto Rifle · Kinetic · tiered, vendor 6-perk, obtainable · GFS 893 · pool 144 combos · 9 copies · 53 combos covered
- Pool col 2 (12): Dynamic Sway Reduction, Encore, Enlightened Action, Eye of the Storm, Feeding Frenzy, Heating Up, Hip-Fire Grip, Keep Away, Pugilist, Shoot to Loot, Subsistence, Under Pressure
- Pool col 3 (12): Adagio, Attrition Orbs, Deconstruct, Demolitionist, Harmony, Kinetic Tremors, Moving Target, Offhand Strike, Onslaught, Osmosis, Tap the Trigger, Target Lock
- Copy 1: [Eye of the Storm, Feeding Frenzy, Heating Up] x [Attrition Orbs, Deconstruct, Offhand Strike] — 9 combos
- Copy 2: [Dynamic Sway Reduction, Enlightened Action, Under Pressure] x [Deconstruct, Demolitionist, Offhand Strike] — 9 combos
- Copy 3: [Dynamic Sway Reduction, Encore, Enlightened Action] x [Adagio, Onslaught, Osmosis] — 7 combos
- Copy 4: [Eye of the Storm, Heating Up, Pugilist] x [Deconstruct, Kinetic Tremors, Onslaught] — 6 combos
- Copy 5: [Encore, Shoot to Loot, Under Pressure] x [Attrition Orbs, Deconstruct, Onslaught] — 6 combos
- Copy 6: [Encore, Enlightened Action, Eye of the Storm] x [Kinetic Tremors, Moving Target, Tap the Trigger] — 6 combos
- Copy 7: [Feeding Frenzy, Pugilist, Subsistence] x [Deconstruct, Onslaught, Osmosis] — 5 combos
- Copy 8: [Keep Away, Pugilist, Subsistence] x [Deconstruct, Kinetic Tremors, Offhand Strike] — 4 combos
- Copy 9: [Hip-Fire Grip] x [Offhand Strike] — 1 combo

### Wicked Sister
Grenade Launcher · Strand · vendor 6-perk, obtainable · GFS 1,019 · pool 144 combos · 9 copies · 53 combos covered
- Pool col 2 (12): Auto-Loading Holster, Clown Cartridge, Danger Zone, Envious Arsenal, Envious Assassin, Field Prep, Impulse Amplifier, Perpetual Motion, Quickdraw, Slice, Strategist, Unrelenting
- Pool col 3 (12): Bait and Switch, Cascade Point, Chain Reaction, Deconstruct, Demolitionist, Explosive Light, Full Court, Hatchling, High Ground, One for All, Reverberation, Vorpal Weapon
- Copy 1: [Danger Zone, Envious Assassin, Perpetual Motion] x [Cascade Point, Deconstruct, Reverberation] — 9 combos
- Copy 2: [Slice, Strategist, Unrelenting] x [Cascade Point, Explosive Light, Full Court] — 8 combos
- Copy 3: [Danger Zone, Envious Arsenal, Quickdraw] x [Deconstruct, Demolitionist, One for All] — 7 combos
- Copy 4: [Perpetual Motion, Quickdraw, Unrelenting] x [Full Court, Hatchling, Reverberation] — 6 combos
- Copy 5: [Clown Cartridge, Danger Zone, Perpetual Motion] x [Chain Reaction, Full Court, Reverberation] — 5 combos
- Copy 6: [Envious Arsenal, Slice, Strategist] x [Bait and Switch, Deconstruct, High Ground] — 5 combos
- Copy 7: [Clown Cartridge, Field Prep, Unrelenting] x [Demolitionist, One for All, Reverberation] — 5 combos
- Copy 8: [Envious Assassin, Perpetual Motion, Strategist] x [Chain Reaction, High Ground, Reverberation] — 4 combos
- Copy 9: [Auto-Loading Holster, Clown Cartridge, Danger Zone] x [Cascade Point, Chain Reaction, Explosive Light] — 4 combos

### Luna Regolith III
Sniper Rifle · Solar · vendor 6-perk, obtainable · GFS 1,020 · pool 144 combos · 9 copies · 51 combos covered
- Pool col 2 (12): Clown Cartridge, Field Prep, Heal Clip, Keep Away, No Distractions, Perfect Float, Quickdraw, Shoot to Loot, Snapshot Sights, Surplus, Triple Tap, Under Pressure
- Pool col 3 (12): Box Breathing, Cascade Point, Collective Action, Demolitionist, Explosive Payload, Eye of the Storm, Firing Line, High Ground, Incandescent, Moving Target, Opening Shot, Precision Instrument
- Copy 1: [Clown Cartridge, Field Prep, Under Pressure] x [Box Breathing, Cascade Point, Collective Action] — 7 combos
- Copy 2: [Heal Clip, Perfect Float, Quickdraw] x [Box Breathing, Collective Action, Firing Line] — 9 combos
- Copy 3: [Clown Cartridge, Snapshot Sights, Under Pressure] x [Cascade Point, Explosive Payload, Eye of the Storm] — 6 combos
- Copy 4: [Field Prep, Snapshot Sights, Surplus] x [Collective Action, High Ground, Precision Instrument] — 4 combos
- Copy 5: [Heal Clip, Perfect Float, Under Pressure] x [Cascade Point, Incandescent, Precision Instrument] — 7 combos
- Copy 6: [Heal Clip, No Distractions, Surplus] x [Demolitionist, Explosive Payload, High Ground] — 7 combos
- Copy 7: [No Distractions, Perfect Float, Triple Tap] x [Demolitionist, Explosive Payload, Incandescent] — 4 combos
- Copy 8: [Heal Clip, Keep Away, Perfect Float] x [Collective Action, Demolitionist, Opening Shot] — 4 combos
- Copy 9: [No Distractions, Perfect Float, Shoot to Loot] x [Eye of the Storm, Precision Instrument] — 3 combos

### Unending Tempest
Submachine Gun · Stasis · tiered, vendor 6-perk, obtainable · GFS 1,226 · pool 144 combos · 9 copies · 50 combos covered
- Pool col 2 (12): Demolitionist, Discord, Dynamic Sway Reduction, Enlightened Action, Gutshot Straight, Killing Wind, Moving Target, Offhand Strike, Perpetual Motion, Shot Swap, Subsistence, Under-Over
- Pool col 3 (12): Adrenaline Junkie, Cascade Point, Collective Action, Fragile Focus, Frenzy, Harmony, Headstone, Multikill Clip, Rangefinder, Surrounded, Tap the Trigger, Target Lock
- Copy 1: [Discord, Enlightened Action, Gutshot Straight] x [Fragile Focus, Harmony, Headstone] — 7 combos
- Copy 2: [Discord, Gutshot Straight, Under-Over] x [Cascade Point, Collective Action, Multikill Clip] — 7 combos
- Copy 3: [Dynamic Sway Reduction, Killing Wind, Shot Swap] x [Fragile Focus, Headstone, Rangefinder] — 6 combos
- Copy 4: [Discord, Gutshot Straight, Shot Swap] x [Adrenaline Junkie, Collective Action, Tap the Trigger] — 7 combos
- Copy 5: [Demolitionist, Subsistence, Under-Over] x [Fragile Focus, Harmony, Tap the Trigger] — 6 combos
- Copy 6: [Moving Target, Perpetual Motion, Shot Swap] x [Collective Action, Surrounded, Target Lock] — 7 combos
- Copy 7: [Discord, Dynamic Sway Reduction, Offhand Strike] x [Collective Action, Headstone, Surrounded] — 3 combos
- Copy 8: [Demolitionist, Killing Wind, Offhand Strike] x [Cascade Point, Harmony, Tap the Trigger] — 4 combos
- Copy 9: [Perpetual Motion, Shot Swap] x [Harmony, Headstone, Rangefinder] — 3 combos

### Qua Xaphan V
Machine Gun · Void · vendor 6-perk, obtainable · GFS 1,008 · pool 144 combos · 8 copies · 56 combos covered
- Pool col 2 (12): Clown Cartridge, Dynamic Sway Reduction, Encore, Field Prep, Heating Up, Killing Wind, Offhand Strike, Shot Swap, Slideways, Surplus, Triple Tap, Under Pressure
- Pool col 3 (12): Adrenaline Junkie, Cascade Point, Destabilizing Rounds, Dragonfly, Elemental Capacitor, Firing Line, Frenzy, High Ground, Rampage, Target Lock, Thresh, Wellspring
- Copy 1: [Clown Cartridge, Heating Up, Offhand Strike] x [Cascade Point, Firing Line, Target Lock] — 9 combos
- Copy 2: [Heating Up, Offhand Strike, Triple Tap] x [High Ground, Thresh, Wellspring] — 9 combos
- Copy 3: [Encore, Heating Up, Slideways] x [Cascade Point, Destabilizing Rounds, Elemental Capacitor] — 6 combos
- Copy 4: [Killing Wind, Shot Swap, Slideways] x [Firing Line, High Ground, Wellspring] — 7 combos
- Copy 5: [Surplus, Triple Tap, Under Pressure] x [Adrenaline Junkie, Destabilizing Rounds, Target Lock] — 9 combos
- Copy 6: [Clown Cartridge, Dynamic Sway Reduction, Encore] x [Dragonfly, Firing Line, Thresh] — 5 combos
- Copy 7: [Clown Cartridge, Encore, Field Prep] x [Adrenaline Junkie, Destabilizing Rounds, Rampage] — 5 combos
- Copy 8: [Clown Cartridge, Field Prep, Triple Tap] x [Dragonfly, Elemental Capacitor, Wellspring] — 6 combos

### Riptide
Fusion Rifle · Stasis · tiered, vendor 6-perk, obtainable · GFS 1,463 · pool 156 combos · 8 copies · 54 combos covered
- Pool col 2 (12): Auto-Loading Holster, Compulsive Reloader, Ensemble, Feeding Frenzy, Field Prep, Heating Up, Lead from Gold, Perpetual Motion, Stats for All, Steady Hands, Under Pressure, Well-Rounded
- Pool col 3 (13): Chill Clip, Cornered, Demolitionist, Frenzy, Golden Tricorn, Golden Tricorn Enhanced, Harmony, Snapshot Sights, Successful Warm-Up, Thresh, Unrelenting, Vorpal Weapon, Wellspring
- Copy 1: [Auto-Loading Holster, Feeding Frenzy, Well-Rounded] x [Chill Clip, Cornered, Thresh] — 9 combos
- Copy 2: [Compulsive Reloader, Field Prep, Steady Hands] x [Chill Clip, Cornered, Successful Warm-Up] — 8 combos
- Copy 3: [Auto-Loading Holster, Heating Up, Stats for All] x [Cornered, Golden Tricorn Enhanced, Successful Warm-Up] — 7 combos
- Copy 4: [Feeding Frenzy, Perpetual Motion, Under Pressure] x [Cornered, Successful Warm-Up, Unrelenting] — 8 combos
- Copy 5: [Ensemble, Lead from Gold, Well-Rounded] x [Golden Tricorn Enhanced, Successful Warm-Up, Unrelenting] — 5 combos
- Copy 6: [Compulsive Reloader, Ensemble, Well-Rounded] x [Cornered, Demolitionist, Wellspring] — 7 combos
- Copy 7: [Lead from Gold, Stats for All, Under Pressure] x [Golden Tricorn Enhanced, Harmony, Thresh] — 5 combos
- Copy 8: [Feeding Frenzy, Under Pressure, Well-Rounded] x [Frenzy, Golden Tricorn, Harmony] — 5 combos

### Forthcoming Deviance (Adept)
Glaive · Void · adept, craftable · GFS 403 · pool 81 combos · 8 copies · 53 combos covered
- Pool col 2 (9): Demolitionist, Dimensional Shift, Disruption Break, Grave Robber, Immovable Object, Impulse Amplifier, Reconstruction, Replenishing Aegis, Repulsor Brace
- Pool col 3 (9): Chain Reaction, Chaos Reshaped, Close to Melee, Collective Action, Collective Demolition, Desperate Measures, Destabilizing Rounds, Unstoppable Force, Vorpal Weapon
- Copy 1: [Dimensional Shift, Disruption Break, Immovable Object] x [Chain Reaction, Chaos Reshaped, Close to Melee] — 8 combos
- Copy 2: [Disruption Break, Reconstruction, Replenishing Aegis] x [Chain Reaction, Close to Melee, Collective Action] — 6 combos
- Copy 3: [Dimensional Shift, Disruption Break, Immovable Object] x [Collective Action, Collective Demolition, Unstoppable Force] — 8 combos
- Copy 4: [Grave Robber, Impulse Amplifier, Replenishing Aegis] x [Chaos Reshaped, Collective Demolition, Desperate Measures] — 7 combos
- Copy 5: [Dimensional Shift, Disruption Break, Repulsor Brace] x [Chain Reaction, Collective Demolition, Vorpal Weapon] — 5 combos
- Copy 6: [Demolitionist, Reconstruction, Repulsor Brace] x [Chaos Reshaped, Close to Melee, Unstoppable Force] — 7 combos
- Copy 7: [Demolitionist, Immovable Object, Reconstruction] x [Collective Demolition, Destabilizing Rounds] — 3 combos
- Copy 8: [Grave Robber, Impulse Amplifier, Replenishing Aegis] x [Destabilizing Rounds, Unstoppable Force, Vorpal Weapon] — 9 combos

### Yesteryear
Pulse Rifle · Void · tiered, vendor 6-perk, obtainable · GFS 1,054 · pool 156 combos · 8 copies · 52 combos covered
- Pool col 2 (12): Ambitious Assassin, Compulsive Reloader, Ensemble, Heating Up, Outlaw, Perpetual Motion, Slideways, Steady Hands, Subsistence, Tunnel Vision, Under Pressure, Well-Rounded
- Pool col 3 (13): Desperado, Dragonfly, Eye of the Storm, Focused Fury, Golden Tricorn, Golden Tricorn Enhanced, Gutshot Straight, Multikill Clip, Pugilist, Rampage, Repulsor Brace, Under-Over, Wellspring
- Copy 1: [Compulsive Reloader, Ensemble, Slideways] x [Desperado, Repulsor Brace, Under-Over] — 9 combos
- Copy 2: [Heating Up, Outlaw, Well-Rounded] x [Desperado, Repulsor Brace, Under-Over] — 9 combos
- Copy 3: [Ambitious Assassin, Ensemble, Under Pressure] x [Gutshot Straight, Repulsor Brace, Under-Over] — 4 combos
- Copy 4: [Ambitious Assassin, Perpetual Motion, Tunnel Vision] x [Dragonfly, Repulsor Brace, Under-Over] — 6 combos
- Copy 5: [Compulsive Reloader, Steady Hands, Subsistence] x [Desperado, Eye of the Storm, Multikill Clip] — 7 combos
- Copy 6: [Heating Up, Outlaw, Steady Hands] x [Dragonfly, Gutshot Straight, Pugilist] — 6 combos
- Copy 7: [Compulsive Reloader, Ensemble, Subsistence] x [Dragonfly, Repulsor Brace, Under-Over] — 4 combos
- Copy 8: [Compulsive Reloader, Slideways, Tunnel Vision] x [Golden Tricorn, Golden Tricorn Enhanced, Pugilist] — 7 combos

### Axial Lacuna
Fusion Rifle · Solar · tiered, craftable, obtainable · GFS 817 · pool 99 combos · 8 copies · 51 combos covered
- Pool col 2 (10): Cornered, Demolitionist, Empty Traits Socket, Eye of the Storm, Firmly Planted, Heal Clip, Keep Away, Reconstruction, Slickdraw, Threat Detector
- Pool col 3 (10): Closing Time, Controlled Burst, Desperate Measures, Empty Traits Socket, Frenzy, Incandescent, Kickstart, Reservoir Burst, Surrounded, Vorpal Weapon
- Copy 1: [Cornered, Firmly Planted, Keep Away] x [Controlled Burst, Desperate Measures, Incandescent] — 9 combos
- Copy 2: [Eye of the Storm, Heal Clip, Slickdraw] x [Desperate Measures, Kickstart, Reservoir Burst] — 8 combos
- Copy 3: [Demolitionist, Firmly Planted, Keep Away] x [Closing Time, Kickstart, Reservoir Burst] — 8 combos
- Copy 4: [Cornered, Heal Clip, Threat Detector] x [Controlled Burst, Frenzy, Vorpal Weapon] — 7 combos
- Copy 5: [Cornered, Heal Clip, Reconstruction] x [Closing Time, Empty Traits Socket, Surrounded] — 6 combos
- Copy 6: [Demolitionist, Empty Traits Socket, Reconstruction] x [Controlled Burst, Kickstart, Reservoir Burst] — 5 combos
- Copy 7: [Empty Traits Socket, Slickdraw, Threat Detector] x [Desperate Measures, Incandescent, Kickstart] — 4 combos
- Copy 8: [Empty Traits Socket, Slickdraw, Threat Detector] x [Closing Time, Empty Traits Socket, Surrounded] — 4 combos

### Lubrae's Ruin (Adept)
Glaive · Solar · adept, craftable · GFS 374 · pool 81 combos · 8 copies · 51 combos covered
- Pool col 2 (9): Close to Melee, Frenzy, Grave Robber, Immovable Object, Killing Wind, Sleight of Hand, Steady Hands, Tilting at Windmills, Turnabout
- Pool col 3 (9): Bait and Switch, Chaos Reshaped, Incandescent, Surrounded, Swashbuckler, Unrelenting, Unstoppable Force, Vorpal Weapon, Wellspring
- Copy 1: [Close to Melee, Immovable Object, Tilting at Windmills] x [Bait and Switch, Chaos Reshaped, Incandescent] — 9 combos
- Copy 2: [Close to Melee, Frenzy, Killing Wind] x [Chaos Reshaped, Surrounded, Swashbuckler] — 7 combos
- Copy 3: [Close to Melee, Frenzy, Immovable Object] x [Unrelenting, Unstoppable Force, Vorpal Weapon] — 7 combos
- Copy 4: [Close to Melee, Immovable Object, Sleight of Hand] x [Incandescent, Swashbuckler, Wellspring] — 6 combos
- Copy 5: [Killing Wind, Sleight of Hand, Steady Hands] x [Bait and Switch, Unrelenting, Unstoppable Force] — 8 combos
- Copy 6: [Grave Robber, Tilting at Windmills, Turnabout] x [Swashbuckler, Unstoppable Force, Wellspring] — 6 combos
- Copy 7: [Immovable Object, Sleight of Hand, Steady Hands] x [Chaos Reshaped, Incandescent, Surrounded] — 4 combos
- Copy 8: [Tilting at Windmills, Turnabout] x [Surrounded, Unrelenting, Vorpal Weapon] — 4 combos

### No Hesitation
Auto Rifle · Solar · tiered, craftable, obtainable · GFS 702 · pool 99 combos · 8 copies · 51 combos covered
- Pool col 2 (10): Burning Ambition, Demolitionist, Empty Traits Socket, Ensemble, Grave Robber, Overflow, Physic, Strategist, Subsistence, Target Lock
- Pool col 3 (10): Attrition Orbs, Chaos Reshaped, Circle of Life, Desperate Measures, Disruption Break, Elemental Honing, Empty Traits Socket, Frenzy, Incandescent, Surrounded
- Copy 1: [Burning Ambition, Physic, Target Lock] x [Attrition Orbs, Chaos Reshaped, Circle of Life] — 8 combos
- Copy 2: [Empty Traits Socket, Grave Robber, Overflow] x [Chaos Reshaped, Circle of Life, Disruption Break] — 9 combos
- Copy 3: [Ensemble, Physic, Strategist] x [Circle of Life, Desperate Measures, Disruption Break] — 7 combos
- Copy 4: [Burning Ambition, Physic, Target Lock] x [Desperate Measures, Disruption Break, Elemental Honing] — 7 combos
- Copy 5: [Physic, Strategist, Target Lock] x [Empty Traits Socket, Frenzy, Incandescent] — 7 combos
- Copy 6: [Ensemble, Physic, Target Lock] x [Attrition Orbs, Elemental Honing, Surrounded] — 5 combos
- Copy 7: [Burning Ambition, Overflow, Subsistence] x [Attrition Orbs, Circle of Life, Empty Traits Socket] — 6 combos
- Copy 8: [Grave Robber] x [Empty Traits Socket, Incandescent] — 2 combos

### Oversoul Edict (Adept)
Pulse Rifle · Arc · adept, craftable · GFS 489 · pool 81 combos · 8 copies · 48 combos covered
- Pool col 2 (9): Demolitionist, Eddy Current, Encore, Enlightened Action, Eye of the Storm, Keep Away, Perpetual Motion, Rolling Storm, Supercharged Magazine
- Pool col 3 (9): Adrenaline Junkie, Gear Shift, Headseeker, High Ground, Jolting Feedback, Moving Target, Swashbuckler, Sword Logic, Voltshot
- Copy 1: [Eddy Current, Encore, Eye of the Storm] x [Adrenaline Junkie, Gear Shift, Moving Target] — 9 combos
- Copy 2: [Encore, Eye of the Storm, Rolling Storm] x [High Ground, Jolting Feedback, Voltshot] — 9 combos
- Copy 3: [Perpetual Motion, Rolling Storm, Supercharged Magazine] x [Gear Shift, Headseeker, Swashbuckler] — 8 combos
- Copy 4: [Enlightened Action, Eye of the Storm, Rolling Storm] x [Gear Shift, Jolting Feedback, Sword Logic] — 4 combos
- Copy 5: [Eddy Current, Eye of the Storm, Supercharged Magazine] x [Headseeker, High Ground, Moving Target] — 4 combos
- Copy 6: [Demolitionist, Eye of the Storm, Supercharged Magazine] x [Gear Shift, Swashbuckler, Sword Logic] — 4 combos
- Copy 7: [Keep Away, Perpetual Motion, Rolling Storm] x [Gear Shift, Jolting Feedback, Moving Target] — 5 combos
- Copy 8: [Enlightened Action, Keep Away, Perpetual Motion] x [Adrenaline Junkie, Sword Logic, Voltshot] — 5 combos

### Bygones
Pulse Rifle · Kinetic · tiered, vendor 6-perk, obtainable · GFS 1,294 · pool 144 combos · 8 copies · 47 combos covered
- Pool col 2 (12): Attrition Orbs, Demolitionist, Keep Away, Lone Wolf, Outlaw, Perpetual Motion, Rangefinder, Shoot to Loot, Subsistence, To the Pain, Under Pressure, Zen Moment
- Pool col 3 (12): Closing Time, Desperado, Desperate Measures, Eye of the Storm, Firefly, Frenzy, Headseeker, High Ground, Kill Clip, Kinetic Tremors, Osmosis, Vorpal Weapon
- Copy 1: [Attrition Orbs, Subsistence, Under Pressure] x [Firefly, High Ground, Osmosis] — 9 combos
- Copy 2: [Lone Wolf, Rangefinder, To the Pain] x [Closing Time, High Ground, Osmosis] — 8 combos
- Copy 3: [Outlaw, Rangefinder, Shoot to Loot] x [Closing Time, Firefly, High Ground] — 7 combos
- Copy 4: [Attrition Orbs, Under Pressure, Zen Moment] x [Desperado, Headseeker, Osmosis] — 6 combos
- Copy 5: [Outlaw, Perpetual Motion, Under Pressure] x [Desperate Measures, Firefly, Kinetic Tremors] — 4 combos
- Copy 6: [Attrition Orbs, Keep Away, Subsistence] x [Closing Time, Headseeker, Osmosis] — 4 combos
- Copy 7: [Attrition Orbs, Demolitionist, To the Pain] x [Firefly, Kill Clip, Vorpal Weapon] — 4 combos
- Copy 8: [Demolitionist, Rangefinder, Zen Moment] x [Eye of the Storm, Frenzy, Kill Clip] — 5 combos

### Autumn Wind
Pulse Rifle · Kinetic · tiered, vendor 6-perk, obtainable · GFS 1,409 · pool 144 combos · 8 copies · 43 combos covered
- Pool col 2 (12): Demolitionist, Envious Assassin, Heating Up, Killing Wind, Offhand Strike, Perfect Float, Perpetual Motion, Pugilist, Rangefinder, Shot Swap, Slideways, Tunnel Vision
- Pool col 3 (12): Adrenaline Junkie, Elemental Capacitor, Focused Fury, Frenzy, Harmony, Headseeker, Moving Target, Multikill Clip, Rampage, Swashbuckler, Thresh, Vorpal Weapon
- Copy 1: [Envious Assassin, Offhand Strike, Tunnel Vision] x [Moving Target, Multikill Clip, Rampage] — 9 combos
- Copy 2: [Perfect Float, Pugilist, Slideways] x [Adrenaline Junkie, Elemental Capacitor, Multikill Clip] — 5 combos
- Copy 3: [Envious Assassin, Pugilist, Shot Swap] x [Focused Fury, Swashbuckler, Thresh] — 6 combos
- Copy 4: [Pugilist, Rangefinder, Tunnel Vision] x [Elemental Capacitor, Headseeker, Rampage] — 4 combos
- Copy 5: [Killing Wind, Perfect Float, Pugilist] x [Headseeker, Moving Target, Rampage] — 6 combos
- Copy 6: [Envious Assassin, Offhand Strike, Shot Swap] x [Adrenaline Junkie, Elemental Capacitor, Rampage] — 4 combos
- Copy 7: [Demolitionist, Offhand Strike, Slideways] x [Focused Fury, Thresh, Vorpal Weapon] — 4 combos
- Copy 8: [Perfect Float, Rangefinder, Tunnel Vision] x [Focused Fury, Harmony, Vorpal Weapon] — 5 combos

### Trinary System
Fusion Rifle · Solar · vendor 6-perk, obtainable · GFS 1,281 · pool 144 combos · 8 copies · 42 combos covered
- Pool col 2 (12): Ambitious Assassin, Auto-Loading Holster, Feeding Frenzy, Firmly Planted, Grave Robber, Hip-Fire Grip, Killing Wind, Quickdraw, Slideshot, Slideways, Surplus, Under Pressure
- Pool col 3 (12): Backup Plan, Demolitionist, Disruption Break, High-Impact Reserves, Kill Clip, Multikill Clip, One for All, Swashbuckler, Tap the Trigger, Thresh, Unrelenting, Wellspring
- Copy 1: [Ambitious Assassin, Feeding Frenzy, Grave Robber] x [Backup Plan, High-Impact Reserves, Tap the Trigger] — 8 combos
- Copy 2: [Slideways, Surplus, Under Pressure] x [Backup Plan, Disruption Break, Kill Clip] — 7 combos
- Copy 3: [Firmly Planted, Quickdraw, Slideways] x [Disruption Break, Tap the Trigger, Unrelenting] — 7 combos
- Copy 4: [Ambitious Assassin, Firmly Planted, Slideways] x [Backup Plan, Demolitionist, High-Impact Reserves] — 5 combos
- Copy 5: [Quickdraw, Slideshot, Under Pressure] x [Kill Clip, Thresh, Wellspring] — 6 combos
- Copy 6: [Ambitious Assassin, Hip-Fire Grip, Under Pressure] x [Multikill Clip, One for All, Wellspring] — 5 combos
- Copy 7: [Auto-Loading Holster, Feeding Frenzy] x [Disruption Break, Kill Clip, Multikill Clip] — 3 combos
- Copy 8: [Hip-Fire Grip] x [Swashbuckler] — 1 combo

### Fortissimo-11
Shotgun · Kinetic · tiered, vendor 6-perk, obtainable · GFS 1,551 · pool 144 combos · 8 copies · 41 combos covered
- Pool col 2 (12): Demolitionist, Feeding Frenzy, Fourth Time's the Charm, Lead from Gold, Outlaw, Perpetual Motion, Pulse Monitor, Steady Hands, Subsistence, Surplus, Threat Detector, Unrelenting
- Pool col 3 (12): Adagio, Adrenaline Junkie, Elemental Capacitor, Focused Fury, Frenzy, Moving Target, Opening Shot, Osmosis, Surrounded, Turnabout, Vorpal Weapon, Wellspring
- Copy 1: [Pulse Monitor, Steady Hands, Unrelenting] x [Adagio, Elemental Capacitor, Osmosis] — 7 combos
- Copy 2: [Pulse Monitor, Threat Detector, Unrelenting] x [Focused Fury, Opening Shot, Turnabout] — 6 combos
- Copy 3: [Lead from Gold, Outlaw, Subsistence] x [Adagio, Osmosis, Turnabout] — 7 combos
- Copy 4: [Perpetual Motion, Steady Hands, Threat Detector] x [Adrenaline Junkie, Moving Target, Osmosis] — 6 combos
- Copy 5: [Feeding Frenzy, Surplus, Threat Detector] x [Adagio, Focused Fury, Moving Target] — 5 combos
- Copy 6: [Demolitionist, Outlaw, Unrelenting] x [Moving Target, Surrounded, Vorpal Weapon] — 5 combos
- Copy 7: [Feeding Frenzy, Steady Hands, Subsistence] x [Focused Fury, Frenzy, Vorpal Weapon] — 4 combos
- Copy 8: [Lead from Gold] x [Vorpal Weapon] — 1 combo

### Volta Bracket
Sniper Rifle · Strand · tiered, craftable, obtainable · GFS 617 · pool 99 combos · 7 copies · 52 combos covered
- Pool col 2 (10): Ambitious Assassin, Empty Traits Socket, Envious Assassin, Firmly Planted, Keep Away, Lucky Shot, Perfect Float, Shoot to Loot, Subsistence, Triple Tap
- Pool col 3 (10): Cascade Point, Empty Traits Socket, Explosive Payload, Eye of the Storm, Firing Line, Hatchling, Mega Kill Clip, Opening Shot, Rewind Rounds, Under Pressure
- Copy 1: [Ambitious Assassin, Firmly Planted, Lucky Shot] x [Firing Line, Mega Kill Clip, Rewind Rounds] — 8 combos
- Copy 2: [Ambitious Assassin, Firmly Planted, Lucky Shot] x [Cascade Point, Explosive Payload, Under Pressure] — 9 combos
- Copy 3: [Envious Assassin, Keep Away, Perfect Float] x [Mega Kill Clip, Rewind Rounds, Under Pressure] — 9 combos
- Copy 4: [Shoot to Loot, Subsistence, Triple Tap] x [Cascade Point, Mega Kill Clip, Rewind Rounds] — 9 combos
- Copy 5: [Empty Traits Socket, Firmly Planted, Shoot to Loot] x [Firing Line, Hatchling, Mega Kill Clip] — 5 combos
- Copy 6: [Envious Assassin, Subsistence, Triple Tap] x [Explosive Payload, Firing Line, Under Pressure] — 6 combos
- Copy 7: [Envious Assassin, Firmly Planted, Lucky Shot] x [Empty Traits Socket, Eye of the Storm, Opening Shot] — 6 combos

### Cataclysmic (Adept)
Linear Fusion Rifle · Solar · adept, craftable · GFS 304 · pool 81 combos · 7 copies · 50 combos covered
- Pool col 2 (9): Burning Ambition, Compulsive Reloader, Dragonfly, Fourth Time's the Charm, No Distractions, Sleight of Hand, Slideshot, Successful Warm-Up, Surplus
- Pool col 3 (9): Adaptive Munitions, Aggregate Charge, Bait and Switch, Box Breathing, Clown Cartridge, Elemental Honing, Focused Fury, High-Impact Reserves, Turnabout
- Copy 1: [Burning Ambition, No Distractions, Slideshot] x [Adaptive Munitions, Bait and Switch, Box Breathing] — 9 combos
- Copy 2: [Dragonfly, Sleight of Hand, Successful Warm-Up] x [Adaptive Munitions, Aggregate Charge, Box Breathing] — 9 combos
- Copy 3: [Burning Ambition, Compulsive Reloader, Surplus] x [Aggregate Charge, Clown Cartridge, Turnabout] — 9 combos
- Copy 4: [Fourth Time's the Charm, No Distractions, Sleight of Hand] x [Clown Cartridge, Elemental Honing, Focused Fury] — 9 combos
- Copy 5: [Compulsive Reloader, Slideshot, Surplus] x [Clown Cartridge, Elemental Honing, Turnabout] — 4 combos
- Copy 6: [Dragonfly, Sleight of Hand, Successful Warm-Up] x [Focused Fury, High-Impact Reserves, Turnabout] — 7 combos
- Copy 7: [Fourth Time's the Charm, Surplus] x [Box Breathing, Turnabout] — 3 combos

### Non-Denouement (Adept)
Combat Bow · Arc · adept, craftable · GFS 348 · pool 81 combos · 7 copies · 50 combos covered
- Pool col 2 (9): Archer's Tempo, Dragonfly, Hip-Fire Grip, Impulse Amplifier, Opening Shot, Rolling Storm, Shoot to Loot, Strategist, Successful Warm-Up
- Pool col 3 (9): Archer's Gambit, Chaos Reshaped, Desperate Measures, Explosive Head, Gear Shift, Meganeura, Moving Target, One for All, Voltshot
- Copy 1: [Hip-Fire Grip, Rolling Storm, Shoot to Loot] x [Archer's Gambit, Chaos Reshaped, Desperate Measures] — 8 combos
- Copy 2: [Archer's Tempo, Strategist, Successful Warm-Up] x [Archer's Gambit, Chaos Reshaped, Desperate Measures] — 9 combos
- Copy 3: [Archer's Tempo, Dragonfly, Opening Shot] x [Explosive Head, Gear Shift, Voltshot] — 9 combos
- Copy 4: [Shoot to Loot, Strategist, Successful Warm-Up] x [Explosive Head, Gear Shift, Meganeura] — 8 combos
- Copy 5: [Dragonfly, Impulse Amplifier, Opening Shot] x [Archer's Gambit, Desperate Measures, Moving Target] — 7 combos
- Copy 6: [Impulse Amplifier, Opening Shot, Rolling Storm] x [Gear Shift, Meganeura, One for All] — 6 combos
- Copy 7: [Archer's Tempo, Hip-Fire Grip, Successful Warm-Up] x [Explosive Head, One for All] — 3 combos

### Doom of Chelchis (Harrowed)
Scout Rifle · Void · adept, craftable · GFS 472 · pool 81 combos · 7 copies · 49 combos covered
- Pool col 2 (9): Adaptive Munitions, Demoralize, Destabilizing Rounds, Explosive Payload, Firefly, Rangefinder, Stats for All, Steady Hands, Vorpal Weapon
- Pool col 3 (9): Dragonfly, Eye of the Storm, Focused Fury, Frenzy, Meganeura, One for All, Repulsor Brace, Unrelenting, Withering Gaze
- Copy 1: [Adaptive Munitions, Demoralize, Destabilizing Rounds] x [Focused Fury, Meganeura, Withering Gaze] — 9 combos
- Copy 2: [Demoralize, Destabilizing Rounds, Explosive Payload] x [Frenzy, One for All, Unrelenting] — 9 combos
- Copy 3: [Firefly, Steady Hands, Vorpal Weapon] x [Eye of the Storm, Frenzy, Meganeura] — 8 combos
- Copy 4: [Rangefinder, Stats for All, Vorpal Weapon] x [Focused Fury, One for All, Withering Gaze] — 8 combos
- Copy 5: [Explosive Payload, Firefly, Steady Hands] x [One for All, Repulsor Brace, Withering Gaze] — 7 combos
- Copy 6: [Adaptive Munitions, Demoralize, Firefly] x [Dragonfly, Eye of the Storm, Repulsor Brace] — 4 combos
- Copy 7: [Adaptive Munitions, Explosive Payload, Vorpal Weapon] x [Dragonfly, Meganeura, Unrelenting] — 4 combos

### Anonymous Autumn
Sidearm · Arc · tiered, vendor 6-perk, obtainable · GFS 1,101 · pool 144 combos · 7 copies · 47 combos covered
- Pool col 2 (12): Attrition Orbs, Closing Time, Demolitionist, Discord, Eddy Current, Enlightened Action, Lone Wolf, Offhand Strike, Rangefinder, Strategist, To the Pain, Zen Moment
- Pool col 3 (12): Adagio, Adrenaline Junkie, Desperate Measures, Frenzy, Harmony, Kill Clip, Multikill Clip, Precision Instrument, Rampage, Surrounded, Swashbuckler, Voltshot
- Copy 1: [Attrition Orbs, Rangefinder, Strategist] x [Adagio, Multikill Clip, Voltshot] — 9 combos
- Copy 2: [Closing Time, Eddy Current, To the Pain] x [Adagio, Multikill Clip, Rampage] — 8 combos
- Copy 3: [Closing Time, Eddy Current, Strategist] x [Frenzy, Kill Clip, Precision Instrument] — 7 combos
- Copy 4: [Closing Time, Offhand Strike, Zen Moment] x [Adagio, Surrounded, Voltshot] — 7 combos
- Copy 5: [Rangefinder, To the Pain, Zen Moment] x [Adrenaline Junkie, Desperate Measures, Surrounded] — 6 combos
- Copy 6: [Attrition Orbs, Enlightened Action, Offhand Strike] x [Desperate Measures, Precision Instrument, Rampage] — 6 combos
- Copy 7: [Discord, Strategist, To the Pain] x [Precision Instrument, Surrounded, Swashbuckler] — 4 combos

### Corrective Measure (Timelost)
Machine Gun · Void · adept, craftable · GFS 367 · pool 81 combos · 7 copies · 47 combos covered
- Pool col 2 (9): Collective Demolition, Demolitionist, Destabilizing Rounds, Dimensional Shift, Dynamic Sway Reduction, Firefly, Redirection, Rewind Rounds, Subsistence
- Pool col 3 (9): Adrenaline Junkie, Aggregate Charge, Butterfly, Demoralize, Elemental Honing, High-Impact Reserves, Killing Tally, One for All, Withering Gaze
- Copy 1: [Destabilizing Rounds, Dimensional Shift, Redirection] x [Adrenaline Junkie, Butterfly, Demoralize] — 9 combos
- Copy 2: [Collective Demolition, Demolitionist, Dynamic Sway Reduction] x [Aggregate Charge, Butterfly, Demoralize] — 9 combos
- Copy 3: [Collective Demolition, Dimensional Shift, Subsistence] x [Butterfly, Elemental Honing, Withering Gaze] — 7 combos
- Copy 4: [Dimensional Shift, Firefly, Redirection] x [Elemental Honing, High-Impact Reserves, Killing Tally] — 8 combos
- Copy 5: [Dimensional Shift, Firefly, Redirection] x [Aggregate Charge, Butterfly, Demoralize] — 5 combos
- Copy 6: [Collective Demolition, Destabilizing Rounds, Subsistence] x [Demoralize, Killing Tally, One for All] — 4 combos
- Copy 7: [Collective Demolition, Dimensional Shift, Dynamic Sway Reduction] x [Adrenaline Junkie, High-Impact Reserves, One for All] — 5 combos

### Qullim's Terminus (Harrowed)
Machine Gun · Stasis · adept, craftable · GFS 390 · pool 81 combos · 7 copies · 46 combos covered
- Pool col 2 (9): Demolitionist, Dynamic Sway Reduction, Enlightened Action, Ensemble, Firmly Planted, Heating Up, Slickdraw, Stats for All, Unrelenting
- Pool col 3 (9): Crystalline Corpsebloom, Eye of the Storm, Firefly, Firing Line, Focused Fury, Headstone, Killing Tally, Mega Kill Clip, Wellspring
- Copy 1: [Enlightened Action, Ensemble, Firmly Planted] x [Crystalline Corpsebloom, Killing Tally, Mega Kill Clip] — 8 combos
- Copy 2: [Dynamic Sway Reduction, Firmly Planted, Slickdraw] x [Crystalline Corpsebloom, Firefly, Mega Kill Clip] — 5 combos
- Copy 3: [Heating Up, Stats for All, Unrelenting] x [Firing Line, Headstone, Mega Kill Clip] — 8 combos
- Copy 4: [Heating Up, Slickdraw, Unrelenting] x [Crystalline Corpsebloom, Eye of the Storm, Killing Tally] — 8 combos
- Copy 5: [Heating Up, Slickdraw, Unrelenting] x [Firefly, Focused Fury, Headstone] — 6 combos
- Copy 6: [Demolitionist, Dynamic Sway Reduction, Enlightened Action] x [Firing Line, Mega Kill Clip, Wellspring] — 7 combos
- Copy 7: [Demolitionist, Firmly Planted, Stats for All] x [Crystalline Corpsebloom, Headstone, Killing Tally] — 4 combos

### Dimensional Hypotrochoid
Grenade Launcher · Stasis · tiered, craftable, obtainable · GFS 863 · pool 99 combos · 7 copies · 45 combos covered
- Pool col 2 (10): Empty Traits Socket, Envious Arsenal, Envious Assassin, Field Prep, Genesis, Rimestealer, Shot Swap, Stats for All, Threat Detector, Unrelenting
- Pool col 3 (10): Bait and Switch, Chain Reaction, Crystalline Corpsebloom, Disruption Break, Empty Traits Socket, One for All, Pugilist, Thresh, Turnabout, Vorpal Weapon
- Copy 1: [Field Prep, Rimestealer, Shot Swap] x [Bait and Switch, Chain Reaction, Crystalline Corpsebloom] — 8 combos
- Copy 2: [Envious Arsenal, Genesis, Threat Detector] x [Crystalline Corpsebloom, Disruption Break, Pugilist] — 9 combos
- Copy 3: [Envious Arsenal, Rimestealer, Shot Swap] x [Disruption Break, Thresh, Turnabout] — 8 combos
- Copy 4: [Envious Assassin, Field Prep, Genesis] x [Bait and Switch, Pugilist, Turnabout] — 6 combos
- Copy 5: [Envious Arsenal, Envious Assassin, Rimestealer] x [Crystalline Corpsebloom, Disruption Break, Empty Traits Socket] — 5 combos
- Copy 6: [Empty Traits Socket, Threat Detector, Unrelenting] x [Bait and Switch, Pugilist, Thresh] — 6 combos
- Copy 7: [Empty Traits Socket, Field Prep, Shot Swap] x [Chain Reaction, Thresh, Vorpal Weapon] — 3 combos

### Phyllotactic Spiral
Pulse Rifle · Arc · tiered, craftable, obtainable · GFS 774 · pool 99 combos · 7 copies · 45 combos covered
- Pool col 2 (10): Compulsive Reloader, Empty Traits Socket, Hip-Fire Grip, Keep Away, Perfect Float, Rapid Hit, Shot Swap, Trickle Charge, Tunnel Vision, Under-Over
- Pool col 3 (10): Desperado, Elemental Capacitor, Empty Traits Socket, Frenzy, Gutshot Straight, Harmony, Headseeker, Kill Clip, Rolling Storm, Voltshot
- Copy 1: [Hip-Fire Grip, Perfect Float, Shot Swap] x [Desperado, Headseeker, Rolling Storm] — 9 combos
- Copy 2: [Compulsive Reloader, Trickle Charge, Under-Over] x [Desperado, Gutshot Straight, Headseeker] — 8 combos
- Copy 3: [Compulsive Reloader, Tunnel Vision, Under-Over] x [Kill Clip, Rolling Storm, Voltshot] — 7 combos
- Copy 4: [Empty Traits Socket, Trickle Charge, Tunnel Vision] x [Desperado, Harmony, Rolling Storm] — 6 combos
- Copy 5: [Perfect Float, Shot Swap, Trickle Charge] x [Empty Traits Socket, Frenzy, Voltshot] — 8 combos
- Copy 6: [Empty Traits Socket, Keep Away, Under-Over] x [Desperado, Empty Traits Socket, Headseeker] — 3 combos
- Copy 7: [Compulsive Reloader, Empty Traits Socket, Hip-Fire Grip] x [Empty Traits Socket, Frenzy, Kill Clip] — 4 combos

### Critical Anomaly (Adept)
Sniper Rifle · Stasis · adept, craftable · GFS 329 · pool 81 combos · 7 copies · 44 combos covered
- Pool col 2 (9): Built to Blast, Chill Clip, Crystalline Corpsebloom, Keep Away, Opening Shot, Quickdraw, Rampage, Reconstruction, Rewind Rounds
- Pool col 3 (9): Bait and Switch, Chaos Reshaped, Elemental Honing, Explosive Payload, Firing Line, Headstone, Mega Kill Clip, Snapshot Sights, Triple Tap
- Copy 1: [Built to Blast, Chill Clip, Opening Shot] x [Bait and Switch, Chaos Reshaped, Firing Line] — 9 combos
- Copy 2: [Built to Blast, Quickdraw, Rampage] x [Chaos Reshaped, Mega Kill Clip, Triple Tap] — 8 combos
- Copy 3: [Chill Clip, Crystalline Corpsebloom, Opening Shot] x [Explosive Payload, Mega Kill Clip, Snapshot Sights] — 9 combos
- Copy 4: [Chill Clip, Crystalline Corpsebloom, Rampage] x [Elemental Honing, Firing Line, Triple Tap] — 6 combos
- Copy 5: [Opening Shot, Quickdraw, Reconstruction] x [Elemental Honing, Headstone, Triple Tap] — 5 combos
- Copy 6: [Chill Clip, Rampage, Rewind Rounds] x [Explosive Payload, Headstone, Mega Kill Clip] — 5 combos
- Copy 7: [Rampage, Reconstruction] x [Snapshot Sights] — 2 combos

### Midha's Reckoning (Harrowed)
Fusion Rifle · Arc · adept, craftable · GFS 407 · pool 90 combos · 7 copies · 44 combos covered
- Pool col 2 (9): Backup Plan, Cornered, Field Prep, Hip-Fire Grip, Pugilist, Under Pressure, Unrelenting, Voltshot, Well-Rounded
- Pool col 3 (10): Closing Time, Gear Shift, Golden Tricorn, Golden Tricorn Enhanced, Kickstart, Reservoir Burst, Successful Warm-Up, Surrounded, Tap the Trigger, Vorpal Weapon
- Copy 1: [Backup Plan, Cornered, Pugilist] x [Golden Tricorn, Golden Tricorn Enhanced, Kickstart] — 9 combos
- Copy 2: [Backup Plan, Hip-Fire Grip, Unrelenting] x [Reservoir Burst, Successful Warm-Up, Tap the Trigger] — 8 combos
- Copy 3: [Backup Plan, Field Prep, Hip-Fire Grip] x [Closing Time, Gear Shift, Vorpal Weapon] — 9 combos
- Copy 4: [Cornered, Under Pressure, Unrelenting] x [Closing Time, Gear Shift, Kickstart] — 6 combos
- Copy 5: [Field Prep, Voltshot, Well-Rounded] x [Gear Shift, Kickstart, Reservoir Burst] — 6 combos
- Copy 6: [Pugilist, Under Pressure] x [Closing Time, Reservoir Burst, Surrounded] — 4 combos
- Copy 7: [Field Prep, Well-Rounded] x [Tap the Trigger, Vorpal Weapon] — 2 combos

### Royal Entry
Rocket Launcher · Void · vendor 6-perk, obtainable · GFS 674 · pool 90 combos · 7 copies · 44 combos covered
- Pool col 2 (9): Auto-Loading Holster, Field Prep, Genesis, Impulse Amplifier, Moving Target, Pulse Monitor, Quickdraw, Rangefinder, Threat Detector
- Pool col 3 (10): Ambitious Assassin, Chain Reaction, Clown Cartridge, Cluster Bomb, Demolitionist, Lasting Impression, One for All, Thresh, Unrelenting, Wellspring
- Copy 1: [Genesis, Pulse Monitor, Rangefinder] x [Ambitious Assassin, Chain Reaction, Clown Cartridge] — 9 combos
- Copy 2: [Field Prep, Moving Target, Rangefinder] x [Clown Cartridge, Cluster Bomb, Lasting Impression] — 8 combos
- Copy 3: [Field Prep, Pulse Monitor, Threat Detector] x [Ambitious Assassin, Cluster Bomb, Lasting Impression] — 6 combos
- Copy 4: [Impulse Amplifier, Moving Target, Threat Detector] x [Ambitious Assassin, Chain Reaction, Clown Cartridge] — 6 combos
- Copy 5: [Auto-Loading Holster, Impulse Amplifier, Quickdraw] x [Clown Cartridge, Lasting Impression, Thresh] — 5 combos
- Copy 6: [Auto-Loading Holster, Impulse Amplifier, Rangefinder] x [Ambitious Assassin, Cluster Bomb, Unrelenting] — 5 combos
- Copy 7: [Genesis, Impulse Amplifier, Rangefinder] x [Demolitionist, Wellspring] — 5 combos

### Pure Poetry
Hand Cannon · Kinetic · vendor 6-perk, obtainable · GFS 1,182 · pool 144 combos · 7 copies · 42 combos covered
- Pool col 2 (12): Air Assault, Ambitious Assassin, Ensemble, Fourth Time's the Charm, Fragile Focus, Grave Robber, Outlaw, Perpetual Motion, Shoot to Loot, Steady Hands, Tunnel Vision, Well-Rounded
- Pool col 3 (12): Elemental Capacitor, Eye of the Storm, Focused Fury, Frenzy, Harmony, Multikill Clip, Opening Shot, Osmosis, Pugilist, Rampage, Swashbuckler, Under-Over
- Copy 1: [Air Assault, Grave Robber, Shoot to Loot] x [Elemental Capacitor, Swashbuckler, Under-Over] — 7 combos
- Copy 2: [Ensemble, Fourth Time's the Charm, Grave Robber] x [Focused Fury, Osmosis, Under-Over] — 6 combos
- Copy 3: [Air Assault, Ambitious Assassin, Well-Rounded] x [Focused Fury, Osmosis, Pugilist] — 8 combos
- Copy 4: [Air Assault, Ensemble, Fragile Focus] x [Frenzy, Harmony, Rampage] — 7 combos
- Copy 5: [Ambitious Assassin, Fragile Focus, Well-Rounded] x [Elemental Capacitor, Multikill Clip, Swashbuckler] — 7 combos
- Copy 6: [Fragile Focus, Grave Robber, Shoot to Loot] x [Harmony, Osmosis, Pugilist] — 3 combos
- Copy 7: [Ensemble, Steady Hands, Well-Rounded] x [Eye of the Storm, Rampage, Swashbuckler] — 4 combos

### Crisis Inverted
Hand Cannon · Arc · vendor 6-perk, obtainable · GFS 1,566 · pool 144 combos · 7 copies · 40 combos covered
- Pool col 2 (12): Compulsive Reloader, Demolitionist, Ensemble, Heating Up, Moving Target, Outlaw, Rapid Hit, Shoot to Loot, Stats for All, Steady Hands, Tunnel Vision, Under Pressure
- Pool col 3 (12): Adaptive Munitions, Adrenaline Junkie, Elemental Capacitor, Focused Fury, Harmony, Kill Clip, One for All, Opening Shot, Rangefinder, Snapshot Sights, Turnabout, Vorpal Weapon
- Copy 1: [Heating Up, Outlaw, Steady Hands] x [Adaptive Munitions, Opening Shot, Turnabout] — 8 combos
- Copy 2: [Moving Target, Stats for All, Tunnel Vision] x [Adaptive Munitions, Rangefinder, Turnabout] — 5 combos
- Copy 3: [Demolitionist, Rapid Hit, Under Pressure] x [Adaptive Munitions, Rangefinder, Turnabout] — 7 combos
- Copy 4: [Compulsive Reloader, Ensemble, Shoot to Loot] x [Adaptive Munitions, Kill Clip, Rangefinder] — 4 combos
- Copy 5: [Compulsive Reloader, Stats for All, Steady Hands] x [Opening Shot, Rangefinder, Snapshot Sights] — 5 combos
- Copy 6: [Compulsive Reloader, Ensemble, Shoot to Loot] x [Elemental Capacitor, Harmony, Snapshot Sights] — 5 combos
- Copy 7: [Demolitionist, Outlaw, Under Pressure] x [Elemental Capacitor, Focused Fury, Snapshot Sights] — 6 combos

### The Third Axiom
Pulse Rifle · Arc · tiered, vendor 6-perk, obtainable · GFS 1,362 · pool 144 combos · 7 copies · 40 combos covered
- Pool col 2 (12): Feeding Frenzy, Genesis, Hip-Fire Grip, Killing Wind, Moving Target, Quickdraw, Rangefinder, Slideshot, Slideways, Subsistence, Surplus, Zen Moment
- Pool col 3 (12): Disruption Break, Dragonfly, Elemental Capacitor, Headseeker, Multikill Clip, One for All, Opening Shot, Rampage, Sympathetic Arsenal, Thresh, Unrelenting, Vorpal Weapon
- Copy 1: [Genesis, Quickdraw, Slideshot] x [Headseeker, One for All, Sympathetic Arsenal] — 8 combos
- Copy 2: [Moving Target, Rangefinder, Zen Moment] x [Disruption Break, Sympathetic Arsenal, Thresh] — 9 combos
- Copy 3: [Feeding Frenzy, Hip-Fire Grip, Slideways] x [Headseeker, Opening Shot, Sympathetic Arsenal] — 7 combos
- Copy 4: [Genesis, Slideshot, Subsistence] x [Elemental Capacitor, Sympathetic Arsenal, Unrelenting] — 3 combos
- Copy 5: [Slideshot, Surplus, Zen Moment] x [Disruption Break, Sympathetic Arsenal, Unrelenting] — 4 combos
- Copy 6: [Genesis, Hip-Fire Grip, Zen Moment] x [Disruption Break, Dragonfly, Opening Shot] — 4 combos
- Copy 7: [Genesis, Killing Wind, Zen Moment] x [One for All, Sympathetic Arsenal, Vorpal Weapon] — 5 combos

### Servant Leader
Scout Rifle · Kinetic · vendor 6-perk, obtainable · GFS 1,538 · pool 144 combos · 7 copies · 36 combos covered
- Pool col 2 (12): Fourth Time's the Charm, Heating Up, Hip-Fire Grip, Killing Wind, No Distractions, Outlaw, Pulse Monitor, Rapid Hit, Shoot to Loot, Subsistence, Surplus, Tunnel Vision
- Pool col 3 (12): Adrenaline Junkie, Frenzy, Harmony, Kill Clip, Multikill Clip, One for All, Osmosis, Rampage, Snapshot Sights, Thresh, Unrelenting, Wellspring
- Copy 1: [Heating Up, Pulse Monitor, Shoot to Loot] x [Harmony, Osmosis, Thresh] — 6 combos
- Copy 2: [Killing Wind, Rapid Hit, Subsistence] x [Osmosis, Snapshot Sights, Thresh] — 7 combos
- Copy 3: [No Distractions, Pulse Monitor, Tunnel Vision] x [Adrenaline Junkie, One for All, Osmosis] — 6 combos
- Copy 4: [No Distractions, Pulse Monitor, Surplus] x [Kill Clip, Osmosis, Wellspring] — 6 combos
- Copy 5: [Hip-Fire Grip, Rapid Hit, Subsistence] x [Osmosis, Thresh, Wellspring] — 4 combos
- Copy 6: [Hip-Fire Grip, Pulse Monitor, Rapid Hit] x [Adrenaline Junkie, Harmony, Multikill Clip] — 4 combos
- Copy 7: [Heating Up, Hip-Fire Grip, Rapid Hit] x [Frenzy, Rampage] — 3 combos

### Found Verdict (Timelost)
Shotgun · Arc · adept, craftable · GFS 369 · pool 81 combos · 6 copies · 45 combos covered
- Pool col 2 (9): Aggregate Charge, Barrel Constrictor, Discord, Pugilist, Rewind Rounds, Slideshot, Supercharged Magazine, Threat Detector, Threat Remover
- Pool col 3 (9): Binary Orbit, Desperate Measures, Elemental Honing, Gear Shift, One-Two Punch, Opening Shot, Rolling Storm, Trench Barrel, Voltshot
- Copy 1: [Aggregate Charge, Barrel Constrictor, Supercharged Magazine] x [Binary Orbit, Desperate Measures, Elemental Honing] — 8 combos
- Copy 2: [Aggregate Charge, Barrel Constrictor, Slideshot] x [Gear Shift, One-Two Punch, Rolling Storm] — 8 combos
- Copy 3: [Aggregate Charge, Barrel Constrictor, Threat Remover] x [Elemental Honing, Trench Barrel, Voltshot] — 7 combos
- Copy 4: [Rewind Rounds, Supercharged Magazine, Threat Remover] x [One-Two Punch, Rolling Storm, Trench Barrel] — 7 combos
- Copy 5: [Discord, Slideshot, Threat Remover] x [Binary Orbit, Desperate Measures, Gear Shift] — 8 combos
- Copy 6: [Barrel Constrictor, Pugilist, Threat Detector] x [Gear Shift, Opening Shot, Rolling Storm] — 7 combos

### Smite of Merain (Harrowed)
Pulse Rifle · Kinetic · adept, craftable · GFS 582 · pool 81 combos · 6 copies · 44 combos covered
- Pool col 2 (9): Ancillary Ordinance, Bewildering Burst, Demolitionist, Ensemble, Focused Fury, Moving Target, Pugilist, Stats for All, Well-Rounded
- Pool col 3 (9): Adhesive Ordnance, Adrenaline Junkie, All-Star, Eye of the Storm, Firefly, Gutshot Straight, One for All, Swashbuckler, Vorpal Weapon
- Copy 1: [Demolitionist, Ensemble, Focused Fury] x [Adhesive Ordnance, All-Star, One for All] — 9 combos
- Copy 2: [Ancillary Ordinance, Pugilist, Well-Rounded] x [Adhesive Ordnance, Adrenaline Junkie, All-Star] — 9 combos
- Copy 3: [Ancillary Ordinance, Bewildering Burst, Focused Fury] x [Adrenaline Junkie, Eye of the Storm, Firefly] — 7 combos
- Copy 4: [Ancillary Ordinance, Bewildering Burst, Focused Fury] x [Gutshot Straight, One for All, Swashbuckler] — 8 combos
- Copy 5: [Ancillary Ordinance, Moving Target, Stats for All] x [Adhesive Ordnance, All-Star, Vorpal Weapon] — 6 combos
- Copy 6: [Moving Target, Pugilist, Stats for All] x [Firefly, Gutshot Straight, Vorpal Weapon] — 5 combos

### Exile's Curse
Fusion Rifle · Arc · tiered, obtainable · GFS 669 · pool 100 combos · 6 copies · 43 combos covered
- Pool col 2 (10): Field Prep, Firmly Planted, Grave Robber, Hip-Fire Grip, Killing Wind, No Distractions, Pulse Monitor, Quickdraw, Slideshot, Threat Detector
- Pool col 3 (10): Backup Plan, Celerity, Disruption Break, Elemental Capacitor, Feeding Frenzy, High-Impact Reserves, Kickstart, Multikill Clip, Snapshot Sights, Vorpal Weapon
- Copy 1: [Field Prep, No Distractions, Pulse Monitor] x [Backup Plan, Celerity, Disruption Break] — 9 combos
- Copy 2: [Field Prep, Firmly Planted, Grave Robber] x [Celerity, Feeding Frenzy, Kickstart] — 7 combos
- Copy 3: [Hip-Fire Grip, Killing Wind, No Distractions] x [Backup Plan, Feeding Frenzy, Kickstart] — 8 combos
- Copy 4: [Pulse Monitor, Quickdraw, Slideshot] x [Backup Plan, Feeding Frenzy, Kickstart] — 8 combos
- Copy 5: [Killing Wind, Slideshot, Threat Detector] x [Backup Plan, Celerity, Feeding Frenzy] — 5 combos
- Copy 6: [Field Prep, Firmly Planted, No Distractions] x [Elemental Capacitor, Multikill Clip, Vorpal Weapon] — 6 combos

### Swordbreaker (Adept)
Shotgun · Strand · adept, craftable · GFS 560 · pool 90 combos · 6 copies · 41 combos covered
- Pool col 2 (9): Demolitionist, Elemental Capacitor, Fragile Focus, Paracausal Affinity, Pugilist, Slice, Slideshot, Subsistence, Threat Detector
- Pool col 3 (10): Aggregate Charge, Barrel Constrictor, Chaos Reshaped, Golden Tricorn, Golden Tricorn Enhanced, Hatchling, One-Two Punch, Opening Shot, Surrounded, Sword Logic
- Copy 1: [Elemental Capacitor, Fragile Focus, Paracausal Affinity] x [Aggregate Charge, Barrel Constrictor, Chaos Reshaped] — 8 combos
- Copy 2: [Demolitionist, Slice, Subsistence] x [Barrel Constrictor, One-Two Punch, Opening Shot] — 7 combos
- Copy 3: [Elemental Capacitor, Paracausal Affinity, Threat Detector] x [Chaos Reshaped, Surrounded, Sword Logic] — 7 combos
- Copy 4: [Paracausal Affinity, Slideshot, Threat Detector] x [Golden Tricorn, Golden Tricorn Enhanced, Hatchling] — 7 combos
- Copy 5: [Elemental Capacitor, Paracausal Affinity, Slideshot] x [Barrel Constrictor, One-Two Punch, Opening Shot] — 5 combos
- Copy 6: [Fragile Focus, Pugilist, Slideshot] x [Aggregate Charge, One-Two Punch, Sword Logic] — 7 combos

### False Idols
Sword · Solar · tiered, craftable, obtainable · GFS 731 · pool 99 combos · 6 copies · 40 combos covered
- Pool col 2 (10): Attrition Orbs, Duelist's Trance, Eager Edge, Empty Traits Socket, Flash Counter, Incandescent, Relentless Strikes, Strategist, Unrelenting, Wellspring
- Pool col 3 (10): Bait and Switch, Burning Ambition, Chain Reaction, Collective Action, Counterattack, Elemental Honing, Empty Traits Socket, One for All, Surrounded, Vorpal Weapon
- Copy 1: [Attrition Orbs, Flash Counter, Wellspring] x [Bait and Switch, Burning Ambition, Counterattack] — 8 combos
- Copy 2: [Duelist's Trance, Eager Edge, Strategist] x [Burning Ambition, Counterattack, Empty Traits Socket] — 9 combos
- Copy 3: [Incandescent, Relentless Strikes, Unrelenting] x [Burning Ambition, Counterattack, One for All] — 9 combos
- Copy 4: [Eager Edge, Flash Counter, Incandescent] x [Collective Action, One for All, Surrounded] — 5 combos
- Copy 5: [Empty Traits Socket, Flash Counter, Wellspring] x [Counterattack, Elemental Honing, Empty Traits Socket] — 5 combos
- Copy 6: [Duelist's Trance, Unrelenting] x [Chain Reaction, Empty Traits Socket, Surrounded] — 4 combos

### Iterative Loop
Fusion Rifle · Arc · tiered, craftable, obtainable · GFS 651 · pool 99 combos · 6 copies · 40 combos covered
- Pool col 2 (10): Compulsive Reloader, Empty Traits Socket, Grave Robber, Killing Wind, Lead from Gold, Slickdraw, Successful Warm-Up, Supercharged Magazine, Under Pressure, Well-Rounded
- Pool col 3 (10): Adagio, Adrenaline Junkie, Closing Time, Controlled Burst, Demolitionist, Elemental Capacitor, Empty Traits Socket, Kickstart, Pugilist, Voltshot
- Copy 1: [Compulsive Reloader, Supercharged Magazine, Well-Rounded] x [Adagio, Closing Time, Kickstart] — 8 combos
- Copy 2: [Grave Robber, Killing Wind, Supercharged Magazine] x [Adrenaline Junkie, Controlled Burst, Demolitionist] — 8 combos
- Copy 3: [Slickdraw, Successful Warm-Up, Supercharged Magazine] x [Adrenaline Junkie, Demolitionist, Elemental Capacitor] — 7 combos
- Copy 4: [Compulsive Reloader, Slickdraw, Supercharged Magazine] x [Controlled Burst, Pugilist, Voltshot] — 6 combos
- Copy 5: [Successful Warm-Up, Supercharged Magazine, Well-Rounded] x [Empty Traits Socket, Pugilist, Voltshot] — 6 combos
- Copy 6: [Empty Traits Socket, Under Pressure] x [Adagio, Controlled Burst, Voltshot] — 5 combos

### Praedyth's Revenge (Timelost)
Sniper Rifle · Kinetic · adept, craftable · GFS 420 · pool 81 combos · 6 copies · 39 combos covered
- Pool col 2 (9): Bewildering Burst, Discord, Envious Arsenal, Fourth Time's the Charm, Kinetic Tremors, No Distractions, Osmosis, Rewind Rounds, Snapshot Sights
- Pool col 3 (9): All-Star, Bait and Switch, Closing Time, Elemental Honing, Firefly, Frenzy, High-Impact Reserves, Opening Shot, Precision Instrument
- Copy 1: [Bewildering Burst, Envious Arsenal, Fourth Time's the Charm] x [All-Star, Bait and Switch, Closing Time] — 9 combos
- Copy 2: [Bewildering Burst, Kinetic Tremors, Osmosis] x [Bait and Switch, Closing Time, High-Impact Reserves] — 6 combos
- Copy 3: [Discord, Envious Arsenal, Fourth Time's the Charm] x [All-Star, Firefly, High-Impact Reserves] — 7 combos
- Copy 4: [Bewildering Burst, Kinetic Tremors, No Distractions] x [Firefly, Frenzy, Opening Shot] — 6 combos
- Copy 5: [Bewildering Burst, Kinetic Tremors, Osmosis] x [Elemental Honing, Firefly, Precision Instrument] — 7 combos
- Copy 6: [Envious Arsenal, Osmosis, Snapshot Sights] x [Bait and Switch, Frenzy, Opening Shot] — 4 combos

### Reghusk's Pledge
Auto Rifle · Void · tiered, obtainable · GFS 256 · pool 56 combos · 6 copies · 38 combos covered
- Pool col 2 (7): Built to Blast, Demoralize, Destabilizing Rounds, Dynamic Sway Reduction, Impromptu Ammunition, Proximity Power, Rewind Rounds
- Pool col 3 (8): Attrition Orbs, Golden Tricorn, Golden Tricorn Enhanced, Kill Clip, Repulsor Brace, Swashbuckler, Target Lock, Zen Moment
- Copy 1: [Built to Blast, Demoralize, Impromptu Ammunition] x [Attrition Orbs, Golden Tricorn, Golden Tricorn Enhanced] — 9 combos
- Copy 2: [Built to Blast, Demoralize, Proximity Power] x [Attrition Orbs, Kill Clip, Swashbuckler] — 7 combos
- Copy 3: [Built to Blast, Demoralize, Proximity Power] x [Golden Tricorn, Golden Tricorn Enhanced, Target Lock] — 5 combos
- Copy 4: [Impromptu Ammunition, Proximity Power, Rewind Rounds] x [Repulsor Brace, Swashbuckler, Zen Moment] — 7 combos
- Copy 5: [Destabilizing Rounds, Dynamic Sway Reduction, Rewind Rounds] x [Attrition Orbs, Golden Tricorn, Golden Tricorn Enhanced] — 7 combos
- Copy 6: [Destabilizing Rounds, Impromptu Ammunition] x [Kill Clip, Swashbuckler, Target Lock] — 3 combos

### The Call
Sidearm · Strand · tiered, craftable, obtainable · GFS 1,088 · pool 109 combos · 6 copies · 36 combos covered
- Pool col 2 (10): Beacon Rounds, Demolitionist, Empty Traits Socket, Impulse Amplifier, Lead from Gold, Reconstruction, Slice, Stats for All, Strategist, Subsistence
- Pool col 3 (11): Adrenaline Junkie, Aggregate Charge, Chaos Reshaped, Desperate Measures, Empty Traits Socket, Golden Tricorn, Golden Tricorn Enhanced, Hatchling, Multikill Clip, One for All, Vorpal Weapon
- Copy 1: [Beacon Rounds, Lead from Gold, Strategist] x [Aggregate Charge, Chaos Reshaped, Hatchling] — 8 combos
- Copy 2: [Beacon Rounds, Reconstruction, Slice] x [Desperate Measures, Multikill Clip, Vorpal Weapon] — 8 combos
- Copy 3: [Empty Traits Socket, Impulse Amplifier, Slice] x [Adrenaline Junkie, Aggregate Charge, Multikill Clip] — 8 combos
- Copy 4: [Slice, Stats for All, Strategist] x [Desperate Measures, Empty Traits Socket, Golden Tricorn] — 5 combos
- Copy 5: [Beacon Rounds, Stats for All, Subsistence] x [Aggregate Charge, Multikill Clip, One for All] — 3 combos
- Copy 6: [Empty Traits Socket, Impulse Amplifier, Subsistence] x [Empty Traits Socket, Golden Tricorn, Golden Tricorn Enhanced] — 4 combos

### Round Robin
Hand Cannon · Strand · tiered, craftable, obtainable · GFS 1,014 · pool 109 combos · 6 copies · 32 combos covered
- Pool col 2 (10): Empty Traits Socket, Envious Assassin, Fourth Time's the Charm, Keep Away, Killing Wind, Perfect Float, Slideshot, Subsistence, Tear, Under Pressure
- Pool col 3 (11): Adagio, Elemental Capacitor, Empty Traits Socket, Golden Tricorn, Golden Tricorn Enhanced, Harmony, Hatchling, Kill Clip, Opening Shot, Precision Instrument, Pugilist
- Copy 1: [Envious Assassin, Fourth Time's the Charm, Tear] x [Adagio, Elemental Capacitor, Kill Clip] — 9 combos
- Copy 2: [Fourth Time's the Charm, Slideshot, Tear] x [Empty Traits Socket, Golden Tricorn, Harmony] — 6 combos
- Copy 3: [Fourth Time's the Charm, Slideshot, Tear] x [Golden Tricorn Enhanced, Opening Shot, Pugilist] — 5 combos
- Copy 4: [Keep Away, Subsistence, Tear] x [Adagio, Precision Instrument, Pugilist] — 5 combos
- Copy 5: [Envious Assassin, Perfect Float, Under Pressure] x [Adagio, Hatchling, Precision Instrument] — 3 combos
- Copy 6: [Envious Assassin, Keep Away, Under Pressure] x [Empty Traits Socket, Golden Tricorn, Harmony] — 4 combos

### Abyss Defiant (Adept)
Auto Rifle · Solar · adept, craftable · GFS 612 · pool 90 combos · 6 copies · 30 combos covered
- Pool col 2 (10): Burning Ambition, Enlightened Action, Heal Clip, Outlaw, Proximity Power, Pugilist, Reconstruction, Stats for All, Subsistence, Zen Moment
- Pool col 3 (9): Binary Orbit, Collective Action, Collective Pugilism, Eye of the Storm, Incandescent, Kill Clip, Swashbuckler, Sword Logic, Target Lock
- Copy 1: [Burning Ambition, Proximity Power, Reconstruction] x [Collective Action, Eye of the Storm, Kill Clip] — 7 combos
- Copy 2: [Enlightened Action, Outlaw, Reconstruction] x [Binary Orbit, Collective Pugilism, Sword Logic] — 7 combos
- Copy 3: [Burning Ambition, Proximity Power, Zen Moment] x [Binary Orbit, Collective Pugilism, Swashbuckler] — 6 combos
- Copy 4: [Outlaw, Stats for All, Subsistence] x [Collective Action, Incandescent, Sword Logic] — 5 combos
- Copy 5: [Enlightened Action, Heal Clip, Reconstruction] x [Eye of the Storm, Swashbuckler, Target Lock] — 3 combos
- Copy 6: [Pugilist] x [Eye of the Storm, Kill Clip] — 2 combos

### Borrowed Time
Submachine Gun · Solar · vendor 6-perk, obtainable · GFS 1,510 · pool 144 combos · 6 copies · 30 combos covered
- Pool col 2 (12): Dynamic Sway Reduction, Feeding Frenzy, Firmly Planted, Fourth Time's the Charm, Grave Robber, Heating Up, Killing Wind, Overflow, Rangefinder, Surplus, Threat Detector, Tunnel Vision
- Pool col 3 (12): Adrenaline Junkie, Demolitionist, Dragonfly, Frenzy, One for All, Rampage, Snapshot Sights, Surrounded, Swashbuckler, Tap the Trigger, Thresh, Wellspring
- Copy 1: [Firmly Planted, Overflow, Tunnel Vision] x [Adrenaline Junkie, Demolitionist, Dragonfly] — 7 combos
- Copy 2: [Heating Up, Overflow, Tunnel Vision] x [Snapshot Sights, Surrounded, Thresh] — 6 combos
- Copy 3: [Firmly Planted, Fourth Time's the Charm, Overflow] x [Snapshot Sights, Thresh, Wellspring] — 6 combos
- Copy 4: [Dynamic Sway Reduction, Grave Robber, Heating Up] x [One for All, Swashbuckler, Thresh] — 4 combos
- Copy 5: [Firmly Planted, Rangefinder, Surplus] x [Dragonfly, One for All, Rampage] — 5 combos
- Copy 6: [Threat Detector] x [One for All, Snapshot Sights] — 2 combos

### Chain of Command
Machine Gun · Stasis · tiered, vendor 6-perk, obtainable · GFS 228 · pool 49 combos · 5 copies · 38 combos covered
- Pool col 2 (7): Adrenaline Junkie, Headstone, Osmosis, Overflow, Subsistence, Turnabout, Under-Over
- Pool col 3 (7): Adaptive Munitions, Demolitionist, Desperate Measures, Focused Fury, Killing Tally, Meganeura, Target Lock
- Copy 1: [Headstone, Osmosis, Overflow] x [Adaptive Munitions, Desperate Measures, Meganeura] — 9 combos
- Copy 2: [Adrenaline Junkie, Turnabout, Under-Over] x [Adaptive Munitions, Desperate Measures, Killing Tally] — 9 combos
- Copy 3: [Adrenaline Junkie, Turnabout, Under-Over] x [Focused Fury, Meganeura, Target Lock] — 9 combos
- Copy 4: [Headstone, Osmosis, Subsistence] x [Adaptive Munitions, Killing Tally, Target Lock] — 7 combos
- Copy 5: [Headstone, Osmosis, Under-Over] x [Demolitionist, Focused Fury] — 4 combos

### Albedo Wing
Glaive · Arc · tiered, obtainable · GFS 225 · pool 56 combos · 5 copies · 37 combos covered
- Pool col 2 (7): Beacon Rounds, Clown Cartridge, Field Prep, Grave Robber, Immovable Object, Keep Away, Replenishing Aegis
- Pool col 3 (8): Attrition Orbs, Close to Melee, Deconstruct, Demolitionist, Golden Tricorn, Golden Tricorn Enhanced, High-Impact Reserves, Lead from Gold
- Copy 1: [Field Prep, Immovable Object, Replenishing Aegis] x [Attrition Orbs, Close to Melee, Deconstruct] — 8 combos
- Copy 2: [Beacon Rounds, Clown Cartridge, Keep Away] x [Close to Melee, High-Impact Reserves, Lead from Gold] — 9 combos
- Copy 3: [Beacon Rounds, Immovable Object, Replenishing Aegis] x [Demolitionist, Golden Tricorn, Golden Tricorn Enhanced] — 9 combos
- Copy 4: [Grave Robber, Immovable Object, Replenishing Aegis] x [Golden Tricorn Enhanced, High-Impact Reserves, Lead from Gold] — 7 combos
- Copy 5: [Clown Cartridge, Field Prep] x [Attrition Orbs, Golden Tricorn, Lead from Gold] — 4 combos

### Defiance of Yasmin (Harrowed)
Sniper Rifle · Kinetic · adept, craftable · GFS 478 · pool 81 combos · 5 copies · 37 combos covered
- Pool col 2 (9): Ensemble, Firefly, Lead from Gold, No Distractions, Osmosis, Rewind Rounds, Shoot to Loot, Snapshot Sights, Stopping Power
- Pool col 3 (9): Aggregate Charge, All-Star, Demolitionist, Firing Line, Focused Fury, Moving Target, Opening Shot, Slickdraw, Vorpal Weapon
- Copy 1: [Osmosis, Shoot to Loot, Stopping Power] x [Aggregate Charge, Demolitionist, Firing Line] — 9 combos
- Copy 2: [Firefly, Lead from Gold, Rewind Rounds] x [All-Star, Firing Line, Slickdraw] — 8 combos
- Copy 3: [Ensemble, Shoot to Loot, Stopping Power] x [Moving Target, Opening Shot, Slickdraw] — 9 combos
- Copy 4: [Osmosis, Rewind Rounds, Stopping Power] x [All-Star, Opening Shot, Vorpal Weapon] — 6 combos
- Copy 5: [No Distractions, Osmosis, Snapshot Sights] x [Focused Fury, Moving Target, Slickdraw] — 5 combos

### Deliverance (Adept)
Fusion Rifle · Stasis · adept, craftable · GFS 466 · pool 81 combos · 5 copies · 36 combos covered
- Pool col 2 (9): Compulsive Reloader, Cornered, Crystalline Corpsebloom, Demolitionist, Heating Up, Lone Wolf, Perpetual Motion, Sleight of Hand, Steady Hands
- Pool col 3 (9): Adrenaline Junkie, Bait and Switch, Chain Reaction, Chill Clip, Controlled Burst, Harmony, Successful Warm-Up, Surrounded, Tap the Trigger
- Copy 1: [Compulsive Reloader, Cornered, Crystalline Corpsebloom] x [Adrenaline Junkie, Chain Reaction, Chill Clip] — 9 combos
- Copy 2: [Heating Up, Lone Wolf, Sleight of Hand] x [Chain Reaction, Chill Clip, Controlled Burst] — 9 combos
- Copy 3: [Cornered, Crystalline Corpsebloom, Steady Hands] x [Controlled Burst, Harmony, Surrounded] — 8 combos
- Copy 4: [Cornered, Crystalline Corpsebloom, Sleight of Hand] x [Bait and Switch, Successful Warm-Up, Tap the Trigger] — 7 combos
- Copy 5: [Compulsive Reloader, Demolitionist, Lone Wolf] x [Chill Clip, Successful Warm-Up, Tap the Trigger] — 3 combos

### Vision of Confluence (Timelost)
Scout Rifle · Solar · adept, craftable · GFS 477 · pool 81 combos · 5 copies · 36 combos covered
- Pool col 2 (9): Butterfly, Demolitionist, Heal Clip, Incandescent, Light Touch, Outlaw, Rewind Rounds, Tunnel Vision, Zen Moment
- Pool col 3 (9): Burning Ambition, Desperate Measures, Elemental Honing, Explosive Payload, Firefly, Frenzy, Kill Clip, Master of Arms, Paracausal Affinity
- Copy 1: [Butterfly, Incandescent, Tunnel Vision] x [Burning Ambition, Desperate Measures, Elemental Honing] — 8 combos
- Copy 2: [Butterfly, Incandescent, Light Touch] x [Explosive Payload, Frenzy, Kill Clip] — 8 combos
- Copy 3: [Butterfly, Heal Clip, Outlaw] x [Elemental Honing, Master of Arms, Paracausal Affinity] — 8 combos
- Copy 4: [Incandescent, Light Touch, Zen Moment] x [Elemental Honing, Firefly, Master of Arms] — 7 combos
- Copy 5: [Light Touch, Tunnel Vision, Zen Moment] x [Burning Ambition, Master of Arms, Paracausal Affinity] — 5 combos

### Fatebringer (Timelost)
Hand Cannon · Kinetic · adept, craftable · GFS 329 · pool 81 combos · 5 copies · 35 combos covered
- Pool col 2 (9): Explosive Payload, Impromptu Ammunition, Keep Away, Kinetic Tremors, Opening Shot, Osmosis, Rewind Rounds, Stopping Power, To the Pain
- Pool col 3 (9): All-Star, Binary Orbit, Elemental Honing, Eye of the Storm, Firefly, Frenzy, Magnificent Howl, One for All, Precision Instrument
- Copy 1: [Explosive Payload, Kinetic Tremors, Opening Shot] x [All-Star, Binary Orbit, Magnificent Howl] — 9 combos
- Copy 2: [Osmosis, Rewind Rounds, Stopping Power] x [Binary Orbit, Eye of the Storm, Magnificent Howl] — 8 combos
- Copy 3: [Impromptu Ammunition, Osmosis, To the Pain] x [Binary Orbit, Magnificent Howl, One for All] — 7 combos
- Copy 4: [Keep Away, Opening Shot, Stopping Power] x [Binary Orbit, One for All, Precision Instrument] — 7 combos
- Copy 5: [Keep Away, Stopping Power, To the Pain] x [Elemental Honing, Firefly, Frenzy] — 4 combos

### Nessa's Oblation (Adept)
Shotgun · Void · adept, craftable · GFS 679 · pool 81 combos · 5 copies · 35 combos covered
- Pool col 2 (9): Compulsive Reloader, Demolitionist, Dragonfly, Envious Assassin, Fourth Time's the Charm, Proximity Power, Rapid Hit, Reconstruction, Repulsor Brace
- Pool col 3 (9): Demoralize, Destabilizing Rounds, Focused Fury, Frenzy, Harmony, Meganeura, Opening Shot, Paracausal Affinity, Vorpal Weapon
- Copy 1: [Compulsive Reloader, Dragonfly, Envious Assassin] x [Destabilizing Rounds, Meganeura, Paracausal Affinity] — 9 combos
- Copy 2: [Envious Assassin, Proximity Power, Reconstruction] x [Demoralize, Focused Fury, Meganeura] — 8 combos
- Copy 3: [Fourth Time's the Charm, Proximity Power, Repulsor Brace] x [Harmony, Meganeura, Paracausal Affinity] — 7 combos
- Copy 4: [Fourth Time's the Charm, Proximity Power, Rapid Hit] x [Destabilizing Rounds, Frenzy, Paracausal Affinity] — 6 combos
- Copy 5: [Demolitionist, Dragonfly, Reconstruction] x [Frenzy, Harmony, Paracausal Affinity] — 5 combos

### Summum Bonum (Adept)
Sword · Arc · adept, craftable · GFS 525 · pool 81 combos · 5 copies · 35 combos covered
- Pool col 2 (9): Attrition Orbs, Deconstruct, Duelist's Trance, Proximity Power, Relentless Strikes, Sharp Harvest, Strategist, Tireless Blade, Unrelenting
- Pool col 3 (9): Bait and Switch, Chain Reaction, Chaos Reshaped, Elemental Honing, Jolting Feedback, One for All, Surrounded, Vorpal Weapon, Whirlwind Blade
- Copy 1: [Proximity Power, Sharp Harvest, Tireless Blade] x [Bait and Switch, Chaos Reshaped, Jolting Feedback] — 9 combos
- Copy 2: [Deconstruct, Duelist's Trance, Relentless Strikes] x [Bait and Switch, Chaos Reshaped, Whirlwind Blade] — 9 combos
- Copy 3: [Attrition Orbs, Strategist, Unrelenting] x [Chaos Reshaped, Jolting Feedback, Whirlwind Blade] — 6 combos
- Copy 4: [Deconstruct, Relentless Strikes, Sharp Harvest] x [Elemental Honing, Jolting Feedback, Vorpal Weapon] — 6 combos
- Copy 5: [Deconstruct, Sharp Harvest, Strategist] x [Chain Reaction, Elemental Honing, One for All] — 5 combos

### Bellowing Giant
Rocket Launcher · Void · tiered, vendor 6-perk, obtainable · GFS 128 · pool 49 combos · 5 copies · 34 combos covered
- Pool col 2 (7): Air Trigger, Ambitious Assassin, Impromptu Ammunition, Lasting Impression, Overflow, Quickdraw, Tracking Module
- Pool col 3 (7): Aggregate Charge, Auto-Loading Holster, Bipod, Clown Cartridge, Cluster Bomb, Collective Demolition, Reaper's Tithe
- Copy 1: [Air Trigger, Ambitious Assassin, Lasting Impression] x [Aggregate Charge, Clown Cartridge, Collective Demolition] — 9 combos
- Copy 2: [Air Trigger, Impromptu Ammunition, Overflow] x [Auto-Loading Holster, Bipod, Reaper's Tithe] — 8 combos
- Copy 3: [Impromptu Ammunition, Lasting Impression, Overflow] x [Bipod, Clown Cartridge, Cluster Bomb] — 6 combos
- Copy 4: [Impromptu Ammunition, Overflow, Quickdraw] x [Aggregate Charge, Cluster Bomb, Collective Demolition] — 6 combos
- Copy 5: [Air Trigger, Lasting Impression, Tracking Module] x [Cluster Bomb, Collective Demolition, Reaper's Tithe] — 5 combos

### Submission (Adept)
Submachine Gun · Kinetic · adept, craftable · GFS 499 · pool 81 combos · 5 copies · 34 combos covered
- Pool col 2 (9): Closing Time, Encore, Kinetic Tremors, Overflow, Perpetual Motion, Sleight of Hand, Steady Hands, Subsistence, Turnabout
- Pool col 3 (9): Bait and Switch, Chaos Reshaped, Demolitionist, Frenzy, Harmony, Killing Wind, Swashbuckler, Target Lock, Thresh
- Copy 1: [Closing Time, Encore, Kinetic Tremors] x [Bait and Switch, Chaos Reshaped, Target Lock] — 9 combos
- Copy 2: [Closing Time, Kinetic Tremors, Sleight of Hand] x [Demolitionist, Harmony, Thresh] — 9 combos
- Copy 3: [Kinetic Tremors, Sleight of Hand, Steady Hands] x [Killing Wind, Swashbuckler, Target Lock] — 7 combos
- Copy 4: [Steady Hands, Subsistence, Turnabout] x [Bait and Switch, Chaos Reshaped, Thresh] — 8 combos
- Copy 5: [Encore] x [Swashbuckler] — 1 combo

### Hezen Vengeance (Timelost)
Rocket Launcher · Solar · adept, craftable · GFS 484 · pool 81 combos · 5 copies · 33 combos covered
- Pool col 2 (9): Auto-Loading Holster, Blast Distributor, Cluster Bomb, Collective Demolition, Demolitionist, Envious Arsenal, Impulse Amplifier, Incandescent, Overflow
- Pool col 3 (9): Aggregate Charge, Bait and Switch, Binary Orbit, Bipod, Collective Action, Elemental Honing, Explosive Light, Lasting Impression, Vorpal Weapon
- Copy 1: [Blast Distributor, Collective Demolition, Envious Arsenal] x [Bait and Switch, Bipod, Collective Action] — 8 combos
- Copy 2: [Blast Distributor, Collective Demolition, Incandescent] x [Bipod, Explosive Light, Lasting Impression] — 6 combos
- Copy 3: [Auto-Loading Holster, Cluster Bomb, Overflow] x [Collective Action, Explosive Light, Vorpal Weapon] — 9 combos
- Copy 4: [Cluster Bomb, Collective Demolition, Overflow] x [Bait and Switch, Binary Orbit, Elemental Honing] — 5 combos
- Copy 5: [Auto-Loading Holster, Blast Distributor, Demolitionist] x [Aggregate Charge, Bipod, Elemental Honing] — 5 combos

### Willful Hamartia
Linear Fusion Rifle · Arc · tiered, obtainable · GFS 210 · pool 49 combos · 5 copies · 33 combos covered
- Pool col 2 (7): Envious Assassin, High-Impact Reserves, Lone Wolf, Rapid Hit, Slideways, Successful Warm-Up, Tap the Trigger
- Pool col 3 (7): Bait and Switch, Headseeker, Jolting Feedback, Kickstart, Offhand Strike, Precision Instrument, Reservoir Burst
- Copy 1: [High-Impact Reserves, Successful Warm-Up, Tap the Trigger] x [Bait and Switch, Headseeker, Kickstart] — 9 combos
- Copy 2: [Envious Assassin, High-Impact Reserves, Tap the Trigger] x [Jolting Feedback, Offhand Strike, Reservoir Burst] — 9 combos
- Copy 3: [Envious Assassin, Rapid Hit, Slideways] x [Jolting Feedback, Kickstart, Offhand Strike] — 7 combos
- Copy 4: [Envious Assassin, Slideways, Successful Warm-Up] x [Headseeker, Offhand Strike, Reservoir Burst] — 5 combos
- Copy 5: [Lone Wolf, Rapid Hit] x [Bait and Switch, Offhand Strike, Reservoir Burst] — 3 combos

### A Distant Pull
Sniper Rifle · Stasis · tiered, craftable, obtainable · GFS 533 · pool 63 combos · 5 copies · 32 combos covered
- Pool col 2 (8): Ambitious Assassin, Empty Traits Socket, Ensemble, Keep Away, Moving Target, Overflow, Triple Tap, Tunnel Vision
- Pool col 3 (8): Collective Action, Discord, Empty Traits Socket, Explosive Payload, Focused Fury, Headstone, Killing Wind, Opening Shot
- Copy 1: [Ambitious Assassin, Ensemble, Tunnel Vision] x [Collective Action, Discord, Killing Wind] — 9 combos
- Copy 2: [Ensemble, Overflow, Triple Tap] x [Discord, Explosive Payload, Killing Wind] — 6 combos
- Copy 3: [Ambitious Assassin, Moving Target, Triple Tap] x [Collective Action, Headstone, Opening Shot] — 6 combos
- Copy 4: [Keep Away, Moving Target, Tunnel Vision] x [Discord, Empty Traits Socket, Headstone] — 5 combos
- Copy 5: [Empty Traits Socket, Keep Away, Overflow] x [Discord, Focused Fury, Headstone] — 6 combos

### Finite Impactor
Hand Cannon · Solar · tiered, obtainable · GFS 154 · pool 49 combos · 5 copies · 32 combos covered
- Pool col 2 (7): Elemental Capacitor, Enlightened Action, Fragile Focus, Heal Clip, Iron Grip, Killing Wind, Slideways
- Pool col 3 (7): Burning Ambition, Heating Up, Iron Reach, Magnificent Howl, Moving Target, Precision Instrument, Rapid Hit
- Copy 1: [Fragile Focus, Iron Grip, Slideways] x [Burning Ambition, Magnificent Howl, Rapid Hit] — 9 combos
- Copy 2: [Elemental Capacitor, Enlightened Action, Heal Clip] x [Heating Up, Iron Reach, Magnificent Howl] — 9 combos
- Copy 3: [Enlightened Action, Heal Clip, Killing Wind] x [Heating Up, Iron Reach, Rapid Hit] — 5 combos
- Copy 4: [Elemental Capacitor, Fragile Focus, Iron Grip] x [Burning Ambition, Heating Up, Precision Instrument] — 5 combos
- Copy 5: [Fragile Focus, Heal Clip, Slideways] x [Heating Up, Moving Target] — 4 combos

### Insidious (Adept)
Pulse Rifle · Arc · adept, craftable · GFS 614 · pool 81 combos · 5 copies · 32 combos covered
- Pool col 2 (9): Compulsive Reloader, Demolitionist, Dragonfly, Frenzy, Heating Up, Rapid Hit, Rolling Storm, Sleight of Hand, Stats for All
- Pool col 3 (9): Adaptive Munitions, Adrenaline Junkie, Bait and Switch, Chaos Reshaped, One for All, Rampage, Turnabout, Voltshot, Vorpal Weapon
- Copy 1: [Compulsive Reloader, Frenzy, Rolling Storm] x [Adaptive Munitions, Adrenaline Junkie, Chaos Reshaped] — 8 combos
- Copy 2: [Dragonfly, Frenzy, Heating Up] x [Chaos Reshaped, One for All, Rampage] — 8 combos
- Copy 3: [Dragonfly, Heating Up, Sleight of Hand] x [Adrenaline Junkie, Bait and Switch, Voltshot] — 6 combos
- Copy 4: [Frenzy, Rolling Storm, Sleight of Hand] x [Bait and Switch, Turnabout, Vorpal Weapon] — 5 combos
- Copy 5: [Compulsive Reloader, Rolling Storm, Stats for All] x [Bait and Switch, Chaos Reshaped, Rampage] — 5 combos

### The Spiteful Fang
Combat Bow · Stasis · tiered, vendor 6-perk, obtainable · GFS 211 · pool 56 combos · 5 copies · 32 combos covered
- Pool col 2 (7): Archer's Tempo, Headstone, Impromptu Ammunition, Impulse Amplifier, Perfect Float, Rimestealer, Successful Warm-Up
- Pool col 3 (8): Archer's Gambit, Crystalline Corpsebloom, Explosive Head, Firefly, Frenzy, Golden Tricorn, Golden Tricorn Enhanced, Rampage
- Copy 1: [Headstone, Perfect Float, Rimestealer] x [Archer's Gambit, Crystalline Corpsebloom, Explosive Head] — 8 combos
- Copy 2: [Archer's Tempo, Impulse Amplifier, Perfect Float] x [Crystalline Corpsebloom, Firefly, Golden Tricorn] — 8 combos
- Copy 3: [Impromptu Ammunition, Rimestealer, Successful Warm-Up] x [Crystalline Corpsebloom, Firefly, Rampage] — 6 combos
- Copy 4: [Archer's Tempo, Headstone, Successful Warm-Up] x [Frenzy, Golden Tricorn, Rampage] — 6 combos
- Copy 5: [Impulse Amplifier, Perfect Float, Successful Warm-Up] x [Explosive Head, Frenzy, Golden Tricorn Enhanced] — 4 combos

### Tempered Dynamo
Fusion Rifle · Arc · tiered, vendor 6-perk, obtainable · GFS 153 · pool 49 combos · 5 copies · 31 combos covered
- Pool col 2 (7): Backup Plan, Impromptu Ammunition, Kickstart, Opening Shot, Overflow, Rewind Rounds, Supercharged Magazine
- Pool col 3 (7): Closing Time, Discord, Gear Shift, Jolting Feedback, Kill Clip, Rampage, Surrounded
- Copy 1: [Backup Plan, Kickstart, Opening Shot] x [Closing Time, Discord, Jolting Feedback] — 8 combos
- Copy 2: [Impromptu Ammunition, Rewind Rounds, Supercharged Magazine] x [Discord, Jolting Feedback, Surrounded] — 9 combos
- Copy 3: [Backup Plan, Impromptu Ammunition, Kickstart] x [Gear Shift, Rampage, Surrounded] — 6 combos
- Copy 4: [Backup Plan, Kickstart, Rewind Rounds] x [Gear Shift, Kill Clip] — 4 combos
- Copy 5: [Opening Shot, Overflow] x [Kill Clip, Rampage, Surrounded] — 4 combos

### Chivalric Fire
Sword · Void · tiered, vendor 6-perk, obtainable · GFS 191 · pool 49 combos · 5 copies · 30 combos covered
- Pool col 2 (7): Collective Demolition, Dimensional Shift, Relentless Strikes, Repulsor Brace, Sharp Harvest, Strategist, Tilting at Windmills
- Pool col 3 (7): Attrition Orbs, Collective Action, Destabilizing Rounds, Eager Edge, Energy Transfer, Flash Counter, Whirlwind Blade
- Copy 1: [Collective Demolition, Sharp Harvest, Tilting at Windmills] x [Attrition Orbs, Collective Action, Eager Edge] — 7 combos
- Copy 2: [Collective Demolition, Dimensional Shift, Relentless Strikes] x [Energy Transfer, Flash Counter, Whirlwind Blade] — 8 combos
- Copy 3: [Dimensional Shift, Sharp Harvest, Strategist] x [Eager Edge, Energy Transfer, Flash Counter] — 6 combos
- Copy 4: [Repulsor Brace, Tilting at Windmills] x [Energy Transfer, Flash Counter, Whirlwind Blade] — 5 combos
- Copy 5: [Collective Demolition, Dimensional Shift, Strategist] x [Attrition Orbs, Destabilizing Rounds] — 4 combos

### Ill Omen
Sword · Stasis · tiered, craftable, obtainable · GFS 590 · pool 63 combos · 5 copies · 30 combos covered
- Pool col 2 (8): Attrition Orbs, Duelist's Trance, Empty Traits Socket, Relentless Strikes, Strategist, Tireless Blade, Unrelenting, Valiant Charge
- Pool col 3 (8): Assassin's Blade, Cold Steel, Empty Traits Socket, En Garde, One for All, Surrounded, Vorpal Weapon, Whirlwind Blade
- Copy 1: [Attrition Orbs, Strategist, Valiant Charge] x [Assassin's Blade, Cold Steel, En Garde] — 8 combos
- Copy 2: [Duelist's Trance, Empty Traits Socket, Valiant Charge] x [Cold Steel, En Garde, Vorpal Weapon] — 7 combos
- Copy 3: [Empty Traits Socket, Strategist, Valiant Charge] x [Assassin's Blade, One for All, Whirlwind Blade] — 7 combos
- Copy 4: [Relentless Strikes, Tireless Blade, Valiant Charge] x [Empty Traits Socket, One for All, Surrounded] — 5 combos
- Copy 5: [Attrition Orbs, Duelist's Trance, Unrelenting] x [En Garde, One for All] — 3 combos

### Hushed Whisper
Combat Bow · Strand · tiered, obtainable · GFS 182 · pool 49 combos · 5 copies · 29 combos covered
- Pool col 2 (7): Impulse Amplifier, Lead From Light, Lone Wolf, Slice, Snapshot Sights, Successful Warm-Up, Tear
- Pool col 3 (7): Aggregate Charge, Archer's Gambit, Collective Action, Collective Pugilism, Explosive Head, Hatchling, Precision Instrument
- Copy 1: [Lead From Light, Lone Wolf, Tear] x [Aggregate Charge, Archer's Gambit, Collective Pugilism] — 8 combos
- Copy 2: [Lead From Light, Slice, Snapshot Sights] x [Archer's Gambit, Collective Pugilism, Explosive Head] — 7 combos
- Copy 3: [Lone Wolf, Snapshot Sights, Tear] x [Collective Action, Explosive Head, Hatchling] — 6 combos
- Copy 4: [Lead From Light, Slice, Successful Warm-Up] x [Collective Action, Hatchling, Precision Instrument] — 5 combos
- Copy 5: [Impulse Amplifier] x [Collective Action, Collective Pugilism, Precision Instrument] — 3 combos

### Pointed Inquiry
Scout Rifle · Void · tiered, craftable, obtainable · GFS 730 · pool 80 combos · 5 copies · 29 combos covered
- Pool col 2 (9): Compulsive Reloader, Empty Traits Socket, Firmly Planted, Fourth Time's the Charm, Genesis, Rapid Hit, Repulsor Brace, Shoot to Loot, Stats for All
- Pool col 3 (9): Adaptive Munitions, Demolitionist, Demoralize, Dragonfly, Empty Traits Socket, Focused Fury, Harmony, Precision Instrument, Turnabout
- Copy 1: [Compulsive Reloader, Firmly Planted, Genesis] x [Adaptive Munitions, Demoralize, Precision Instrument] — 8 combos
- Copy 2: [Firmly Planted, Fourth Time's the Charm, Stats for All] x [Adaptive Munitions, Demoralize, Harmony] — 6 combos
- Copy 3: [Empty Traits Socket, Repulsor Brace, Stats for All] x [Demoralize, Precision Instrument, Turnabout] — 7 combos
- Copy 4: [Firmly Planted, Rapid Hit, Repulsor Brace] x [Demolitionist, Demoralize, Turnabout] — 4 combos
- Copy 5: [Firmly Planted, Genesis, Repulsor Brace] x [Dragonfly, Empty Traits Socket, Focused Fury] — 4 combos

### Nullify (Adept)
Pulse Rifle · Solar · adept, craftable · GFS 525 · pool 81 combos · 5 copies · 28 combos covered
- Pool col 2 (9): Burning Ambition, Collective Demolition, Demolitionist, Firefly, Fourth Time's the Charm, Heal Clip, Rapid Hit, Subsistence, Under-Over
- Pool col 3 (9): Adrenaline Junkie, Attrition Orbs, Chaos Reshaped, Desperate Measures, Incandescent, Meganeura, Multikill Clip, Sword Logic, Vorpal Weapon
- Copy 1: [Burning Ambition, Firefly, Fourth Time's the Charm] x [Adrenaline Junkie, Chaos Reshaped, Multikill Clip] — 9 combos
- Copy 2: [Collective Demolition, Heal Clip, Under-Over] x [Chaos Reshaped, Desperate Measures, Multikill Clip] — 7 combos
- Copy 3: [Burning Ambition, Fourth Time's the Charm, Under-Over] x [Incandescent, Sword Logic, Vorpal Weapon] — 5 combos
- Copy 4: [Firefly, Rapid Hit, Under-Over] x [Attrition Orbs, Incandescent, Vorpal Weapon] — 4 combos
- Copy 5: [Demolitionist, Heal Clip] x [Desperate Measures, Meganeura] — 3 combos

### Fang of Ir Yût (Adept)
Scout Rifle · Strand · adept, craftable · GFS 629 · pool 90 combos · 5 copies · 26 combos covered
- Pool col 2 (9): Keep Away, Killing Wind, Rapid Hit, Rewind Rounds, Shoot to Loot, Slice, Surplus, Tear, Tunnel Vision
- Pool col 3 (10): Binary Orbit, Golden Tricorn, Golden Tricorn Enhanced, Hatchling, High Ground, Kill Clip, Meganeura, Opening Shot, Precision Instrument, Sword Logic
- Copy 1: [Rewind Rounds, Surplus, Tear] x [Binary Orbit, High Ground, Meganeura] — 7 combos
- Copy 2: [Surplus, Tear, Tunnel Vision] x [Binary Orbit, Meganeura, Sword Logic] — 5 combos
- Copy 3: [Killing Wind, Surplus, Tunnel Vision] x [Hatchling, High Ground, Meganeura] — 5 combos
- Copy 4: [Rapid Hit, Shoot to Loot, Tunnel Vision] x [Binary Orbit, Precision Instrument, Sword Logic] — 5 combos
- Copy 5: [Keep Away, Slice] x [Binary Orbit, Meganeura, Sword Logic] — 4 combos

### Herod-C
Auto Rifle · Stasis · tiered, vendor 6-perk, obtainable · GFS 1,560 · pool 144 combos · 5 copies · 25 combos covered
- Pool col 2 (12): Auto-Loading Holster, Compulsive Reloader, Dynamic Sway Reduction, Ensemble, Fourth Time's the Charm, Heating Up, Hip-Fire Grip, Perpetual Motion, Shoot to Loot, Stats for All, Steady Hands, Subsistence
- Pool col 3 (12): Demolitionist, Elemental Capacitor, Focused Fury, Frenzy, Headstone, Moving Target, Multikill Clip, One for All, Tap the Trigger, Turnabout, Unrelenting, Vorpal Weapon
- Copy 1: [Dynamic Sway Reduction, Shoot to Loot, Steady Hands] x [Tap the Trigger, Turnabout, Unrelenting] — 6 combos
- Copy 2: [Heating Up, Hip-Fire Grip, Stats for All] x [Demolitionist, Moving Target, Turnabout] — 5 combos
- Copy 3: [Compulsive Reloader, Ensemble, Fourth Time's the Charm] x [Headstone, Moving Target, Multikill Clip] — 5 combos
- Copy 4: [Dynamic Sway Reduction, Heating Up, Hip-Fire Grip] x [Focused Fury, Tap the Trigger, Unrelenting] — 5 combos
- Copy 5: [Auto-Loading Holster, Hip-Fire Grip, Perpetual Motion] x [Elemental Capacitor, Focused Fury, Turnabout] — 4 combos

### Mykel's Reverence (Adept)
Sidearm · Strand · adept, craftable · GFS 451 · pool 81 combos · 4 copies · 33 combos covered
- Pool col 2 (9): Collective Demolition, Elemental Capacitor, Perfect Float, Perpetual Motion, Pugilist, Rewind Rounds, Slice, Thresh, Unrelenting
- Pool col 3 (9): Binary Orbit, Frenzy, Harmony, Hatchling, Master of Arms, Offhand Strike, Paracausal Affinity, Swashbuckler, Tap the Trigger
- Copy 1: [Elemental Capacitor, Perfect Float, Thresh] x [Binary Orbit, Master of Arms, Paracausal Affinity] — 9 combos
- Copy 2: [Collective Demolition, Rewind Rounds, Slice] x [Hatchling, Offhand Strike, Swashbuckler] — 9 combos
- Copy 3: [Collective Demolition, Perfect Float, Unrelenting] x [Offhand Strike, Paracausal Affinity, Tap the Trigger] — 7 combos
- Copy 4: [Collective Demolition, Pugilist, Slice] x [Frenzy, Harmony, Master of Arms] — 8 combos

### Thin Precipice
Sword · Strand · tiered, craftable, obtainable · GFS 450 · pool 71 combos · 4 copies · 31 combos covered
- Pool col 2 (8): Duelist's Trance, Empty Traits Socket, Flash Counter, Relentless Strikes, Steady Hands, Tireless Blade, Unrelenting, Valiant Charge
- Pool col 3 (9): Adrenaline Junkie, Chain Reaction, Collective Action, Counterattack, Empty Traits Socket, Golden Tricorn, Golden Tricorn Enhanced, Harmony, Hatchling
- Copy 1: [Duelist's Trance, Steady Hands, Valiant Charge] x [Collective Action, Counterattack, Golden Tricorn] — 8 combos
- Copy 2: [Duelist's Trance, Flash Counter, Relentless Strikes] x [Adrenaline Junkie, Golden Tricorn, Golden Tricorn Enhanced] — 8 combos
- Copy 3: [Tireless Blade, Unrelenting, Valiant Charge] x [Adrenaline Junkie, Golden Tricorn, Golden Tricorn Enhanced] — 7 combos
- Copy 4: [Relentless Strikes, Steady Hands, Valiant Charge] x [Chain Reaction, Harmony, Hatchling] — 8 combos

### Song of Ir Yût (Adept)
Machine Gun · Arc · adept, craftable · GFS 381 · pool 81 combos · 4 copies · 30 combos covered
- Pool col 2 (9): Demolitionist, Feeding Frenzy, Jolting Feedback, Keep Away, Reconstruction, Rewind Rounds, Supercharged Magazine, Unrelenting, Zen Moment
- Pool col 3 (9): Bait and Switch, Cascade Point, Elemental Capacitor, High Ground, Master of Arms, Mega Kill Clip, Sword Logic, Target Lock, Voltshot
- Copy 1: [Feeding Frenzy, Jolting Feedback, Zen Moment] x [Bait and Switch, Cascade Point, Elemental Capacitor] — 9 combos
- Copy 2: [Feeding Frenzy, Jolting Feedback, Unrelenting] x [High Ground, Master of Arms, Sword Logic] — 9 combos
- Copy 3: [Jolting Feedback, Supercharged Magazine, Zen Moment] x [Cascade Point, Mega Kill Clip, Target Lock] — 7 combos
- Copy 4: [Jolting Feedback, Rewind Rounds, Unrelenting] x [Elemental Capacitor, Target Lock, Voltshot] — 5 combos

### Zaouli's Bane (Harrowed)
Hand Cannon · Solar · adept, craftable · GFS 428 · pool 81 combos · 4 copies · 30 combos covered
- Pool col 2 (9): Ensemble, Explosive Payload, Gutshot Straight, Hip-Fire Grip, Keep Away, Opening Shot, Pugilist, Redirection, Well-Rounded
- Pool col 3 (9): Chaos Reshaped, Demolitionist, Eye of the Storm, Firefly, Focused Fury, Incandescent, Meganeura, One for All, Surrounded
- Copy 1: [Explosive Payload, Gutshot Straight, Redirection] x [Chaos Reshaped, Eye of the Storm, Surrounded] — 9 combos
- Copy 2: [Ensemble, Gutshot Straight, Well-Rounded] x [Chaos Reshaped, Firefly, Meganeura] — 8 combos
- Copy 3: [Explosive Payload, Opening Shot, Redirection] x [Firefly, Focused Fury, Incandescent] — 7 combos
- Copy 4: [Gutshot Straight, Hip-Fire Grip, Redirection] x [Incandescent, Meganeura, One for All] — 6 combos

### Briar's Contempt (Adept)
Linear Fusion Rifle · Solar · adept, craftable · GFS 558 · pool 81 combos · 4 copies · 29 combos covered
- Pool col 2 (9): Burning Ambition, Demolitionist, Envious Assassin, Incandescent, Keep Away, Rapid Hit, Reconstruction, Rewind Rounds, Slideshot
- Pool col 3 (9): Adagio, Aggregate Charge, Chaos Reshaped, Focused Fury, Frenzy, Harmony, High-Impact Reserves, Paracausal Affinity, Surrounded
- Copy 1: [Incandescent, Rapid Hit, Reconstruction] x [Adagio, Aggregate Charge, Chaos Reshaped] — 9 combos
- Copy 2: [Burning Ambition, Incandescent, Rewind Rounds] x [Focused Fury, Harmony, High-Impact Reserves] — 8 combos
- Copy 3: [Burning Ambition, Incandescent, Slideshot] x [Adagio, Paracausal Affinity, Surrounded] — 8 combos
- Copy 4: [Burning Ambition, Rapid Hit, Slideshot] x [Chaos Reshaped, Frenzy, Surrounded] — 4 combos

### Imminence (Adept)
Submachine Gun · Strand · adept, craftable · GFS 458 · pool 81 combos · 4 copies · 29 combos covered
- Pool col 2 (9): Ambitious Assassin, Demolitionist, Dynamic Sway Reduction, Enlightened Action, Fragile Focus, Perpetual Motion, Pugilist, Slice, Tear
- Pool col 3 (9): Binary Orbit, Chaos Reshaped, Desperate Measures, Firefly, Hatchling, Kill Clip, Paracausal Affinity, Strategist, Target Lock
- Copy 1: [Ambitious Assassin, Dynamic Sway Reduction, Enlightened Action] x [Firefly, Paracausal Affinity, Target Lock] — 8 combos
- Copy 2: [Dynamic Sway Reduction, Enlightened Action, Fragile Focus] x [Binary Orbit, Chaos Reshaped, Firefly] — 7 combos
- Copy 3: [Fragile Focus, Perpetual Motion, Tear] x [Chaos Reshaped, Paracausal Affinity, Strategist] — 8 combos
- Copy 4: [Dynamic Sway Reduction, Enlightened Action, Tear] x [Desperate Measures, Strategist, Target Lock] — 6 combos

### Keraunios
Trace Rifle · Arc · tiered, obtainable · GFS 162 · pool 49 combos · 4 copies · 28 combos covered
- Pool col 2 (7): Fourth Time's the Charm, Overflow, Rapid Hit, Rewind Rounds, Shoot to Loot, Supercharged Magazine, Trickle Charge
- Pool col 3 (7): Butterfly, Chain Reaction, Detonator Beam, Jolting Feedback, Killing Tally, Rolling Storm, Target Lock
- Copy 1: [Fourth Time's the Charm, Overflow, Rapid Hit] x [Butterfly, Chain Reaction, Detonator Beam] — 9 combos
- Copy 2: [Shoot to Loot, Supercharged Magazine, Trickle Charge] x [Butterfly, Chain Reaction, Detonator Beam] — 9 combos
- Copy 3: [Rapid Hit, Shoot to Loot, Supercharged Magazine] x [Jolting Feedback, Killing Tally, Target Lock] — 6 combos
- Copy 4: [Overflow, Rewind Rounds, Trickle Charge] x [Butterfly, Target Lock] — 4 combos

### Stryker's Sure-Hand
Sword · Void · tiered, vendor 6-perk, obtainable · GFS 278 · pool 49 combos · 4 copies · 28 combos covered
- Pool col 2 (7): Assassin's Blade, Duelist's Trance, Rampage, Relentless Strikes, Repulsor Brace, Sharp Harvest, Tireless Blade
- Pool col 3 (7): Binary Orbit, Destabilizing Rounds, Flash Counter, Impromptu Ammunition, Redirection, Surrounded, Whirlwind Blade
- Copy 1: [Assassin's Blade, Duelist's Trance, Relentless Strikes] x [Destabilizing Rounds, Impromptu Ammunition, Redirection] — 9 combos
- Copy 2: [Rampage, Sharp Harvest, Tireless Blade] x [Binary Orbit, Flash Counter, Impromptu Ammunition] — 8 combos
- Copy 3: [Rampage, Repulsor Brace, Sharp Harvest] x [Destabilizing Rounds, Redirection, Whirlwind Blade] — 7 combos
- Copy 4: [Assassin's Blade, Duelist's Trance, Relentless Strikes] x [Binary Orbit, Flash Counter, Whirlwind Blade] — 4 combos

### Veiled Threat
Auto Rifle · Stasis · tiered, craftable, obtainable · GFS 453 · pool 63 combos · 4 copies · 28 combos covered
- Pool col 2 (8): Attrition Orbs, Empty Traits Socket, Fragile Focus, Loose Change, Shoot to Loot, Strategist, Threat Detector, To the Pain
- Pool col 3 (8): Collective Action, Desperate Measures, Empty Traits Socket, Encore, Gutshot Straight, Headstone, Moving Target, Surrounded
- Copy 1: [Fragile Focus, Loose Change, Shoot to Loot] x [Collective Action, Encore, Headstone] — 9 combos
- Copy 2: [Strategist, Threat Detector, To the Pain] x [Encore, Gutshot Straight, Headstone] — 9 combos
- Copy 3: [Attrition Orbs, Fragile Focus, Shoot to Loot] x [Desperate Measures, Headstone, Surrounded] — 5 combos
- Copy 4: [Empty Traits Socket, Shoot to Loot, Threat Detector] x [Collective Action, Encore, Gutshot Straight] — 5 combos

### Wild Style
Grenade Launcher · Solar · tiered, vendor 6-perk, obtainable · GFS 479 · pool 64 combos · 4 copies · 28 combos covered
- Pool col 2 (8): Danger Zone, Enlightened Action, Envious Assassin, Grave Robber, Keep Away, Reconstruction, Stats for All, Unrelenting
- Pool col 3 (8): Attrition Orbs, Bait and Switch, Collective Action, Incandescent, One for All, Permeability, Surrounded, Vorpal Weapon
- Copy 1: [Danger Zone, Enlightened Action, Envious Assassin] x [Attrition Orbs, Incandescent, Permeability] — 8 combos
- Copy 2: [Keep Away, Reconstruction, Unrelenting] x [Attrition Orbs, Incandescent, Permeability] — 8 combos
- Copy 3: [Danger Zone, Grave Robber, Stats for All] x [Attrition Orbs, Collective Action, Permeability] — 6 combos
- Copy 4: [Danger Zone, Enlightened Action, Envious Assassin] x [Bait and Switch, Collective Action, Vorpal Weapon] — 6 combos

### Bad Omens
Rocket Launcher · Void · tiered, vendor 6-perk, obtainable · GFS 225 · pool 49 combos · 4 copies · 27 combos covered
- Pool col 2 (7): Auto-Loading Holster, Bipod, Destabilizing Rounds, Light Touch, Perpetual Motion, Snapshot Sights, Tracking Module
- Pool col 3 (7): Bait and Switch, Cluster Bomb, Elemental Honing, Explosive Light, Kill Clip, Quickdraw, Withering Gaze
- Copy 1: [Bipod, Destabilizing Rounds, Light Touch] x [Bait and Switch, Elemental Honing, Explosive Light] — 9 combos
- Copy 2: [Bipod, Light Touch, Perpetual Motion] x [Cluster Bomb, Kill Clip, Quickdraw] — 9 combos
- Copy 3: [Auto-Loading Holster, Light Touch, Tracking Module] x [Kill Clip, Quickdraw, Withering Gaze] — 6 combos
- Copy 4: [Snapshot Sights] x [Cluster Bomb, Explosive Light, Withering Gaze] — 3 combos

### King Orfeo
Combat Bow · Arc · tiered, obtainable · GFS 213 · pool 49 combos · 4 copies · 27 combos covered
- Pool col 2 (7): Archer's Tempo, Explosive Head, Impulse Amplifier, Pugilist, Shoot to Loot, Successful Warm-Up, Surplus
- Pool col 3 (7): Dragonfly, Jolting Feedback, Meganeura, Precision Instrument, Rangefinder, Rolling Storm, Swashbuckler
- Copy 1: [Archer's Tempo, Explosive Head, Impulse Amplifier] x [Jolting Feedback, Rangefinder, Rolling Storm] — 9 combos
- Copy 2: [Archer's Tempo, Explosive Head, Surplus] x [Jolting Feedback, Meganeura, Precision Instrument] — 7 combos
- Copy 3: [Explosive Head, Pugilist, Successful Warm-Up] x [Dragonfly, Jolting Feedback, Swashbuckler] — 5 combos
- Copy 4: [Pugilist, Shoot to Loot, Surplus] x [Meganeura, Rangefinder, Rolling Storm] — 6 combos

### Tatara Gaze
Sniper Rifle · Arc · tiered, vendor 6-perk, obtainable · GFS 180 · pool 49 combos · 4 copies · 27 combos covered
- Pool col 2 (7): Discord, Impromptu Ammunition, Light Touch, Overflow, Quickdraw, Rewind Rounds, Snapshot Sights
- Pool col 3 (7): Box Breathing, Closing Time, Elemental Honing, Mega Kill Clip, Redirection, Triple Tap, Voltshot
- Copy 1: [Discord, Impromptu Ammunition, Light Touch] x [Box Breathing, Mega Kill Clip, Triple Tap] — 8 combos
- Copy 2: [Overflow, Quickdraw, Snapshot Sights] x [Mega Kill Clip, Triple Tap, Voltshot] — 7 combos
- Copy 3: [Impromptu Ammunition, Light Touch, Quickdraw] x [Closing Time, Elemental Honing, Redirection] — 7 combos
- Copy 4: [Discord, Snapshot Sights] x [Box Breathing, Elemental Honing, Redirection] — 5 combos

### Xenoclast IV
Shotgun · Arc · tiered, vendor 6-perk, obtainable · GFS 1,175 · pool 132 combos · 4 copies · 27 combos covered
- Pool col 2 (11): Auto-Loading Holster, Dual Loader, Field Prep, Genesis, Grave Robber, Hip-Fire Grip, Lead from Gold, Pulse Monitor, Slideshot, Slideways, Surplus
- Pool col 3 (12): Demolitionist, Disruption Break, Eye of the Storm, Killing Wind, One-Two Punch, Rampage, Surrounded, Swashbuckler, Thresh, Trench Barrel, Unrelenting, Vorpal Weapon
- Copy 1: [Dual Loader, Field Prep, Genesis] x [Disruption Break, Killing Wind, Rampage] — 7 combos
- Copy 2: [Dual Loader, Genesis, Slideways] x [One-Two Punch, Trench Barrel, Unrelenting] — 7 combos
- Copy 3: [Genesis, Grave Robber, Pulse Monitor] x [Eye of the Storm, Killing Wind, Surrounded] — 5 combos
- Copy 4: [Hip-Fire Grip, Slideways, Surplus] x [Eye of the Storm, Killing Wind, Trench Barrel] — 8 combos

### Anamnesis (Adept)
Combat Bow · Void · adept, obtainable · GFS 248 · pool 49 combos · 4 copies · 26 combos covered
- Pool col 2 (7): Archer's Tempo, Dragonfly, Hip-Fire Grip, Perfect Float, Repulsor Brace, Successful Warm-Up, To the Pain
- Pool col 3 (7): Adagio, Demoralize, Destabilizing Rounds, Explosive Head, Impulse Amplifier, Moving Target, Sword Logic
- Copy 1: [Archer's Tempo, Hip-Fire Grip, Perfect Float] x [Demoralize, Destabilizing Rounds, Impulse Amplifier] — 9 combos
- Copy 2: [Dragonfly, Successful Warm-Up, To the Pain] x [Adagio, Demoralize, Impulse Amplifier] — 7 combos
- Copy 3: [Archer's Tempo, Dragonfly, Repulsor Brace] x [Adagio, Moving Target, Sword Logic] — 6 combos
- Copy 4: [Repulsor Brace, Successful Warm-Up, To the Pain] x [Destabilizing Rounds, Explosive Head] — 4 combos

### Koraxis's Distress (Adept)
Grenade Launcher · Strand · adept, craftable · GFS 523 · pool 81 combos · 4 copies · 26 combos covered
- Pool col 2 (9): Blast Distributor, Chain Reaction, Danger Zone, Demolitionist, Envious Arsenal, Envious Assassin, Field Prep, Impulse Amplifier, Reconstruction
- Pool col 3 (9): Bait and Switch, Chaos Reshaped, Frenzy, Full Court, Harmony, Hatchling, Paracausal Affinity, Surrounded, Wellspring
- Copy 1: [Blast Distributor, Chain Reaction, Danger Zone] x [Chaos Reshaped, Harmony, Paracausal Affinity] — 9 combos
- Copy 2: [Chain Reaction, Envious Arsenal, Reconstruction] x [Chaos Reshaped, Full Court, Wellspring] — 6 combos
- Copy 3: [Blast Distributor, Chain Reaction, Envious Arsenal] x [Frenzy, Surrounded, Wellspring] — 6 combos
- Copy 4: [Chain Reaction, Demolitionist, Envious Arsenal] x [Full Court, Harmony, Hatchling] — 5 combos

### Rapid Growth
Sniper Rifle · Arc · tiered, obtainable · GFS 177 · pool 49 combos · 4 copies · 26 combos covered
- Pool col 2 (7): Fourth Time's the Charm, Keep Away, Light Touch, Lucky Shot, Snapshot Sights, Supercharged Magazine, Trickle Charge
- Pool col 3 (7): Aggregate Charge, Binary Orbit, Closing Time, Gear Shift, Jolting Feedback, Meganeura, Rolling Storm
- Copy 1: [Lucky Shot, Supercharged Magazine, Trickle Charge] x [Aggregate Charge, Binary Orbit, Closing Time] — 8 combos
- Copy 2: [Fourth Time's the Charm, Lucky Shot, Snapshot Sights] x [Binary Orbit, Gear Shift, Jolting Feedback] — 6 combos
- Copy 3: [Lucky Shot, Supercharged Magazine, Trickle Charge] x [Meganeura, Rolling Storm] — 5 combos
- Copy 4: [Fourth Time's the Charm, Light Touch, Snapshot Sights] x [Aggregate Charge, Meganeura, Rolling Storm] — 7 combos

### Retraced Path
Trace Rifle · Solar · tiered, craftable, obtainable · GFS 739 · pool 72 combos · 4 copies · 26 combos covered
- Pool col 2 (8): Adaptive Munitions, Feeding Frenzy, Genesis, Killing Wind, Perpetual Motion, Shoot to Loot, Subsistence, Well-Rounded
- Pool col 3 (9): Demolitionist, Disruption Break, Focused Fury, Frenzy, Golden Tricorn, Golden Tricorn Enhanced, Harmony, Incandescent, One for All
- Copy 1: [Adaptive Munitions, Genesis, Killing Wind] x [Golden Tricorn, Golden Tricorn Enhanced, Incandescent] — 8 combos
- Copy 2: [Adaptive Munitions, Perpetual Motion, Well-Rounded] x [Disruption Break, Harmony, One for All] — 8 combos
- Copy 3: [Feeding Frenzy, Perpetual Motion, Shoot to Loot] x [Disruption Break, Golden Tricorn Enhanced, Incandescent] — 7 combos
- Copy 4: [Shoot to Loot] x [Frenzy, Golden Tricorn, One for All] — 3 combos

### Unwavering Duty
Machine Gun · Solar · tiered, obtainable · GFS 291 · pool 49 combos · 4 copies · 26 combos covered
- Pool col 2 (7): Auto-Loading Holster, Dynamic Sway Reduction, Envious Assassin, Fourth Time's the Charm, Incandescent, Rampage, Subsistence
- Pool col 3 (7): Bait and Switch, Burning Ambition, Cascade Point, Killing Tally, Onslaught, Tap the Trigger, Target Lock
- Copy 1: [Auto-Loading Holster, Dynamic Sway Reduction, Rampage] x [Burning Ambition, Killing Tally, Onslaught] — 9 combos
- Copy 2: [Dynamic Sway Reduction, Incandescent, Rampage] x [Bait and Switch, Cascade Point, Killing Tally] — 7 combos
- Copy 3: [Auto-Loading Holster, Fourth Time's the Charm, Incandescent] x [Burning Ambition, Tap the Trigger, Target Lock] — 5 combos
- Copy 4: [Envious Assassin, Fourth Time's the Charm, Incandescent] x [Burning Ambition, Killing Tally, Onslaught] — 5 combos

### Wastelander M5
Shotgun · Kinetic · tiered, craftable, obtainable · GFS 509 · pool 64 combos · 4 copies · 26 combos covered
- Pool col 2 (8): Air Assault, Dual Loader, Ensemble, Lead from Gold, Perpetual Motion, Pugilist, Slideshot, Subsistence
- Pool col 3 (8): Adagio, Fragile Focus, Harmony, Killing Wind, One-Two Punch, Opening Shot, Trench Barrel, Vorpal Weapon
- Copy 1: [Air Assault, Dual Loader, Ensemble] x [Adagio, Fragile Focus, One-Two Punch] — 9 combos
- Copy 2: [Air Assault, Dual Loader, Perpetual Motion] x [Harmony, Killing Wind, Trench Barrel] — 6 combos
- Copy 3: [Ensemble, Lead from Gold, Slideshot] x [Fragile Focus, Killing Wind, Trench Barrel] — 7 combos
- Copy 4: [Perpetual Motion, Pugilist, Subsistence] x [Adagio, Killing Wind, Trench Barrel] — 4 combos

### 21% Delirium
Machine Gun · Arc · tiered, vendor 6-perk, obtainable · GFS 258 · pool 49 combos · 4 copies · 25 combos covered
- Pool col 2 (7): Eddy Current, Feeding Frenzy, Fourth Time's the Charm, Light Touch, Overflow, Reconstruction, Trickle Charge
- Pool col 3 (7): Frenzy, Gear Shift, Jolting Feedback, Killing Tally, Mega Kill Clip, One for All, Rolling Storm
- Copy 1: [Eddy Current, Feeding Frenzy, Fourth Time's the Charm] x [Gear Shift, Jolting Feedback, Mega Kill Clip] — 8 combos
- Copy 2: [Overflow, Reconstruction, Trickle Charge] x [Gear Shift, Jolting Feedback, Mega Kill Clip] — 6 combos
- Copy 3: [Light Touch, Reconstruction, Trickle Charge] x [Killing Tally, One for All, Rolling Storm] — 6 combos
- Copy 4: [Eddy Current, Feeding Frenzy, Overflow] x [Killing Tally, One for All, Rolling Storm] — 5 combos

### Burden of Guilt
Fusion Rifle · Stasis · tiered, obtainable · GFS 201 · pool 49 combos · 4 copies · 25 combos covered
- Pool col 2 (7): Ambitious Assassin, Envious Arsenal, Eye of the Storm, Lone Wolf, Perpetual Motion, Rimestealer, Under Pressure
- Pool col 3 (7): Aggregate Charge, Chill Clip, Closing Time, Controlled Burst, Crystalline Corpsebloom, High-Impact Reserves, Kickstart
- Copy 1: [Eye of the Storm, Rimestealer, Under Pressure] x [Aggregate Charge, Chill Clip, Closing Time] — 8 combos
- Copy 2: [Envious Arsenal, Eye of the Storm, Lone Wolf] x [Controlled Burst, Crystalline Corpsebloom, Kickstart] — 7 combos
- Copy 3: [Ambitious Assassin, Perpetual Motion, Rimestealer] x [Controlled Burst, Crystalline Corpsebloom, Kickstart] — 7 combos
- Copy 4: [Eye of the Storm, Under Pressure] x [Crystalline Corpsebloom, High-Impact Reserves] — 3 combos

### Fair Judgment
Auto Rifle · Stasis · tiered, vendor 6-perk, obtainable · GFS 371 · pool 49 combos · 4 copies · 25 combos covered
- Pool col 2 (7): Deconstruct, Dynamic Sway Reduction, Enlightened Action, Keep Away, Perpetual Motion, Rimestealer, Slideshot
- Pool col 3 (7): Built to Blast, Frenzy, Headstone, Kill Clip, Onslaught, Rangefinder, Tap the Trigger
- Copy 1: [Deconstruct, Enlightened Action, Perpetual Motion] x [Built to Blast, Kill Clip, Onslaught] — 8 combos
- Copy 2: [Deconstruct, Dynamic Sway Reduction, Slideshot] x [Built to Blast, Rangefinder, Tap the Trigger] — 7 combos
- Copy 3: [Deconstruct, Rimestealer, Slideshot] x [Headstone, Onslaught, Rangefinder] — 5 combos
- Copy 4: [Deconstruct, Enlightened Action, Keep Away] x [Frenzy, Rangefinder, Tap the Trigger] — 5 combos

### Gunnora's Axe
Shotgun · Arc · tiered, obtainable · GFS 567 · pool 56 combos · 4 copies · 25 combos covered
- Pool col 2 (7): Auto-Loading Holster, Field Prep, Full Auto Trigger System, Outlaw, Pulse Monitor, Quickdraw, Threat Detector
- Pool col 3 (8): Demolitionist, Moving Target, Opening Shot, Rampage, Slideshot, Snapshot Sights, Swashbuckler, Triple Tap
- Copy 1: [Auto-Loading Holster, Field Prep, Full Auto Trigger System] x [Moving Target, Slideshot, Triple Tap] — 9 combos
- Copy 2: [Outlaw, Pulse Monitor, Threat Detector] x [Slideshot, Swashbuckler, Triple Tap] — 8 combos
- Copy 3: [Field Prep, Full Auto Trigger System, Quickdraw] x [Moving Target, Opening Shot, Slideshot] — 5 combos
- Copy 4: [Full Auto Trigger System, Outlaw, Quickdraw] x [Demolitionist, Swashbuckler] — 3 combos

### Liturgy
Grenade Launcher · Stasis · tiered, obtainable · GFS 313 · pool 49 combos · 4 copies · 25 combos covered
- Pool col 2 (7): Envious Arsenal, Perpetual Motion, Quickdraw, Rimestealer, Slideways, Strategist, Surplus
- Pool col 3 (7): Chain Reaction, Chill Clip, Desperate Measures, Harmony, Lead from Gold, One for All, Swashbuckler
- Copy 1: [Quickdraw, Strategist, Surplus] x [Chill Clip, Desperate Measures, Lead from Gold] — 8 combos
- Copy 2: [Envious Arsenal, Perpetual Motion, Rimestealer] x [Chill Clip, Desperate Measures, Lead from Gold] — 8 combos
- Copy 3: [Envious Arsenal, Rimestealer, Slideways] x [Chill Clip, Lead from Gold, Swashbuckler] — 5 combos
- Copy 4: [Quickdraw, Rimestealer, Slideways] x [Harmony, One for All] — 4 combos

### Parabellum
Submachine Gun · Solar · tiered, obtainable · GFS 233 · pool 49 combos · 4 copies · 25 combos covered
- Pool col 2 (7): Collective Demolition, Discord, Enlightened Action, Heal Clip, Killing Wind, Light Touch, Rewind Rounds
- Pool col 3 (7): Adagio, Attrition Orbs, Burning Ambition, Collective Action, Incandescent, One for All, Perfect Float
- Copy 1: [Collective Demolition, Killing Wind, Light Touch] x [Adagio, Attrition Orbs, Burning Ambition] — 9 combos
- Copy 2: [Collective Demolition, Discord, Enlightened Action] x [Attrition Orbs, Burning Ambition, Perfect Float] — 6 combos
- Copy 3: [Heal Clip, Killing Wind, Light Touch] x [Attrition Orbs, Collective Action, Perfect Float] — 6 combos
- Copy 4: [Enlightened Action, Heal Clip, Rewind Rounds] x [Collective Action, One for All] — 4 combos

### Resounding
Fusion Rifle · Strand · tiered, vendor 6-perk, obtainable · GFS 357 · pool 49 combos · 4 copies · 25 combos covered
- Pool col 2 (7): Ambitious Assassin, Compulsive Reloader, Cornered, Feeding Frenzy, Slice, Subsistence, Threat Detector
- Pool col 3 (7): Aggregate Charge, Hatchling, One for All, Rampage, Reservoir Burst, Strategist, Surrounded
- Copy 1: [Compulsive Reloader, Cornered, Feeding Frenzy] x [Aggregate Charge, One for All, Strategist] — 7 combos
- Copy 2: [Cornered, Feeding Frenzy, Slice] x [Hatchling, Rampage, Reservoir Burst] — 8 combos
- Copy 3: [Ambitious Assassin, Subsistence, Threat Detector] x [Reservoir Burst, Strategist, Surrounded] — 6 combos
- Copy 4: [Compulsive Reloader, Slice] x [One for All, Reservoir Burst, Surrounded] — 4 combos

### Rufus's Fury (Adept)
Auto Rifle · Strand · adept, craftable · GFS 701 · pool 81 combos · 4 copies · 25 combos covered
- Pool col 2 (9): Demolitionist, Keep Away, Moving Target, Perpetual Motion, Pugilist, Reconstruction, Rewind Rounds, Slice, Thresh
- Pool col 3 (9): Adrenaline Junkie, Aggregate Charge, Chaos Reshaped, Frenzy, Harmony, Hatchling, Paracausal Affinity, Tap the Trigger, Target Lock
- Copy 1: [Keep Away, Moving Target, Thresh] x [Aggregate Charge, Chaos Reshaped, Paracausal Affinity] — 7 combos
- Copy 2: [Reconstruction, Rewind Rounds, Thresh] x [Hatchling, Tap the Trigger, Target Lock] — 7 combos
- Copy 3: [Pugilist, Rewind Rounds, Slice] x [Chaos Reshaped, Paracausal Affinity, Tap the Trigger] — 8 combos
- Copy 4: [Demolitionist, Pugilist] x [Hatchling, Target Lock] — 3 combos

### Action Item
Trace Rifle · Stasis · tiered, obtainable · GFS 261 · pool 49 combos · 4 copies · 24 combos covered
- Pool col 2 (7): Deconstruct, Demolitionist, Dynamic Sway Reduction, Envious Assassin, High-Impact Reserves, Rewind Rounds, Rimestealer
- Pool col 3 (7): Binary Orbit, Crystalline Corpsebloom, Detonator Beam, Elemental Honing, Headstone, Killing Tally, Target Lock
- Copy 1: [Deconstruct, High-Impact Reserves, Rewind Rounds] x [Binary Orbit, Crystalline Corpsebloom, Detonator Beam] — 9 combos
- Copy 2: [Demolitionist, High-Impact Reserves, Rimestealer] x [Detonator Beam, Elemental Honing, Killing Tally] — 6 combos
- Copy 3: [Deconstruct, Dynamic Sway Reduction, Envious Assassin] x [Detonator Beam, Killing Tally, Target Lock] — 6 combos
- Copy 4: [Envious Assassin, High-Impact Reserves] x [Binary Orbit, Elemental Honing, Target Lock] — 3 combos

### Fimbulwinter Stitch
Sidearm · Arc · tiered, obtainable · GFS 259 · pool 49 combos · 4 copies · 24 combos covered
- Pool col 2 (7): Collective Pugilism, Lone Wolf, Loose Change, Rangefinder, Rapid Hit, Supercharged Magazine, Trickle Charge
- Pool col 3 (7): Collective Action, Jolting Feedback, Kill Clip, Precision Instrument, Redirection, Rolling Storm, Voltshot
- Copy 1: [Collective Pugilism, Supercharged Magazine, Trickle Charge] x [Collective Action, Kill Clip, Precision Instrument] — 8 combos
- Copy 2: [Collective Pugilism, Lone Wolf, Rangefinder] x [Redirection, Rolling Storm, Voltshot] — 7 combos
- Copy 3: [Loose Change, Rangefinder, Supercharged Magazine] x [Collective Action, Jolting Feedback, Redirection] — 4 combos
- Copy 4: [Loose Change, Rapid Hit, Trickle Charge] x [Precision Instrument, Redirection, Rolling Storm] — 5 combos

### Nasreddin
Sword · Arc · tiered, obtainable · GFS 338 · pool 49 combos · 4 copies · 24 combos covered
- Pool col 2 (7): Duelist's Trance, Energy Transfer, Flash Counter, Relentless Strikes, Sharp Harvest, Tireless Blade, Wellspring
- Pool col 3 (7): Eager Edge, En Garde, Jolting Feedback, One for All, Rolling Storm, Surrounded, Whirlwind Blade
- Copy 1: [Duelist's Trance, Energy Transfer, Flash Counter] x [Eager Edge, Jolting Feedback, Rolling Storm] — 9 combos
- Copy 2: [Relentless Strikes, Sharp Harvest, Tireless Blade] x [Eager Edge, Rolling Storm, Surrounded] — 8 combos
- Copy 3: [Wellspring] x [Eager Edge, Jolting Feedback, Rolling Storm] — 3 combos
- Copy 4: [Energy Transfer, Flash Counter, Wellspring] x [En Garde, Surrounded] — 4 combos

### Ribbontail
Trace Rifle · Strand · tiered, obtainable · GFS 153 · pool 36 combos · 4 copies · 24 combos covered
- Pool col 2 (6): Envious Arsenal, Proximity Power, Subsistence, Threat Detector, Transcendent Moment, Wellspring
- Pool col 3 (6): Binary Orbit, Detonator Beam, Killing Tally, Redirection, Surrounded, Tear
- Copy 1: [Envious Arsenal, Proximity Power, Subsistence] x [Detonator Beam, Redirection, Tear] — 8 combos
- Copy 2: [Threat Detector, Transcendent Moment, Wellspring] x [Detonator Beam, Killing Tally, Redirection] — 9 combos
- Copy 3: [Proximity Power, Threat Detector, Wellspring] x [Binary Orbit, Killing Tally, Tear] — 5 combos
- Copy 4: [Envious Arsenal, Transcendent Moment] x [Killing Tally, Tear] — 2 combos

### The Riposte
Auto Rifle · Void · tiered, vendor 6-perk, obtainable · GFS 273 · pool 49 combos · 4 copies · 24 combos covered
- Pool col 2 (7): Demoralize, Dimensional Shift, Light Touch, Repulsor Brace, Rewind Rounds, Tap the Trigger, Zen Moment
- Pool col 3 (7): Binary Orbit, Built to Blast, Desperate Measures, Destabilizing Rounds, Dynamic Sway Reduction, Kill Clip, Target Lock
- Copy 1: [Demoralize, Dimensional Shift, Tap the Trigger] x [Binary Orbit, Built to Blast, Desperate Measures] — 8 combos
- Copy 2: [Light Touch, Repulsor Brace, Rewind Rounds] x [Built to Blast, Desperate Measures, Destabilizing Rounds] — 8 combos
- Copy 3: [Dimensional Shift, Light Touch, Zen Moment] x [Built to Blast, Dynamic Sway Reduction, Kill Clip] — 5 combos
- Copy 4: [Dimensional Shift, Light Touch, Tap the Trigger] x [Target Lock] — 3 combos

### Cataphract GL3
Grenade Launcher · Strand · tiered, obtainable · GFS 366 · pool 49 combos · 4 copies · 23 combos covered
- Pool col 2 (7): Auto-Loading Holster, Blast Distributor, Envious Arsenal, Envious Assassin, Impulse Amplifier, Lead From Light, Quickdraw
- Pool col 3 (7): Bait and Switch, Chain Reaction, Demolitionist, Explosive Light, Full Court, Impromptu Ammunition, Vorpal Weapon
- Copy 1: [Blast Distributor, Envious Arsenal, Lead From Light] x [Demolitionist, Full Court, Impromptu Ammunition] — 8 combos
- Copy 2: [Envious Assassin, Impulse Amplifier, Quickdraw] x [Explosive Light, Full Court, Impromptu Ammunition] — 7 combos
- Copy 3: [Envious Arsenal, Lead From Light, Quickdraw] x [Bait and Switch, Explosive Light, Vorpal Weapon] — 6 combos
- Copy 4: [Lead From Light, Quickdraw] x [Chain Reaction] — 2 combos

### Eleatic Principle
Machine Gun · Arc · tiered, craftable, obtainable · GFS 593 · pool 71 combos · 4 copies · 23 combos covered
- Pool col 2 (8): Eddy Current, Empty Traits Socket, Ensemble, Heating Up, Moving Target, Offhand Strike, Well-Rounded, Zen Moment
- Pool col 3 (9): Adaptive Munitions, Adrenaline Junkie, Empty Traits Socket, Golden Tricorn, Golden Tricorn Enhanced, Harmony, Rangefinder, Tap the Trigger, Target Lock
- Copy 1: [Eddy Current, Ensemble, Offhand Strike] x [Adaptive Munitions, Rangefinder, Tap the Trigger] — 8 combos
- Copy 2: [Eddy Current, Ensemble, Zen Moment] x [Empty Traits Socket, Golden Tricorn, Target Lock] — 6 combos
- Copy 3: [Eddy Current, Well-Rounded, Zen Moment] x [Golden Tricorn Enhanced, Harmony, Rangefinder] — 6 combos
- Copy 4: [Offhand Strike, Well-Rounded, Zen Moment] x [Adaptive Munitions, Golden Tricorn Enhanced, Tap the Trigger] — 3 combos

### Peculiar Charm
Submachine Gun · Kinetic · tiered, vendor 6-perk, obtainable · GFS 210 · pool 49 combos · 4 copies · 23 combos covered
- Pool col 2 (7): Attrition Orbs, Impromptu Ammunition, Lone Wolf, Rangefinder, Rapid Hit, Shoot to Loot, Stopping Power
- Pool col 3 (7): All-Star, Bewildering Burst, Desperado, Firefly, Headseeker, Kinetic Tremors, Master of Arms
- Copy 1: [Attrition Orbs, Impromptu Ammunition, Rangefinder] x [All-Star, Bewildering Burst, Desperado] — 9 combos
- Copy 2: [Rapid Hit, Shoot to Loot, Stopping Power] x [All-Star, Bewildering Burst, Master of Arms] — 7 combos
- Copy 3: [Lone Wolf, Shoot to Loot, Stopping Power] x [All-Star, Bewildering Burst, Desperado] — 4 combos
- Copy 4: [Lone Wolf, Stopping Power] x [Firefly, Headseeker, Kinetic Tremors] — 3 combos

### The Beacon
Fusion Rifle · Solar · tiered, obtainable · GFS 227 · pool 49 combos · 4 copies · 23 combos covered
- Pool col 2 (7): Collective Pugilism, Demolitionist, Envious Arsenal, Lead from Gold, Lone Wolf, Overflow, Rewind Rounds
- Pool col 3 (7): Bait and Switch, Burning Ambition, Closing Time, Controlled Burst, Deconstruct, Reservoir Burst, Successful Warm-Up
- Copy 1: [Collective Pugilism, Demolitionist, Overflow] x [Bait and Switch, Burning Ambition, Closing Time] — 8 combos
- Copy 2: [Collective Pugilism, Lone Wolf, Rewind Rounds] x [Controlled Burst, Deconstruct, Reservoir Burst] — 8 combos
- Copy 3: [Collective Pugilism, Overflow, Rewind Rounds] x [Closing Time, Deconstruct, Successful Warm-Up] — 5 combos
- Copy 4: [Lead from Gold] x [Burning Ambition, Controlled Burst] — 2 combos

### The Slammer
Sword · Stasis · tiered, vendor 6-perk, obtainable · GFS 155 · pool 36 combos · 4 copies · 23 combos covered
- Pool col 2 (6): Attrition Orbs, Chain Reaction, Eager Edge, Pugilist, Relentless Strikes, Thresh
- Pool col 3 (6): Bait and Switch, Cold Steel, Collective Action, Demolitionist, One for All, Permeability
- Copy 1: [Chain Reaction, Pugilist, Thresh] x [Bait and Switch, Cold Steel, One for All] — 9 combos
- Copy 2: [Chain Reaction, Eager Edge, Relentless Strikes] x [Cold Steel, Demolitionist, Permeability] — 8 combos
- Copy 3: [Eager Edge, Pugilist, Thresh] x [Bait and Switch, Collective Action, Permeability] — 5 combos
- Copy 4: [Attrition Orbs] x [Permeability] — 1 combo

### A Good Shout
Combat Bow · Void · tiered, vendor 6-perk, obtainable · GFS 158 · pool 36 combos · 4 copies · 22 combos covered
- Pool col 2 (6): Bolt Scavenger, Built to Blast, Envious Arsenal, No Distractions, Repulsor Brace, Withering Gaze
- Pool col 3 (6): Box Breathing, Butterfly, Demoralize, Destabilizing Rounds, High Ground, Rampage
- Copy 1: [Bolt Scavenger, Built to Blast, Repulsor Brace] x [Box Breathing, Butterfly, Demoralize] — 9 combos
- Copy 2: [Bolt Scavenger, Built to Blast, Envious Arsenal] x [Butterfly, Destabilizing Rounds, Rampage] — 7 combos
- Copy 3: [Envious Arsenal, No Distractions] x [Box Breathing, Butterfly, Demoralize] — 4 combos
- Copy 4: [No Distractions] x [Destabilizing Rounds, Rampage] — 2 combos

### Acasia's Dejection (Adept)
Trace Rifle · Solar · adept, craftable · GFS 601 · pool 81 combos · 4 copies · 22 combos covered
- Pool col 2 (9): Burning Ambition, Collective Demolition, Envious Assassin, Field Prep, Hip-Fire Grip, Keep Away, Perpetual Motion, Reconstruction, Rewind Rounds
- Pool col 3 (9): Chaos Reshaped, Detonator Beam, Frenzy, Harmony, High-Impact Reserves, Incandescent, Paracausal Affinity, Target Lock, Vorpal Weapon
- Copy 1: [Burning Ambition, Collective Demolition, Field Prep] x [Chaos Reshaped, Detonator Beam, Vorpal Weapon] — 6 combos
- Copy 2: [Keep Away, Perpetual Motion, Reconstruction] x [Detonator Beam, High-Impact Reserves, Vorpal Weapon] — 7 combos
- Copy 3: [Burning Ambition, Collective Demolition, Hip-Fire Grip] x [Detonator Beam, Paracausal Affinity, Target Lock] — 5 combos
- Copy 4: [Collective Demolition, Envious Assassin, Hip-Fire Grip] x [Chaos Reshaped, High-Impact Reserves, Incandescent] — 4 combos

### Gunburn
Submachine Gun · Kinetic · tiered, obtainable · GFS 252 · pool 49 combos · 4 copies · 22 combos covered
- Pool col 2 (7): Bewildering Burst, Lead From Light, Lone Wolf, Pugilist, Recycled Energy, Stats for All, Threat Detector
- Pool col 3 (7): Ancillary Ordinance, Attrition Orbs, Binary Orbit, Kinetic Tremors, One for All, Target Lock, Wellspring
- Copy 1: [Lead From Light, Pugilist, Recycled Energy] x [Ancillary Ordinance, Kinetic Tremors, One for All] — 8 combos
- Copy 2: [Bewildering Burst, Stats for All, Threat Detector] x [Ancillary Ordinance, Target Lock, Wellspring] — 8 combos
- Copy 3: [Lead From Light, Recycled Energy, Stats for All] x [Kinetic Tremors, Wellspring] — 3 combos
- Copy 4: [Lone Wolf, Pugilist] x [Ancillary Ordinance, Binary Orbit, Wellspring] — 3 combos

### Watchful Eye
Machine Gun · Arc · tiered, obtainable · GFS 213 · pool 49 combos · 4 copies · 22 combos covered
- Pool col 2 (7): Dynamic Sway Reduction, Eddy Current, Field Prep, Hip-Fire Grip, Mulligan, Overflow, Wellspring
- Pool col 3 (7): Elemental Honing, Jolting Feedback, Killing Tally, Rolling Storm, Surrounded, Sword Logic, Target Lock
- Copy 1: [Field Prep, Hip-Fire Grip, Mulligan] x [Elemental Honing, Jolting Feedback, Sword Logic] — 9 combos
- Copy 2: [Dynamic Sway Reduction, Eddy Current, Mulligan] x [Killing Tally, Rolling Storm, Surrounded] — 7 combos
- Copy 3: [Field Prep, Mulligan, Wellspring] x [Killing Tally, Sword Logic, Target Lock] — 5 combos
- Copy 4: [Hip-Fire Grip] x [Killing Tally] — 1 combo

### Ammit AR2
Auto Rifle · Solar · tiered, craftable, obtainable · GFS 552 · pool 63 combos · 4 copies · 21 combos covered
- Pool col 2 (8): Ambitious Assassin, Dynamic Sway Reduction, Empty Traits Socket, Stats for All, Surplus, Triple Tap, Turnabout, Well-Rounded
- Pool col 3 (8): Adaptive Munitions, Adrenaline Junkie, Empty Traits Socket, Gutshot Straight, Incandescent, One for All, Pugilist, Tap the Trigger
- Copy 1: [Ambitious Assassin, Triple Tap, Turnabout] x [Adaptive Munitions, Gutshot Straight, Pugilist] — 7 combos
- Copy 2: [Surplus, Turnabout, Well-Rounded] x [Adrenaline Junkie, One for All, Tap the Trigger] — 6 combos
- Copy 3: [Triple Tap, Turnabout, Well-Rounded] x [Gutshot Straight, Incandescent, Tap the Trigger] — 4 combos
- Copy 4: [Dynamic Sway Reduction, Empty Traits Socket, Stats for All] x [Adaptive Munitions, Empty Traits Socket, Tap the Trigger] — 4 combos

### Submersion
Combat Bow · Stasis · tiered, obtainable · GFS 122 · pool 36 combos · 4 copies · 20 combos covered
- Pool col 2 (6): Auto-Loading Holster, Bolt Scavenger, Ensemble, Impulse Amplifier, Lead From Light, No Distractions
- Pool col 3 (6): Aggregate Charge, Chill Clip, Collective Action, Firing Line, Headstone, High Ground
- Copy 1: [Bolt Scavenger, Ensemble, Lead From Light] x [Aggregate Charge, Chill Clip, Collective Action] — 7 combos
- Copy 2: [Bolt Scavenger, Impulse Amplifier, Lead From Light] x [Firing Line, Headstone, High Ground] — 9 combos
- Copy 3: [No Distractions] x [Aggregate Charge, Chill Clip, Collective Action] — 3 combos
- Copy 4: [No Distractions] x [Headstone] — 1 combo

### Motif-41
Grenade Launcher · Solar · tiered, obtainable · GFS 358 · pool 49 combos · 4 copies · 19 combos covered
- Pool col 2 (7): Auto-Loading Holster, Heal Clip, Impulse Amplifier, Loose Change, Stats for All, Threat Detector, Wellspring
- Pool col 3 (7): Attrition Orbs, Binary Orbit, Demolitionist, Incandescent, Master of Arms, Reverberation, Vorpal Weapon
- Copy 1: [Auto-Loading Holster, Loose Change, Wellspring] x [Attrition Orbs, Master of Arms, Reverberation] — 9 combos
- Copy 2: [Impulse Amplifier, Loose Change, Stats for All] x [Attrition Orbs, Binary Orbit, Reverberation] — 5 combos
- Copy 3: [Impulse Amplifier, Threat Detector, Wellspring] x [Attrition Orbs, Incandescent, Master of Arms] — 3 combos
- Copy 4: [Loose Change] x [Incandescent, Vorpal Weapon] — 2 combos

### Better Devils
Hand Cannon · Kinetic · tiered, vendor 6-perk, obtainable · GFS 526 · pool 60 combos · 4 copies · 18 combos covered
- Pool col 2 (9): Auto-Loading Holster, Explosive Payload, Hip-Fire Grip, Moving Target, Outlaw, Rangefinder, Snapshot Sights, Threat Detector, Triple Tap
- Pool col 3 (7): Explosive Payload, Field Prep, Hip-Fire Grip, Kill Clip, Opening Shot, Timed Payload, Zen Moment
- Copy 1: [Auto-Loading Holster, Explosive Payload, Outlaw] x [Explosive Payload, Field Prep, Timed Payload] — 6 combos
- Copy 2: [Auto-Loading Holster, Hip-Fire Grip, Threat Detector] x [Hip-Fire Grip, Timed Payload, Zen Moment] — 5 combos
- Copy 3: [Explosive Payload, Threat Detector, Triple Tap] x [Explosive Payload, Kill Clip, Zen Moment] — 5 combos
- Copy 4: [Rangefinder, Threat Detector] x [Field Prep] — 2 combos

### No Reprieve
Shotgun · Stasis · tiered, craftable, obtainable · GFS 753 · pool 63 combos · 4 copies · 15 combos covered
- Pool col 2 (8): Empty Traits Socket, Feeding Frenzy, Outlaw, Pugilist, Stats for All, Steady Hands, Surplus, Triple Tap
- Pool col 3 (8): Empty Traits Socket, Focused Fury, Harmony, Headstone, Snapshot Sights, Surrounded, Swashbuckler, Wellspring
- Copy 1: [Stats for All, Surplus, Triple Tap] x [Headstone, Surrounded, Swashbuckler] — 6 combos
- Copy 2: [Feeding Frenzy, Outlaw, Surplus] x [Empty Traits Socket, Snapshot Sights, Wellspring] — 5 combos
- Copy 3: [Empty Traits Socket, Triple Tap] x [Empty Traits Socket, Focused Fury, Snapshot Sights] — 3 combos
- Copy 4: [Empty Traits Socket] x [Swashbuckler] — 1 combo

### Punching Out
Sidearm · Solar · tiered, vendor 6-perk, obtainable · GFS 386 · pool 49 combos · 3 copies · 24 combos covered
- Pool col 2 (7): Demolitionist, Heal Clip, Light Touch, Overflow, Rangefinder, Recycled Energy, Subsistence
- Pool col 3 (7): Adrenaline Junkie, Binary Orbit, Feeding Frenzy, Incandescent, Kill Clip, Meganeura, Swashbuckler
- Copy 1: [Heal Clip, Light Touch, Rangefinder] x [Adrenaline Junkie, Binary Orbit, Feeding Frenzy] — 9 combos
- Copy 2: [Overflow, Recycled Energy, Subsistence] x [Adrenaline Junkie, Feeding Frenzy, Meganeura] — 8 combos
- Copy 3: [Light Touch, Rangefinder, Recycled Energy] x [Incandescent, Meganeura, Swashbuckler] — 7 combos

### Aberrant Action
Sidearm · Solar · tiered, craftable, obtainable · GFS 703 · pool 71 combos · 3 copies · 23 combos covered
- Pool col 2 (8): Ambitious Assassin, Beacon Rounds, Empty Traits Socket, Field Prep, Heal Clip, Pugilist, Strategist, Threat Detector
- Pool col 3 (9): Demolitionist, Empty Traits Socket, Golden Tricorn, Golden Tricorn Enhanced, Harmony, Incandescent, Reverberation, Snapshot Sights, Swashbuckler
- Copy 1: [Beacon Rounds, Heal Clip, Strategist] x [Harmony, Snapshot Sights, Swashbuckler] — 8 combos
- Copy 2: [Beacon Rounds, Heal Clip, Pugilist] x [Empty Traits Socket, Incandescent, Reverberation] — 8 combos
- Copy 3: [Ambitious Assassin, Empty Traits Socket, Threat Detector] x [Empty Traits Socket, Incandescent, Reverberation] — 7 combos

### Cry Mutiny
Grenade Launcher · Solar · tiered, vendor 6-perk, obtainable · GFS 326 · pool 49 combos · 3 copies · 23 combos covered
- Pool col 2 (7): Blast Distributor, Danger Zone, Demolitionist, Grave Robber, Impulse Amplifier, Incandescent, Reverberation
- Pool col 3 (7): Adrenaline Junkie, Aggregate Charge, Full Court, Mega Kill Clip, Surrounded, Swashbuckler, Vorpal Weapon
- Copy 1: [Blast Distributor, Danger Zone, Incandescent] x [Adrenaline Junkie, Mega Kill Clip, Swashbuckler] — 8 combos
- Copy 2: [Grave Robber, Impulse Amplifier, Reverberation] x [Full Court, Mega Kill Clip, Swashbuckler] — 9 combos
- Copy 3: [Blast Distributor, Incandescent, Reverberation] x [Adrenaline Junkie, Surrounded, Vorpal Weapon] — 6 combos

### Semiotician
Rocket Launcher · Strand · tiered, craftable, obtainable · GFS 609 · pool 63 combos · 3 copies · 23 combos covered
- Pool col 2 (8): Empty Traits Socket, Field Prep, Impulse Amplifier, Keep Away, Perpetual Motion, Shot Swap, Stats for All, Wellspring
- Pool col 3 (8): Bipod, Danger Zone, Empty Traits Socket, Explosive Light, Frenzy, Harmony, Hatchling, Pugilist
- Copy 1: [Keep Away, Perpetual Motion, Shot Swap] x [Bipod, Danger Zone, Explosive Light] — 9 combos
- Copy 2: [Shot Swap, Stats for All, Wellspring] x [Bipod, Explosive Light, Hatchling] — 7 combos
- Copy 3: [Empty Traits Socket, Impulse Amplifier, Wellspring] x [Bipod, Danger Zone, Pugilist] — 7 combos

### Sublimation
Scout Rifle · Arc · tiered, obtainable · GFS 268 · pool 49 combos · 3 copies · 23 combos covered
- Pool col 2 (7): Demolitionist, Eddy Current, Impromptu Ammunition, Moving Target, Rapid Hit, Shoot to Loot, Sympathetic Arsenal
- Pool col 3 (7): Adagio, Explosive Payload, No Distractions, Precision Instrument, Redirection, Rolling Storm, Voltshot
- Copy 1: [Eddy Current, Impromptu Ammunition, Sympathetic Arsenal] x [Adagio, No Distractions, Redirection] — 8 combos
- Copy 2: [Eddy Current, Shoot to Loot, Sympathetic Arsenal] x [Explosive Payload, No Distractions, Precision Instrument] — 7 combos
- Copy 3: [Demolitionist, Impromptu Ammunition, Sympathetic Arsenal] x [Explosive Payload, Rolling Storm, Voltshot] — 8 combos

### Word of Crota (Adept)
Hand Cannon · Void · adept, craftable · GFS 714 · pool 81 combos · 3 copies · 23 combos covered
- Pool col 2 (9): Collective Demolition, Demolitionist, Dragonfly, Enlightened Action, Killing Wind, Rangefinder, Rapid Hit, Repulsor Brace, Subsistence
- Pool col 3 (9): Adrenaline Junkie, Destabilizing Rounds, Focused Fury, Frenzy, Magnificent Howl, Master of Arms, Precision Instrument, Rampage, Sword Logic
- Copy 1: [Collective Demolition, Demolitionist, Dragonfly] x [Focused Fury, Magnificent Howl, Precision Instrument] — 9 combos
- Copy 2: [Dragonfly, Killing Wind, Rapid Hit] x [Frenzy, Magnificent Howl, Master of Arms] — 7 combos
- Copy 3: [Collective Demolition, Rangefinder, Subsistence] x [Magnificent Howl, Rampage, Sword Logic] — 7 combos

### Adamantite (Adept)
Auto Rifle · Strand · adept, obtainable · GFS 336 · pool 49 combos · 3 copies · 22 combos covered
- Pool col 2 (7): Demolitionist, Ensemble, Pugilist, Reciprocity, Slice, Subsistence, Unrelenting
- Pool col 3 (7): Attrition Orbs, Circle of Life, Elemental Honing, Frenzy, Hatchling, Kill Clip, Tear
- Copy 1: [Pugilist, Reciprocity, Slice] x [Attrition Orbs, Circle of Life, Elemental Honing] — 8 combos
- Copy 2: [Ensemble, Reciprocity, Unrelenting] x [Circle of Life, Frenzy, Tear] — 7 combos
- Copy 3: [Demolitionist, Reciprocity, Unrelenting] x [Circle of Life, Hatchling, Kill Clip] — 7 combos

### Corundum Hammer
Hand Cannon · Strand · tiered, obtainable · GFS 271 · pool 49 combos · 3 copies · 22 combos covered
- Pool col 2 (7): Firefly, Fragile Focus, Lone Wolf, Reconstruction, Shoot to Loot, Slice, Slideshot
- Pool col 3 (7): Elemental Honing, Explosive Payload, Keep Away, Opening Shot, Precision Instrument, Sword Logic, Tear
- Copy 1: [Firefly, Fragile Focus, Slice] x [Elemental Honing, Explosive Payload, Precision Instrument] — 7 combos
- Copy 2: [Fragile Focus, Reconstruction, Shoot to Loot] x [Elemental Honing, Keep Away, Tear] — 8 combos
- Copy 3: [Lone Wolf, Slice, Slideshot] x [Explosive Payload, Keep Away, Tear] — 7 combos

### Eye of Sol
Sniper Rifle · Kinetic · tiered, obtainable · GFS 367 · pool 49 combos · 3 copies · 22 combos covered
- Pool col 2 (7): Encore, Fragile Focus, Moving Target, No Distractions, Perpetual Motion, Shot Swap, Slickdraw
- Pool col 3 (7): Deconstruct, Firing Line, Keep Away, Opening Shot, Precision Instrument, Snapshot Sights, Vorpal Weapon
- Copy 1: [Fragile Focus, Moving Target, Slickdraw] x [Deconstruct, Firing Line, Keep Away] — 8 combos
- Copy 2: [Encore, No Distractions, Shot Swap] x [Deconstruct, Keep Away, Snapshot Sights] — 9 combos
- Copy 3: [Encore, Perpetual Motion, Shot Swap] x [Firing Line, Opening Shot, Precision Instrument] — 5 combos

### Live Fire
Scout Rifle · Stasis · tiered, obtainable · GFS 156 · pool 36 combos · 3 copies · 22 combos covered
- Pool col 2 (6): Air Trigger, Heating Up, Perfect Float, Rapid Hit, Rimestealer, Subsistence
- Pool col 3 (6): Headstone, No Distractions, Offhand Strike, Rampage, Shoot to Loot, To the Pain
- Copy 1: [Air Trigger, Heating Up, Perfect Float] x [No Distractions, Shoot to Loot, To the Pain] — 9 combos
- Copy 2: [Rapid Hit, Rimestealer, Subsistence] x [No Distractions, Shoot to Loot, To the Pain] — 9 combos
- Copy 3: [Air Trigger, Rimestealer, Subsistence] x [Headstone, Offhand Strike] — 4 combos

### The Martlet
Pulse Rifle · Void · tiered, obtainable · GFS 342 · pool 49 combos · 3 copies · 22 combos covered
- Pool col 2 (7): Firefly, Headseeker, Keep Away, Lone Wolf, Loose Change, Perpetual Motion, Repulsor Brace
- Pool col 3 (7): Desperado, Desperate Measures, Destabilizing Rounds, Kill Clip, Sword Logic, Withering Gaze, Zen Moment
- Copy 1: [Firefly, Headseeker, Loose Change] x [Desperado, Destabilizing Rounds, Kill Clip] — 9 combos
- Copy 2: [Firefly, Headseeker, Loose Change] x [Desperate Measures, Sword Logic, Withering Gaze] — 7 combos
- Copy 3: [Keep Away, Loose Change, Perpetual Motion] x [Destabilizing Rounds, Withering Gaze, Zen Moment] — 6 combos

### Abyssal Edge
Sword · Strand · tiered, obtainable · GFS 276 · pool 49 combos · 3 copies · 21 combos covered
- Pool col 2 (7): Duelist's Trance, Energy Transfer, Flash Counter, Relentless Strikes, Slice, Tireless Blade, Valiant Charge
- Pool col 3 (7): Demolitionist, Elemental Honing, En Garde, Hatchling, Redirection, Surrounded, Sword Logic
- Copy 1: [Duelist's Trance, Energy Transfer, Flash Counter] x [Demolitionist, Hatchling, Sword Logic] — 9 combos
- Copy 2: [Relentless Strikes, Tireless Blade, Valiant Charge] x [Elemental Honing, Redirection, Sword Logic] — 8 combos
- Copy 3: [Slice, Tireless Blade] x [Demolitionist, Hatchling, Redirection] — 4 combos

### Archon's Thunder
Machine Gun · Stasis · tiered, obtainable · GFS 293 · pool 49 combos · 3 copies · 21 combos covered
- Pool col 2 (7): Air Trigger, Dynamic Sway Reduction, Enlightened Action, Envious Assassin, Fourth Time's the Charm, High-Impact Reserves, Rimestealer
- Pool col 3 (7): Desperate Measures, Headstone, Killing Tally, Onslaught, Rewind Rounds, Tap the Trigger, Target Lock
- Copy 1: [Air Trigger, Enlightened Action, High-Impact Reserves] x [Killing Tally, Onslaught, Rewind Rounds] — 8 combos
- Copy 2: [Air Trigger, Dynamic Sway Reduction, Rimestealer] x [Rewind Rounds, Tap the Trigger, Target Lock] — 6 combos
- Copy 3: [Envious Assassin, Fourth Time's the Charm, High-Impact Reserves] x [Desperate Measures, Headstone, Tap the Trigger] — 7 combos

### Ascendancy
Rocket Launcher · Solar · tiered, vendor 6-perk, obtainable · GFS 248 · pool 49 combos · 3 copies · 21 combos covered
- Pool col 2 (7): Ambitious Assassin, Attrition Orbs, Field Prep, Impulse Amplifier, Lead From Light, Reconstruction, Slideways
- Pool col 3 (7): Bipod, Chain Reaction, Cluster Bomb, Explosive Light, Incandescent, Lasting Impression, Reaper's Tithe
- Copy 1: [Attrition Orbs, Lead From Light, Slideways] x [Bipod, Cluster Bomb, Lasting Impression] — 9 combos
- Copy 2: [Field Prep, Lead From Light, Slideways] x [Explosive Light, Incandescent, Reaper's Tithe] — 8 combos
- Copy 3: [Impulse Amplifier, Reconstruction, Slideways] x [Chain Reaction, Explosive Light, Reaper's Tithe] — 4 combos

### Auric Disabler
Auto Rifle · Strand · tiered, obtainable · GFS 293 · pool 49 combos · 3 copies · 21 combos covered
- Pool col 2 (7): Dragonfly, Dynamic Sway Reduction, Gutshot Straight, Hatchling, Lone Wolf, Slice, Zen Moment
- Pool col 3 (7): Desperate Measures, Kill Clip, Onslaught, Sword Logic, Tap the Trigger, Target Lock, Tear
- Copy 1: [Dynamic Sway Reduction, Gutshot Straight, Hatchling] x [Onslaught, Sword Logic, Tear] — 8 combos
- Copy 2: [Dragonfly, Hatchling, Lone Wolf] x [Desperate Measures, Onslaught, Tap the Trigger] — 6 combos
- Copy 3: [Dragonfly, Gutshot Straight, Hatchling] x [Kill Clip, Target Lock, Tear] — 7 combos

### Belisarius-D
Pulse Rifle · Strand · tiered, vendor 6-perk, obtainable · GFS 368 · pool 49 combos · 3 copies · 21 combos covered
- Pool col 2 (7): Dragonfly, Elemental Capacitor, Keep Away, Lone Wolf, Rapid Hit, Slice, Tear
- Pool col 3 (7): Desperado, Elemental Honing, Eye of the Storm, Firefly, Hatchling, Headseeker, Kill Clip
- Copy 1: [Elemental Capacitor, Slice, Tear] x [Desperado, Eye of the Storm, Firefly] — 9 combos
- Copy 2: [Dragonfly, Elemental Capacitor, Tear] x [Elemental Honing, Hatchling, Headseeker] — 7 combos
- Copy 3: [Dragonfly, Elemental Capacitor, Rapid Hit] x [Eye of the Storm, Firefly, Kill Clip] — 5 combos

### Crowning Duologue
Rocket Launcher · Strand · tiered, obtainable · GFS 245 · pool 49 combos · 3 copies · 21 combos covered
- Pool col 2 (7): Air Trigger, Auto-Loading Holster, Demolitionist, Grave Robber, Hatchling, Impulse Amplifier, Reconstruction
- Pool col 3 (7): Bait and Switch, Bipod, Chain Reaction, Cluster Bomb, Deconstruct, Envious Assassin, Reverberation
- Copy 1: [Air Trigger, Grave Robber, Hatchling] x [Bipod, Envious Assassin, Reverberation] — 9 combos
- Copy 2: [Grave Robber, Hatchling, Reconstruction] x [Cluster Bomb, Deconstruct, Envious Assassin] — 7 combos
- Copy 3: [Demolitionist, Impulse Amplifier] x [Bait and Switch, Deconstruct, Envious Assassin] — 5 combos

### Doomsday
Grenade Launcher · Arc · tiered, vendor 6-perk, obtainable · GFS 218 · pool 42 combos · 3 copies · 21 combos covered
- Pool col 2 (7): Ambitious Assassin, Attrition Orbs, Auto-Loading Holster, Eddy Current, Envious Arsenal, Snapshot Sights, Supercharged Magazine
- Pool col 3 (6): Bait and Switch, Chain Reaction, Explosive Light, Full Court, Jolting Feedback, Quickdraw
- Copy 1: [Ambitious Assassin, Attrition Orbs, Auto-Loading Holster] x [Full Court, Jolting Feedback, Quickdraw] — 9 combos
- Copy 2: [Ambitious Assassin, Eddy Current, Supercharged Magazine] x [Bait and Switch, Explosive Light, Full Court] — 8 combos
- Copy 3: [Eddy Current, Snapshot Sights, Supercharged Magazine] x [Chain Reaction, Full Court, Quickdraw] — 4 combos

### Forbearance (Adept)
Grenade Launcher · Arc · adept, craftable · GFS 735 · pool 90 combos · 3 copies · 21 combos covered
- Pool col 2 (9): Ambitious Assassin, Demolitionist, Genesis, Rolling Storm, Sleight of Hand, Stats for All, Steady Hands, Surplus, Unrelenting
- Pool col 3 (10): Bait and Switch, Chain Reaction, Frenzy, Gear Shift, Golden Tricorn, Golden Tricorn Enhanced, One for All, Rampage, Turnabout, Wellspring
- Copy 1: [Genesis, Rolling Storm, Sleight of Hand] x [Frenzy, Gear Shift, Golden Tricorn] — 8 combos
- Copy 2: [Rolling Storm, Steady Hands, Surplus] x [Bait and Switch, Gear Shift, Golden Tricorn Enhanced] — 7 combos
- Copy 3: [Sleight of Hand, Stats for All, Unrelenting] x [Gear Shift, Golden Tricorn Enhanced, Rampage] — 6 combos

### Forced Memorializer
Scout Rifle · Kinetic · tiered, vendor 6-perk, obtainable · GFS 149 · pool 36 combos · 3 copies · 21 combos covered
- Pool col 2 (6): Auto-Loading Holster, Bewildering Burst, Explosive Payload, Lone Wolf, Rapid Hit, Shoot to Loot
- Pool col 3 (6): Ancillary Ordinance, Elemental Honing, Kinetic Tremors, Multikill Clip, Outlaw, To the Pain
- Copy 1: [Auto-Loading Holster, Explosive Payload, Shoot to Loot] x [Ancillary Ordinance, Kinetic Tremors, To the Pain] — 9 combos
- Copy 2: [Bewildering Burst, Explosive Payload, Lone Wolf] x [Multikill Clip, Outlaw, To the Pain] — 8 combos
- Copy 3: [Auto-Loading Holster, Rapid Hit, Shoot to Loot] x [Ancillary Ordinance, Outlaw] — 4 combos

### Jorum's Claw
Pulse Rifle · Solar · tiered, obtainable · GFS 250 · pool 36 combos · 3 copies · 21 combos covered
- Pool col 2 (6): Encore, Gutshot Straight, Iron Grip, Moving Target, Offhand Strike, Outlaw
- Pool col 3 (6): Frenzy, Golden Tricorn, Headseeker, Incandescent, Iron Reach, Kill Clip
- Copy 1: [Encore, Gutshot Straight, Iron Grip] x [Frenzy, Headseeker, Iron Reach] — 9 combos
- Copy 2: [Iron Grip, Offhand Strike, Outlaw] x [Incandescent, Iron Reach, Kill Clip] — 8 combos
- Copy 3: [Iron Grip, Moving Target, Offhand Strike] x [Frenzy, Golden Tricorn, Incandescent] — 4 combos

### Nightshade
Pulse Rifle · Strand · tiered, vendor 6-perk, obtainable · GFS 351 · pool 48 combos · 3 copies · 21 combos covered
- Pool col 2 (7): Keep Away, Lead From Light, Lucky Shot, Moving Target, Outlaw, Slice, Under Pressure
- Pool col 3 (7): Desperate Measures, Eye of the Storm, Feeding Frenzy, Hatchling, Headseeker, Kill Clip, Moving Target
- Copy 1: [Keep Away, Lead From Light, Lucky Shot] x [Eye of the Storm, Feeding Frenzy, Headseeker] — 9 combos
- Copy 2: [Lead From Light, Outlaw, Slice] x [Feeding Frenzy, Kill Clip, Moving Target] — 7 combos
- Copy 3: [Lucky Shot, Under Pressure] x [Feeding Frenzy, Kill Clip, Moving Target] — 5 combos

### Occluded Finality
Sniper Rifle · Arc · tiered, obtainable · GFS 478 · pool 49 combos · 3 copies · 21 combos covered
- Pool col 2 (7): Auto-Loading Holster, Mulligan, No Distractions, Rapid Hit, Snapshot Sights, Surplus, Under Pressure
- Pool col 3 (7): Demolitionist, Elemental Capacitor, Eye of the Storm, Firing Line, Iron Reach, Opening Shot, Vorpal Weapon
- Copy 1: [Mulligan, No Distractions, Snapshot Sights] x [Demolitionist, Firing Line, Iron Reach] — 9 combos
- Copy 2: [Mulligan, Rapid Hit, Surplus] x [Iron Reach, Opening Shot, Vorpal Weapon] — 7 combos
- Copy 3: [Rapid Hit, Surplus, Under Pressure] x [Firing Line, Opening Shot, Vorpal Weapon] — 5 combos

### Python
Shotgun · Void · tiered, vendor 6-perk, obtainable · GFS 383 · pool 49 combos · 3 copies · 21 combos covered
- Pool col 2 (7): Dimensional Shift, Loose Change, Overflow, Pugilist, Repulsor Brace, Slideshot, Threat Detector
- Pool col 3 (7): Destabilizing Rounds, Harmony, One-Two Punch, Opening Shot, Swashbuckler, Trench Barrel, Withering Gaze
- Copy 1: [Dimensional Shift, Loose Change, Slideshot] x [Destabilizing Rounds, Harmony, One-Two Punch] — 8 combos
- Copy 2: [Dimensional Shift, Overflow, Repulsor Brace] x [One-Two Punch, Opening Shot, Trench Barrel] — 8 combos
- Copy 3: [Dimensional Shift, Overflow, Slideshot] x [Destabilizing Rounds, Swashbuckler, Withering Gaze] — 5 combos

### Sarpedon-D
Hand Cannon · Arc · tiered, vendor 6-perk, obtainable · GFS 115 · pool 36 combos · 3 copies · 21 combos covered
- Pool col 2 (6): Eddy Current, Impromptu Ammunition, Lead From Light, Proximity Power, To the Pain, Trickle Charge
- Pool col 3 (6): Collective Pugilism, Desperate Measures, One-Two Punch, Rolling Storm, Trench Barrel, Voltshot
- Copy 1: [Eddy Current, Impromptu Ammunition, Trickle Charge] x [Desperate Measures, One-Two Punch, Trench Barrel] — 9 combos
- Copy 2: [Lead From Light, Proximity Power, To the Pain] x [One-Two Punch, Rolling Storm, Trench Barrel] — 8 combos
- Copy 3: [Lead From Light, Proximity Power, To the Pain] x [Desperate Measures, Voltshot] — 4 combos

### Something Something
Sniper Rifle · Kinetic · tiered, vendor 6-perk, obtainable · GFS 138 · pool 36 combos · 3 copies · 21 combos covered
- Pool col 2 (6): Bewildering Burst, Discord, No Distractions, Snapshot Sights, Stopping Power, Triple Tap
- Pool col 3 (6): Adhesive Ordnance, All-Star, Box Breathing, Elemental Honing, Kinetic Tremors, Redirection
- Copy 1: [Discord, No Distractions, Snapshot Sights] x [Adhesive Ordnance, All-Star, Kinetic Tremors] — 7 combos
- Copy 2: [Bewildering Burst, Stopping Power, Triple Tap] x [Adhesive Ordnance, All-Star, Box Breathing] — 7 combos
- Copy 3: [No Distractions, Stopping Power, Triple Tap] x [Elemental Honing, Kinetic Tremors, Redirection] — 7 combos

### The Heron
Glaive · Void · tiered, obtainable · GFS 186 · pool 49 combos · 3 copies · 21 combos covered
- Pool col 2 (7): Disruption Break, Envious Assassin, Lead from Gold, Overflow, Proximity Power, Replenishing Aegis, Repulsor Brace
- Pool col 3 (7): Binary Orbit, Close to Melee, Destabilizing Rounds, Redirection, Sword Logic, Unrelenting, Unstoppable Force
- Copy 1: [Disruption Break, Envious Assassin, Proximity Power] x [Close to Melee, Redirection, Sword Logic] — 8 combos
- Copy 2: [Envious Assassin, Lead from Gold, Proximity Power] x [Sword Logic, Unrelenting, Unstoppable Force] — 6 combos
- Copy 3: [Overflow, Replenishing Aegis, Repulsor Brace] x [Redirection, Sword Logic, Unrelenting] — 7 combos

### Trachinus
Shotgun · Stasis · tiered, obtainable · GFS 202 · pool 36 combos · 3 copies · 21 combos covered
- Pool col 2 (6): Killing Wind, Lead from Gold, Proximity Power, Rapid Hit, Rimestealer, Transcendent Moment
- Pool col 3 (6): Binary Orbit, Chill Clip, Encore, Headstone, Precision Instrument, Swashbuckler
- Copy 1: [Lead from Gold, Proximity Power, Rapid Hit] x [Chill Clip, Encore, Headstone] — 9 combos
- Copy 2: [Killing Wind, Rimestealer, Transcendent Moment] x [Binary Orbit, Encore, Headstone] — 8 combos
- Copy 3: [Killing Wind, Lead from Gold, Transcendent Moment] x [Chill Clip, Precision Instrument] — 4 combos

### Ahab Char
Auto Rifle · Solar · tiered, obtainable · GFS 349 · pool 49 combos · 3 copies · 20 combos covered
- Pool col 2 (7): Grave Robber, Heal Clip, Perpetual Motion, Proximity Power, Recycled Energy, Subsistence, Transcendent Moment
- Pool col 3 (7): Adagio, Binary Orbit, Burning Ambition, Eye of the Storm, High-Impact Reserves, Kill Clip, Swashbuckler
- Copy 1: [Grave Robber, Proximity Power, Recycled Energy] x [Burning Ambition, Eye of the Storm, High-Impact Reserves] — 6 combos
- Copy 2: [Grave Robber, Heal Clip, Transcendent Moment] x [Adagio, High-Impact Reserves, Kill Clip] — 7 combos
- Copy 3: [Perpetual Motion, Subsistence, Transcendent Moment] x [Binary Orbit, Burning Ambition, Swashbuckler] — 7 combos

### Aisha's Embrace
Scout Rifle · Void · tiered, obtainable · GFS 300 · pool 49 combos · 3 copies · 20 combos covered
- Pool col 2 (7): Demoralize, Encore, Eye of the Storm, Keep Away, Rapid Hit, Shoot to Loot, Vorpal Weapon
- Pool col 3 (7): Adagio, Desperate Measures, Destabilizing Rounds, Kill Clip, Precision Instrument, Sword Logic, Withering Gaze
- Copy 1: [Demoralize, Eye of the Storm, Vorpal Weapon] x [Adagio, Precision Instrument, Sword Logic] — 8 combos
- Copy 2: [Encore, Eye of the Storm, Vorpal Weapon] x [Destabilizing Rounds, Kill Clip, Withering Gaze] — 9 combos
- Copy 3: [Rapid Hit, Shoot to Loot, Vorpal Weapon] x [Desperate Measures, Destabilizing Rounds] — 3 combos

### Felwinter's Lie
Shotgun · Solar · tiered, obtainable · GFS 342 · pool 49 combos · 3 copies · 20 combos covered
- Pool col 2 (7): Cascade Point, Dual Loader, Heal Clip, Lone Wolf, Slickdraw, Slideshot, Threat Detector
- Pool col 3 (7): Bait and Switch, Closing Time, Incandescent, Iron Reach, One-Two Punch, Opening Shot, Trench Barrel
- Copy 1: [Cascade Point, Dual Loader, Lone Wolf] x [Closing Time, Iron Reach, Opening Shot] — 9 combos
- Copy 2: [Cascade Point, Heal Clip, Threat Detector] x [Iron Reach, One-Two Punch, Trench Barrel] — 7 combos
- Copy 3: [Dual Loader, Slickdraw, Slideshot] x [Bait and Switch, Iron Reach, One-Two Punch] — 4 combos

### Indebted Kindness
Sidearm · Arc · tiered, obtainable · GFS 134 · pool 36 combos · 3 copies · 20 combos covered
- Pool col 2 (6): Air Trigger, Beacon Rounds, Danger Zone, Deconstruct, Impulse Amplifier, Trickle Charge
- Pool col 3 (6): Attrition Orbs, Chain Reaction, Gear Shift, Rolling Storm, Surrounded, Voltshot
- Copy 1: [Air Trigger, Beacon Rounds, Trickle Charge] x [Attrition Orbs, Gear Shift, Rolling Storm] — 9 combos
- Copy 2: [Beacon Rounds, Danger Zone, Deconstruct] x [Gear Shift, Surrounded, Voltshot] — 7 combos
- Copy 3: [Danger Zone, Deconstruct, Trickle Charge] x [Chain Reaction, Rolling Storm, Surrounded] — 4 combos

### Last Rite
Scout Rifle · Kinetic · tiered, vendor 6-perk, obtainable · GFS 297 · pool 49 combos · 3 copies · 20 combos covered
- Pool col 2 (7): Bewildering Burst, Dual Loader, Hip-Fire Grip, Keep Away, Reconstruction, Shoot to Loot, Stopping Power
- Pool col 3 (7): Adhesive Ordnance, Explosive Payload, Firefly, Focused Fury, Offhand Strike, Opening Shot, Vorpal Weapon
- Copy 1: [Dual Loader, Hip-Fire Grip, Reconstruction] x [Adhesive Ordnance, Explosive Payload, Firefly] — 9 combos
- Copy 2: [Bewildering Burst, Dual Loader, Stopping Power] x [Explosive Payload, Focused Fury, Offhand Strike] — 6 combos
- Copy 3: [Bewildering Burst, Reconstruction, Shoot to Loot] x [Adhesive Ordnance, Offhand Strike, Vorpal Weapon] — 5 combos

### Last Thursday
Pulse Rifle · Strand · tiered, obtainable · GFS 366 · pool 49 combos · 3 copies · 20 combos covered
- Pool col 2 (7): Built to Blast, Demolitionist, Moving Target, Rapid Hit, Strategist, Subsistence, Transcendent Moment
- Pool col 3 (7): Binary Orbit, Dragonfly, Elemental Honing, Frenzy, Hatchling, Headseeker, Slice
- Copy 1: [Built to Blast, Strategist, Transcendent Moment] x [Binary Orbit, Frenzy, Headseeker] — 8 combos
- Copy 2: [Built to Blast, Rapid Hit, Subsistence] x [Elemental Honing, Hatchling, Slice] — 7 combos
- Copy 3: [Demolitionist, Moving Target, Transcendent Moment] x [Binary Orbit, Elemental Honing, Slice] — 5 combos

### Monody-44
Fusion Rifle · Void · tiered, obtainable · GFS 342 · pool 49 combos · 3 copies · 20 combos covered
- Pool col 2 (7): Attrition Orbs, Cornered, Discord, Enlightened Action, Lone Wolf, Repulsor Brace, Subsistence
- Pool col 3 (7): Closing Time, Controlled Burst, Destabilizing Rounds, Frenzy, Successful Warm-Up, Surrounded, Withering Gaze
- Copy 1: [Cornered, Discord, Enlightened Action] x [Closing Time, Controlled Burst, Destabilizing Rounds] — 8 combos
- Copy 2: [Attrition Orbs, Cornered, Enlightened Action] x [Controlled Burst, Successful Warm-Up, Withering Gaze] — 6 combos
- Copy 3: [Discord, Repulsor Brace, Subsistence] x [Controlled Burst, Successful Warm-Up, Withering Gaze] — 6 combos

### No Feelings
Scout Rifle · Arc · tiered, vendor 6-perk, obtainable · GFS 296 · pool 49 combos · 3 copies · 20 combos covered
- Pool col 2 (7): Collective Demolition, Impromptu Ammunition, Keep Away, Outlaw, Rapid Hit, Rolling Storm, Voltshot
- Pool col 3 (7): Adrenaline Junkie, Box Breathing, Explosive Payload, Gear Shift, Kill Clip, Meganeura, Rampage
- Copy 1: [Collective Demolition, Rolling Storm, Voltshot] x [Box Breathing, Gear Shift, Kill Clip] — 9 combos
- Copy 2: [Collective Demolition, Rapid Hit, Voltshot] x [Explosive Payload, Gear Shift, Meganeura] — 6 combos
- Copy 3: [Impromptu Ammunition, Outlaw, Voltshot] x [Box Breathing, Meganeura, Rampage] — 5 combos

### Qua Vinctus IV
Machine Gun · Strand · tiered, vendor 6-perk, obtainable · GFS 99 · pool 36 combos · 3 copies · 20 combos covered
- Pool col 2 (6): Built to Blast, Demolitionist, Hatchling, Slice, Transcendent Moment, Triple Tap
- Pool col 3 (6): Killing Tally, Lone Wolf, Meganeura, Rewind Rounds, Strategist, Tear
- Copy 1: [Built to Blast, Demolitionist, Hatchling] x [Killing Tally, Lone Wolf, Strategist] — 8 combos
- Copy 2: [Hatchling, Slice, Transcendent Moment] x [Killing Tally, Lone Wolf, Meganeura] — 6 combos
- Copy 3: [Slice, Transcendent Moment, Triple Tap] x [Lone Wolf, Rewind Rounds, Strategist] — 6 combos

### Reckless Endangerment
Shotgun · Kinetic · tiered, vendor 6-perk, obtainable · GFS 291 · pool 49 combos · 3 copies · 20 combos covered
- Pool col 2 (7): Barrel Constrictor, Bewildering Burst, Dual Loader, Grave Robber, Lone Wolf, Perpetual Motion, Steady Hands
- Pool col 3 (7): All-Star, Binary Orbit, Offhand Strike, Opening Shot, Snapshot Sights, Swashbuckler, Trench Barrel
- Copy 1: [Barrel Constrictor, Dual Loader, Perpetual Motion] x [All-Star, Offhand Strike, Snapshot Sights] — 9 combos
- Copy 2: [Bewildering Burst, Dual Loader, Steady Hands] x [Binary Orbit, Offhand Strike, Trench Barrel] — 8 combos
- Copy 3: [Barrel Constrictor, Bewildering Burst, Steady Hands] x [All-Star, Snapshot Sights, Swashbuckler] — 3 combos

### Salvager's Salvo
Grenade Launcher · Arc · tiered, vendor 6-perk, obtainable · GFS 180 · pool 36 combos · 3 copies · 20 combos covered
- Pool col 2 (6): Ambitious Assassin, Chain Reaction, Demolitionist, Light Touch, Trickle Charge, Unrelenting
- Pool col 3 (6): Collective Action, Gear Shift, Reaper's Tithe, Rolling Storm, Voltshot, Vorpal Weapon
- Copy 1: [Ambitious Assassin, Chain Reaction, Light Touch] x [Gear Shift, Reaper's Tithe, Voltshot] — 8 combos
- Copy 2: [Chain Reaction, Trickle Charge, Unrelenting] x [Reaper's Tithe, Rolling Storm, Vorpal Weapon] — 7 combos
- Copy 3: [Chain Reaction, Demolitionist, Light Touch] x [Collective Action, Reaper's Tithe, Vorpal Weapon] — 5 combos

### Sixth Sense
Hand Cannon · Strand · tiered, obtainable · GFS 337 · pool 49 combos · 3 copies · 20 combos covered
- Pool col 2 (7): Built to Blast, Demolitionist, Explosive Payload, Keep Away, Lucky Shot, Rapid Hit, Triple Tap
- Pool col 3 (7): Desperate Measures, Dragonfly, Eye of the Storm, Hatchling, Meganeura, Opening Shot, Tear
- Copy 1: [Built to Blast, Explosive Payload, Lucky Shot] x [Desperate Measures, Hatchling, Tear] — 9 combos
- Copy 2: [Built to Blast, Lucky Shot, Rapid Hit] x [Dragonfly, Meganeura, Tear] — 5 combos
- Copy 3: [Demolitionist, Keep Away, Triple Tap] x [Dragonfly, Hatchling, Tear] — 6 combos

### Tarnished Mettle
Scout Rifle · Arc · tiered, craftable, obtainable · GFS 737 · pool 63 combos · 3 copies · 20 combos covered
- Pool col 2 (8): Demolitionist, Empty Traits Socket, Fourth Time's the Charm, Killing Wind, Moving Target, Rapid Hit, Shoot to Loot, Steady Hands
- Pool col 3 (8): Dragonfly, Empty Traits Socket, Explosive Payload, Eye of the Storm, Focused Fury, Multikill Clip, Swashbuckler, Voltshot
- Copy 1: [Fourth Time's the Charm, Moving Target, Steady Hands] x [Explosive Payload, Eye of the Storm, Voltshot] — 7 combos
- Copy 2: [Killing Wind, Rapid Hit, Shoot to Loot] x [Focused Fury, Multikill Clip, Voltshot] — 9 combos
- Copy 3: [Empty Traits Socket, Killing Wind, Shoot to Loot] x [Dragonfly, Empty Traits Socket, Explosive Payload] — 4 combos

### Ulterior Observation
Machine Gun · Stasis · tiered, obtainable · GFS 239 · pool 49 combos · 3 copies · 20 combos covered
- Pool col 2 (7): Built to Blast, Demolitionist, Envious Arsenal, Feeding Frenzy, Headstone, Moving Target, Subsistence
- Pool col 3 (7): Adagio, Binary Orbit, Closing Time, Dragonfly, Dynamic Sway Reduction, Killing Tally, Rimestealer
- Copy 1: [Built to Blast, Envious Arsenal, Headstone] x [Adagio, Binary Orbit, Closing Time] — 7 combos
- Copy 2: [Demolitionist, Envious Arsenal, Feeding Frenzy] x [Dragonfly, Dynamic Sway Reduction, Rimestealer] — 8 combos
- Copy 3: [Headstone, Moving Target, Subsistence] x [Dragonfly, Killing Tally, Rimestealer] — 5 combos

### Unfall
Sidearm · Arc · tiered, vendor 6-perk, obtainable · GFS 102 · pool 36 combos · 3 copies · 20 combos covered
- Pool col 2 (6): Beacon Rounds, Disruption Break, Impulse Amplifier, Lead from Gold, Reverberation, Sleight of Hand
- Pool col 3 (6): Binary Orbit, Deconstruct, Jolting Feedback, Master of Arms, One for All, Rolling Storm
- Copy 1: [Beacon Rounds, Disruption Break, Sleight of Hand] x [Binary Orbit, Deconstruct, Jolting Feedback] — 7 combos
- Copy 2: [Disruption Break, Lead from Gold, Sleight of Hand] x [Jolting Feedback, One for All, Rolling Storm] — 7 combos
- Copy 3: [Lead from Gold, Reverberation, Sleight of Hand] x [Binary Orbit, Master of Arms, One for All] — 6 combos

### Aisha's Care
Pulse Rifle · Strand · tiered, obtainable · GFS 440 · pool 64 combos · 3 copies · 19 combos covered
- Pool col 2 (8): Encore, Gutshot Straight, Keep Away, Outlaw, Slice, To the Pain, Under Pressure, Zen Moment
- Pool col 3 (8): Collective Action, Desperado, Golden Tricorn, Golden Tricorn Enhanced, Hatchling, Headseeker, Kill Clip, Moving Target
- Copy 1: [Encore, Gutshot Straight, Zen Moment] x [Collective Action, Golden Tricorn, Golden Tricorn Enhanced] — 9 combos
- Copy 2: [Encore, Gutshot Straight, To the Pain] x [Desperado, Golden Tricorn Enhanced, Hatchling] — 5 combos
- Copy 3: [Outlaw, Slice, To the Pain] x [Golden Tricorn Enhanced, Hatchling, Headseeker] — 5 combos

### BxR-55 Battler
Pulse Rifle · Solar · tiered, craftable, obtainable · GFS 570 · pool 64 combos · 3 copies · 19 combos covered
- Pool col 2 (8): Auto-Loading Holster, Demolitionist, Heating Up, Killing Wind, Outlaw, Perpetual Motion, Pugilist, Snapshot Sights
- Pool col 3 (8): Adrenaline Junkie, Blunt Execution Rounds, Elemental Capacitor, Eye of the Storm, Gutshot Straight, Incandescent, Kill Clip, Rangefinder
- Copy 1: [Auto-Loading Holster, Demolitionist, Heating Up] x [Blunt Execution Rounds, Gutshot Straight, Incandescent] — 7 combos
- Copy 2: [Killing Wind, Outlaw, Perpetual Motion] x [Adrenaline Junkie, Blunt Execution Rounds, Gutshot Straight] — 7 combos
- Copy 3: [Pugilist, Snapshot Sights] x [Adrenaline Junkie, Blunt Execution Rounds, Gutshot Straight] — 5 combos

### Dead Weight
Shotgun · Arc · vendor 6-perk, obtainable · GFS 1,510 · pool 144 combos · 3 copies · 19 combos covered
- Pool col 2 (12): Auto-Loading Holster, Dual Loader, Ensemble, Feeding Frenzy, Field Prep, Grave Robber, Lead from Gold, Perpetual Motion, Steady Hands, Subsistence, Surplus, Well-Rounded
- Pool col 3 (12): Adrenaline Junkie, Demolitionist, Frenzy, Golden Tricorn, Harmony, One-Two Punch, Snapshot Sights, Surrounded, Swashbuckler, Trench Barrel, Turnabout, Vorpal Weapon
- Copy 1: [Dual Loader, Feeding Frenzy, Grave Robber] x [Adrenaline Junkie, Golden Tricorn, Turnabout] — 9 combos
- Copy 2: [Dual Loader, Feeding Frenzy, Well-Rounded] x [One-Two Punch, Surrounded, Trench Barrel] — 6 combos
- Copy 3: [Auto-Loading Holster, Dual Loader, Field Prep] x [Adrenaline Junkie, Surrounded, Vorpal Weapon] — 4 combos

### Deadlock
Shotgun · Stasis · tiered, vendor 6-perk, obtainable · GFS 444 · pool 49 combos · 3 copies · 19 combos covered
- Pool col 2 (7): Lone Wolf, Offhand Strike, Perpetual Motion, Quickdraw, Slideshot, Surplus, Threat Detector
- Pool col 3 (7): Closing Time, Fragile Focus, Master of Arms, One-Two Punch, Opening Shot, Snapshot Sights, Vorpal Weapon
- Copy 1: [Offhand Strike, Quickdraw, Surplus] x [Fragile Focus, Master of Arms, Snapshot Sights] — 9 combos
- Copy 2: [Offhand Strike, Perpetual Motion, Quickdraw] x [Closing Time, Master of Arms, One-Two Punch] — 6 combos
- Copy 3: [Lone Wolf, Slideshot] x [Closing Time, Master of Arms, One-Two Punch] — 4 combos

### Ecliptic Distaff
Glaive · Void · tiered, vendor 6-perk, obtainable · GFS 206 · pool 49 combos · 3 copies · 19 combos covered
- Pool col 2 (7): Disruption Break, Grave Robber, Immovable Object, Impulse Amplifier, Replenishing Aegis, Repulsor Brace, Tilting at Windmills
- Pool col 3 (7): Binary Orbit, Chaos Reshaped, Close to Melee, Desperate Measures, Destabilizing Rounds, Unstoppable Force, Withering Gaze
- Copy 1: [Disruption Break, Immovable Object, Tilting at Windmills] x [Binary Orbit, Desperate Measures, Withering Gaze] — 8 combos
- Copy 2: [Grave Robber, Impulse Amplifier, Replenishing Aegis] x [Binary Orbit, Close to Melee, Withering Gaze] — 8 combos
- Copy 3: [Disruption Break, Tilting at Windmills] x [Close to Melee, Destabilizing Rounds] — 3 combos

### Empty Vessel
Grenade Launcher · Solar · tiered, vendor 6-perk, obtainable · GFS 1,120 · pool 100 combos · 3 copies · 19 combos covered
- Pool col 2 (10): Ambitious Assassin, Auto-Loading Holster, Feeding Frenzy, Field Prep, Genesis, Lead from Gold, Pulse Monitor, Quickdraw, Surplus, Threat Detector
- Pool col 3 (10): Danger Zone, Demolitionist, Disruption Break, Multikill Clip, One for All, Snapshot Sights, Swashbuckler, Thresh, Unrelenting, Vorpal Weapon
- Copy 1: [Ambitious Assassin, Feeding Frenzy, Genesis] x [Danger Zone, Disruption Break, Thresh] — 6 combos
- Copy 2: [Lead from Gold, Surplus, Threat Detector] x [Danger Zone, Disruption Break, Multikill Clip] — 7 combos
- Copy 3: [Ambitious Assassin, Field Prep, Quickdraw] x [Danger Zone, Snapshot Sights, Unrelenting] — 6 combos

### Exalted Truth
Hand Cannon · Void · tiered, obtainable · GFS 416 · pool 49 combos · 3 copies · 19 combos covered
- Pool col 2 (7): Destabilizing Rounds, Keep Away, Lone Wolf, Moving Target, Slideshot, Withering Gaze, Zen Moment
- Pool col 3 (7): Demoralize, Eye of the Storm, Magnificent Howl, One for All, Opening Shot, Precision Instrument, Repulsor Brace
- Copy 1: [Destabilizing Rounds, Lone Wolf, Slideshot] x [Demoralize, Magnificent Howl, Repulsor Brace] — 7 combos
- Copy 2: [Destabilizing Rounds, Moving Target, Withering Gaze] x [Magnificent Howl, One for All, Opening Shot] — 6 combos
- Copy 3: [Keep Away, Moving Target, Zen Moment] x [Demoralize, Magnificent Howl, Repulsor Brace] — 6 combos

### Fortunate Star
Combat Bow · Void · tiered, obtainable · GFS 239 · pool 49 combos · 3 copies · 19 combos covered
- Pool col 2 (7): Archer's Tempo, Dragonfly, Impromptu Ammunition, Killing Wind, Repulsor Brace, Successful Warm-Up, Transcendent Moment
- Pool col 3 (7): Archer's Gambit, Demoralize, Destabilizing Rounds, Explosive Head, Eye of the Storm, Precision Instrument, Sword Logic
- Copy 1: [Impromptu Ammunition, Repulsor Brace, Transcendent Moment] x [Archer's Gambit, Demoralize, Destabilizing Rounds] — 7 combos
- Copy 2: [Killing Wind, Successful Warm-Up, Transcendent Moment] x [Archer's Gambit, Eye of the Storm, Sword Logic] — 7 combos
- Copy 3: [Archer's Tempo, Impromptu Ammunition, Transcendent Moment] x [Explosive Head, Eye of the Storm, Precision Instrument] — 5 combos

### Locus Locutus
Sniper Rifle · Stasis · tiered, craftable, obtainable · GFS 479 · pool 63 combos · 3 copies · 19 combos covered
- Pool col 2 (8): Discord, Empty Traits Socket, Ensemble, Keep Away, Overflow, Steady Hands, Surplus, Wellspring
- Pool col 3 (8): Box Breathing, Empty Traits Socket, Firing Line, Headstone, High Ground, Kill Clip, Opening Shot, Under-Over
- Copy 1: [Discord, Steady Hands, Wellspring] x [Box Breathing, High Ground, Under-Over] — 9 combos
- Copy 2: [Discord, Ensemble, Overflow] x [Box Breathing, Firing Line, High Ground] — 6 combos
- Copy 3: [Keep Away, Overflow, Steady Hands] x [Box Breathing, Firing Line, Under-Over] — 4 combos

### Main Ingredient
Fusion Rifle · Arc · tiered, vendor 6-perk, obtainable · GFS 479 · pool 55 combos · 3 copies · 19 combos covered
- Pool col 2 (8): Auto-Loading Holster, Firmly Planted, Hip-Fire Grip, Moving Target, Rampage, Snapshot Sights, Threat Detector, Under Pressure
- Pool col 3 (7): Backup Plan, High-Impact Reserves, Kill Clip, Quickdraw, Rampage, Rangefinder, Tap the Trigger
- Copy 1: [Auto-Loading Holster, Moving Target, Snapshot Sights] x [Backup Plan, High-Impact Reserves, Tap the Trigger] — 6 combos
- Copy 2: [Firmly Planted, Hip-Fire Grip, Under Pressure] x [Kill Clip, Quickdraw, Rangefinder] — 8 combos
- Copy 3: [Rampage, Snapshot Sights, Threat Detector] x [Kill Clip, Quickdraw, Tap the Trigger] — 5 combos

### Rake Angle
Glaive · Stasis · tiered, vendor 6-perk, obtainable · GFS 219 · pool 36 combos · 3 copies · 19 combos covered
- Pool col 2 (6): Impulse Amplifier, Lead from Gold, Overflow, Pugilist, Replenishing Aegis, Rimestealer
- Pool col 3 (6): Chill Clip, Close to Melee, Surrounded, Swashbuckler, Unstoppable Force, Vorpal Weapon
- Copy 1: [Overflow, Pugilist, Replenishing Aegis] x [Chill Clip, Surrounded, Swashbuckler] — 9 combos
- Copy 2: [Lead from Gold, Pugilist, Rimestealer] x [Close to Melee, Surrounded, Unstoppable Force] — 7 combos
- Copy 3: [Impulse Amplifier, Overflow] x [Close to Melee, Surrounded, Unstoppable Force] — 3 combos

### Solemn Lie
Hand Cannon · Arc · tiered, vendor 6-perk, obtainable · GFS 406 · pool 49 combos · 3 copies · 19 combos covered
- Pool col 2 (7): Keep Away, Killing Wind, Moving Target, Quickdraw, Rangefinder, Slideshot, Trickle Charge
- Pool col 3 (7): Elemental Capacitor, Eye of the Storm, Lone Wolf, Opening Shot, Rapid Hit, Rolling Storm, Snapshot Sights
- Copy 1: [Killing Wind, Quickdraw, Trickle Charge] x [Eye of the Storm, Lone Wolf, Rolling Storm] — 7 combos
- Copy 2: [Quickdraw, Slideshot, Trickle Charge] x [Elemental Capacitor, Rapid Hit, Snapshot Sights] — 8 combos
- Copy 3: [Keep Away, Slideshot, Trickle Charge] x [Eye of the Storm, Opening Shot, Rolling Storm] — 4 combos

### The Immortal
Submachine Gun · Strand · tiered, obtainable · GFS 310 · pool 49 combos · 3 copies · 19 combos covered
- Pool col 2 (7): Attrition Orbs, Dynamic Sway Reduction, Hatchling, Keep Away, Rangefinder, Slice, Threat Detector
- Pool col 3 (7): Demolitionist, Elemental Honing, Kill Clip, Lone Wolf, Master of Arms, Target Lock, Transcendent Moment
- Copy 1: [Dynamic Sway Reduction, Keep Away, Rangefinder] x [Elemental Honing, Lone Wolf, Transcendent Moment] — 9 combos
- Copy 2: [Dynamic Sway Reduction, Hatchling, Threat Detector] x [Lone Wolf, Master of Arms, Transcendent Moment] — 6 combos
- Copy 3: [Attrition Orbs, Hatchling, Keep Away] x [Elemental Honing, Lone Wolf, Master of Arms] — 4 combos

### Trendsetter
Auto Rifle · Arc · tiered, obtainable · GFS 191 · pool 36 combos · 3 copies · 19 combos covered
- Pool col 2 (6): Ambitious Assassin, Dynamic Sway Reduction, Light Touch, Outlaw, Supercharged Magazine, Trickle Charge
- Pool col 3 (6): Gear Shift, Jolting Feedback, Rampage, Rolling Storm, Tap the Trigger, Zen Moment
- Copy 1: [Dynamic Sway Reduction, Light Touch, Outlaw] x [Gear Shift, Jolting Feedback, Tap the Trigger] — 7 combos
- Copy 2: [Light Touch, Supercharged Magazine, Trickle Charge] x [Rampage, Tap the Trigger, Zen Moment] — 8 combos
- Copy 3: [Ambitious Assassin, Outlaw] x [Rolling Storm, Zen Moment] — 4 combos

### Frontier's Cry
Hand Cannon · Solar · tiered, obtainable · GFS 243 · pool 36 combos · 3 copies · 18 combos covered
- Pool col 2 (6): Adaptive Munitions, Compulsive Reloader, Rapid Hit, Stats for All, Steady Hands, Tunnel Vision
- Pool col 3 (6): Adagio, Eye of the Storm, Iron Grip, Iron Reach, Kill Clip, One for All
- Copy 1: [Adaptive Munitions, Compulsive Reloader, Steady Hands] x [Adagio, Iron Grip, Iron Reach] — 8 combos
- Copy 2: [Adaptive Munitions, Stats for All, Tunnel Vision] x [Iron Grip, Iron Reach, Kill Clip] — 7 combos
- Copy 3: [Rapid Hit, Stats for All, Tunnel Vision] x [Adagio, One for All] — 3 combos

### Giver's Blessing
Auto Rifle · Kinetic · tiered, obtainable · GFS 351 · pool 49 combos · 3 copies · 18 combos covered
- Pool col 2 (7): Demolitionist, Feeding Frenzy, Impromptu Ammunition, Moving Target, Rewind Rounds, Shoot to Loot, Transcendent Moment
- Pool col 3 (7): Adagio, Adrenaline Junkie, High Ground, Kinetic Tremors, Multikill Clip, One for All, Zen Moment
- Copy 1: [Impromptu Ammunition, Moving Target, Transcendent Moment] x [Adrenaline Junkie, High Ground, Multikill Clip] — 8 combos
- Copy 2: [Feeding Frenzy, Impromptu Ammunition, Transcendent Moment] x [Kinetic Tremors, One for All, Zen Moment] — 5 combos
- Copy 3: [Demolitionist, Rewind Rounds, Shoot to Loot] x [Adagio, Adrenaline Junkie, Kinetic Tremors] — 5 combos

### Gnawing Hunger
Auto Rifle · Void · tiered, vendor 6-perk, obtainable · GFS 378 · pool 49 combos · 3 copies · 18 combos covered
- Pool col 2 (7): Demolitionist, Enlightened Action, Overflow, Repulsor Brace, Subsistence, Tap the Trigger, Withering Gaze
- Pool col 3 (7): Destabilizing Rounds, Dynamic Sway Reduction, Master of Arms, Multikill Clip, Rampage, Swashbuckler, Target Lock
- Copy 1: [Enlightened Action, Overflow, Tap the Trigger] x [Dynamic Sway Reduction, Master of Arms, Swashbuckler] — 7 combos
- Copy 2: [Enlightened Action, Overflow, Withering Gaze] x [Master of Arms, Multikill Clip, Swashbuckler] — 5 combos
- Copy 3: [Repulsor Brace, Subsistence, Withering Gaze] x [Dynamic Sway Reduction, Rampage, Target Lock] — 6 combos

### Micromort
Rocket Launcher · Arc · tiered, obtainable · GFS 252 · pool 49 combos · 3 copies · 18 combos covered
- Pool col 2 (7): Clown Cartridge, Cluster Bomb, Envious Arsenal, Field Prep, Impulse Amplifier, Lead From Light, Reconstruction
- Pool col 3 (7): Bait and Switch, Binary Orbit, Bipod, Chain Reaction, Paracausal Affinity, Rolling Storm, Voltshot
- Copy 1: [Clown Cartridge, Cluster Bomb, Lead From Light] x [Binary Orbit, Paracausal Affinity, Rolling Storm] — 8 combos
- Copy 2: [Cluster Bomb, Envious Arsenal, Impulse Amplifier] x [Chain Reaction, Paracausal Affinity, Voltshot] — 7 combos
- Copy 3: [Field Prep] x [Binary Orbit, Paracausal Affinity, Rolling Storm] — 3 combos

### MIDA Mini-Tool
Submachine Gun · Solar · tiered, obtainable · GFS 283 · pool 49 combos · 3 copies · 18 combos covered
- Pool col 2 (7): Attrition Orbs, Discord, Envious Assassin, Heal Clip, Hip-Fire Grip, Loose Change, Perpetual Motion
- Pool col 3 (7): Aggregate Charge, Burning Ambition, Collective Pugilism, Frenzy, Incandescent, Master of Arms, Offhand Strike
- Copy 1: [Attrition Orbs, Discord, Hip-Fire Grip] x [Aggregate Charge, Burning Ambition, Collective Pugilism] — 7 combos
- Copy 2: [Attrition Orbs, Loose Change, Perpetual Motion] x [Aggregate Charge, Collective Pugilism, Offhand Strike] — 6 combos
- Copy 3: [Discord, Heal Clip, Loose Change] x [Burning Ambition, Master of Arms, Offhand Strike] — 5 combos

### Psi Aeterna IV
Pulse Rifle · Arc · tiered, vendor 6-perk, obtainable · GFS 190 · pool 36 combos · 3 copies · 18 combos covered
- Pool col 2 (6): Beacon Rounds, Blast Distributor, Eddy Current, Reverberation, Stats for All, Trickle Charge
- Pool col 3 (6): Adrenaline Junkie, Collective Pugilism, Elemental Honing, Jolting Feedback, One for All, Rolling Storm
- Copy 1: [Beacon Rounds, Blast Distributor, Trickle Charge] x [Adrenaline Junkie, Collective Pugilism, Jolting Feedback] — 9 combos
- Copy 2: [Eddy Current, Reverberation, Trickle Charge] x [Collective Pugilism, Elemental Honing, Jolting Feedback] — 6 combos
- Copy 3: [Stats for All] x [Elemental Honing, Jolting Feedback, Rolling Storm] — 3 combos

### Shayura's Wrath
Submachine Gun · Void · tiered, obtainable · GFS 660 · pool 64 combos · 3 copies · 18 combos covered
- Pool col 2 (8): Dynamic Sway Reduction, Heating Up, Hip-Fire Grip, Killing Wind, Moving Target, Perpetual Motion, Quickdraw, Tunnel Vision
- Pool col 3 (8): Adrenaline Junkie, Celerity, Elemental Capacitor, Golden Tricorn, Harmony, Kill Clip, Snapshot Sights, Tap the Trigger
- Copy 1: [Dynamic Sway Reduction, Heating Up, Moving Target] x [Celerity, Elemental Capacitor, Snapshot Sights] — 7 combos
- Copy 2: [Hip-Fire Grip, Perpetual Motion, Tunnel Vision] x [Adrenaline Junkie, Celerity, Tap the Trigger] — 7 combos
- Copy 3: [Heating Up, Quickdraw] x [Adrenaline Junkie, Celerity, Golden Tricorn] — 4 combos

### Shoreline Dissident
Sniper Rifle · Void · tiered, obtainable · GFS 212 · pool 49 combos · 3 copies · 18 combos covered
- Pool col 2 (7): Ambitious Assassin, Explosive Payload, Lone Wolf, Outlaw, Recycled Energy, Shoot to Loot, Triple Tap
- Pool col 3 (7): Adagio, Binary Orbit, Closing Time, Demoralize, Destabilizing Rounds, High Ground, Precision Instrument
- Copy 1: [Ambitious Assassin, Explosive Payload, Triple Tap] x [Adagio, Demoralize, Precision Instrument] — 9 combos
- Copy 2: [Explosive Payload, Recycled Energy, Triple Tap] x [Adagio, Binary Orbit, High Ground] — 4 combos
- Copy 3: [Ambitious Assassin, Explosive Payload, Recycled Energy] x [Closing Time, Destabilizing Rounds, Precision Instrument] — 5 combos

### The Inquisitor
Shotgun · Arc · tiered, obtainable · GFS 352 · pool 49 combos · 3 copies · 18 combos covered
- Pool col 2 (7): Envious Assassin, Lone Wolf, Loose Change, Offhand Strike, Perpetual Motion, Slideshot, Threat Detector
- Pool col 3 (7): Bait and Switch, Cascade Point, Closing Time, Fragile Focus, Opening Shot, Precision Instrument, Rolling Storm
- Copy 1: [Envious Assassin, Lone Wolf, Offhand Strike] x [Bait and Switch, Fragile Focus, Rolling Storm] — 6 combos
- Copy 2: [Loose Change, Perpetual Motion, Threat Detector] x [Bait and Switch, Fragile Focus, Opening Shot] — 6 combos
- Copy 3: [Perpetual Motion, Slideshot, Threat Detector] x [Cascade Point, Precision Instrument, Rolling Storm] — 6 combos

### Uzume RR4
Sniper Rifle · Solar · tiered, vendor 6-perk, obtainable · GFS 244 · pool 42 combos · 3 copies · 18 combos covered
- Pool col 2 (6): Attrition Orbs, Clown Cartridge, Discord, Fourth Time's the Charm, Lead from Gold, Snapshot Sights
- Pool col 3 (7): Deconstruct, Explosive Payload, Golden Tricorn, Golden Tricorn Enhanced, Incandescent, Precision Instrument, Vorpal Weapon
- Copy 1: [Discord, Lead from Gold, Snapshot Sights] x [Deconstruct, Explosive Payload, Golden Tricorn] — 9 combos
- Copy 2: [Clown Cartridge, Fourth Time's the Charm, Snapshot Sights] x [Deconstruct, Golden Tricorn Enhanced, Incandescent] — 6 combos
- Copy 3: [Attrition Orbs, Fourth Time's the Charm] x [Deconstruct, Incandescent, Precision Instrument] — 3 combos

### Veles-X
Pulse Rifle · Void · tiered, vendor 6-perk, obtainable · GFS 371 · pool 56 combos · 3 copies · 18 combos covered
- Pool col 2 (7): Demoralize, Lone Wolf, Rapid Hit, Repulsor Brace, To the Pain, Tunnel Vision, Wellspring
- Pool col 3 (8): Desperado, Destabilizing Rounds, Eye of the Storm, Firefly, Golden Tricorn, Golden Tricorn Enhanced, Kill Clip, Withering Gaze
- Copy 1: [Demoralize, Lone Wolf, Wellspring] x [Desperado, Golden Tricorn, Golden Tricorn Enhanced] — 7 combos
- Copy 2: [To the Pain, Tunnel Vision, Wellspring] x [Eye of the Storm, Firefly, Withering Gaze] — 9 combos
- Copy 3: [Lone Wolf, Repulsor Brace] x [Eye of the Storm, Kill Clip] — 2 combos

### Astral Horizon
Shotgun · Kinetic · tiered, obtainable · GFS 603 · pool 64 combos · 3 copies · 17 combos covered
- Pool col 2 (8): Auto-Loading Holster, Dual Loader, Field Prep, Lead from Gold, Pulse Monitor, Slideshot, Surplus, Threat Detector
- Pool col 3 (8): Celerity, Demolitionist, Elemental Capacitor, Killing Wind, One-Two Punch, Opening Shot, Swashbuckler, Trench Barrel
- Copy 1: [Auto-Loading Holster, Dual Loader, Lead from Gold] x [Celerity, Demolitionist, Elemental Capacitor] — 9 combos
- Copy 2: [Auto-Loading Holster, Pulse Monitor, Surplus] x [Celerity, Killing Wind, One-Two Punch] — 4 combos
- Copy 3: [Auto-Loading Holster, Slideshot, Threat Detector] x [Demolitionist, Killing Wind, Swashbuckler] — 4 combos

### Crowd Pleaser
Grenade Launcher · Void · vendor 6-perk, obtainable · GFS 771 · pool 81 combos · 3 copies · 17 combos covered
- Pool col 2 (9): Ambitious Assassin, Clown Cartridge, Field Prep, Genesis, Grave Robber, Killing Wind, Pulse Monitor, Surplus, Threat Detector
- Pool col 3 (9): Chain Reaction, Demolitionist, Elemental Capacitor, Moving Target, Quickdraw, Rampage, Snapshot Sights, Thresh, Unrelenting
- Copy 1: [Clown Cartridge, Genesis, Grave Robber] x [Moving Target, Quickdraw, Unrelenting] — 7 combos
- Copy 2: [Grave Robber, Killing Wind, Surplus] x [Chain Reaction, Elemental Capacitor, Quickdraw] — 6 combos
- Copy 3: [Pulse Monitor, Threat Detector] x [Elemental Capacitor, Quickdraw, Unrelenting] — 4 combos

### Hullabaloo
Grenade Launcher · Arc · tiered, obtainable · GFS 479 · pool 56 combos · 3 copies · 17 combos covered
- Pool col 2 (7): Demolitionist, Envious Arsenal, Envious Assassin, Field Prep, Impulse Amplifier, Stats for All, Voltshot
- Pool col 3 (8): Adrenaline Junkie, Cascade Point, Chain Reaction, Golden Tricorn, Golden Tricorn Enhanced, One for All, Rolling Storm, Strategist
- Copy 1: [Envious Arsenal, Field Prep, Voltshot] x [Adrenaline Junkie, Cascade Point, Strategist] — 8 combos
- Copy 2: [Envious Arsenal, Envious Assassin, Impulse Amplifier] x [Cascade Point, Rolling Storm, Strategist] — 4 combos
- Copy 3: [Envious Assassin, Stats for All, Voltshot] x [Golden Tricorn Enhanced, One for All, Strategist] — 5 combos

### Seraphine Haze
Submachine Gun · Stasis · tiered, vendor 6-perk, obtainable · GFS 270 · pool 36 combos · 3 copies · 17 combos covered
- Pool col 2 (6): Demolitionist, Dynamic Sway Reduction, Hip-Fire Grip, Lead From Light, Rimestealer, Subsistence
- Pool col 3 (6): Adrenaline Junkie, Attrition Orbs, Collective Pugilism, Crystalline Corpsebloom, Desperate Measures, Target Lock
- Copy 1: [Demolitionist, Lead From Light, Rimestealer] x [Adrenaline Junkie, Attrition Orbs, Collective Pugilism] — 9 combos
- Copy 2: [Dynamic Sway Reduction, Hip-Fire Grip, Lead From Light] x [Collective Pugilism, Crystalline Corpsebloom, Target Lock] — 5 combos
- Copy 3: [Hip-Fire Grip, Subsistence] x [Attrition Orbs, Collective Pugilism, Crystalline Corpsebloom] — 3 combos

### Solemn Remembrance
Hand Cannon · Stasis · tiered, vendor 6-perk, obtainable · GFS 304 · pool 49 combos · 3 copies · 17 combos covered
- Pool col 2 (7): Built to Blast, Headstone, Impromptu Ammunition, Lone Wolf, Moving Target, Slideshot, Zen Moment
- Pool col 3 (7): Eye of the Storm, Firefly, Keep Away, Magnificent Howl, Opening Shot, Precision Instrument, Rimestealer
- Copy 1: [Built to Blast, Headstone, Slideshot] x [Firefly, Magnificent Howl, Rimestealer] — 7 combos
- Copy 2: [Built to Blast, Impromptu Ammunition, Lone Wolf] x [Keep Away, Opening Shot, Rimestealer] — 6 combos
- Copy 3: [Built to Blast, Headstone, Zen Moment] x [Precision Instrument, Rimestealer] — 4 combos

### Taipan-4fr
Linear Fusion Rifle · Void · tiered, craftable, obtainable · GFS 557 · pool 63 combos · 3 copies · 17 combos covered
- Pool col 2 (8): Clown Cartridge, Compulsive Reloader, Empty Traits Socket, Ensemble, Field Prep, Fragile Focus, Genesis, Triple Tap
- Pool col 3 (8): Box Breathing, Empty Traits Socket, Firing Line, Focused Fury, Frenzy, Opening Shot, Repulsor Brace, Snapshot Sights
- Copy 1: [Clown Cartridge, Field Prep, Genesis] x [Box Breathing, Focused Fury, Repulsor Brace] — 7 combos
- Copy 2: [Compulsive Reloader, Fragile Focus, Triple Tap] x [Box Breathing, Firing Line, Repulsor Brace] — 4 combos
- Copy 3: [Clown Cartridge, Field Prep, Genesis] x [Empty Traits Socket, Firing Line, Snapshot Sights] — 6 combos

### The Title
Submachine Gun · Void · tiered, obtainable · GFS 348 · pool 49 combos · 3 copies · 17 combos covered
- Pool col 2 (7): Closing Time, Grave Robber, Perpetual Motion, Recycled Energy, Repulsor Brace, Threat Detector, To the Pain
- Pool col 3 (7): Demoralize, Destabilizing Rounds, Elemental Honing, Rangefinder, Surrounded, Swashbuckler, Under Pressure
- Copy 1: [Closing Time, Grave Robber, Perpetual Motion] x [Demoralize, Elemental Honing, Under Pressure] — 7 combos
- Copy 2: [Recycled Energy, Threat Detector, To the Pain] x [Rangefinder, Surrounded, Under Pressure] — 7 combos
- Copy 3: [Recycled Energy, Repulsor Brace, Threat Detector] x [Demoralize, Elemental Honing, Rangefinder] — 3 combos

### Folded Root
Rocket Launcher · Void · tiered, obtainable · GFS 145 · pool 36 combos · 3 copies · 16 combos covered
- Pool col 2 (6): Air Trigger, Ambitious Assassin, Cluster Bomb, Danger Zone, Lead From Light, Reverberation
- Pool col 3 (6): Bipod, Chain Reaction, Destabilizing Rounds, Frenzy, Lasting Impression, Multikill Clip
- Copy 1: [Air Trigger, Cluster Bomb, Lead From Light] x [Destabilizing Rounds, Lasting Impression, Multikill Clip] — 7 combos
- Copy 2: [Cluster Bomb, Lead From Light, Reverberation] x [Frenzy, Lasting Impression, Multikill Clip] — 5 combos
- Copy 3: [Ambitious Assassin, Danger Zone] x [Bipod, Destabilizing Rounds, Lasting Impression] — 4 combos

### Hammerhead
Machine Gun · Void · tiered, vendor 6-perk, obtainable · GFS 238 · pool 49 combos · 3 copies · 16 combos covered
- Pool col 2 (7): Destabilizing Rounds, Envious Assassin, Feeding Frenzy, Fourth Time's the Charm, Rampage, Rewind Rounds, Under-Over
- Pool col 3 (7): Desperate Measures, High-Impact Reserves, Killing Tally, Onslaught, Surrounded, Tap the Trigger, Target Lock
- Copy 1: [Destabilizing Rounds, Rampage, Under-Over] x [Desperate Measures, High-Impact Reserves, Onslaught] — 7 combos
- Copy 2: [Destabilizing Rounds, Rampage, Under-Over] x [Surrounded, Target Lock] — 5 combos
- Copy 3: [Envious Assassin, Fourth Time's the Charm, Rewind Rounds] x [Killing Tally, Onslaught, Surrounded] — 4 combos

### Kept Confidence
Hand Cannon · Strand · tiered, craftable, obtainable · GFS 469 · pool 63 combos · 3 copies · 16 combos covered
- Pool col 2 (8): Air Assault, Empty Traits Socket, Invisible Hand, Killing Wind, Loose Change, Quickdraw, Shot Swap, Stats for All
- Pool col 3 (8): Collective Action, Empty Traits Socket, Eye of the Storm, Gutshot Straight, Harmony, Multikill Clip, Pugilist, Thresh
- Copy 1: [Invisible Hand, Loose Change, Quickdraw] x [Eye of the Storm, Gutshot Straight, Pugilist] — 8 combos
- Copy 2: [Air Assault, Loose Change, Shot Swap] x [Collective Action, Eye of the Storm, Multikill Clip] — 6 combos
- Copy 3: [Air Assault, Quickdraw] x [Empty Traits Socket] — 2 combos

### Kindled Orchid
Hand Cannon · Void · tiered, vendor 6-perk, obtainable · GFS 336 · pool 49 combos · 3 copies · 16 combos covered
- Pool col 2 (7): Impromptu Ammunition, Keep Away, Kill Clip, Outlaw, Rangefinder, Repulsor Brace, Shoot to Loot
- Pool col 3 (7): Demoralize, Destabilizing Rounds, Explosive Payload, Eye of the Storm, Magnificent Howl, Master of Arms, Rampage
- Copy 1: [Kill Clip, Rangefinder, Shoot to Loot] x [Demoralize, Magnificent Howl, Master of Arms] — 8 combos
- Copy 2: [Impromptu Ammunition, Outlaw, Repulsor Brace] x [Demoralize, Magnificent Howl, Master of Arms] — 5 combos
- Copy 3: [Outlaw, Rangefinder, Repulsor Brace] x [Destabilizing Rounds, Eye of the Storm] — 3 combos

### Malediction
Hand Cannon · Kinetic · tiered, vendor 6-perk, obtainable · GFS 363 · pool 49 combos · 3 copies · 16 combos covered
- Pool col 2 (7): Discord, Enlightened Action, Keep Away, Moving Target, Shoot to Loot, Sleight of Hand, To the Pain
- Pool col 3 (7): All-Star, Explosive Payload, Eye of the Storm, Harmony, Kill Clip, Redirection, Tap the Trigger
- Copy 1: [Enlightened Action, Sleight of Hand, To the Pain] x [All-Star, Explosive Payload, Redirection] — 8 combos
- Copy 2: [Discord, Keep Away, Sleight of Hand] x [All-Star, Eye of the Storm, Kill Clip] — 6 combos
- Copy 3: [Moving Target] x [Harmony, Redirection] — 2 combos

### Multimach CCX
Submachine Gun · Kinetic · tiered, obtainable · GFS 259 · pool 36 combos · 3 copies · 16 combos covered
- Pool col 2 (6): Attrition Orbs, Dynamic Sway Reduction, Iron Gaze, Moving Target, Rangefinder, Under-Over
- Pool col 3 (6): Frenzy, Iron Reach, Kill Clip, Kinetic Tremors, Tap the Trigger, Target Lock
- Copy 1: [Attrition Orbs, Iron Gaze, Under-Over] x [Frenzy, Iron Reach, Kill Clip] — 9 combos
- Copy 2: [Iron Gaze, Rangefinder] x [Kinetic Tremors, Tap the Trigger, Target Lock] — 6 combos
- Copy 3: [Dynamic Sway Reduction] x [Iron Reach] — 1 combo

### Sola's Scar
Sword · Solar · tiered, obtainable · GFS 398 · pool 49 combos · 3 copies · 16 combos covered
- Pool col 2 (7): Demolitionist, Duelist's Trance, Eager Edge, Energy Transfer, Flash Counter, Relentless Strikes, Tireless Blade
- Pool col 3 (7): Assassin's Blade, Chain Reaction, Elemental Honing, Frenzy, Redirection, Vorpal Weapon, Whirlwind Blade
- Copy 1: [Eager Edge, Energy Transfer, Flash Counter] x [Chain Reaction, Elemental Honing, Redirection] — 7 combos
- Copy 2: [Eager Edge, Flash Counter, Tireless Blade] x [Chain Reaction, Frenzy, Vorpal Weapon] — 5 combos
- Copy 3: [Duelist's Trance, Energy Transfer, Relentless Strikes] x [Assassin's Blade, Elemental Honing, Frenzy] — 4 combos

### The Mountaintop
Grenade Launcher · Kinetic · tiered, obtainable · GFS 539 · pool 49 combos · 3 copies · 16 combos covered
- Pool col 2 (7): Ambitious Assassin, Auto-Loading Holster, Demolitionist, Impulse Amplifier, Lead from Gold, Overflow, Slickdraw
- Pool col 3 (7): Adrenaline Junkie, Frenzy, Harmony, One for All, Rampage, Recombination, Vorpal Weapon
- Copy 1: [Ambitious Assassin, Impulse Amplifier, Overflow] x [Harmony, Rampage, Recombination] — 6 combos
- Copy 2: [Auto-Loading Holster, Demolitionist, Slickdraw] x [One for All, Rampage, Recombination] — 7 combos
- Copy 3: [Lead from Gold, Slickdraw] x [Adrenaline Junkie, Harmony, Rampage] — 3 combos

### The Palindrome
Hand Cannon · Arc · tiered, vendor 6-perk, obtainable · GFS 170 · pool 36 combos · 3 copies · 16 combos covered
- Pool col 2 (6): Collective Demolition, Explosive Payload, Light Touch, Lone Wolf, Outlaw, Supercharged Magazine
- Pool col 3 (6): Magnificent Howl, Master of Arms, Opening Shot, Rolling Storm, Snapshot Sights, Voltshot
- Copy 1: [Collective Demolition, Explosive Payload, Supercharged Magazine] x [Master of Arms, Rolling Storm, Snapshot Sights] — 7 combos
- Copy 2: [Collective Demolition, Light Touch, Supercharged Magazine] x [Magnificent Howl, Opening Shot, Voltshot] — 7 combos
- Copy 3: [Light Touch, Lone Wolf] x [Snapshot Sights] — 2 combos

### Boomslang-4fr
Linear Fusion Rifle · Arc · tiered, vendor 6-perk, obtainable · GFS 173 · pool 36 combos · 3 copies · 15 combos covered
- Pool col 2 (6): Envious Arsenal, Field Prep, Heating Up, Rapid Hit, Rolling Storm, Transcendent Moment
- Pool col 3 (6): Binary Orbit, Jolting Feedback, Precision Instrument, Reservoir Burst, Successful Warm-Up, Vorpal Weapon
- Copy 1: [Heating Up, Rolling Storm, Transcendent Moment] x [Binary Orbit, Jolting Feedback, Precision Instrument] — 7 combos
- Copy 2: [Envious Arsenal, Rolling Storm, Transcendent Moment] x [Jolting Feedback, Reservoir Burst, Successful Warm-Up] — 6 combos
- Copy 3: [Heating Up, Rapid Hit] x [Successful Warm-Up, Vorpal Weapon] — 2 combos

### Convened Recurve
Combat Bow · Void · tiered, vendor 6-perk, obtainable · GFS 181 · pool 36 combos · 3 copies · 15 combos covered
- Pool col 2 (6): Built to Blast, Dimensional Shift, Moving Target, Repulsor Brace, Successful Warm-Up, Withering Gaze
- Pool col 3 (6): Adagio, Aggregate Charge, Butterfly, Demoralize, Destabilizing Rounds, Snapshot Sights
- Copy 1: [Built to Blast, Moving Target, Withering Gaze] x [Adagio, Aggregate Charge, Butterfly] — 8 combos
- Copy 2: [Built to Blast, Dimensional Shift, Successful Warm-Up] x [Adagio, Butterfly, Snapshot Sights] — 6 combos
- Copy 3: [Repulsor Brace] x [Snapshot Sights] — 1 combo

### Keen Thistle
Sniper Rifle · Solar · tiered, obtainable · GFS 425 · pool 49 combos · 3 copies · 15 combos covered
- Pool col 2 (7): Envious Arsenal, Incandescent, Lead from Gold, Lone Wolf, Snapshot Sights, Triple Tap, Under Pressure
- Pool col 3 (7): Bait and Switch, Closing Time, Elemental Honing, Fourth Time's the Charm, Moving Target, Opening Shot, Vorpal Weapon
- Copy 1: [Envious Arsenal, Incandescent, Under Pressure] x [Closing Time, Elemental Honing, Fourth Time's the Charm] — 7 combos
- Copy 2: [Envious Arsenal, Lead from Gold, Triple Tap] x [Bait and Switch, Fourth Time's the Charm, Moving Target] — 5 combos
- Copy 3: [Lead from Gold, Lone Wolf, Under Pressure] x [Bait and Switch, Elemental Honing, Fourth Time's the Charm] — 3 combos

### Mercurial Overreach
Sniper Rifle · Arc · tiered, vendor 6-perk, obtainable · GFS 461 · pool 49 combos · 3 copies · 14 combos covered
- Pool col 2 (7): Discord, Envious Assassin, Fragile Focus, Keep Away, Lone Wolf, No Distractions, Snapshot Sights
- Pool col 3 (7): Bait and Switch, Box Breathing, Closing Time, Elemental Capacitor, Moving Target, Opening Shot, Vorpal Weapon
- Copy 1: [Discord, Envious Assassin, Fragile Focus] x [Bait and Switch, Box Breathing, Closing Time] — 6 combos
- Copy 2: [Discord, Keep Away, Lone Wolf] x [Bait and Switch, Elemental Capacitor, Vorpal Weapon] — 6 combos
- Copy 3: [Snapshot Sights] x [Closing Time, Vorpal Weapon] — 2 combos

### Pardon Our Dust
Grenade Launcher · Kinetic · tiered, craftable, obtainable · GFS 695 · pool 64 combos · 3 copies · 14 combos covered
- Pool col 2 (8): Ambitious Assassin, Auto-Loading Holster, Ensemble, Killing Wind, Perpetual Motion, Pulse Monitor, Stats for All, Steady Hands
- Pool col 3 (8): Adrenaline Junkie, Danger Zone, Demolitionist, Pugilist, Rampage, Turnabout, Vorpal Weapon, Wellspring
- Copy 1: [Ensemble, Killing Wind, Steady Hands] x [Danger Zone, Demolitionist, Pugilist] — 6 combos
- Copy 2: [Ambitious Assassin, Auto-Loading Holster, Pulse Monitor] x [Danger Zone, Pugilist, Turnabout] — 6 combos
- Copy 3: [Pulse Monitor, Stats for All] x [Danger Zone, Vorpal Weapon] — 2 combos

### Sightline Survey
Hand Cannon · Arc · tiered, craftable, obtainable · GFS 517 · pool 63 combos · 3 copies · 14 combos covered
- Pool col 2 (8): Air Trigger, Empty Traits Socket, Enlightened Action, Fragile Focus, Keep Away, Strategist, To the Pain, Triple Tap
- Pool col 3 (8): Desperate Measures, Empty Traits Socket, Encore, Eye of the Storm, Kill Clip, Opening Shot, Precision Instrument, Voltshot
- Copy 1: [Air Trigger, Enlightened Action, Fragile Focus] x [Encore, Kill Clip, Voltshot] — 5 combos
- Copy 2: [Air Trigger, Enlightened Action, Triple Tap] x [Desperate Measures, Encore, Opening Shot] — 5 combos
- Copy 3: [Enlightened Action, Fragile Focus, To the Pain] x [Empty Traits Socket, Opening Shot] — 4 combos

### Null Composure
Fusion Rifle · Void · tiered, vendor 6-perk, obtainable · GFS 138 · pool 36 combos · 3 copies · 13 combos covered
- Pool col 2 (6): Envious Arsenal, Feeding Frenzy, Heating Up, Overflow, Reconstruction, Successful Warm-Up
- Pool col 3 (6): Closing Time, Controlled Burst, Elemental Honing, High-Impact Reserves, Master of Arms, Reservoir Burst
- Copy 1: [Envious Arsenal, Heating Up, Successful Warm-Up] x [Closing Time, Controlled Burst, Master of Arms] — 6 combos
- Copy 2: [Feeding Frenzy, Heating Up, Reconstruction] x [Elemental Honing, Master of Arms, Reservoir Burst] — 5 combos
- Copy 3: [Overflow, Successful Warm-Up] x [Elemental Honing, High-Impact Reserves] — 2 combos

### Bottom Dollar
Hand Cannon · Void · tiered, vendor 6-perk, obtainable · GFS 1,468 · pool 144 combos · 3 copies · 12 combos covered
- Pool col 2 (12): Feeding Frenzy, Fourth Time's the Charm, Hip-Fire Grip, Killing Wind, Outlaw, Pulse Monitor, Quickdraw, Rangefinder, Rapid Hit, Slideshot, Subsistence, Surplus
- Pool col 3 (12): Demolitionist, Disruption Break, Dragonfly, Explosive Payload, Eye of the Storm, High-Impact Reserves, Multikill Clip, Opening Shot, Rampage, Thresh, Unrelenting, Wellspring
- Copy 1: [Feeding Frenzy, Outlaw, Rapid Hit] x [Disruption Break, Explosive Payload, Unrelenting] — 5 combos
- Copy 2: [Killing Wind, Pulse Monitor, Quickdraw] x [Disruption Break, Explosive Payload, High-Impact Reserves] — 5 combos
- Copy 3: [Killing Wind, Rangefinder] x [Opening Shot] — 2 combos

### The Time-Worn Spire
Pulse Rifle · Kinetic · tiered, obtainable · GFS 290 · pool 36 combos · 2 copies · 18 combos covered
- Pool col 2 (6): Feeding Frenzy, Moving Target, Quickdraw, Slideways, Subsistence, Under Pressure
- Pool col 3 (6): Iron Gaze, Iron Grip, Iron Reach, One for All, Rampage, Vorpal Weapon
- Copy 1: [Moving Target, Quickdraw, Slideways] x [Iron Gaze, Iron Grip, Iron Reach] — 9 combos
- Copy 2: [Feeding Frenzy, Subsistence, Under Pressure] x [Iron Gaze, Iron Grip, Iron Reach] — 9 combos

### Zephyr
Sword · Stasis · tiered, obtainable · GFS 424 · pool 56 combos · 2 copies · 18 combos covered
- Pool col 2 (8): Duelist's Trance, Osmosis, Relentless Strikes, Thresh, Tireless Blade, Turnabout, Unrelenting, Wellspring
- Pool col 3 (7): Assassin's Blade, Chain Reaction, Cold Steel, En Garde, Surrounded, Vorpal Weapon, Whirlwind Blade
- Copy 1: [Osmosis, Turnabout, Wellspring] x [Assassin's Blade, Chain Reaction, Cold Steel] — 9 combos
- Copy 2: [Osmosis, Thresh, Turnabout] x [En Garde, Surrounded, Whirlwind Blade] — 9 combos

### Aurvandil FR6
Fusion Rifle · Stasis · tiered, obtainable · GFS 383 · pool 42 combos · 2 copies · 17 combos covered
- Pool col 2 (6): Firmly Planted, Hip-Fire Grip, Reconstruction, Slideways, Stats for All, Subsistence
- Pool col 3 (7): Chill Clip, Demolitionist, Elemental Capacitor, Golden Tricorn, Golden Tricorn Enhanced, One for All, Swashbuckler
- Copy 1: [Firmly Planted, Hip-Fire Grip, Reconstruction] x [Chill Clip, Golden Tricorn, Golden Tricorn Enhanced] — 9 combos
- Copy 2: [Reconstruction, Stats for All, Subsistence] x [Chill Clip, Demolitionist, Elemental Capacitor] — 8 combos

### Forgiveness
Sidearm · Arc · tiered, obtainable · GFS 378 · pool 49 combos · 2 copies · 17 combos covered
- Pool col 2 (7): Demolitionist, Lone Wolf, Offhand Strike, Proximity Power, Tap the Trigger, Voltshot, Zen Moment
- Pool col 3 (7): Adrenaline Junkie, Desperate Measures, Headseeker, Kill Clip, Loose Change, Precision Instrument, Surrounded
- Copy 1: [Lone Wolf, Proximity Power, Voltshot] x [Desperate Measures, Headseeker, Loose Change] — 9 combos
- Copy 2: [Proximity Power, Tap the Trigger, Voltshot] x [Adrenaline Junkie, Precision Instrument, Surrounded] — 8 combos

### Steelfeather Repeater
Auto Rifle · Kinetic · tiered, obtainable · GFS 257 · pool 36 combos · 2 copies · 17 combos covered
- Pool col 2 (6): Bewildering Burst, Firmly Planted, Grave Robber, Proximity Power, Slideways, Subsistence
- Pool col 3 (6): All-Star, Ancillary Ordinance, Multikill Clip, Surrounded, Swashbuckler, Vorpal Weapon
- Copy 1: [Firmly Planted, Proximity Power, Slideways] x [All-Star, Ancillary Ordinance, Multikill Clip] — 9 combos
- Copy 2: [Bewildering Burst, Grave Robber, Subsistence] x [All-Star, Ancillary Ordinance, Surrounded] — 8 combos

### Taraxippos
Scout Rifle · Strand · tiered, obtainable · GFS 379 · pool 49 combos · 2 copies · 17 combos covered
- Pool col 2 (7): Closing Time, Enlightened Action, Fourth Time's the Charm, Keep Away, Lone Wolf, Perfect Float, Zen Moment
- Pool col 3 (7): Explosive Payload, Eye of the Storm, Hatchling, High Ground, Kill Clip, Precision Instrument, Tear
- Copy 1: [Closing Time, Enlightened Action, Fourth Time's the Charm] x [Hatchling, High Ground, Tear] — 9 combos
- Copy 2: [Keep Away, Perfect Float, Zen Moment] x [Hatchling, High Ground, Tear] — 8 combos

### The Keening
Sidearm · Arc · tiered, vendor 6-perk, obtainable · GFS 407 · pool 49 combos · 2 copies · 17 combos covered
- Pool col 2 (7): Killing Wind, Lone Wolf, Moving Target, Rapid Hit, Slideshot, Subsistence, Voltshot
- Pool col 3 (7): Dragonfly, High-Impact Reserves, Jolting Feedback, Multikill Clip, Snapshot Sights, Vorpal Weapon, Zen Moment
- Copy 1: [Killing Wind, Lone Wolf, Slideshot] x [Dragonfly, Jolting Feedback, Zen Moment] — 9 combos
- Copy 2: [Slideshot, Subsistence, Voltshot] x [High-Impact Reserves, Multikill Clip, Vorpal Weapon] — 8 combos

### Triple Laureate
Hand Cannon · Stasis · tiered, obtainable · GFS 288 · pool 49 combos · 2 copies · 17 combos covered
- Pool col 2 (7): Ambitious Assassin, Crystalline Corpsebloom, Feeding Frenzy, Grave Robber, Rangefinder, Slideshot, Subsistence
- Pool col 3 (7): Chaos Reshaped, Kill Clip, Master of Arms, One-Two Punch, Opening Shot, Pugilist, Trench Barrel
- Copy 1: [Ambitious Assassin, Crystalline Corpsebloom, Rangefinder] x [Chaos Reshaped, One-Two Punch, Trench Barrel] — 9 combos
- Copy 2: [Ambitious Assassin, Crystalline Corpsebloom, Grave Robber] x [Kill Clip, Master of Arms, Pugilist] — 8 combos

### Acosmic
Grenade Launcher · Void · tiered, obtainable · GFS 264 · pool 49 combos · 2 copies · 16 combos covered
- Pool col 2 (7): Air Trigger, Clown Cartridge, Enlightened Action, Impulse Amplifier, Reverberation, Slickdraw, Withering Gaze
- Pool col 3 (7): Bait and Switch, Cascade Point, Chain Reaction, Deconstruct, Destabilizing Rounds, Explosive Light, Frenzy
- Copy 1: [Enlightened Action, Slickdraw, Withering Gaze] x [Cascade Point, Chain Reaction, Explosive Light] — 9 combos
- Copy 2: [Air Trigger, Reverberation, Withering Gaze] x [Cascade Point, Deconstruct, Explosive Light] — 7 combos

### Afterlight (Adept)
Fusion Rifle · Void · adept, obtainable · GFS 317 · pool 49 combos · 2 copies · 16 combos covered
- Pool col 2 (7): Ambitious Assassin, Discord, Grave Robber, Lead from Gold, Offhand Strike, Pugilist, Under Pressure
- Pool col 3 (7): Adagio, Cornered, Destabilizing Rounds, Reservoir Burst, Successful Warm-Up, Swashbuckler, Vorpal Weapon
- Copy 1: [Ambitious Assassin, Discord, Grave Robber] x [Cornered, Reservoir Burst, Successful Warm-Up] — 9 combos
- Copy 2: [Lead from Gold, Offhand Strike, Pugilist] x [Cornered, Destabilizing Rounds, Reservoir Burst] — 7 combos

### Aureus Neutralizer
Hand Cannon · Kinetic · tiered, obtainable · GFS 275 · pool 49 combos · 2 copies · 16 combos covered
- Pool col 2 (7): Barrel Constrictor, Grave Robber, Lone Wolf, Proximity Power, Threat Detector, Threat Remover, Vorpal Weapon
- Pool col 3 (7): Adagio, Cascade Point, Closing Time, Desperate Measures, One-Two Punch, Opening Shot, Trench Barrel
- Copy 1: [Barrel Constrictor, Proximity Power, Threat Remover] x [Adagio, Cascade Point, Closing Time] — 9 combos
- Copy 2: [Grave Robber, Lone Wolf, Vorpal Weapon] x [Cascade Point, Closing Time, Trench Barrel] — 7 combos

### Blast Furnace
Pulse Rifle · Kinetic · tiered, vendor 6-perk, obtainable · GFS 411 · pool 49 combos · 2 copies · 16 combos covered
- Pool col 2 (7): Headseeker, Keep Away, Kinetic Tremors, Perpetual Motion, Shoot to Loot, Snapshot Sights, Zen Moment
- Pool col 3 (7): Desperate Measures, Firefly, Frenzy, Kill Clip, One for All, Rampage, Rapid Hit
- Copy 1: [Headseeker, Kinetic Tremors, Snapshot Sights] x [Desperate Measures, Firefly, One for All] — 9 combos
- Copy 2: [Keep Away, Kinetic Tremors, Zen Moment] x [Kill Clip, Rampage, Rapid Hit] — 7 combos

### Death Adder
Submachine Gun · Solar · tiered, obtainable · GFS 241 · pool 36 combos · 2 copies · 16 combos covered
- Pool col 2 (6): Auto-Loading Holster, Dynamic Sway Reduction, Feeding Frenzy, Hip-Fire Grip, Mulligan, Subsistence
- Pool col 3 (6): Disruption Break, Dragonfly, Eye of the Storm, Moving Target, Quickdraw, Rangefinder
- Copy 1: [Dynamic Sway Reduction, Mulligan, Subsistence] x [Disruption Break, Dragonfly, Quickdraw] — 9 combos
- Copy 2: [Dynamic Sway Reduction, Feeding Frenzy, Mulligan] x [Eye of the Storm, Moving Target, Rangefinder] — 7 combos

### Different Times
Pulse Rifle · Strand · tiered, craftable, obtainable · GFS 693 · pool 71 combos · 2 copies · 16 combos covered
- Pool col 2 (8): Empty Traits Socket, Heating Up, Invisible Hand, Moving Target, Offhand Strike, Outlaw, Stats for All, Subsistence
- Pool col 3 (9): Adrenaline Junkie, Collective Action, Empty Traits Socket, Focused Fury, Golden Tricorn, Golden Tricorn Enhanced, Hatchling, Headseeker, Multikill Clip
- Copy 1: [Heating Up, Invisible Hand, Stats for All] x [Adrenaline Junkie, Hatchling, Headseeker] — 8 combos
- Copy 2: [Heating Up, Invisible Hand, Offhand Strike] x [Collective Action, Empty Traits Socket, Multikill Clip] — 8 combos

### Drang
Sidearm · Solar · tiered, craftable, obtainable · GFS 260 · pool 49 combos · 2 copies · 16 combos covered
- Pool col 2 (7): Collective Pugilism, Discord, Disruption Break, Envious Assassin, Heal Clip, Loose Change, Moving Target
- Pool col 3 (7): Aggregate Charge, Binary Orbit, Burning Ambition, Eye of the Storm, Frenzy, Incandescent, Master of Arms
- Copy 1: [Collective Pugilism, Disruption Break, Heal Clip] x [Aggregate Charge, Binary Orbit, Eye of the Storm] — 8 combos
- Copy 2: [Collective Pugilism, Disruption Break, Envious Assassin] x [Frenzy, Incandescent, Master of Arms] — 8 combos

### Haliaetus
Rocket Launcher · Strand · tiered, obtainable · GFS 175 · pool 49 combos · 2 copies · 16 combos covered
- Pool col 2 (7): Auto-Loading Holster, Blast Distributor, Cluster Bomb, Envious Assassin, Grave Robber, Impulse Amplifier, Quickdraw
- Pool col 3 (7): Aggregate Charge, Binary Orbit, Bipod, Collective Pugilism, Elemental Honing, Hatchling, Reaper's Tithe
- Copy 1: [Auto-Loading Holster, Cluster Bomb, Quickdraw] x [Binary Orbit, Collective Pugilism, Reaper's Tithe] — 9 combos
- Copy 2: [Cluster Bomb, Envious Assassin, Grave Robber] x [Aggregate Charge, Collective Pugilism, Reaper's Tithe] — 7 combos

### Jurisprudent
Scout Rifle · Stasis · tiered, obtainable · GFS 274 · pool 49 combos · 2 copies · 16 combos covered
- Pool col 2 (7): Built to Blast, Enlightened Action, Lone Wolf, Rapid Hit, Recycled Energy, Rimestealer, Tunnel Vision
- Pool col 3 (7): Adrenaline Junkie, Binary Orbit, Explosive Payload, Focused Fury, Harmony, Headstone, No Distractions
- Copy 1: [Built to Blast, Enlightened Action, Recycled Energy] x [Focused Fury, Harmony, No Distractions] — 9 combos
- Copy 2: [Built to Blast, Recycled Energy, Tunnel Vision] x [Explosive Payload, Headstone, No Distractions] — 7 combos

### Mindbender's Ambition
Shotgun · Solar · tiered, vendor 6-perk, obtainable · GFS 242 · pool 36 combos · 2 copies · 16 combos covered
- Pool col 2 (6): Auto-Loading Holster, Lead from Gold, Pugilist, Slideways, Snapshot Sights, Threat Detector
- Pool col 3 (6): Fragile Focus, Incandescent, One-Two Punch, Steady Hands, Swashbuckler, Well-Rounded
- Copy 1: [Auto-Loading Holster, Lead from Gold, Snapshot Sights] x [One-Two Punch, Steady Hands, Well-Rounded] — 9 combos
- Copy 2: [Auto-Loading Holster, Slideways, Threat Detector] x [Fragile Focus, Steady Hands, Well-Rounded] — 7 combos

### Returned Memory
Sidearm · Solar · tiered, vendor 6-perk, obtainable · GFS 167 · pool 36 combos · 2 copies · 16 combos covered
- Pool col 2 (6): Beacon Rounds, Blast Distributor, Heal Clip, Impromptu Ammunition, Impulse Amplifier, Lead from Gold
- Pool col 3 (6): Adagio, Burning Ambition, Desperate Measures, Incandescent, One for All, Redirection
- Copy 1: [Beacon Rounds, Blast Distributor, Impulse Amplifier] x [Adagio, Burning Ambition, Redirection] — 9 combos
- Copy 2: [Blast Distributor, Heal Clip, Lead from Gold] x [Desperate Measures, Incandescent, Redirection] — 7 combos

### Sorrow's Verse
Auto Rifle · Arc · tiered, vendor 6-perk, obtainable · GFS 476 · pool 49 combos · 2 copies · 16 combos covered
- Pool col 2 (7): Dynamic Sway Reduction, Feeding Frenzy, Recycled Energy, Rewind Rounds, Subsistence, Tap the Trigger, Zen Moment
- Pool col 3 (7): Demolitionist, Frenzy, Kill Clip, Multikill Clip, Rampage, Target Lock, Voltshot
- Copy 1: [Recycled Energy, Rewind Rounds, Tap the Trigger] x [Demolitionist, Frenzy, Multikill Clip] — 9 combos
- Copy 2: [Dynamic Sway Reduction, Recycled Energy, Subsistence] x [Kill Clip, Rampage, Voltshot] — 7 combos

### The Ringing Nail
Auto Rifle · Solar · tiered, vendor 6-perk, obtainable · GFS 235 · pool 49 combos · 2 copies · 16 combos covered
- Pool col 2 (7): Dragonfly, Heal Clip, Impromptu Ammunition, Incandescent, Keep Away, Rewind Rounds, Zen Moment
- Pool col 3 (7): Burning Ambition, Disruption Break, Firefly, Onslaught, Rampage, Sword Logic, Target Lock
- Copy 1: [Dragonfly, Impromptu Ammunition, Keep Away] x [Burning Ambition, Disruption Break, Onslaught] — 9 combos
- Copy 2: [Heal Clip, Incandescent, Rewind Rounds] x [Disruption Break, Rampage, Sword Logic] — 7 combos

### The Summoner
Auto Rifle · Solar · tiered, obtainable · GFS 516 · pool 56 combos · 2 copies · 16 combos covered
- Pool col 2 (7): Dynamic Sway Reduction, Elemental Capacitor, Heal Clip, Overflow, Perpetual Motion, Subsistence, Zen Moment
- Pool col 3 (8): Golden Tricorn, Golden Tricorn Enhanced, Incandescent, Kill Clip, Onslaught, Rampage, Tap the Trigger, Target Lock
- Copy 1: [Elemental Capacitor, Heal Clip, Overflow] x [Onslaught, Rampage, Tap the Trigger] — 9 combos
- Copy 2: [Dynamic Sway Reduction, Elemental Capacitor, Overflow] x [Golden Tricorn, Golden Tricorn Enhanced, Incandescent] — 7 combos

### Theodolite
Grenade Launcher · Arc · tiered, vendor 6-perk, obtainable · GFS 153 · pool 36 combos · 2 copies · 16 combos covered
- Pool col 2 (6): Blast Distributor, Danger Zone, Eddy Current, Reconstruction, Reverberation, Transcendent Moment
- Pool col 3 (6): Binary Orbit, Elemental Honing, Frenzy, Reaper's Tithe, Rolling Storm, Voltshot
- Copy 1: [Blast Distributor, Danger Zone, Eddy Current] x [Binary Orbit, Reaper's Tithe, Voltshot] — 9 combos
- Copy 2: [Blast Distributor, Reverberation, Transcendent Moment] x [Reaper's Tithe, Rolling Storm, Voltshot] — 7 combos

### Tinasha's Mastery
Sidearm · Stasis · tiered, obtainable · GFS 248 · pool 49 combos · 2 copies · 16 combos covered
- Pool col 2 (7): Air Trigger, Deconstruct, Enlightened Action, Impulse Amplifier, Loose Change, Offhand Strike, Reverberation
- Pool col 3 (7): Adagio, Bait and Switch, Chill Clip, Desperate Measures, Frenzy, One for All, Surrounded
- Copy 1: [Air Trigger, Deconstruct, Reverberation] x [Adagio, Chill Clip, Desperate Measures] — 9 combos
- Copy 2: [Enlightened Action, Loose Change, Offhand Strike] x [Adagio, Chill Clip, Surrounded] — 7 combos

### Whatchamacallit
Submachine Gun · Arc · tiered, vendor 6-perk, obtainable · GFS 161 · pool 36 combos · 2 copies · 16 combos covered
- Pool col 2 (6): Collective Pugilism, Enlightened Action, Headseeker, Keep Away, Light Touch, Stats for All
- Pool col 3 (6): Dragonfly, Frenzy, Gear Shift, Jolting Feedback, Rangefinder, Sword Logic
- Copy 1: [Collective Pugilism, Headseeker, Light Touch] x [Dragonfly, Gear Shift, Rangefinder] — 9 combos
- Copy 2: [Collective Pugilism, Headseeker, Light Touch] x [Frenzy, Jolting Feedback, Sword Logic] — 7 combos

### Agape
Hand Cannon · Solar · tiered, obtainable · GFS 294 · pool 49 combos · 2 copies · 15 combos covered
- Pool col 2 (7): Encore, Heal Clip, Moving Target, Outlaw, Pugilist, Rewind Rounds, Snapshot Sights
- Pool col 3 (7): Burning Ambition, Firefly, Fragile Focus, Incandescent, Master of Arms, Precision Instrument, Vorpal Weapon
- Copy 1: [Encore, Moving Target, Snapshot Sights] x [Burning Ambition, Firefly, Master of Arms] — 8 combos
- Copy 2: [Heal Clip, Outlaw, Rewind Rounds] x [Burning Ambition, Firefly, Fragile Focus] — 7 combos

### Everburning Glitz
Auto Rifle · Kinetic · tiered, obtainable · GFS 283 · pool 49 combos · 2 copies · 15 combos covered
- Pool col 2 (7): Attrition Orbs, Bewildering Burst, Dynamic Sway Reduction, Lone Wolf, Subsistence, To the Pain, Transcendent Moment
- Pool col 3 (7): Ancillary Ordinance, Elemental Honing, Eye of the Storm, Kinetic Tremors, One for All, Tap the Trigger, Zen Moment
- Copy 1: [Attrition Orbs, Dynamic Sway Reduction, To the Pain] x [Ancillary Ordinance, Tap the Trigger, Zen Moment] — 8 combos
- Copy 2: [Bewildering Burst, Subsistence, Transcendent Moment] x [Ancillary Ordinance, Tap the Trigger, Zen Moment] — 7 combos

### Last Foray
Sniper Rifle · Solar · tiered, obtainable · GFS 356 · pool 49 combos · 2 copies · 15 combos covered
- Pool col 2 (7): Discord, Envious Assassin, Heal Clip, Keep Away, Moving Target, Quickdraw, Rewind Rounds
- Pool col 3 (7): Bait and Switch, Cascade Point, Explosive Payload, Incandescent, Precision Instrument, Snapshot Sights, Triple Tap
- Copy 1: [Envious Assassin, Heal Clip, Moving Target] x [Bait and Switch, Snapshot Sights, Triple Tap] — 9 combos
- Copy 2: [Keep Away, Quickdraw, Rewind Rounds] x [Cascade Point, Incandescent, Snapshot Sights] — 6 combos

### Oxygen SR3
Scout Rifle · Solar · tiered, vendor 6-perk, obtainable · GFS 201 · pool 36 combos · 2 copies · 15 combos covered
- Pool col 2 (6): Heal Clip, Pugilist, Rapid Hit, Shoot to Loot, Stats for All, To the Pain
- Pool col 3 (6): Binary Orbit, Box Breathing, Burning Ambition, Collective Pugilism, Meganeura, One for All
- Copy 1: [Pugilist, Shoot to Loot, To the Pain] x [Box Breathing, Burning Ambition, Collective Pugilism] — 9 combos
- Copy 2: [Rapid Hit, Stats for All, To the Pain] x [Box Breathing, Collective Pugilism, Meganeura] — 6 combos

### Patron of Lost Causes
Scout Rifle · Kinetic · tiered, obtainable · GFS 234 · pool 36 combos · 2 copies · 15 combos covered
- Pool col 2 (6): Field Prep, Full Auto Trigger System, Grave Robber, Mulligan, Pulse Monitor, Rapid Hit
- Pool col 3 (6): Elemental Capacitor, Explosive Payload, Opening Shot, Osmosis, Under Pressure, Vorpal Weapon
- Copy 1: [Field Prep, Full Auto Trigger System, Mulligan] x [Explosive Payload, Osmosis, Under Pressure] — 9 combos
- Copy 2: [Mulligan, Pulse Monitor, Rapid Hit] x [Elemental Capacitor, Explosive Payload, Under Pressure] — 6 combos

### Precipial
Shotgun · Void · tiered, obtainable · GFS 398 · pool 49 combos · 2 copies · 15 combos covered
- Pool col 2 (7): Lone Wolf, Moving Target, One-Two Punch, Proximity Power, Reconstruction, Repulsor Brace, Threat Detector
- Pool col 3 (7): Binary Orbit, Destabilizing Rounds, Discord, Opening Shot, Slideshot, Swashbuckler, Vorpal Weapon
- Copy 1: [One-Two Punch, Reconstruction, Repulsor Brace] x [Binary Orbit, Destabilizing Rounds, Discord] — 8 combos
- Copy 2: [Lone Wolf, Proximity Power, Reconstruction] x [Discord, Opening Shot, Slideshot] — 7 combos

### Romantic Death
Grenade Launcher · Void · tiered, obtainable · GFS 296 · pool 36 combos · 2 copies · 15 combos covered
- Pool col 2 (6): Feeding Frenzy, Proximity Power, Repulsor Brace, Reverberation, Stats for All, Threat Detector
- Pool col 3 (6): Aggregate Charge, Chain Reaction, Destabilizing Rounds, Impulse Amplifier, One for All, Surrounded
- Copy 1: [Feeding Frenzy, Proximity Power, Threat Detector] x [Aggregate Charge, Chain Reaction, Impulse Amplifier] — 9 combos
- Copy 2: [Repulsor Brace, Reverberation, Stats for All] x [Aggregate Charge, Destabilizing Rounds, Impulse Amplifier] — 6 combos

### The Messenger
Pulse Rifle · Kinetic · tiered, obtainable · GFS 379 · pool 49 combos · 2 copies · 15 combos covered
- Pool col 2 (7): Discord, Moving Target, Offhand Strike, Outlaw, Perpetual Motion, Rapid Hit, Under-Over
- Pool col 3 (7): Desperado, Encore, Harmony, Headseeker, Keep Away, Kill Clip, Kinetic Tremors
- Copy 1: [Discord, Offhand Strike, Outlaw] x [Desperado, Encore, Headseeker] — 7 combos
- Copy 2: [Outlaw, Perpetual Motion, Under-Over] x [Encore, Keep Away, Kinetic Tremors] — 8 combos

### VS Chill Inhibitor
Grenade Launcher · Stasis · tiered, obtainable · GFS 234 · pool 36 combos · 2 copies · 15 combos covered
- Pool col 2 (6): Attrition Orbs, Cascade Point, Chill Clip, Danger Zone, Demolitionist, Envious Arsenal
- Pool col 3 (6): Aggregate Charge, Bait and Switch, Chain Reaction, Elemental Honing, Explosive Light, Surrounded
- Copy 1: [Cascade Point, Chill Clip, Danger Zone] x [Aggregate Charge, Chain Reaction, Elemental Honing] — 9 combos
- Copy 2: [Attrition Orbs, Cascade Point, Chill Clip] x [Bait and Switch, Explosive Light, Surrounded] — 6 combos

### Yeartide Apex
Submachine Gun · Solar · tiered, obtainable · GFS 262 · pool 42 combos · 2 copies · 15 combos covered
- Pool col 2 (7): Attrition Orbs, Demolitionist, Feeding Frenzy, Heal Clip, Lone Wolf, Recycled Energy, Transcendent Moment
- Pool col 3 (6): Binary Orbit, Burning Ambition, Chaos Reshaped, Harmony, Incandescent, Target Lock
- Copy 1: [Feeding Frenzy, Lone Wolf, Recycled Energy] x [Binary Orbit, Burning Ambition, Chaos Reshaped] — 9 combos
- Copy 2: [Lone Wolf, Recycled Energy, Transcendent Moment] x [Chaos Reshaped, Harmony, Target Lock] — 6 combos

### Arcane Embrace
Shotgun · Arc · tiered, obtainable · GFS 362 · pool 49 combos · 2 copies · 14 combos covered
- Pool col 2 (7): Air Trigger, Dual Loader, Fourth Time's the Charm, Grave Robber, Lone Wolf, Slideshot, Threat Detector
- Pool col 3 (7): Closing Time, Desperado, Precision Instrument, Surrounded, Swashbuckler, Tap the Trigger, Voltshot
- Copy 1: [Air Trigger, Dual Loader, Grave Robber] x [Desperado, Precision Instrument, Voltshot] — 9 combos
- Copy 2: [Air Trigger, Slideshot, Threat Detector] x [Desperado, Swashbuckler, Voltshot] — 5 combos

### Gizmo Weft
Grenade Launcher · Strand · tiered, obtainable · GFS 198 · pool 36 combos · 2 copies · 14 combos covered
- Pool col 2 (6): Air Trigger, Blast Distributor, Envious Arsenal, Reverberation, Slice, Slideshot
- Pool col 3 (6): Aggregate Charge, Bait and Switch, Bipod, Chain Reaction, Elemental Honing, Hatchling
- Copy 1: [Air Trigger, Blast Distributor, Slideshot] x [Chain Reaction, Elemental Honing, Hatchling] — 9 combos
- Copy 2: [Air Trigger, Reverberation, Slideshot] x [Bait and Switch, Bipod, Chain Reaction] — 5 combos

### Hawthorne's Field-Forged Shotgun
Shotgun · Kinetic · tiered, obtainable · GFS 205 · pool 30 combos · 2 copies · 14 combos covered
- Pool col 2 (5): Field Prep, Firmly Planted, Full Auto Trigger System, Grave Robber, Pulse Monitor
- Pool col 3 (6): Demolitionist, Eye of the Storm, Hip-Fire Grip, One-Two Punch, Opening Shot, Surrounded
- Copy 1: [Firmly Planted, Full Auto Trigger System, Grave Robber] x [Eye of the Storm, Hip-Fire Grip, One-Two Punch] — 8 combos
- Copy 2: [Firmly Planted, Full Auto Trigger System, Pulse Monitor] x [Demolitionist, Hip-Fire Grip, Surrounded] — 6 combos

### Inbound Surveillance
Scout Rifle · Kinetic · tiered, obtainable · GFS 241 · pool 36 combos · 2 copies · 14 combos covered
- Pool col 2 (6): Bewildering Burst, Keep Away, Lucky Shot, Rapid Hit, Shoot to Loot, Stopping Power
- Pool col 3 (6): Adhesive Ordnance, Explosive Payload, Frenzy, Kinetic Tremors, Precision Instrument, Redirection
- Copy 1: [Keep Away, Lucky Shot, Rapid Hit] x [Adhesive Ordnance, Frenzy, Redirection] — 9 combos
- Copy 2: [Bewildering Burst, Lucky Shot, Shoot to Loot] x [Kinetic Tremors, Precision Instrument, Redirection] — 5 combos

### Infinite Paths 8
Pulse Rifle · Arc · tiered, obtainable · GFS 336 · pool 36 combos · 2 copies · 14 combos covered
- Pool col 2 (6): Auto-Loading Holster, Demolitionist, Genesis, Grave Robber, Moving Target, Threat Detector
- Pool col 3 (6): Dragonfly, Eye of the Storm, Opening Shot, Shield Disorient, Swashbuckler, Zen Moment
- Copy 1: [Auto-Loading Holster, Demolitionist, Grave Robber] x [Dragonfly, Shield Disorient, Zen Moment] — 6 combos
- Copy 2: [Genesis, Moving Target, Threat Detector] x [Shield Disorient, Swashbuckler, Zen Moment] — 8 combos

### Last Man Standing
Shotgun · Solar · tiered, vendor 6-perk, obtainable · GFS 331 · pool 36 combos · 2 copies · 14 combos covered
- Pool col 2 (6): Compulsive Reloader, Hip-Fire Grip, Opening Shot, Pugilist, Subsistence, Threat Detector
- Pool col 3 (6): Discord, One for All, One-Two Punch, Rampage, Shot Swap, Swashbuckler
- Copy 1: [Compulsive Reloader, Hip-Fire Grip, Subsistence] x [Discord, One-Two Punch, Shot Swap] — 9 combos
- Copy 2: [Compulsive Reloader, Opening Shot, Threat Detector] x [Discord, Shot Swap, Swashbuckler] — 5 combos

### Maahes HC4
Hand Cannon · Void · tiered, obtainable · GFS 382 · pool 42 combos · 2 copies · 14 combos covered
- Pool col 2 (6): Enlightened Action, Perpetual Motion, Pulse Monitor, Rapid Hit, Repulsor Brace, Unrelenting
- Pool col 3 (7): Destabilizing Rounds, Disruption Break, Dragonfly, Frenzy, Golden Tricorn, Golden Tricorn Enhanced, Swashbuckler
- Copy 1: [Enlightened Action, Pulse Monitor, Repulsor Brace] x [Disruption Break, Dragonfly, Golden Tricorn] — 8 combos
- Copy 2: [Enlightened Action, Pulse Monitor, Repulsor Brace] x [Destabilizing Rounds, Frenzy, Golden Tricorn Enhanced] — 6 combos

### Mint Retrograde
Pulse Rifle · Strand · tiered, vendor 6-perk, obtainable · GFS 237 · pool 36 combos · 2 copies · 14 combos covered
- Pool col 2 (6): Beacon Rounds, Envious Arsenal, Field Prep, Hatchling, Impulse Amplifier, Rewind Rounds
- Pool col 3 (6): Bait and Switch, Cascade Point, Chain Reaction, Elemental Honing, Frenzy, Master of Arms
- Copy 1: [Beacon Rounds, Hatchling, Rewind Rounds] x [Bait and Switch, Cascade Point, Frenzy] — 7 combos
- Copy 2: [Beacon Rounds, Field Prep, Rewind Rounds] x [Chain Reaction, Elemental Honing, Master of Arms] — 7 combos

### Mirror Imago (Adept)
Submachine Gun · Strand · adept, obtainable · GFS 288 · pool 49 combos · 2 copies · 14 combos covered
- Pool col 2 (7): Grave Robber, Moving Target, Overflow, Pugilist, Recycled Energy, Subsistence, To the Pain
- Pool col 3 (7): Hatchling, Offhand Strike, Permeability, Swashbuckler, Sword Logic, Target Lock, Unrelenting
- Copy 1: [Overflow, Recycled Energy, To the Pain] x [Offhand Strike, Permeability, Sword Logic] — 9 combos
- Copy 2: [Recycled Energy, Subsistence, To the Pain] x [Offhand Strike, Permeability, Unrelenting] — 5 combos

### Pre Astyanax IV
Combat Bow · Solar · tiered, vendor 6-perk, obtainable · GFS 155 · pool 36 combos · 2 copies · 14 combos covered
- Pool col 2 (6): Firefly, Impulse Amplifier, Incandescent, Rapid Hit, Successful Warm-Up, Transcendent Moment
- Pool col 3 (6): Binary Orbit, Burning Ambition, Elemental Honing, Explosive Head, High Ground, Swashbuckler
- Copy 1: [Firefly, Incandescent, Successful Warm-Up] x [Binary Orbit, Burning Ambition, Explosive Head] — 8 combos
- Copy 2: [Firefly, Incandescent, Rapid Hit] x [Explosive Head, High Ground, Swashbuckler] — 6 combos

### Sole Survivor
Sniper Rifle · Arc · tiered, vendor 6-perk, obtainable · GFS 347 · pool 36 combos · 2 copies · 14 combos covered
- Pool col 2 (6): Eddy Current, Field Prep, Lead from Gold, Outlaw, Rapid Hit, Snapshot Sights
- Pool col 3 (6): Eye of the Storm, Firing Line, Focused Fury, Frenzy, Voltshot, Vorpal Weapon
- Copy 1: [Eddy Current, Lead from Gold, Outlaw] x [Eye of the Storm, Firing Line, Focused Fury] — 8 combos
- Copy 2: [Field Prep, Lead from Gold, Outlaw] x [Eye of the Storm, Frenzy, Voltshot] — 6 combos

### Survivor's Epitaph
Hand Cannon · Kinetic · tiered, vendor 6-perk, obtainable · GFS 446 · pool 49 combos · 2 copies · 14 combos covered
- Pool col 2 (7): Eye of the Storm, Feeding Frenzy, High-Impact Reserves, Moving Target, Outlaw, Quickdraw, Rapid Hit
- Pool col 3 (7): Adagio, Explosive Payload, Kill Clip, Multikill Clip, Precision Instrument, Rangefinder, Snapshot Sights
- Copy 1: [Feeding Frenzy, High-Impact Reserves, Quickdraw] x [Adagio, Multikill Clip, Precision Instrument] — 9 combos
- Copy 2: [Moving Target, Outlaw, Quickdraw] x [Multikill Clip, Precision Instrument, Rangefinder] — 5 combos

### The Hero's Burden
Submachine Gun · Void · tiered, obtainable · GFS 199 · pool 36 combos · 2 copies · 14 combos covered
- Pool col 2 (6): Air Assault, Feeding Frenzy, Fragile Focus, Tunnel Vision, Well-Rounded, Zen Moment
- Pool col 3 (6): Eye of the Storm, Iron Grip, Iron Reach, Kill Clip, Repulsor Brace, Vorpal Weapon
- Copy 1: [Air Assault, Fragile Focus, Well-Rounded] x [Iron Grip, Iron Reach, Kill Clip] — 9 combos
- Copy 2: [Air Assault, Feeding Frenzy, Zen Moment] x [Iron Grip, Iron Reach, Repulsor Brace] — 5 combos

### The Scholar
Scout Rifle · Kinetic · tiered, obtainable · GFS 172 · pool 25 combos · 2 copies · 14 combos covered
- Pool col 2 (5): Full Auto Trigger System, Opening Shot, Pulse Monitor, Quickdraw, Slideways
- Pool col 3 (5): Celerity, Elemental Capacitor, No Distractions, Snapshot Sights, Vorpal Weapon
- Copy 1: [Full Auto Trigger System, Opening Shot, Slideways] x [Celerity, No Distractions, Vorpal Weapon] — 9 combos
- Copy 2: [Full Auto Trigger System, Pulse Monitor, Quickdraw] x [Elemental Capacitor, No Distractions, Snapshot Sights] — 5 combos

### Aurora Dawn
Sword · Stasis · tiered, vendor 6-perk, obtainable · GFS 214 · pool 36 combos · 2 copies · 13 combos covered
- Pool col 2 (6): Flash Counter, Proximity Power, Rimestealer, Sharp Harvest, Tireless Blade, Unrelenting
- Pool col 3 (6): Binary Orbit, Cold Steel, Elemental Honing, One for All, Vorpal Weapon, Whirlwind Blade
- Copy 1: [Flash Counter, Proximity Power, Rimestealer] x [Cold Steel, Elemental Honing, Whirlwind Blade] — 8 combos
- Copy 2: [Sharp Harvest, Tireless Blade, Unrelenting] x [Binary Orbit, Cold Steel, Elemental Honing] — 5 combos

### Dawn Far Off
Machine Gun · Solar · tiered, obtainable · GFS 184 · pool 49 combos · 2 copies · 13 combos covered
- Pool col 2 (7): Attrition Orbs, Burning Ambition, Collective Demolition, Impromptu Ammunition, Light Touch, Subsistence, Triple Tap
- Pool col 3 (7): Aggregate Charge, Binary Orbit, Incandescent, Killing Tally, Meganeura, Redirection, Target Lock
- Copy 1: [Attrition Orbs, Burning Ambition, Triple Tap] x [Aggregate Charge, Killing Tally, Meganeura] — 7 combos
- Copy 2: [Burning Ambition, Collective Demolition, Impromptu Ammunition] x [Aggregate Charge, Killing Tally, Redirection] — 6 combos

### Ded Gramarye IV
Shotgun · Arc · tiered, obtainable · GFS 337 · pool 42 combos · 2 copies · 13 combos covered
- Pool col 2 (6): Discord, Eddy Current, Slickdraw, Stats for All, Surplus, Threat Detector
- Pool col 3 (7): Chain Reaction, Disruption Break, Golden Tricorn, Golden Tricorn Enhanced, Surrounded, Voltshot, Vorpal Weapon
- Copy 1: [Discord, Eddy Current, Surplus] x [Chain Reaction, Disruption Break, Voltshot] — 8 combos
- Copy 2: [Slickdraw, Stats for All] x [Disruption Break, Surrounded, Voltshot] — 5 combos

### Faustus Decline
Sidearm · Stasis · tiered, obtainable · GFS 467 · pool 49 combos · 2 copies · 13 combos covered
- Pool col 2 (7): Demolitionist, Hip-Fire Grip, Killing Wind, Lone Wolf, Perpetual Motion, Rangefinder, Rimestealer
- Pool col 3 (7): Headstone, Kill Clip, Offhand Strike, Precision Instrument, Snapshot Sights, Swashbuckler, Sword Logic
- Copy 1: [Hip-Fire Grip, Rangefinder, Rimestealer] x [Headstone, Precision Instrument, Snapshot Sights] — 8 combos
- Copy 2: [Demolitionist, Killing Wind, Rimestealer] x [Kill Clip, Offhand Strike, Sword Logic] — 5 combos

### Permafrost
Grenade Launcher · Stasis · tiered, obtainable · GFS 293 · pool 49 combos · 2 copies · 13 combos covered
- Pool col 2 (7): Attrition Orbs, Blast Distributor, Demolitionist, Impromptu Ammunition, Lead from Gold, Overflow, Rimestealer
- Pool col 3 (7): Adrenaline Junkie, Crystalline Corpsebloom, Desperate Measures, One for All, Pugilist, Reaper's Tithe, Wellspring
- Copy 1: [Blast Distributor, Lead from Gold, Overflow] x [Crystalline Corpsebloom, Pugilist, Reaper's Tithe] — 7 combos
- Copy 2: [Attrition Orbs, Impromptu Ammunition, Rimestealer] x [Pugilist, Reaper's Tithe, Wellspring] — 6 combos

### PLUG ONE.1
Fusion Rifle · Arc · tiered, vendor 6-perk, obtainable · GFS 181 · pool 36 combos · 2 copies · 13 combos covered
- Pool col 2 (6): Feeding Frenzy, Lone Wolf, Reconstruction, Slideways, Under Pressure, Well-Rounded
- Pool col 3 (6): Closing Time, Controlled Burst, Desperate Measures, Kickstart, Reservoir Burst, Voltshot
- Copy 1: [Feeding Frenzy, Slideways, Well-Rounded] x [Closing Time, Controlled Burst, Desperate Measures] — 8 combos
- Copy 2: [Feeding Frenzy, Reconstruction, Slideways] x [Kickstart, Voltshot] — 5 combos

### Qua Nilus II
Submachine Gun · Strand · tiered, vendor 6-perk, obtainable · GFS 211 · pool 36 combos · 2 copies · 13 combos covered
- Pool col 2 (6): Dynamic Sway Reduction, Encore, Offhand Strike, Proximity Power, Slice, Transcendent Moment
- Pool col 3 (6): Binary Orbit, Dragonfly, Harmony, Hatchling, Surrounded, Swashbuckler
- Copy 1: [Encore, Offhand Strike, Proximity Power] x [Binary Orbit, Dragonfly, Hatchling] — 9 combos
- Copy 2: [Dynamic Sway Reduction, Slice, Transcendent Moment] x [Dragonfly, Harmony, Hatchling] — 4 combos

### Warden's Law
Hand Cannon · Kinetic · tiered, vendor 6-perk, obtainable · GFS 391 · pool 36 combos · 2 copies · 13 combos covered
- Pool col 2 (6): Discord, Enlightened Action, Fourth Time's the Charm, Moving Target, Perpetual Motion, Snapshot Sights
- Pool col 3 (6): Frenzy, Kill Clip, Rampage, Shot Swap, Vorpal Weapon, Zen Moment
- Copy 1: [Discord, Enlightened Action, Fourth Time's the Charm] x [Rampage, Shot Swap, Zen Moment] — 8 combos
- Copy 2: [Discord, Moving Target, Perpetual Motion] x [Frenzy, Shot Swap, Zen Moment] — 5 combos

### Adored
Sniper Rifle · Arc · tiered, vendor 6-perk, obtainable · GFS 238 · pool 36 combos · 2 copies · 12 combos covered
- Pool col 2 (6): Elemental Capacitor, Fourth Time's the Charm, Jolting Feedback, Lone Wolf, Snapshot Sights, Supercharged Magazine
- Pool col 3 (6): Closing Time, Collective Action, Elemental Honing, Moving Target, No Distractions, Opening Shot
- Copy 1: [Fourth Time's the Charm, Jolting Feedback, Supercharged Magazine] x [Closing Time, Collective Action, No Distractions] — 7 combos
- Copy 2: [Jolting Feedback, Lone Wolf] x [Elemental Honing, Moving Target, No Distractions] — 5 combos

### Division (Adept)
Sidearm · Arc · adept, obtainable · GFS 388 · pool 49 combos · 2 copies · 12 combos covered
- Pool col 2 (7): Eddy Current, Encore, Grave Robber, Hip-Fire Grip, Perfect Float, Pugilist, To the Pain
- Pool col 3 (7): Eye of the Storm, Kill Clip, Offhand Strike, Surrounded, Swashbuckler, Sword Logic, Voltshot
- Copy 1: [Eddy Current, Grave Robber, Perfect Float] x [Offhand Strike, Swashbuckler, Sword Logic] — 7 combos
- Copy 2: [Encore, Hip-Fire Grip, Pugilist] x [Surrounded, Sword Logic, Voltshot] — 5 combos

### Duty Bound
Auto Rifle · Kinetic · tiered, vendor 6-perk, obtainable · GFS 413 · pool 36 combos · 2 copies · 12 combos covered
- Pool col 2 (6): Compulsive Reloader, Perpetual Motion, Stats for All, Steady Hands, Triple Tap, Zen Moment
- Pool col 3 (6): Dynamic Sway Reduction, Fourth Time's the Charm, Frenzy, One for All, Rampage, Vorpal Weapon
- Copy 1: [Compulsive Reloader, Perpetual Motion, Stats for All] x [Dynamic Sway Reduction, Fourth Time's the Charm, Rampage] — 7 combos
- Copy 2: [Steady Hands, Triple Tap] x [Dynamic Sway Reduction, Fourth Time's the Charm, One for All] — 5 combos

### Eighty-Six
Sword · Strand · tiered, obtainable · GFS 251 · pool 49 combos · 2 copies · 12 combos covered
- Pool col 2 (7): Duelist's Trance, Flash Counter, Lead From Light, Relentless Strikes, Sharp Harvest, Slice, Tireless Blade
- Pool col 3 (7): Attrition Orbs, Binary Orbit, Chain Reaction, Elemental Honing, En Garde, Hatchling, Redirection
- Copy 1: [Lead From Light, Sharp Harvest, Slice] x [Elemental Honing, En Garde, Hatchling] — 6 combos
- Copy 2: [Duelist's Trance, Flash Counter, Lead From Light] x [Attrition Orbs, Binary Orbit, Redirection] — 6 combos

### Hardline Cut
Sword · Arc · tiered, obtainable · GFS 335 · pool 49 combos · 2 copies · 12 combos covered
- Pool col 2 (7): Assassin's Blade, Attrition Orbs, Flash Counter, Proximity Power, Relentless Strikes, Sharp Harvest, Tireless Blade
- Pool col 3 (7): Chain Reaction, Eager Edge, Jolting Feedback, One for All, Surrounded, Vorpal Weapon, Whirlwind Blade
- Copy 1: [Assassin's Blade, Proximity Power] x [Jolting Feedback, One for All, Vorpal Weapon] — 5 combos
- Copy 2: [Assassin's Blade, Attrition Orbs, Proximity Power] x [Chain Reaction, Eager Edge, Surrounded] — 7 combos

### Mechabre
Sniper Rifle · Arc · tiered, obtainable · GFS 429 · pool 49 combos · 2 copies · 12 combos covered
- Pool col 2 (7): Auto-Loading Holster, Clown Cartridge, Demolitionist, Eddy Current, Keep Away, Snapshot Sights, Triple Tap
- Pool col 3 (7): Adrenaline Junkie, Discord, High Ground, High-Impact Reserves, Opening Shot, Voltshot, Vorpal Weapon
- Copy 1: [Auto-Loading Holster, Clown Cartridge, Eddy Current] x [Discord, Opening Shot, Voltshot] — 8 combos
- Copy 2: [Demolitionist, Eddy Current, Triple Tap] x [High-Impact Reserves, Voltshot, Vorpal Weapon] — 4 combos

### Mistral Lift
Linear Fusion Rifle · Void · tiered, obtainable · GFS 483 · pool 63 combos · 2 copies · 12 combos covered
- Pool col 2 (7): Clown Cartridge, Envious Arsenal, Envious Assassin, Keep Away, Moving Target, Reconstruction, Withering Gaze
- Pool col 3 (9): Bait and Switch, Firing Line, Frenzy, Golden Tricorn, Golden Tricorn Enhanced, High Ground, High-Impact Reserves, Precision Instrument, Vorpal Weapon
- Copy 1: [Envious Arsenal, Reconstruction, Withering Gaze] x [Firing Line, Golden Tricorn, Golden Tricorn Enhanced] — 7 combos
- Copy 2: [Clown Cartridge, Envious Arsenal, Withering Gaze] x [Bait and Switch, High-Impact Reserves, Precision Instrument] — 5 combos

### Nameless Midnight
Scout Rifle · Kinetic · tiered, vendor 6-perk, obtainable · GFS 490 · pool 55 combos · 2 copies · 12 combos covered
- Pool col 2 (8): Auto-Loading Holster, Explosive Payload, Grave Robber, High-Impact Reserves, Hip-Fire Grip, Moving Target, Triple Tap, Zen Moment
- Pool col 3 (7): Explosive Payload, Kill Clip, Opening Shot, Outlaw, Rampage, Rangefinder, Threat Detector
- Copy 1: [Grave Robber, High-Impact Reserves, Hip-Fire Grip] x [Explosive Payload, Opening Shot, Outlaw] — 6 combos
- Copy 2: [Auto-Loading Holster, High-Impact Reserves, Triple Tap] x [Kill Clip, Rangefinder, Threat Detector] — 6 combos

### Nox Perennial V
Fusion Rifle · Strand · tiered, obtainable · GFS 184 · pool 36 combos · 2 copies · 12 combos covered
- Pool col 2 (6): Envious Assassin, Fragile Focus, Lead from Gold, Loose Change, Threat Detector, Under Pressure
- Pool col 3 (6): Collective Action, Controlled Burst, Elemental Capacitor, Hatchling, Kickstart, Wellspring
- Copy 1: [Envious Assassin, Fragile Focus, Loose Change] x [Controlled Burst, Elemental Capacitor, Kickstart] — 7 combos
- Copy 2: [Envious Assassin, Lead from Gold, Loose Change] x [Hatchling, Kickstart, Wellspring] — 5 combos

### Nox Sidereal IV
Fusion Rifle · Stasis · tiered, vendor 6-perk, obtainable · GFS 226 · pool 36 combos · 2 copies · 12 combos covered
- Pool col 2 (6): Ambitious Assassin, Clown Cartridge, Demolitionist, Proximity Power, Shot Swap, Stats for All
- Pool col 3 (6): Adrenaline Junkie, Crystalline Corpsebloom, Discord, Frenzy, Master of Arms, Reservoir Burst
- Copy 1: [Clown Cartridge, Proximity Power, Shot Swap] x [Crystalline Corpsebloom, Master of Arms, Reservoir Burst] — 8 combos
- Copy 2: [Demolitionist, Stats for All] x [Discord, Master of Arms, Reservoir Burst] — 4 combos

### Out of Bounds
Submachine Gun · Arc · tiered, vendor 6-perk, obtainable · GFS 650 · pool 56 combos · 2 copies · 12 combos covered
- Pool col 2 (7): Demolitionist, Dynamic Sway Reduction, Loose Change, Moving Target, Perpetual Motion, Subsistence, Voltshot
- Pool col 3 (8): Adrenaline Junkie, Frenzy, Golden Tricorn, Golden Tricorn Enhanced, Jolting Feedback, Kill Clip, Rangefinder, Tap the Trigger
- Copy 1: [Demolitionist, Loose Change, Subsistence] x [Adrenaline Junkie, Jolting Feedback, Rangefinder] — 7 combos
- Copy 2: [Dynamic Sway Reduction, Loose Change, Voltshot] x [Frenzy, Golden Tricorn, Tap the Trigger] — 5 combos

### Palmyra-B
Rocket Launcher · Stasis · tiered, craftable, obtainable · GFS 451 · pool 48 combos · 2 copies · 12 combos covered
- Pool col 2 (7): Ambitious Assassin, Auto-Loading Holster, Empty Traits Socket, Ensemble, Impulse Amplifier, Surplus, Unrelenting
- Pool col 3 (7): Adrenaline Junkie, Chain Reaction, Chill Clip, Empty Traits Socket, Explosive Light, Frenzy, Lasting Impression
- Copy 1: [Ambitious Assassin, Surplus, Unrelenting] x [Chill Clip, Explosive Light, Lasting Impression] — 7 combos
- Copy 2: [Empty Traits Socket, Ensemble, Impulse Amplifier] x [Chill Clip, Explosive Light, Lasting Impression] — 5 combos

### Rapacious Appetite
Submachine Gun · Stasis · tiered, craftable, obtainable · GFS 649 · pool 63 combos · 2 copies · 12 combos covered
- Pool col 2 (8): Empty Traits Socket, Encore, Envious Assassin, Fourth Time's the Charm, Invisible Hand, Offhand Strike, Perpetual Motion, Well-Rounded
- Pool col 3 (8): Cascade Point, Empty Traits Socket, Focused Fury, Frenzy, Harmony, Headstone, One for All, Target Lock
- Copy 1: [Encore, Invisible Hand, Well-Rounded] x [Headstone, One for All, Target Lock] — 8 combos
- Copy 2: [Fourth Time's the Charm, Invisible Hand, Well-Rounded] x [Cascade Point, Frenzy] — 4 combos

### Reed's Regret
Linear Fusion Rifle · Stasis · tiered, obtainable · GFS 388 · pool 49 combos · 2 copies · 12 combos covered
- Pool col 2 (7): Auto-Loading Holster, Clown Cartridge, Compulsive Reloader, Heating Up, Hip-Fire Grip, Surplus, Triple Tap
- Pool col 3 (7): Adagio, Firing Line, Focused Fury, Harmony, Headstone, Successful Warm-Up, Vorpal Weapon
- Copy 1: [Clown Cartridge, Hip-Fire Grip, Triple Tap] x [Adagio, Firing Line, Successful Warm-Up] — 6 combos
- Copy 2: [Auto-Loading Holster, Clown Cartridge, Heating Up] x [Adagio, Harmony, Headstone] — 6 combos

### Stars in Shadow
Pulse Rifle · Solar · tiered, vendor 6-perk, obtainable · GFS 335 · pool 36 combos · 2 copies · 12 combos covered
- Pool col 2 (6): Heal Clip, Impromptu Ammunition, Keep Away, Lone Wolf, Rapid Hit, Zen Moment
- Pool col 3 (6): Burning Ambition, Desperado, Headseeker, Incandescent, Kill Clip, Sword Logic
- Copy 1: [Heal Clip, Impromptu Ammunition, Rapid Hit] x [Burning Ambition, Desperado, Headseeker] — 6 combos
- Copy 2: [Impromptu Ammunition, Lone Wolf, Zen Moment] x [Incandescent, Kill Clip, Sword Logic] — 6 combos

### The Forward Path
Auto Rifle · Kinetic · tiered, obtainable · GFS 276 · pool 36 combos · 2 copies · 12 combos covered
- Pool col 2 (6): Dynamic Sway Reduction, Feeding Frenzy, Fourth Time's the Charm, Grave Robber, Hip-Fire Grip, Pulse Monitor
- Pool col 3 (6): Eye of the Storm, Iron Gaze, Iron Grip, Multikill Clip, Swashbuckler, Tap the Trigger
- Copy 1: [Dynamic Sway Reduction, Fourth Time's the Charm, Grave Robber] x [Iron Gaze, Iron Grip, Multikill Clip] — 7 combos
- Copy 2: [Hip-Fire Grip, Pulse Monitor] x [Iron Gaze, Iron Grip, Tap the Trigger] — 5 combos

### Festival Flight
Grenade Launcher · Strand · tiered, obtainable · GFS 366 · pool 49 combos · 2 copies · 11 combos covered
- Pool col 2 (7): Ambitious Assassin, Blast Distributor, Demolitionist, Envious Arsenal, Recycled Energy, Slice, Transcendent Moment
- Pool col 3 (7): Attrition Orbs, Binary Orbit, Elemental Honing, Frenzy, Hatchling, One for All, Vorpal Weapon
- Copy 1: [Ambitious Assassin, Blast Distributor, Envious Arsenal] x [Attrition Orbs, Binary Orbit, One for All] — 6 combos
- Copy 2: [Recycled Energy, Transcendent Moment] x [Attrition Orbs, Hatchling, Vorpal Weapon] — 5 combos

### Frozen Orbit
Sniper Rifle · Void · tiered, vendor 6-perk, obtainable · GFS 493 · pool 49 combos · 2 copies · 11 combos covered
- Pool col 2 (7): Killing Wind, Lead from Gold, Lone Wolf, Moving Target, No Distractions, Surplus, Triple Tap
- Pool col 3 (7): Cascade Point, Closing Time, High Ground, Keep Away, Opening Shot, Snapshot Sights, Vorpal Weapon
- Copy 1: [Killing Wind, Surplus, Triple Tap] x [Cascade Point, Closing Time, Keep Away] — 8 combos
- Copy 2: [Lead from Gold, No Distractions] x [Closing Time, High Ground, Snapshot Sights] — 3 combos

### Igneous Hammer
Hand Cannon · Solar · tiered, obtainable · GFS 520 · pool 56 combos · 2 copies · 11 combos covered
- Pool col 2 (7): Encore, Fragile Focus, Heal Clip, Keep Away, Rangefinder, Rapid Hit, Slickdraw
- Pool col 3 (8): Eye of the Storm, Frenzy, Golden Tricorn, Golden Tricorn Enhanced, Incandescent, Moving Target, Opening Shot, Precision Instrument
- Copy 1: [Fragile Focus, Heal Clip, Rangefinder] x [Golden Tricorn, Golden Tricorn Enhanced, Incandescent] — 8 combos
- Copy 2: [Keep Away, Rapid Hit, Slickdraw] x [Golden Tricorn, Golden Tricorn Enhanced] — 3 combos

### Insurmountable
Sidearm · Void · tiered, obtainable · GFS 507 · pool 49 combos · 2 copies · 11 combos covered
- Pool col 2 (7): Air Trigger, Attrition Orbs, Demolitionist, Lone Wolf, Repulsor Brace, Threat Detector, To the Pain
- Pool col 3 (7): Closing Time, Desperate Measures, Destabilizing Rounds, Harmony, One for All, Rampage, Surrounded
- Copy 1: [Air Trigger, Lone Wolf, To the Pain] x [Harmony, One for All, Rampage] — 6 combos
- Copy 2: [Air Trigger, Lone Wolf, Repulsor Brace] x [Closing Time, Destabilizing Rounds, Surrounded] — 5 combos

### Last Perdition
Pulse Rifle · Void · tiered, vendor 6-perk, obtainable · GFS 397 · pool 42 combos · 2 copies · 11 combos covered
- Pool col 2 (6): Firmly Planted, Grave Robber, Moving Target, Outlaw, Rangefinder, Under Pressure
- Pool col 3 (7): Full Auto Trigger System, Headseeker, High-Impact Reserves, Kill Clip, Rampage, Snapshot Sights, Zen Moment
- Copy 1: [Firmly Planted, Grave Robber, Outlaw] x [Full Auto Trigger System, Headseeker, Zen Moment] — 7 combos
- Copy 2: [Moving Target, Rangefinder, Under Pressure] x [Full Auto Trigger System, Kill Clip, Rampage] — 4 combos

### Lotus-Eater
Sidearm · Void · tiered, vendor 6-perk, obtainable · GFS 237 · pool 36 combos · 2 copies · 11 combos covered
- Pool col 2 (6): Beacon Rounds, Feeding Frenzy, Reconstruction, Repulsor Brace, Shoot to Loot, Strategist
- Pool col 3 (6): Adrenaline Junkie, Destabilizing Rounds, High Ground, One for All, Reverberation, Withering Gaze
- Copy 1: [Beacon Rounds, Feeding Frenzy, Reconstruction] x [Destabilizing Rounds, High Ground, Withering Gaze] — 6 combos
- Copy 2: [Feeding Frenzy, Repulsor Brace, Shoot to Loot] x [Adrenaline Junkie, High Ground, Reverberation] — 5 combos

### Mos Athanor IV
Hand Cannon · Void · tiered, vendor 6-perk, obtainable · GFS 281 · pool 36 combos · 2 copies · 11 combos covered
- Pool col 2 (6): Built to Blast, Destabilizing Rounds, Keep Away, Lone Wolf, Moving Target, Slideways
- Pool col 3 (6): Adagio, Demoralize, Eye of the Storm, Opening Shot, Precision Instrument, Sword Logic
- Copy 1: [Built to Blast, Destabilizing Rounds, Moving Target] x [Adagio, Eye of the Storm, Sword Logic] — 5 combos
- Copy 2: [Lone Wolf, Slideways] x [Adagio, Precision Instrument, Sword Logic] — 6 combos

### Phoneutria Fera
Hand Cannon · Solar · tiered, obtainable · GFS 241 · pool 36 combos · 2 copies · 11 combos covered
- Pool col 2 (6): Barrel Constrictor, Proximity Power, Slideshot, Threat Detector, Threat Remover, Transcendent Moment
- Pool col 3 (6): Binary Orbit, Frenzy, Incandescent, One-Two Punch, Surrounded, Swashbuckler
- Copy 1: [Barrel Constrictor, Threat Remover, Transcendent Moment] x [Frenzy, Incandescent, Surrounded] — 8 combos
- Copy 2: [Proximity Power, Slideshot, Transcendent Moment] x [Incandescent, One-Two Punch] — 3 combos

### Point of the Stag
Combat Bow · Arc · tiered, obtainable · GFS 253 · pool 42 combos · 2 copies · 11 combos covered
- Pool col 2 (6): Archer's Tempo, Elemental Capacitor, No Distractions, Pugilist, Shot Swap, Slickdraw
- Pool col 3 (7): Dragonfly, Eye of the Storm, Golden Tricorn, Golden Tricorn Enhanced, Precision Instrument, Swashbuckler, Vorpal Weapon
- Copy 1: [Elemental Capacitor, Pugilist, Slickdraw] x [Dragonfly, Golden Tricorn Enhanced, Precision Instrument] — 6 combos
- Copy 2: [Archer's Tempo, No Distractions] x [Dragonfly, Golden Tricorn Enhanced, Swashbuckler] — 5 combos

### Red Tape
Scout Rifle · Stasis · tiered, obtainable · GFS 397 · pool 49 combos · 2 copies · 11 combos covered
- Pool col 2 (7): Attrition Orbs, Closing Time, Demolitionist, Fourth Time's the Charm, Keep Away, Lone Wolf, Rimestealer
- Pool col 3 (7): Adrenaline Junkie, Explosive Payload, Focused Fury, Headstone, High-Impact Reserves, One for All, Rampage
- Copy 1: [Attrition Orbs, Closing Time, Rimestealer] x [Explosive Payload, Focused Fury, High-Impact Reserves] — 9 combos
- Copy 2: [Keep Away, Lone Wolf] x [Explosive Payload, Focused Fury] — 2 combos

### Shadow Price
Auto Rifle · Arc · tiered, vendor 6-perk, obtainable · GFS 338 · pool 36 combos · 2 copies · 11 combos covered
- Pool col 2 (6): Bottomless Grief, Feeding Frenzy, Fourth Time's the Charm, Killing Wind, Overflow, Surplus
- Pool col 3 (6): Disruption Break, Dragonfly, One for All, Swashbuckler, Thresh, Unrelenting
- Copy 1: [Bottomless Grief, Fourth Time's the Charm] x [Disruption Break, Dragonfly, One for All] — 5 combos
- Copy 2: [Bottomless Grief, Fourth Time's the Charm, Surplus] x [Swashbuckler, Thresh, Unrelenting] — 6 combos

### Something New
Hand Cannon · Stasis · tiered, obtainable · GFS 516 · pool 56 combos · 2 copies · 11 combos covered
- Pool col 2 (7): Discord, Feeding Frenzy, Pugilist, Rapid Hit, Subsistence, Triple Tap, Wellspring
- Pool col 3 (8): Demolitionist, Encore, Frenzy, Golden Tricorn, Golden Tricorn Enhanced, Harmony, Headstone, Kill Clip
- Copy 1: [Discord, Feeding Frenzy, Pugilist] x [Demolitionist, Encore, Headstone] — 7 combos
- Copy 2: [Discord, Triple Tap, Wellspring] x [Golden Tricorn Enhanced, Headstone, Kill Clip] — 4 combos

### D.F.A.
Hand Cannon · Kinetic · tiered, vendor 6-perk, obtainable · GFS 380 · pool 36 combos · 2 copies · 10 combos covered
- Pool col 2 (6): Fragile Focus, Outlaw, Perpetual Motion, Steady Hands, Triple Tap, Tunnel Vision
- Pool col 3 (6): Focused Fury, Opening Shot, Rampage, Timed Payload, Vorpal Weapon, Wellspring
- Copy 1: [Fragile Focus, Perpetual Motion, Steady Hands] x [Timed Payload, Wellspring] — 6 combos
- Copy 2: [Triple Tap, Tunnel Vision] x [Opening Shot, Timed Payload, Wellspring] — 4 combos

### Loaded Question
Fusion Rifle · Arc · tiered, vendor 6-perk, obtainable · GFS 274 · pool 36 combos · 2 copies · 10 combos covered
- Pool col 2 (6): Auto-Loading Holster, Demolitionist, Envious Assassin, Firmly Planted, Overflow, Under Pressure
- Pool col 3 (6): Controlled Burst, Eye of the Storm, Frenzy, Harmony, Pugilist, Reservoir Burst
- Copy 1: [Auto-Loading Holster, Firmly Planted, Overflow] x [Controlled Burst, Eye of the Storm, Pugilist] — 6 combos
- Copy 2: [Auto-Loading Holster, Firmly Planted, Overflow] x [Frenzy, Reservoir Burst] — 4 combos

### Pure Recollection
Shotgun · Void · tiered, vendor 6-perk, obtainable · GFS 208 · pool 36 combos · 2 copies · 10 combos covered
- Pool col 2 (6): Dual Loader, Envious Arsenal, High-Impact Reserves, Lone Wolf, Threat Detector, Under Pressure
- Pool col 3 (6): Bait and Switch, Closing Time, Destabilizing Rounds, Headseeker, Tap the Trigger, Withering Gaze
- Copy 1: [Dual Loader, Envious Arsenal, Threat Detector] x [Headseeker, Tap the Trigger, Withering Gaze] — 9 combos
- Copy 2: [Under Pressure] x [Withering Gaze] — 1 combo

### Claws of the Wolf
Pulse Rifle · Void · tiered, obtainable · GFS 262 · pool 36 combos · 2 copies · 9 combos covered
- Pool col 2 (6): Field Prep, Headseeker, Outlaw, Slideshot, Snapshot Sights, Threat Detector
- Pool col 3 (6): Full Auto Trigger System, Grave Robber, High-Impact Reserves, Kill Clip, Rampage, Rangefinder
- Copy 1: [Field Prep, Headseeker, Threat Detector] x [Full Auto Trigger System, Grave Robber, Rampage] — 7 combos
- Copy 2: [Field Prep] x [High-Impact Reserves, Kill Clip] — 2 combos

### Spare Rations
Hand Cannon · Kinetic · tiered, vendor 6-perk, obtainable · GFS 449 · pool 36 combos · 2 copies · 9 combos covered
- Pool col 2 (6): Moving Target, Offhand Strike, Rapid Hit, Slideshot, Snapshot Sights, Subsistence
- Pool col 3 (6): Focused Fury, Kill Clip, Kinetic Tremors, Opening Shot, Swashbuckler, Vorpal Weapon
- Copy 1: [Moving Target, Offhand Strike, Slideshot] x [Focused Fury, Kinetic Tremors, Opening Shot] — 7 combos
- Copy 2: [Offhand Strike, Snapshot Sights] x [Swashbuckler] — 2 combos

### Stay Frosty
Pulse Rifle · Stasis · tiered, obtainable · GFS 479 · pool 49 combos · 2 copies · 9 combos covered
- Pool col 2 (7): Encore, Enlightened Action, Killing Wind, Lone Wolf, Moving Target, Rimestealer, Tunnel Vision
- Pool col 3 (7): Adrenaline Junkie, Desperado, Desperate Measures, Frenzy, Headseeker, Headstone, Kill Clip
- Copy 1: [Encore, Killing Wind, Moving Target] x [Desperado, Desperate Measures, Headseeker] — 5 combos
- Copy 2: [Lone Wolf, Tunnel Vision] x [Adrenaline Junkie, Frenzy, Headstone] — 4 combos

### Syncopation-53
Pulse Rifle · Stasis · tiered, craftable, obtainable · GFS 600 · pool 48 combos · 2 copies · 9 combos covered
- Pool col 2 (7): Compulsive Reloader, Empty Traits Socket, Hip-Fire Grip, Moving Target, Outlaw, Steady Hands, Zen Moment
- Pool col 3 (7): Empty Traits Socket, Focused Fury, Frenzy, Headseeker, Headstone, Rangefinder, Vorpal Weapon
- Copy 1: [Outlaw, Steady Hands, Zen Moment] x [Focused Fury, Headseeker, Headstone] — 6 combos
- Copy 2: [Compulsive Reloader, Empty Traits Socket] x [Focused Fury, Rangefinder, Vorpal Weapon] — 3 combos

### Outrageous Fortune
Grenade Launcher · Solar · tiered, vendor 6-perk, obtainable · GFS 244 · pool 36 combos · 2 copies · 8 combos covered
- Pool col 2 (6): Blast Distributor, Envious Arsenal, Field Prep, Impulse Amplifier, Incandescent, Stats for All
- Pool col 3 (6): Bait and Switch, Binary Orbit, Burning Ambition, Chain Reaction, Explosive Light, Full Court
- Copy 1: [Field Prep, Incandescent, Stats for All] x [Burning Ambition, Chain Reaction, Full Court] — 7 combos
- Copy 2: [Envious Arsenal] x [Burning Ambition] — 1 combo

### Ragnhild-D
Shotgun · Kinetic · tiered, craftable, obtainable · GFS 601 · pool 48 combos · 2 copies · 7 combos covered
- Pool col 2 (7): Auto-Loading Holster, Dual Loader, Empty Traits Socket, Ensemble, Perpetual Motion, Steady Hands, Subsistence
- Pool col 3 (7): Adrenaline Junkie, Demolitionist, Elemental Capacitor, Empty Traits Socket, Frenzy, One-Two Punch, Thresh
- Copy 1: [Dual Loader, Perpetual Motion, Steady Hands] x [Demolitionist, One-Two Punch, Thresh] — 4 combos
- Copy 2: [Auto-Loading Holster, Perpetual Motion, Steady Hands] x [Empty Traits Socket] — 3 combos

### Throne-Cleaver
Sword · Void · tiered, obtainable · GFS 130 · pool 12 combos · 2 copies · 5 combos covered
- Pool col 2 (3): Relentless Strikes, Shattering Blade, Tireless Blade
- Pool col 3 (4): Assassin's Blade, Counterattack, En Garde, Whirlwind Blade
- Copy 1: [Shattering Blade] x [Assassin's Blade, Counterattack, Whirlwind Blade] — 3 combos
- Copy 2: [Relentless Strikes, Shattering Blade] x [En Garde] — 2 combos

### Bite of the Fox
Sniper Rifle · Kinetic · tiered, obtainable · GFS 301 · pool 30 combos · 1 copy · 9 combos covered
- Pool col 2 (5): Firmly Planted, Hip-Fire Grip, Rapid Hit, Snapshot Sights, Threat Detector
- Pool col 3 (6): Ambitious Assassin, Explosive Payload, Field Prep, Moving Target, Opening Shot, Rampage
- Copy 1: [Firmly Planted, Hip-Fire Grip, Rapid Hit] x [Ambitious Assassin, Field Prep, Moving Target] — 9 combos

### Cold Denial
Pulse Rifle · Kinetic · tiered, obtainable · GFS 243 · pool 36 combos · 1 copy · 9 combos covered
- Pool col 2 (6): Ambitious Assassin, Enlightened Action, Steady Hands, Surplus, Tunnel Vision, Zen Moment
- Pool col 3 (6): Desperado, Eye of the Storm, Gutshot Straight, Headseeker, Multikill Clip, Swashbuckler
- Copy 1: [Ambitious Assassin, Enlightened Action, Surplus] x [Desperado, Gutshot Straight, Headseeker] — 9 combos

### Allied Demand
Sidearm · Kinetic · tiered, obtainable · GFS 271 · pool 36 combos · 1 copy · 8 combos covered
- Pool col 2 (6): Air Assault, Auto-Loading Holster, Rangefinder, Rapid Hit, Subsistence, Well-Rounded
- Pool col 3 (6): Eye of the Storm, Frenzy, Gutshot Straight, Iron Reach, Multikill Clip, Under-Over
- Copy 1: [Auto-Loading Holster, Rangefinder, Rapid Hit] x [Gutshot Straight, Iron Reach, Under-Over] — 8 combos

### Compass Rose
Shotgun · Solar · tiered, obtainable · GFS 368 · pool 49 combos · 1 copy · 8 combos covered
- Pool col 2 (7): Dual Loader, Grave Robber, Slickdraw, Slideshot, Threat Detector, Threat Remover, To the Pain
- Pool col 3 (7): Barrel Constrictor, Incandescent, One-Two Punch, Opening Shot, Snapshot Sights, Trench Barrel, Vorpal Weapon
- Copy 1: [Grave Robber, Threat Remover, To the Pain] x [Barrel Constrictor, Opening Shot, Snapshot Sights] — 8 combos

### Luna's Howl
Hand Cannon · Solar · tiered, obtainable · GFS 386 · pool 49 combos · 1 copy · 8 combos covered
- Pool col 2 (7): Discord, Encore, Enlightened Action, Eye of the Storm, Heal Clip, Slideshot, Subsistence
- Pool col 3 (7): Desperate Measures, Harmony, Incandescent, Kill Clip, Magnificent Howl, Opening Shot, Precision Instrument
- Copy 1: [Discord, Encore, Eye of the Storm] x [Harmony, Incandescent, Magnificent Howl] — 8 combos

### Ouster Engine
Grenade Launcher · Stasis · tiered, vendor 6-perk, obtainable · GFS 271 · pool 36 combos · 1 copy · 8 combos covered
- Pool col 2 (6): Air Trigger, Auto-Loading Holster, Blast Distributor, Envious Assassin, Rimestealer, Stats for All
- Pool col 3 (6): Aggregate Charge, Chain Reaction, Chaos Reshaped, Crystalline Corpsebloom, One for All, Vorpal Weapon
- Copy 1: [Air Trigger, Auto-Loading Holster, Rimestealer] x [Chaos Reshaped, Crystalline Corpsebloom, Vorpal Weapon] — 8 combos

### Roar of the Bear
Rocket Launcher · Solar · tiered, obtainable · GFS 311 · pool 36 combos · 1 copy · 8 combos covered
- Pool col 2 (6): Ambitious Assassin, Demolitionist, Field Prep, Impulse Amplifier, Snapshot Sights, Tracking Module
- Pool col 3 (6): Auto-Loading Holster, Chain Reaction, Cluster Bomb, Incandescent, Lasting Impression, Vorpal Weapon
- Copy 1: [Impulse Amplifier, Snapshot Sights, Tracking Module] x [Auto-Loading Holster, Incandescent, Lasting Impression] — 8 combos

### The Last Dance
Sidearm · Arc · tiered, vendor 6-perk, obtainable · GFS 332 · pool 36 combos · 1 copy · 8 combos covered
- Pool col 2 (6): Full Auto Trigger System, Moving Target, Outlaw, Quickdraw, Threat Detector, Under Pressure
- Pool col 3 (6): Dragonfly, Kill Clip, Opening Shot, Rangefinder, Tap the Trigger, Zen Moment
- Copy 1: [Full Auto Trigger System, Quickdraw, Under Pressure] x [Dragonfly, Tap the Trigger, Zen Moment] — 8 combos

### Tusk of the Boar
Grenade Launcher · Strand · tiered, obtainable · GFS 264 · pool 36 combos · 1 copy · 8 combos covered
- Pool col 2 (6): Enlightened Action, Envious Assassin, Grave Robber, Pulse Monitor, Slice, Slideways
- Pool col 3 (6): Bait and Switch, Chain Reaction, Deconstruct, Hatchling, Swashbuckler, Vorpal Weapon
- Copy 1: [Grave Robber, Pulse Monitor, Slideways] x [Bait and Switch, Deconstruct, Hatchling] — 8 combos

### Admetus-D
Scout Rifle · Void · tiered, obtainable · GFS 290 · pool 36 combos · 1 copy · 7 combos covered
- Pool col 2 (6): Keep Away, Lone Wolf, Rapid Hit, Recycled Energy, Repulsor Brace, To the Pain
- Pool col 3 (6): Closing Time, Demoralize, Elemental Honing, Frenzy, Precision Instrument, Withering Gaze
- Copy 1: [Rapid Hit, Recycled Energy, Repulsor Brace] x [Closing Time, Elemental Honing, Withering Gaze] — 7 combos

### Brass Attacks
Sidearm · Void · tiered, obtainable · GFS 374 · pool 36 combos · 1 copy · 7 combos covered
- Pool col 2 (6): Impromptu Ammunition, Killing Wind, Rapid Hit, Repulsor Brace, Slideways, Threat Detector
- Pool col 3 (6): Demoralize, Destabilizing Rounds, Dragonfly, Frenzy, One for All, Rampage
- Copy 1: [Impromptu Ammunition, Slideways, Threat Detector] x [Demoralize, Dragonfly, Frenzy] — 7 combos

### Cruel Mercy
Pulse Rifle · Arc · tiered, vendor 6-perk, obtainable · GFS 372 · pool 36 combos · 1 copy · 7 combos covered
- Pool col 2 (6): Demolitionist, Dragonfly, Eddy Current, Fourth Time's the Charm, Keep Away, Lone Wolf
- Pool col 3 (6): Adrenaline Junkie, Desperado, Frenzy, Headseeker, Kill Clip, Rolling Storm
- Copy 1: [Dragonfly, Eddy Current, Fourth Time's the Charm] x [Desperado, Headseeker, Rolling Storm] — 7 combos

### Glissando-47
Scout Rifle · Strand · tiered, obtainable · GFS 283 · pool 36 combos · 1 copy · 7 combos covered
- Pool col 2 (6): Discord, Keep Away, No Distractions, Overflow, Perfect Float, Reconstruction
- Pool col 3 (6): Box Breathing, Cascade Point, Harmony, Hatchling, One for All, Opening Shot
- Copy 1: [Discord, Overflow, Reconstruction] x [Box Breathing, Cascade Point, One for All] — 7 combos

### Imperial Decree
Shotgun · Kinetic · tiered, craftable, obtainable · GFS 349 · pool 36 combos · 1 copy · 7 combos covered
- Pool col 2 (6): Feeding Frenzy, Full Auto Trigger System, Grave Robber, Pulse Monitor, Slideshot, Threat Detector
- Pool col 3 (6): Auto-Loading Holster, Moving Target, Rampage, Snapshot Sights, Swashbuckler, Trench Barrel
- Copy 1: [Feeding Frenzy, Full Auto Trigger System, Grave Robber] x [Auto-Loading Holster, Rampage, Trench Barrel] — 7 combos

### MIDA Macro-Tool
Shotgun · Arc · tiered, vendor 6-perk, obtainable · GFS 292 · pool 36 combos · 1 copy · 7 combos covered
- Pool col 2 (6): Discord, Envious Assassin, Grave Robber, Lone Wolf, Slideshot, Threat Detector
- Pool col 3 (6): Closing Time, Master of Arms, One-Two Punch, Opening Shot, Rolling Storm, Trench Barrel
- Copy 1: [Discord, Envious Assassin, Grave Robber] x [One-Two Punch, Rolling Storm, Trench Barrel] — 7 combos

### Perfect Pitch
Submachine Gun · Solar · tiered, vendor 6-perk, obtainable · GFS 408 · pool 49 combos · 1 copy · 7 combos covered
- Pool col 2 (7): Discord, Dynamic Sway Reduction, Enlightened Action, Heal Clip, Keep Away, Subsistence, To the Pain
- Pool col 3 (7): Focused Fury, Harmony, Incandescent, Onslaught, Rampage, Rangefinder, Target Lock
- Copy 1: [Discord, Heal Clip, To the Pain] x [Focused Fury, Onslaught, Rangefinder] — 7 combos

### Pressurized Precision
Fusion Rifle · Strand · tiered, obtainable · GFS 426 · pool 49 combos · 1 copy · 7 combos covered
- Pool col 2 (7): Auto-Loading Holster, Discord, Firmly Planted, Lone Wolf, Moving Target, Perpetual Motion, Under Pressure
- Pool col 3 (7): Closing Time, Eye of the Storm, Hatchling, High-Impact Reserves, Kickstart, Rangefinder, Vorpal Weapon
- Copy 1: [Auto-Loading Holster, Discord, Moving Target] x [Closing Time, Hatchling, Kickstart] — 7 combos

### Riiswalker
Shotgun · Kinetic · tiered, obtainable · GFS 275 · pool 36 combos · 1 copy · 7 combos covered
- Pool col 2 (6): Discord, Killing Wind, Shot Swap, Slickdraw, Slideshot, Surplus
- Pool col 3 (6): Adagio, Fragile Focus, Harmony, Iron Reach, Opening Shot, Vorpal Weapon
- Copy 1: [Discord, Shot Swap, Slickdraw] x [Adagio, Fragile Focus, Iron Reach] — 7 combos

### Scintillation
Linear Fusion Rifle · Strand · tiered, vendor 6-perk, obtainable · GFS 193 · pool 36 combos · 1 copy · 7 combos covered
- Pool col 2 (6): Auto-Loading Holster, Cornered, Envious Assassin, Rapid Hit, Rewind Rounds, Slice
- Pool col 3 (6): Attrition Orbs, Bait and Switch, Firing Line, Hatchling, Reservoir Burst, Surrounded
- Copy 1: [Auto-Loading Holster, Cornered, Slice] x [Attrition Orbs, Bait and Switch, Firing Line] — 7 combos

### Synanceia
Sword · Solar · tiered, obtainable · GFS 185 · pool 36 combos · 1 copy · 7 combos covered
- Pool col 2 (6): Assassin's Blade, Attrition Orbs, Proximity Power, Relentless Strikes, Sharp Harvest, Wellspring
- Pool col 3 (6): Binary Orbit, Burning Ambition, Chain Reaction, Eager Edge, Elemental Honing, Surrounded
- Copy 1: [Assassin's Blade, Attrition Orbs, Sharp Harvest] x [Binary Orbit, Burning Ambition, Elemental Honing] — 7 combos

### The Hothead
Rocket Launcher · Arc · tiered, vendor 6-perk, obtainable · GFS 273 · pool 36 combos · 1 copy · 7 combos covered
- Pool col 2 (6): Auto-Loading Holster, Demolitionist, Envious Arsenal, Impulse Amplifier, Reconstruction, Tracking Module
- Pool col 3 (6): Aggregate Charge, Bait and Switch, Bipod, Clown Cartridge, Elemental Honing, Explosive Light
- Copy 1: [Envious Arsenal, Reconstruction, Tracking Module] x [Aggregate Charge, Bait and Switch, Clown Cartridge] — 7 combos

### The Other Half
Sword · Void · tiered, craftable, obtainable · GFS 172 · pool 25 combos · 1 copy · 7 combos covered
- Pool col 2 (5): Duelist's Trance, Eager Edge, Energy Transfer, Flash Counter, Relentless Strikes
- Pool col 3 (5): Frenzy, Repulsor Brace, Surrounded, Vorpal Weapon, Whirlwind Blade
- Copy 1: [Duelist's Trance, Eager Edge, Relentless Strikes] x [Frenzy, Repulsor Brace, Whirlwind Blade] — 7 combos

### Evening SI4
Sidearm · Solar · tiered, vendor 6-perk, obtainable · GFS 221 · pool 36 combos · 1 copy · 6 combos covered
- Pool col 2 (6): Heal Clip, Impromptu Ammunition, Lone Wolf, Offhand Strike, Proximity Power, Subsistence
- Pool col 3 (6): Burning Ambition, Collective Pugilism, Desperate Measures, Headseeker, Incandescent, Sword Logic
- Copy 1: [Heal Clip, Impromptu Ammunition, Offhand Strike] x [Burning Ambition, Collective Pugilism, Sword Logic] — 6 combos

### Gridskipper
Pulse Rifle · Void · tiered, obtainable · GFS 424 · pool 36 combos · 1 copy · 6 combos covered
- Pool col 2 (6): Demolitionist, Killing Wind, Lone Wolf, Perpetual Motion, Repulsor Brace, Zen Moment
- Pool col 3 (6): Desperate Measures, Destabilizing Rounds, Elemental Capacitor, Frenzy, Headseeker, Multikill Clip
- Copy 1: [Perpetual Motion, Repulsor Brace, Zen Moment] x [Elemental Capacitor, Headseeker, Multikill Clip] — 6 combos

### Half-Truths
Sword · Arc · tiered, craftable, obtainable · GFS 192 · pool 25 combos · 1 copy · 6 combos covered
- Pool col 2 (5): Duelist's Trance, Relentless Strikes, Thresh, Tireless Blade, Unrelenting
- Pool col 3 (5): Assassin's Blade, Chain Reaction, Eager Edge, En Garde, Harmony
- Copy 1: [Thresh, Tireless Blade, Unrelenting] x [Assassin's Blade, Eager Edge, Harmony] — 6 combos

### Horror Story
Auto Rifle · Stasis · tiered, obtainable · GFS 468 · pool 49 combos · 1 copy · 6 combos covered
- Pool col 2 (7): Demolitionist, Discord, Dynamic Sway Reduction, Elemental Capacitor, Enlightened Action, Envious Assassin, Under-Over
- Pool col 3 (7): Adrenaline Junkie, Cascade Point, Collective Action, Frenzy, Headstone, Target Lock, Vorpal Weapon
- Copy 1: [Dynamic Sway Reduction, Elemental Capacitor, Under-Over] x [Adrenaline Junkie, Headstone, Vorpal Weapon] — 6 combos

### Horror's Least
Pulse Rifle · Arc · tiered, vendor 6-perk, obtainable · GFS 444 · pool 36 combos · 1 copy · 6 combos covered
- Pool col 2 (6): Compulsive Reloader, Heating Up, Perpetual Motion, Steady Hands, Under Pressure, Zen Moment
- Pool col 3 (6): Focused Fury, Frenzy, High-Impact Reserves, Kill Clip, Turnabout, Vorpal Weapon
- Copy 1: [Heating Up, Steady Hands, Zen Moment] x [High-Impact Reserves, Kill Clip, Turnabout] — 6 combos

### Mercury-A
Combat Bow · Kinetic · tiered, vendor 6-perk, obtainable · GFS 260 · pool 36 combos · 1 copy · 6 combos covered
- Pool col 2 (6): Attrition Orbs, Built to Blast, Demolitionist, Rapid Hit, Successful Warm-Up, Tunnel Vision
- Pool col 3 (6): Adagio, Adrenaline Junkie, Elemental Honing, High Ground, Kinetic Tremors, Precision Instrument
- Copy 1: [Attrition Orbs, Built to Blast, Successful Warm-Up] x [Adrenaline Junkie, High Ground, Kinetic Tremors] — 6 combos

### Ogma PR6
Pulse Rifle · Solar · tiered, obtainable · GFS 404 · pool 36 combos · 1 copy · 6 combos covered
- Pool col 2 (6): Adaptive Munitions, Demolitionist, Heating Up, Perpetual Motion, Stats for All, Unrelenting
- Pool col 3 (6): Adrenaline Junkie, Disruption Break, Dragonfly, One for All, Turnabout, Wellspring
- Copy 1: [Adaptive Munitions, Heating Up, Unrelenting] x [Disruption Break, Dragonfly, Wellspring] — 6 combos

### Perfect Paradox
Shotgun · Kinetic · tiered, obtainable · GFS 391 · pool 36 combos · 1 copy · 6 combos covered
- Pool col 2 (6): Demolitionist, Field Prep, Firmly Planted, Pulse Monitor, Slideshot, Threat Detector
- Pool col 3 (6): Eye of the Storm, One-Two Punch, Opening Shot, Rampage, Swashbuckler, Trench Barrel
- Copy 1: [Demolitionist, Field Prep, Firmly Planted] x [One-Two Punch, Swashbuckler, Trench Barrel] — 6 combos

### Redrix's Estoc
Pulse Rifle · Stasis · tiered, vendor 6-perk, obtainable · GFS 407 · pool 49 combos · 1 copy · 6 combos covered
- Pool col 2 (7): Demolitionist, Encore, Lone Wolf, Offhand Strike, Perpetual Motion, Rimestealer, Zen Moment
- Pool col 3 (7): Desperado, Desperate Measures, Headseeker, Headstone, Kill Clip, Rapid Hit, Sword Logic
- Copy 1: [Lone Wolf, Perpetual Motion, Rimestealer] x [Desperado, Headseeker, Rapid Hit] — 6 combos

### The Helmsman
Sniper Rifle · Arc · tiered, vendor 6-perk, obtainable · GFS 301 · pool 36 combos · 1 copy · 6 combos covered
- Pool col 2 (6): Discord, Explosive Payload, Light Touch, Lone Wolf, No Distractions, Snapshot Sights
- Pool col 3 (6): Box Breathing, Closing Time, Elemental Honing, Gear Shift, Opening Shot, Vorpal Weapon
- Copy 1: [Explosive Payload, Lone Wolf, No Distractions] x [Box Breathing, Elemental Honing, Gear Shift] — 6 combos

### Tomorrow's Answer
Rocket Launcher · Void · tiered, obtainable · GFS 352 · pool 49 combos · 1 copy · 6 combos covered
- Pool col 2 (7): Air Trigger, Danger Zone, Envious Arsenal, Envious Assassin, Impulse Amplifier, Tracking Module, Withering Gaze
- Pool col 3 (7): Bait and Switch, Bipod, Chain Reaction, Cluster Bomb, Explosive Light, Frenzy, Vorpal Weapon
- Copy 1: [Envious Arsenal, Envious Assassin, Withering Gaze] x [Bipod, Cluster Bomb, Frenzy] — 6 combos

### Wishbringer
Shotgun · Solar · vendor 6-perk, obtainable · GFS 328 · pool 30 combos · 1 copy · 6 combos covered
- Pool col 2 (6): Field Prep, Grave Robber, Hip-Fire Grip, Pulse Monitor, Slideshot, Threat Detector
- Pool col 3 (5): Auto-Loading Holster, Moving Target, Opening Shot, Rampage, Snapshot Sights
- Copy 1: [Pulse Monitor, Slideshot, Threat Detector] x [Auto-Loading Holster, Moving Target, Rampage] — 6 combos

### Chroma Rush
Auto Rifle · Kinetic · tiered, obtainable · GFS 428 · pool 36 combos · 1 copy · 5 combos covered
- Pool col 2 (6): Dynamic Sway Reduction, Heating Up, Killing Wind, Subsistence, To the Pain, Tunnel Vision
- Pool col 3 (6): Frenzy, Kill Clip, Kinetic Tremors, Rampage, Tap the Trigger, Target Lock
- Copy 1: [Dynamic Sway Reduction, To the Pain, Tunnel Vision] x [Kinetic Tremors, Target Lock] — 5 combos

### Crimil's Dagger
Hand Cannon · Kinetic · tiered, obtainable · GFS 526 · pool 60 combos · 1 copy · 5 combos covered
- Pool col 2 (9): Auto-Loading Holster, Explosive Payload, Hip-Fire Grip, Moving Target, Outlaw, Rangefinder, Snapshot Sights, Threat Detector, Triple Tap
- Pool col 3 (7): Explosive Payload, Field Prep, Hip-Fire Grip, Kill Clip, Opening Shot, Timed Payload, Zen Moment
- Copy 1: [Moving Target, Rangefinder, Snapshot Sights] x [Explosive Payload, Timed Payload, Zen Moment] — 5 combos

### Lionfish-4fr
Fusion Rifle · Stasis · tiered, vendor 6-perk, obtainable · GFS 190 · pool 36 combos · 1 copy · 5 combos covered
- Pool col 2 (6): Lead from Gold, Proximity Power, Reconstruction, Rimestealer, Subsistence, Transcendent Moment
- Pool col 3 (6): Binary Orbit, Chill Clip, Controlled Burst, Elemental Honing, Reservoir Burst, Swashbuckler
- Copy 1: [Proximity Power, Rimestealer, Transcendent Moment] x [Controlled Burst, Reservoir Burst] — 5 combos

### Spoiler Alert
Sidearm · Kinetic · tiered, vendor 6-perk, obtainable · GFS 432 · pool 36 combos · 1 copy · 5 combos covered
- Pool col 2 (6): Feeding Frenzy, Killing Wind, Surplus, Threat Detector, Tunnel Vision, Under Pressure
- Pool col 3 (6): Demolitionist, Frenzy, High-Impact Reserves, Osmosis, Swashbuckler, Unrelenting
- Copy 1: [Surplus, Tunnel Vision, Under Pressure] x [High-Impact Reserves, Swashbuckler, Unrelenting] — 5 combos

### Temptation's Hook
Sword · Arc · tiered, obtainable · GFS 306 · pool 36 combos · 1 copy · 5 combos covered
- Pool col 2 (6): Attrition Orbs, Duelist's Trance, Energy Transfer, Relentless Strikes, Tireless Blade, Wellspring
- Pool col 3 (6): Assassin's Blade, Chain Reaction, Collective Action, En Garde, Valiant Charge, Whirlwind Blade
- Copy 1: [Attrition Orbs, Tireless Blade, Wellspring] x [Collective Action, En Garde, Valiant Charge] — 5 combos

### The Recluse
Submachine Gun · Void · tiered, obtainable · GFS 518 · pool 49 combos · 1 copy · 5 combos covered
- Pool col 2 (7): Dynamic Sway Reduction, Enlightened Action, Feeding Frenzy, Hip-Fire Grip, Repulsor Brace, Subsistence, Threat Detector
- Pool col 3 (7): Desperate Measures, Destabilizing Rounds, Frenzy, Master of Arms, Surrounded, Tap the Trigger, Target Lock
- Copy 1: [Hip-Fire Grip, Subsistence, Threat Detector] x [Desperate Measures, Destabilizing Rounds, Master of Arms] — 5 combos

### Timeworn Wayfarer
Scout Rifle · Solar · tiered, craftable, obtainable · GFS 581 · pool 63 combos · 1 copy · 5 combos covered
- Pool col 2 (8): Dual Loader, Empty Traits Socket, Fourth Time's the Charm, Heal Clip, Keep Away, Shoot to Loot, Strategist, To the Pain
- Pool col 3 (8): Desperate Measures, Empty Traits Socket, Eye of the Storm, High Ground, Incandescent, Opening Shot, Precision Instrument, Snapshot Sights
- Copy 1: [Dual Loader, Strategist, To the Pain] x [Desperate Measures, Eye of the Storm, Incandescent] — 5 combos

### Trust
Hand Cannon · Solar · tiered, vendor 6-perk, obtainable · GFS 245 · pool 30 combos · 1 copy · 5 combos covered
- Pool col 2 (6): Dragonfly, Genesis, Opening Shot, Outlaw, Snapshot Sights, Triple Tap
- Pool col 3 (5): Explosive Payload, Hip-Fire Grip, Rampage, Rapid Hit, Zen Moment
- Copy 1: [Genesis, Triple Tap] x [Explosive Payload, Hip-Fire Grip, Rapid Hit] — 5 combos

### Bug-Out Bag
Submachine Gun · Solar · tiered, vendor 6-perk, obtainable · GFS 256 · pool 36 combos · 1 copy · 4 combos covered
- Pool col 2 (6): Air Assault, Gutshot Straight, Perpetual Motion, Slideways, Subsistence, Threat Detector
- Pool col 3 (6): Collective Action, Fragile Focus, Incandescent, Killing Wind, Multikill Clip, Swashbuckler
- Copy 1: [Air Assault, Gutshot Straight, Slideways] x [Collective Action, Incandescent, Swashbuckler] — 4 combos

### Lethal Abundance
Auto Rifle · Strand · tiered, obtainable · GFS 264 · pool 36 combos · 1 copy · 4 combos covered
- Pool col 2 (6): Discord, Dynamic Sway Reduction, Elemental Capacitor, Enlightened Action, Keep Away, Slice
- Pool col 3 (6): Attrition Orbs, Collective Action, Hatchling, Onslaught, Tap the Trigger, Target Lock
- Copy 1: [Discord, Elemental Capacitor, Slice] x [Onslaught, Target Lock] — 4 combos

### Lonesome
Sidearm · Kinetic · tiered, vendor 6-perk, obtainable · GFS 325 · pool 30 combos · 1 copy · 4 combos covered
- Pool col 2 (5): Full Auto Trigger System, Grave Robber, Outlaw, Rapid Hit, Zen Moment
- Pool col 3 (6): Demolitionist, Kill Clip, Multikill Clip, Opening Shot, Slideshot, Swashbuckler
- Copy 1: [Full Auto Trigger System, Grave Robber] x [Kill Clip, Multikill Clip, Slideshot] — 4 combos

### Yesterday's Question
Hand Cannon · Arc · tiered, obtainable · GFS 337 · pool 49 combos · 1 copy · 4 combos covered
- Pool col 2 (7): Air Trigger, Closing Time, Dragonfly, Fourth Time's the Charm, Lone Wolf, Rapid Hit, To the Pain
- Pool col 3 (7): Desperate Measures, Eye of the Storm, Headseeker, Moving Target, Voltshot, Vorpal Weapon, Zen Moment
- Copy 1: [Air Trigger, To the Pain] x [Headseeker, Moving Target, Zen Moment] — 4 combos

### Goldtusk
Sword · Void · tiered, obtainable · GFS 154 · pool 12 combos · 1 copy · 3 combos covered
- Pool col 2 (4): En Garde, Energy Transfer, Relentless Strikes, Tireless Blade
- Pool col 3 (3): Assassin's Blade, Surrounded, Whirlwind Blade
- Copy 1: [En Garde, Tireless Blade] x [Surrounded, Whirlwind Blade] — 3 combos

### Peacebond
Sidearm · Stasis · tiered, obtainable · GFS 358 · pool 36 combos · 1 copy · 3 combos covered
- Pool col 2 (6): Headstone, Lone Wolf, Moving Target, Rangefinder, Subsistence, Zen Moment
- Pool col 3 (6): Desperado, Desperate Measures, Frenzy, Headseeker, Kill Clip, Rimestealer
- Copy 1: [Headstone] x [Desperado, Headseeker, Kill Clip] — 3 combos

### Night Watch
Scout Rifle · Kinetic · tiered, vendor 6-perk, obtainable · GFS 326 · pool 25 combos · 1 copy · 2 combos covered
- Pool col 2 (5): Outlaw, Rapid Hit, Snapshot Sights, Subsistence, Threat Detector
- Pool col 3 (5): Demolitionist, Explosive Payload, Moving Target, Multikill Clip, Rampage
- Copy 1: [Snapshot Sights, Subsistence] x [Moving Target, Multikill Clip] — 2 combos

### Rose
Hand Cannon · Kinetic · tiered, vendor 6-perk, obtainable · GFS 1 · pool 1 combos · 1 copy · 1 combo covered
- Pool col 2 (1): Outlaw
- Pool col 3 (1): Polymer Grip
- Copy 1: [Outlaw] x [Polymer Grip] — 1 combo

## 1x1 gap-fill guns

These guns drop with one perk per column, so each copy is worth exactly one combination — and each of these combinations exists on no 3x3 gun.


### Posterity
Hand Cannon · Arc · craftable · GFS 1,006 · pool 144 combos · 32 copies · 32 combos covered
- Pool col 2 (12): Feeding Frenzy, Fourth Time's the Charm, Genesis, Killing Wind, Perfect Float, Rapid Hit, Reconstruction, Supercharged Magazine, Surplus, Trickle Charge, Voltshot, Wellspring
- Pool col 3 (12): Demolitionist, Explosive Payload, Focused Fury, Frenzy, Gutshot Straight, One for All, Opening Shot, Pugilist, Rampage, Redirection, Rolling Storm, Unrelenting
- Copy 1: Trickle Charge + Demolitionist
- Copy 2: Supercharged Magazine + Explosive Payload
- Copy 3: Wellspring + Explosive Payload
- Copy 4: Supercharged Magazine + Focused Fury
- Copy 5: Trickle Charge + Focused Fury
- Copy 6: Voltshot + Focused Fury
- Copy 7: Wellspring + Focused Fury
- Copy 8: Supercharged Magazine + Frenzy
- Copy 9: Genesis + Gutshot Straight
- Copy 10: Genesis + Redirection
- Copy 11: Reconstruction + Gutshot Straight
- Copy 12: Supercharged Magazine + Gutshot Straight
- Copy 13: Voltshot + Gutshot Straight
- Copy 14: Perfect Float + Redirection
- Copy 15: Perfect Float + Unrelenting
- Copy 16: Reconstruction + Pugilist
- Copy 17: Trickle Charge + Pugilist
- Copy 18: Voltshot + Redirection
- Copy 19: Supercharged Magazine + Unrelenting
- Copy 20: Trickle Charge + Unrelenting
- Copy 21: Trickle Charge + Explosive Payload
- Copy 22: Feeding Frenzy + Redirection
- Copy 23: Fourth Time's the Charm + Redirection
- Copy 24: Genesis + Rolling Storm
- Copy 25: Wellspring + Gutshot Straight
- Copy 26: Supercharged Magazine + One for All
- Copy 27: Rapid Hit + Pugilist
- Copy 28: Wellspring + Rampage
- Copy 29: Reconstruction + Rampage
- Copy 30: Reconstruction + Unrelenting
- Copy 31: Surplus + Redirection
- Copy 32: Killing Wind + Redirection

### Succession
Sniper Rifle · Kinetic · craftable · GFS 748 · pool 121 combos · 30 copies · 30 combos covered
- Pool col 2 (11): Demolitionist, Discord, Firmly Planted, Killing Wind, Lead from Gold, Moving Target, No Distractions, Reconstruction, Shot Swap, Slideways, Stopping Power
- Pool col 3 (11): Box Breathing, Elemental Honing, Firing Line, Focused Fury, Osmosis, Rampage, Recombination, Redirection, Snapshot Sights, Thresh, Vorpal Weapon
- Copy 1: Shot Swap + Box Breathing
- Copy 2: Slideways + Box Breathing
- Copy 3: Discord + Osmosis
- Copy 4: Discord + Recombination
- Copy 5: Discord + Thresh
- Copy 6: Firmly Planted + Elemental Honing
- Copy 7: Shot Swap + Elemental Honing
- Copy 8: Slideways + Elemental Honing
- Copy 9: Firmly Planted + Osmosis
- Copy 10: Firmly Planted + Recombination
- Copy 11: Firmly Planted + Redirection
- Copy 12: Killing Wind + Recombination
- Copy 13: Moving Target + Recombination
- Copy 14: No Distractions + Recombination
- Copy 15: Reconstruction + Osmosis
- Copy 16: Stopping Power + Osmosis
- Copy 17: Shot Swap + Recombination
- Copy 18: Slideways + Recombination
- Copy 19: Stopping Power + Recombination
- Copy 20: Shot Swap + Redirection
- Copy 21: Slideways + Redirection
- Copy 22: Stopping Power + Snapshot Sights
- Copy 23: Stopping Power + Thresh
- Copy 24: Shot Swap + Osmosis
- Copy 25: Slideways + Osmosis
- Copy 26: Stopping Power + Rampage
- Copy 27: Reconstruction + Recombination
- Copy 28: Reconstruction + Thresh
- Copy 29: Firmly Planted + Box Breathing
- Copy 30: Killing Wind + Elemental Honing

### Commemoration
Machine Gun · Void · craftable · GFS 875 · pool 143 combos · 29 copies · 29 combos covered
- Pool col 2 (12): Adaptive Munitions, Dragonfly, Dynamic Sway Reduction, Feeding Frenzy, Fourth Time's the Charm, No Distractions, Rapid Hit, Reconstruction, Subsistence, Surplus, Well-Rounded, Zen Moment
- Pool col 3 (12): Dragonfly, Eye of the Storm, Firing Line, Focused Fury, High-Impact Reserves, Killing Tally, Moving Target, Rampage, Redirection, Repulsor Brace, Under Pressure, Unrelenting
- Copy 1: Adaptive Munitions + Firing Line
- Copy 2: Adaptive Munitions + High-Impact Reserves
- Copy 3: Adaptive Munitions + Rampage
- Copy 4: Adaptive Munitions + Redirection
- Copy 5: Dragonfly + Killing Tally
- Copy 6: Dragonfly + Redirection
- Copy 7: Dynamic Sway Reduction + Redirection
- Copy 8: Dynamic Sway Reduction + Under Pressure
- Copy 9: Well-Rounded + Firing Line
- Copy 10: Zen Moment + Firing Line
- Copy 11: Fourth Time's the Charm + Repulsor Brace
- Copy 12: Well-Rounded + High-Impact Reserves
- Copy 13: Zen Moment + Killing Tally
- Copy 14: No Distractions + Repulsor Brace
- Copy 15: No Distractions + Under Pressure
- Copy 16: Reconstruction + Repulsor Brace
- Copy 17: Reconstruction + Under Pressure
- Copy 18: Well-Rounded + Redirection
- Copy 19: Well-Rounded + Under Pressure
- Copy 20: Adaptive Munitions + Killing Tally
- Copy 21: Reconstruction + Dragonfly
- Copy 22: Feeding Frenzy + Firing Line
- Copy 23: No Distractions + Killing Tally
- Copy 24: Surplus + Killing Tally
- Copy 25: Well-Rounded + Killing Tally
- Copy 26: Well-Rounded + Moving Target
- Copy 27: Rapid Hit + Repulsor Brace
- Copy 28: Surplus + Under Pressure
- Copy 29: Dragonfly + Firing Line

### Tyranny of Heaven
Combat Bow · Solar · craftable · GFS 703 · pool 109 combos · 29 copies · 29 combos covered
- Pool col 2 (10): Archer's Tempo, Burning Ambition, Dragonfly, Empty Traits Socket, Explosive Head, Meganeura, Moving Target, Pugilist, Successful Warm-Up, Wellspring
- Pool col 3 (11): Adagio, Archer's Gambit, Collective Action, Empty Traits Socket, Frenzy, Golden Tricorn, Golden Tricorn Enhanced, Incandescent, One for All, Snapshot Sights, Swashbuckler
- Copy 1: Explosive Head + Adagio
- Copy 2: Meganeura + Adagio
- Copy 3: Wellspring + Adagio
- Copy 4: Burning Ambition + Archer's Gambit
- Copy 5: Explosive Head + Archer's Gambit
- Copy 6: Meganeura + Archer's Gambit
- Copy 7: Moving Target + Archer's Gambit
- Copy 8: Pugilist + Archer's Gambit
- Copy 9: Archer's Tempo + Collective Action
- Copy 10: Burning Ambition + Golden Tricorn
- Copy 11: Burning Ambition + Golden Tricorn Enhanced
- Copy 12: Burning Ambition + One for All
- Copy 13: Explosive Head + Collective Action
- Copy 14: Dragonfly + Incandescent
- Copy 15: Explosive Head + Frenzy
- Copy 16: Explosive Head + Golden Tricorn
- Copy 17: Explosive Head + Golden Tricorn Enhanced
- Copy 18: Explosive Head + One for All
- Copy 19: Meganeura + Frenzy
- Copy 20: Meganeura + Incandescent
- Copy 21: Successful Warm-Up + Incandescent
- Copy 22: Meganeura + One for All
- Copy 23: Meganeura + Swashbuckler
- Copy 24: Empty Traits Socket + Archer's Gambit
- Copy 25: Wellspring + Archer's Gambit
- Copy 26: Archer's Tempo + Snapshot Sights
- Copy 27: Wellspring + Swashbuckler
- Copy 28: Archer's Tempo + Empty Traits Socket
- Copy 29: Explosive Head + Empty Traits Socket

### Heritage
Shotgun · Kinetic · craftable · GFS 724 · pool 121 combos · 28 copies · 28 combos covered
- Pool col 2 (11): Auto-Loading Holster, Demolitionist, Dual Loader, Envious Arsenal, Hip-Fire Grip, Outlaw, Pugilist, Reconstruction, Redirection, Slideshot, Threat Detector
- Pool col 3 (11): Aggregate Charge, Cascade Point, Focused Fury, Killing Wind, Moving Target, Offhand Strike, Recombination, Snapshot Sights, Swashbuckler, Thresh, Unrelenting
- Copy 1: Dual Loader + Aggregate Charge
- Copy 2: Outlaw + Aggregate Charge
- Copy 3: Outlaw + Cascade Point
- Copy 4: Redirection + Cascade Point
- Copy 5: Dual Loader + Moving Target
- Copy 6: Envious Arsenal + Focused Fury
- Copy 7: Envious Arsenal + Killing Wind
- Copy 8: Envious Arsenal + Offhand Strike
- Copy 9: Envious Arsenal + Recombination
- Copy 10: Envious Arsenal + Unrelenting
- Copy 11: Hip-Fire Grip + Recombination
- Copy 12: Outlaw + Killing Wind
- Copy 13: Reconstruction + Killing Wind
- Copy 14: Outlaw + Offhand Strike
- Copy 15: Redirection + Offhand Strike
- Copy 16: Slideshot + Offhand Strike
- Copy 17: Outlaw + Recombination
- Copy 18: Pugilist + Recombination
- Copy 19: Redirection + Recombination
- Copy 20: Slideshot + Recombination
- Copy 21: Redirection + Swashbuckler
- Copy 22: Auto-Loading Holster + Offhand Strike
- Copy 23: Envious Arsenal + Snapshot Sights
- Copy 24: Threat Detector + Offhand Strike
- Copy 25: Hip-Fire Grip + Cascade Point
- Copy 26: Pugilist + Cascade Point
- Copy 27: Redirection + Thresh
- Copy 28: Redirection + Unrelenting

### The Enigma
Glaive · Void · craftable · GFS 599 · pool 80 combos · 28 copies · 28 combos covered
- Pool col 2 (9): Empty Traits Socket, Feeding Frenzy, Grave Robber, Impulse Amplifier, Lead from Gold, Replenishing Aegis, Subsistence, Threat Detector, Tilting at Windmills
- Pool col 3 (9): Close to Melee, Empty Traits Socket, Frenzy, Kill Clip, Proximity Power, Rampage, Thresh, Unrelenting, Unstoppable Force
- Copy 1: Feeding Frenzy + Close to Melee
- Copy 2: Subsistence + Close to Melee
- Copy 3: Threat Detector + Close to Melee
- Copy 4: Empty Traits Socket + Proximity Power
- Copy 5: Replenishing Aegis + Empty Traits Socket
- Copy 6: Feeding Frenzy + Proximity Power
- Copy 7: Feeding Frenzy + Unstoppable Force
- Copy 8: Replenishing Aegis + Frenzy
- Copy 9: Grave Robber + Proximity Power
- Copy 10: Impulse Amplifier + Kill Clip
- Copy 11: Lead from Gold + Kill Clip
- Copy 12: Replenishing Aegis + Kill Clip
- Copy 13: Tilting at Windmills + Kill Clip
- Copy 14: Lead from Gold + Proximity Power
- Copy 15: Replenishing Aegis + Proximity Power
- Copy 16: Subsistence + Proximity Power
- Copy 17: Threat Detector + Proximity Power
- Copy 18: Tilting at Windmills + Proximity Power
- Copy 19: Replenishing Aegis + Rampage
- Copy 20: Tilting at Windmills + Rampage
- Copy 21: Replenishing Aegis + Thresh
- Copy 22: Subsistence + Unstoppable Force
- Copy 23: Threat Detector + Unstoppable Force
- Copy 24: Tilting at Windmills + Thresh
- Copy 25: Empty Traits Socket + Close to Melee
- Copy 26: Tilting at Windmills + Frenzy
- Copy 27: Tilting at Windmills + Empty Traits Socket
- Copy 28: Empty Traits Socket + Unstoppable Force

### Techeun Force
Fusion Rifle · Arc · craftable · GFS 675 · pool 109 combos · 23 copies · 23 combos covered
- Pool col 2 (10): Collective Demolition, Demolitionist, Empty Traits Socket, Envious Assassin, Kill Clip, Reconstruction, Rewind Rounds, Slideways, Threat Detector, Under Pressure
- Pool col 3 (11): Aggregate Charge, Backup Plan, Collective Action, Controlled Burst, Empty Traits Socket, Golden Tricorn, Golden Tricorn Enhanced, High-Impact Reserves, Kickstart, Rangefinder, Voltshot
- Copy 1: Kill Clip + Aggregate Charge
- Copy 2: Slideways + Aggregate Charge
- Copy 3: Collective Demolition + Backup Plan
- Copy 4: Demolitionist + Backup Plan
- Copy 5: Envious Assassin + Backup Plan
- Copy 6: Reconstruction + Backup Plan
- Copy 7: Rewind Rounds + Backup Plan
- Copy 8: Kill Clip + Collective Action
- Copy 9: Collective Demolition + Controlled Burst
- Copy 10: Collective Demolition + Golden Tricorn
- Copy 11: Collective Demolition + Golden Tricorn Enhanced
- Copy 12: Collective Demolition + Kickstart
- Copy 13: Collective Demolition + Rangefinder
- Copy 14: Kill Clip + Controlled Burst
- Copy 15: Envious Assassin + Rangefinder
- Copy 16: Kill Clip + Golden Tricorn
- Copy 17: Kill Clip + Golden Tricorn Enhanced
- Copy 18: Rewind Rounds + Kickstart
- Copy 19: Reconstruction + Rangefinder
- Copy 20: Rewind Rounds + Rangefinder
- Copy 21: Slideways + Rangefinder
- Copy 22: Empty Traits Socket + Backup Plan
- Copy 23: Envious Assassin + Voltshot

### Transfiguration
Scout Rifle · Kinetic · craftable · GFS 870 · pool 99 combos · 23 copies · 23 combos covered
- Pool col 2 (10): Adhesive Ordnance, Collective Demolition, Demolitionist, Discord, Empty Traits Socket, Keep Away, Perfect Float, Rampage, Rapid Hit, Rewind Rounds
- Pool col 3 (10): Adrenaline Junkie, Ancillary Ordinance, Collective Action, Empty Traits Socket, Explosive Payload, Harmony, Kill Clip, Kinetic Tremors, Moving Target, Opening Shot
- Copy 1: Adhesive Ordnance + Adrenaline Junkie
- Copy 2: Adhesive Ordnance + Collective Action
- Copy 3: Adhesive Ordnance + Explosive Payload
- Copy 4: Adhesive Ordnance + Harmony
- Copy 5: Adhesive Ordnance + Kill Clip
- Copy 6: Adhesive Ordnance + Kinetic Tremors
- Copy 7: Adhesive Ordnance + Opening Shot
- Copy 8: Rampage + Adrenaline Junkie
- Copy 9: Collective Demolition + Ancillary Ordinance
- Copy 10: Demolitionist + Ancillary Ordinance
- Copy 11: Discord + Ancillary Ordinance
- Copy 12: Keep Away + Ancillary Ordinance
- Copy 13: Perfect Float + Ancillary Ordinance
- Copy 14: Rewind Rounds + Ancillary Ordinance
- Copy 15: Rampage + Collective Action
- Copy 16: Collective Demolition + Kinetic Tremors
- Copy 17: Collective Demolition + Moving Target
- Copy 18: Adhesive Ordnance + Empty Traits Socket
- Copy 19: Empty Traits Socket + Ancillary Ordinance
- Copy 20: Rampage + Ancillary Ordinance
- Copy 21: Rampage + Harmony
- Copy 22: Perfect Float + Kinetic Tremors
- Copy 23: Collective Demolition + Empty Traits Socket

### Trustee
Scout Rifle · Solar · craftable · GFS 953 · pool 121 combos · 21 copies · 21 combos covered
- Pool col 2 (11): Heal Clip, Keep Away, Killing Wind, Outlaw, Perpetual Motion, Pugilist, Rapid Hit, Reconstruction, Surplus, Under Pressure, Zen Moment
- Pool col 3 (11): Burning Ambition, Eye of the Storm, Focused Fury, High-Impact Reserves, Incandescent, Meganeura, Opening Shot, Redirection, Swashbuckler, Sympathetic Arsenal, Wellspring
- Copy 1: Reconstruction + Burning Ambition
- Copy 2: Surplus + Burning Ambition
- Copy 3: Under Pressure + Burning Ambition
- Copy 4: Heal Clip + Sympathetic Arsenal
- Copy 5: Heal Clip + Wellspring
- Copy 6: Keep Away + Sympathetic Arsenal
- Copy 7: Perpetual Motion + Meganeura
- Copy 8: Under Pressure + Meganeura
- Copy 9: Zen Moment + Meganeura
- Copy 10: Outlaw + Redirection
- Copy 11: Perpetual Motion + Redirection
- Copy 12: Rapid Hit + Sympathetic Arsenal
- Copy 13: Reconstruction + Sympathetic Arsenal
- Copy 14: Under Pressure + Redirection
- Copy 15: Keep Away + Wellspring
- Copy 16: Outlaw + Sympathetic Arsenal
- Copy 17: Pugilist + Redirection
- Copy 18: Pugilist + Sympathetic Arsenal
- Copy 19: Zen Moment + Redirection
- Copy 20: Perpetual Motion + Sympathetic Arsenal
- Copy 21: Under Pressure + Sympathetic Arsenal

### Prophet of Doom
Shotgun · Arc · craftable · GFS 478 · pool 99 combos · 20 copies · 20 combos covered
- Pool col 2 (10): Air Trigger, Empty Traits Socket, Envious Arsenal, Light Touch, Pugilist, Reconstruction, Slideways, Supercharged Magazine, Threat Detector, Threat Remover
- Pool col 3 (10): Barrel Constrictor, Cascade Point, Closing Time, Empty Traits Socket, Gear Shift, Jolting Feedback, One-Two Punch, Opening Shot, Trench Barrel, Voltshot
- Copy 1: Air Trigger + Barrel Constrictor
- Copy 2: Air Trigger + Jolting Feedback
- Copy 3: Air Trigger + One-Two Punch
- Copy 4: Air Trigger + Trench Barrel
- Copy 5: Envious Arsenal + Barrel Constrictor
- Copy 6: Light Touch + Barrel Constrictor
- Copy 7: Reconstruction + Barrel Constrictor
- Copy 8: Slideways + Barrel Constrictor
- Copy 9: Supercharged Magazine + Barrel Constrictor
- Copy 10: Light Touch + Cascade Point
- Copy 11: Envious Arsenal + Gear Shift
- Copy 12: Envious Arsenal + One-Two Punch
- Copy 13: Envious Arsenal + Trench Barrel
- Copy 14: Slideways + Gear Shift
- Copy 15: Threat Detector + Jolting Feedback
- Copy 16: Threat Remover + Jolting Feedback
- Copy 17: Light Touch + One-Two Punch
- Copy 18: Light Touch + Trench Barrel
- Copy 19: Reconstruction + One-Two Punch
- Copy 20: Reconstruction + Trench Barrel

### Accrued Redemption
Combat Bow · Kinetic · craftable · GFS 546 · pool 99 combos · 19 copies · 19 combos covered
- Pool col 2 (10): Archer's Tempo, Attrition Orbs, Empty Traits Socket, Impulse Amplifier, Killing Wind, Offhand Strike, Successful Warm-Up, To the Pain, Tunnel Vision, Wellspring
- Pool col 3 (10): Adrenaline Junkie, Archer's Gambit, Empty Traits Socket, Explosive Head, Firefly, Kinetic Tremors, Lone Wolf, Precision Instrument, Rapid Hit, Swashbuckler
- Copy 1: Attrition Orbs + Archer's Gambit
- Copy 2: Offhand Strike + Archer's Gambit
- Copy 3: To the Pain + Archer's Gambit
- Copy 4: Tunnel Vision + Archer's Gambit
- Copy 5: Archer's Tempo + Kinetic Tremors
- Copy 6: Archer's Tempo + Lone Wolf
- Copy 7: Archer's Tempo + Rapid Hit
- Copy 8: Attrition Orbs + Explosive Head
- Copy 9: Offhand Strike + Explosive Head
- Copy 10: Offhand Strike + Firefly
- Copy 11: Impulse Amplifier + Kinetic Tremors
- Copy 12: Impulse Amplifier + Lone Wolf
- Copy 13: Impulse Amplifier + Rapid Hit
- Copy 14: Wellspring + Kinetic Tremors
- Copy 15: Tunnel Vision + Lone Wolf
- Copy 16: Wellspring + Precision Instrument
- Copy 17: Tunnel Vision + Rapid Hit
- Copy 18: Tunnel Vision + Explosive Head
- Copy 19: Wellspring + Explosive Head

### Nation of Beasts
Hand Cannon · Arc · craftable · GFS 789 · pool 109 combos · 19 copies · 19 combos covered
- Pool col 2 (10): Discord, Dragonfly, Eddy Current, Empty Traits Socket, Gear Shift, Hip-Fire Grip, Keep Away, Opening Shot, Perpetual Motion, Trickle Charge
- Pool col 3 (11): Collective Action, Empty Traits Socket, Explosive Payload, Golden Tricorn, Golden Tricorn Enhanced, Harmony, Jolting Feedback, Kill Clip, Offhand Strike, Rolling Storm, Voltshot
- Copy 1: Eddy Current + Collective Action
- Copy 2: Gear Shift + Collective Action
- Copy 3: Hip-Fire Grip + Collective Action
- Copy 4: Discord + Jolting Feedback
- Copy 5: Dragonfly + Jolting Feedback
- Copy 6: Gear Shift + Golden Tricorn
- Copy 7: Gear Shift + Golden Tricorn Enhanced
- Copy 8: Gear Shift + Harmony
- Copy 9: Gear Shift + Jolting Feedback
- Copy 10: Gear Shift + Kill Clip
- Copy 11: Gear Shift + Offhand Strike
- Copy 12: Opening Shot + Harmony
- Copy 13: Trickle Charge + Offhand Strike
- Copy 14: Opening Shot + Rolling Storm
- Copy 15: Gear Shift + Empty Traits Socket
- Copy 16: Trickle Charge + Golden Tricorn
- Copy 17: Trickle Charge + Golden Tricorn Enhanced
- Copy 18: Empty Traits Socket + Jolting Feedback
- Copy 19: Perpetual Motion + Explosive Payload

### Neoptolemus II
Combat Bow · Kinetic · obtainable · GFS 121 · pool 36 combos · 19 copies · 19 combos covered
- Pool col 2 (6): Air Trigger, Pugilist, Rangefinder, Slickdraw, Strategist, To the Pain
- Pool col 3 (6): Lone Wolf, Perfect Float, Sneak Bow, Tunnel Vision, Vorpal Weapon, Wellspring
- Copy 1: Air Trigger + Lone Wolf
- Copy 2: Air Trigger + Perfect Float
- Copy 3: Air Trigger + Sneak Bow
- Copy 4: Air Trigger + Tunnel Vision
- Copy 5: Air Trigger + Wellspring
- Copy 6: Pugilist + Lone Wolf
- Copy 7: Slickdraw + Lone Wolf
- Copy 8: Strategist + Lone Wolf
- Copy 9: Slickdraw + Perfect Float
- Copy 10: Strategist + Perfect Float
- Copy 11: Pugilist + Sneak Bow
- Copy 12: Rangefinder + Sneak Bow
- Copy 13: Slickdraw + Sneak Bow
- Copy 14: Slickdraw + Tunnel Vision
- Copy 15: Strategist + Sneak Bow
- Copy 16: To the Pain + Sneak Bow
- Copy 17: Strategist + Tunnel Vision
- Copy 18: To the Pain + Tunnel Vision
- Copy 19: To the Pain + Wellspring

### The Supremacy
Sniper Rifle · Kinetic · craftable · GFS 785 · pool 99 combos · 19 copies · 19 combos covered
- Pool col 2 (10): Discord, Empty Traits Socket, Genesis, Keep Away, Lead from Gold, Lone Wolf, Lucky Shot, Rapid Hit, Rewind Rounds, Snapshot Sights
- Pool col 3 (10): Bait and Switch, Bewildering Burst, Closing Time, Elemental Capacitor, Empty Traits Socket, Focused Fury, Fourth Time's the Charm, Kinetic Tremors, Opening Shot, Vorpal Weapon
- Copy 1: Genesis + Bewildering Burst
- Copy 2: Lead from Gold + Bewildering Burst
- Copy 3: Lucky Shot + Bewildering Burst
- Copy 4: Rewind Rounds + Bewildering Burst
- Copy 5: Genesis + Closing Time
- Copy 6: Discord + Fourth Time's the Charm
- Copy 7: Lucky Shot + Elemental Capacitor
- Copy 8: Lucky Shot + Focused Fury
- Copy 9: Genesis + Fourth Time's the Charm
- Copy 10: Keep Away + Fourth Time's the Charm
- Copy 11: Lucky Shot + Fourth Time's the Charm
- Copy 12: Rapid Hit + Fourth Time's the Charm
- Copy 13: Genesis + Kinetic Tremors
- Copy 14: Lead from Gold + Kinetic Tremors
- Copy 15: Lucky Shot + Bait and Switch
- Copy 16: Discord + Bewildering Burst
- Copy 17: Empty Traits Socket + Bewildering Burst
- Copy 18: Keep Away + Bewildering Burst
- Copy 19: Lucky Shot + Vorpal Weapon

### Reckless Oracle
Auto Rifle · Void · craftable · GFS 805 · pool 99 combos · 18 copies · 18 combos covered
- Pool col 2 (10): Demolitionist, Destabilizing Rounds, Dimensional Shift, Empty Traits Socket, Keep Away, Killing Wind, Light Touch, Strategist, Subsistence, Tap the Trigger
- Pool col 3 (10): Collective Action, Demoralize, Dynamic Sway Reduction, Empty Traits Socket, Kill Clip, One for All, Paracausal Affinity, Repulsor Brace, Swashbuckler, Target Lock
- Copy 1: Destabilizing Rounds + Collective Action
- Copy 2: Light Touch + Demoralize
- Copy 3: Tap the Trigger + Demoralize
- Copy 4: Destabilizing Rounds + Paracausal Affinity
- Copy 5: Dimensional Shift + Paracausal Affinity
- Copy 6: Keep Away + Dynamic Sway Reduction
- Copy 7: Killing Wind + Dynamic Sway Reduction
- Copy 8: Empty Traits Socket + Paracausal Affinity
- Copy 9: Killing Wind + Paracausal Affinity
- Copy 10: Light Touch + Repulsor Brace
- Copy 11: Tap the Trigger + One for All
- Copy 12: Strategist + Paracausal Affinity
- Copy 13: Subsistence + Paracausal Affinity
- Copy 14: Tap the Trigger + Paracausal Affinity
- Copy 15: Strategist + Repulsor Brace
- Copy 16: Dimensional Shift + Repulsor Brace
- Copy 17: Killing Wind + Repulsor Brace
- Copy 18: Light Touch + Empty Traits Socket

### Adverse Possession IX
Scout Rifle · Arc · obtainable · GFS 156 · pool 36 combos · 16 copies · 16 combos covered
- Pool col 2 (6): Compulsive Reloader, Discord, Eddy Current, Elemental Capacitor, Overflow, Threat Detector
- Pool col 3 (6): Frenzy, Heating Up, High-Impact Reserves, Keep Away, Sympathetic Arsenal, Wellspring
- Copy 1: Compulsive Reloader + Keep Away
- Copy 2: Compulsive Reloader + Sympathetic Arsenal
- Copy 3: Discord + Heating Up
- Copy 4: Discord + Sympathetic Arsenal
- Copy 5: Discord + Wellspring
- Copy 6: Eddy Current + Heating Up
- Copy 7: Eddy Current + Keep Away
- Copy 8: Eddy Current + Sympathetic Arsenal
- Copy 9: Eddy Current + Wellspring
- Copy 10: Elemental Capacitor + Sympathetic Arsenal
- Copy 11: Elemental Capacitor + Wellspring
- Copy 12: Overflow + Heating Up
- Copy 13: Threat Detector + Heating Up
- Copy 14: Overflow + Keep Away
- Copy 15: Threat Detector + Keep Away
- Copy 16: Overflow + Sympathetic Arsenal

### Age-Old Bond
Auto Rifle · Void · craftable · GFS 1,058 · pool 109 combos · 16 copies · 16 combos covered
- Pool col 2 (10): Demolitionist, Discord, Dragonfly, Dynamic Sway Reduction, Empty Traits Socket, Fourth Time's the Charm, Meganeura, Repulsor Brace, Stats for All, Tap the Trigger
- Pool col 3 (11): Adrenaline Junkie, Collective Action, Destabilizing Rounds, Empty Traits Socket, Focused Fury, Golden Tricorn, Golden Tricorn Enhanced, Harmony, Kill Clip, Rampage, Target Lock
- Copy 1: Meganeura + Focused Fury
- Copy 2: Tap the Trigger + Focused Fury
- Copy 3: Meganeura + Harmony
- Copy 4: Tap the Trigger + Harmony
- Copy 5: Meganeura + Kill Clip
- Copy 6: Meganeura + Rampage
- Copy 7: Meganeura + Target Lock
- Copy 8: Meganeura + Collective Action
- Copy 9: Tap the Trigger + Collective Action
- Copy 10: Meganeura + Empty Traits Socket
- Copy 11: Meganeura + Golden Tricorn
- Copy 12: Meganeura + Golden Tricorn Enhanced
- Copy 13: Dragonfly + Collective Action
- Copy 14: Dragonfly + Golden Tricorn
- Copy 15: Dragonfly + Golden Tricorn Enhanced
- Copy 16: Empty Traits Socket + Rampage

### Chattering Bone
Pulse Rifle · Kinetic · craftable · GFS 692 · pool 99 combos · 16 copies · 16 combos covered
- Pool col 2 (10): Ancillary Ordinance, Discord, Empty Traits Socket, Keep Away, Kill Clip, Rangefinder, Rapid Hit, Slideways, Stopping Power, Under Pressure
- Pool col 3 (10): Bewildering Burst, Elemental Capacitor, Empty Traits Socket, Focused Fury, Harmony, Headseeker, High-Impact Reserves, Kinetic Tremors, Lone Wolf, Rampage
- Copy 1: Ancillary Ordinance + Elemental Capacitor
- Copy 2: Ancillary Ordinance + Focused Fury
- Copy 3: Ancillary Ordinance + Harmony
- Copy 4: Ancillary Ordinance + Headseeker
- Copy 5: Ancillary Ordinance + High-Impact Reserves
- Copy 6: Ancillary Ordinance + Kinetic Tremors
- Copy 7: Kill Clip + Bewildering Burst
- Copy 8: Slideways + Bewildering Burst
- Copy 9: Under Pressure + Bewildering Burst
- Copy 10: Stopping Power + Elemental Capacitor
- Copy 11: Kill Clip + Focused Fury
- Copy 12: Kill Clip + Harmony
- Copy 13: Stopping Power + Harmony
- Copy 14: Stopping Power + High-Impact Reserves
- Copy 15: Slideways + Lone Wolf
- Copy 16: Stopping Power + Lone Wolf

### Omniscient Eye
Sniper Rifle · Solar · craftable · GFS 684 · pool 99 combos · 16 copies · 16 combos covered
- Pool col 2 (10): Elemental Capacitor, Empty Traits Socket, Envious Arsenal, Fourth Time's the Charm, Lead from Gold, Light Touch, Lone Wolf, Lucky Shot, Mulligan, No Distractions
- Pool col 3 (10): Box Breathing, Burning Ambition, Closing Time, Elemental Honing, Empty Traits Socket, Incandescent, Opening Shot, Precision Instrument, Snapshot Sights, Vorpal Weapon
- Copy 1: Elemental Capacitor + Box Breathing
- Copy 2: Lucky Shot + Box Breathing
- Copy 3: Mulligan + Box Breathing
- Copy 4: Lucky Shot + Burning Ambition
- Copy 5: Mulligan + Burning Ambition
- Copy 6: No Distractions + Burning Ambition
- Copy 7: Mulligan + Closing Time
- Copy 8: Envious Arsenal + Incandescent
- Copy 9: Lucky Shot + Incandescent
- Copy 10: Mulligan + Incandescent
- Copy 11: Light Touch + Precision Instrument
- Copy 12: Lucky Shot + Snapshot Sights
- Copy 13: Mulligan + Precision Instrument
- Copy 14: Mulligan + Snapshot Sights
- Copy 15: Lucky Shot + Elemental Honing
- Copy 16: Mulligan + Empty Traits Socket

### Apex Predator
Rocket Launcher · Solar · craftable · GFS 690 · pool 99 combos · 15 copies · 15 combos covered
- Pool col 2 (10): Chain Reaction, Cluster Bomb, Danger Zone, Demolitionist, Empty Traits Socket, Incandescent, Reconstruction, Slideways, Threat Detector, Tracking Module
- Pool col 3 (10): Bait and Switch, Bipod, Collective Action, Collective Demolition, Empty Traits Socket, Explosive Light, Frenzy, Reaper's Tithe, Surrounded, Vorpal Weapon
- Copy 1: Chain Reaction + Bipod
- Copy 2: Threat Detector + Bipod
- Copy 3: Chain Reaction + Collective Demolition
- Copy 4: Chain Reaction + Explosive Light
- Copy 5: Cluster Bomb + Collective Demolition
- Copy 6: Cluster Bomb + Surrounded
- Copy 7: Tracking Module + Collective Action
- Copy 8: Danger Zone + Collective Demolition
- Copy 9: Slideways + Collective Demolition
- Copy 10: Threat Detector + Collective Demolition
- Copy 11: Empty Traits Socket + Reaper's Tithe
- Copy 12: Threat Detector + Explosive Light
- Copy 13: Incandescent + Reaper's Tithe
- Copy 14: Threat Detector + Reaper's Tithe
- Copy 15: Tracking Module + Surrounded

### Likely Suspect
Fusion Rifle · Void · craftable · GFS 812 · pool 89 combos · 15 copies · 15 combos covered
- Pool col 2 (9): Dimensional Shift, Empty Traits Socket, Ensemble, Firmly Planted, Heating Up, Perpetual Motion, Repulsor Brace, Slideways, Stats for All
- Pool col 3 (10): Adagio, Collective Action, Destabilizing Rounds, Empty Traits Socket, Golden Tricorn, Golden Tricorn Enhanced, One for All, Successful Warm-Up, Turnabout, Wellspring
- Copy 1: Firmly Planted + Collective Action
- Copy 2: Ensemble + Destabilizing Rounds
- Copy 3: Firmly Planted + Destabilizing Rounds
- Copy 4: Dimensional Shift + Golden Tricorn
- Copy 5: Dimensional Shift + Golden Tricorn Enhanced
- Copy 6: Dimensional Shift + Successful Warm-Up
- Copy 7: Dimensional Shift + Turnabout
- Copy 8: Dimensional Shift + Wellspring
- Copy 9: Slideways + Successful Warm-Up
- Copy 10: Slideways + Turnabout
- Copy 11: Firmly Planted + Adagio
- Copy 12: Dimensional Shift + Empty Traits Socket
- Copy 13: Repulsor Brace + Wellspring
- Copy 14: Firmly Planted + Successful Warm-Up
- Copy 15: Slideways + Empty Traits Socket

### Pro Memoria
Machine Gun · Strand · craftable · GFS 674 · pool 99 combos · 15 copies · 15 combos covered
- Pool col 2 (10): Attrition Orbs, Demolitionist, Empty Traits Socket, Envious Assassin, Hatchling, Lucky Shot, Reconstruction, Strategist, Tear, To the Pain
- Pool col 3 (10): Bait and Switch, Collective Action, Desperate Measures, Dragonfly, Elemental Honing, Empty Traits Socket, Frenzy, Mega Kill Clip, Tap the Trigger, Target Lock
- Copy 1: Attrition Orbs + Mega Kill Clip
- Copy 2: Tear + Bait and Switch
- Copy 3: To the Pain + Bait and Switch
- Copy 4: Hatchling + Collective Action
- Copy 5: Lucky Shot + Collective Action
- Copy 6: Envious Assassin + Dragonfly
- Copy 7: Tear + Frenzy
- Copy 8: Hatchling + Mega Kill Clip
- Copy 9: Lucky Shot + Tap the Trigger
- Copy 10: Lucky Shot + Target Lock
- Copy 11: Strategist + Mega Kill Clip
- Copy 12: Tear + Mega Kill Clip
- Copy 13: To the Pain + Mega Kill Clip
- Copy 14: Strategist + Tap the Trigger
- Copy 15: Tear + Tap the Trigger

### Sacred Provenance
Pulse Rifle · Kinetic · craftable · GFS 1,014 · pool 99 combos · 15 copies · 15 combos covered
- Pool col 2 (10): Demolitionist, Empty Traits Socket, Heating Up, Keep Away, Killing Wind, Lone Wolf, Rapid Hit, Stats for All, Steady Hands, Stopping Power
- Pool col 3 (10): All-Star, Desperado, Desperate Measures, Empty Traits Socket, Firefly, Frenzy, Headseeker, Kill Clip, Kinetic Tremors, One for All
- Copy 1: Empty Traits Socket + All-Star
- Copy 2: Heating Up + All-Star
- Copy 3: Killing Wind + All-Star
- Copy 4: Stopping Power + Desperate Measures
- Copy 5: Steady Hands + Firefly
- Copy 6: Stopping Power + Kill Clip
- Copy 7: Steady Hands + Kinetic Tremors
- Copy 8: Stats for All + Desperado
- Copy 9: Heating Up + Desperate Measures
- Copy 10: Steady Hands + Desperate Measures
- Copy 11: Empty Traits Socket + Firefly
- Copy 12: Stopping Power + Empty Traits Socket
- Copy 13: Killing Wind + Firefly
- Copy 14: Empty Traits Socket + Kinetic Tremors
- Copy 15: Lone Wolf + Empty Traits Socket

### Zealot's Reward
Fusion Rifle · Void · craftable · GFS 632 · pool 99 combos · 15 copies · 15 combos covered
- Pool col 2 (10): Ambitious Assassin, Attrition Orbs, Auto-Loading Holster, Destabilizing Rounds, Empty Traits Socket, Feeding Frenzy, Lead from Gold, Repulsor Brace, Subsistence, Under Pressure
- Pool col 3 (10): Closing Time, Controlled Burst, Dimensional Shift, Empty Traits Socket, Kickstart, One for All, Rampage, Reservoir Burst, Successful Warm-Up, Withering Gaze
- Copy 1: Ambitious Assassin + Dimensional Shift
- Copy 2: Ambitious Assassin + Withering Gaze
- Copy 3: Attrition Orbs + Kickstart
- Copy 4: Attrition Orbs + Reservoir Burst
- Copy 5: Auto-Loading Holster + Dimensional Shift
- Copy 6: Destabilizing Rounds + Controlled Burst
- Copy 7: Destabilizing Rounds + Kickstart
- Copy 8: Destabilizing Rounds + Reservoir Burst
- Copy 9: Feeding Frenzy + Dimensional Shift
- Copy 10: Lead from Gold + Dimensional Shift
- Copy 11: Subsistence + Dimensional Shift
- Copy 12: Under Pressure + Dimensional Shift
- Copy 13: Repulsor Brace + Kickstart
- Copy 14: Subsistence + Kickstart
- Copy 15: Repulsor Brace + Reservoir Burst

### Come to Pass
Auto Rifle · Arc · craftable · GFS 738 · pool 89 combos · 14 copies · 14 combos covered
- Pool col 2 (9): Compulsive Reloader, Empty Traits Socket, Genesis, Perpetual Motion, Shoot to Loot, Stats for All, Supercharged Magazine, Trickle Charge, Triple Tap
- Pool col 3 (10): Adaptive Munitions, Dragonfly, Empty Traits Socket, Golden Tricorn, Golden Tricorn Enhanced, Jolting Feedback, One for All, Rolling Storm, Turnabout, Wellspring
- Copy 1: Supercharged Magazine + Adaptive Munitions
- Copy 2: Trickle Charge + Adaptive Munitions
- Copy 3: Compulsive Reloader + Jolting Feedback
- Copy 4: Supercharged Magazine + Dragonfly
- Copy 5: Trickle Charge + Dragonfly
- Copy 6: Genesis + Jolting Feedback
- Copy 7: Supercharged Magazine + Golden Tricorn
- Copy 8: Supercharged Magazine + Golden Tricorn Enhanced
- Copy 9: Triple Tap + Jolting Feedback
- Copy 10: Triple Tap + Rolling Storm
- Copy 11: Supercharged Magazine + Turnabout
- Copy 12: Supercharged Magazine + Wellspring
- Copy 13: Trickle Charge + Turnabout
- Copy 14: Trickle Charge + Wellspring

### Forensic Nightmare
Submachine Gun · Stasis · craftable · GFS 609 · pool 80 combos · 14 copies · 14 combos covered
- Pool col 2 (9): Attrition Orbs, Empty Traits Socket, Encore, Grave Robber, Heating Up, Perpetual Motion, Rimestealer, Slideways, Under Pressure
- Pool col 3 (9): Crystalline Corpsebloom, Empty Traits Socket, Harmony, Headstone, Kill Clip, Swashbuckler, Sword Logic, Sympathetic Arsenal, Thresh
- Copy 1: Attrition Orbs + Sword Logic
- Copy 2: Attrition Orbs + Sympathetic Arsenal
- Copy 3: Encore + Crystalline Corpsebloom
- Copy 4: Grave Robber + Crystalline Corpsebloom
- Copy 5: Slideways + Crystalline Corpsebloom
- Copy 6: Heating Up + Sword Logic
- Copy 7: Heating Up + Sympathetic Arsenal
- Copy 8: Rimestealer + Sympathetic Arsenal
- Copy 9: Under Pressure + Sword Logic
- Copy 10: Empty Traits Socket + Sword Logic
- Copy 11: Encore + Sympathetic Arsenal
- Copy 12: Grave Robber + Sympathetic Arsenal
- Copy 13: Slideways + Headstone
- Copy 14: Under Pressure + Headstone

### Crux Termination IV
Rocket Launcher · Arc · obtainable · GFS 130 · pool 36 combos · 13 copies · 13 combos covered
- Pool col 2 (6): Clown Cartridge, Eddy Current, Envious Assassin, Permeability, Reconstruction, Slideshot
- Pool col 3 (6): Bipod, Demolitionist, Explosive Light, Quickdraw, Surrounded, Tracking Module
- Copy 1: Eddy Current + Bipod
- Copy 2: Permeability + Bipod
- Copy 3: Clown Cartridge + Surrounded
- Copy 4: Eddy Current + Demolitionist
- Copy 5: Permeability + Demolitionist
- Copy 6: Eddy Current + Tracking Module
- Copy 7: Envious Assassin + Tracking Module
- Copy 8: Permeability + Explosive Light
- Copy 9: Slideshot + Explosive Light
- Copy 10: Permeability + Quickdraw
- Copy 11: Permeability + Tracking Module
- Copy 12: Reconstruction + Tracking Module
- Copy 13: Slideshot + Tracking Module

### Fel Taradiddle
Combat Bow · Kinetic · craftable · GFS 604 · pool 80 combos · 13 copies · 13 combos covered
- Pool col 2 (9): Archer's Tempo, Empty Traits Socket, Impulse Amplifier, Killing Wind, Perpetual Motion, Rangefinder, Shoot to Loot, Stats for All, To the Pain
- Pool col 3 (9): Adhesive Ordnance, Adrenaline Junkie, Cornered, Empty Traits Socket, Explosive Head, One for All, Successful Warm-Up, Sword Logic, Thresh
- Copy 1: Archer's Tempo + Adhesive Ordnance
- Copy 2: Impulse Amplifier + Adhesive Ordnance
- Copy 3: Killing Wind + Adhesive Ordnance
- Copy 4: Perpetual Motion + Adhesive Ordnance
- Copy 5: Rangefinder + Adhesive Ordnance
- Copy 6: To the Pain + Adhesive Ordnance
- Copy 7: To the Pain + Cornered
- Copy 8: Impulse Amplifier + Sword Logic
- Copy 9: To the Pain + Successful Warm-Up
- Copy 10: To the Pain + Thresh
- Copy 11: Archer's Tempo + Thresh
- Copy 12: Impulse Amplifier + Cornered
- Copy 13: Stats for All + Explosive Head

### Scatter Signal
Fusion Rifle · Strand · craftable · GFS 340 · pool 63 combos · 13 copies · 13 combos covered
- Pool col 2 (8): Empty Traits Socket, Encore, Enlightened Action, Loose Change, Overflow, Perpetual Motion, Slice, Surplus
- Pool col 3 (8): Adagio, Attrition Orbs, Controlled Burst, Deconstruct, Empty Traits Socket, Hatchling, Kickstart, Under-Over
- Copy 1: Perpetual Motion + Attrition Orbs
- Copy 2: Surplus + Attrition Orbs
- Copy 3: Encore + Controlled Burst
- Copy 4: Slice + Controlled Burst
- Copy 5: Surplus + Controlled Burst
- Copy 6: Surplus + Deconstruct
- Copy 7: Encore + Kickstart
- Copy 8: Enlightened Action + Kickstart
- Copy 9: Overflow + Kickstart
- Copy 10: Slice + Kickstart
- Copy 11: Slice + Adagio
- Copy 12: Surplus + Kickstart
- Copy 13: Slice + Under-Over

### Ancient Gospel
Hand Cannon · Void · craftable · GFS 818 · pool 99 combos · 12 copies · 12 combos covered
- Pool col 2 (10): Air Trigger, Demolitionist, Destabilizing Rounds, Empty Traits Socket, Ensemble, Eye of the Storm, Lone Wolf, Rampage, Rapid Hit, Repulsor Brace
- Pool col 3 (10): Closing Time, Demoralize, Empty Traits Socket, Explosive Payload, Harmony, Kill Clip, Precision Instrument, Rangefinder, Swashbuckler, To the Pain
- Copy 1: Air Trigger + Demoralize
- Copy 2: Air Trigger + Explosive Payload
- Copy 3: Air Trigger + Rangefinder
- Copy 4: Ensemble + Closing Time
- Copy 5: Ensemble + Demoralize
- Copy 6: Rampage + Demoralize
- Copy 7: Destabilizing Rounds + Harmony
- Copy 8: Ensemble + To the Pain
- Copy 9: Rampage + Precision Instrument
- Copy 10: Rampage + Swashbuckler
- Copy 11: Repulsor Brace + To the Pain
- Copy 12: Ensemble + Precision Instrument

### Bequest
Sword · Arc · craftable · GFS 669 · pool 100 combos · 12 copies · 12 combos covered
- Pool col 2 (10): Duelist's Trance, Energy Transfer, Jolting Feedback, Killing Wind, Relentless Strikes, Thresh, Tireless Blade, Unrelenting, Valiant Charge, Wellspring
- Pool col 3 (10): Assassin's Blade, Chain Reaction, Demolitionist, Elemental Honing, En Garde, Flash Counter, One for All, Redirection, Surrounded, Vorpal Weapon
- Copy 1: Killing Wind + Assassin's Blade
- Copy 2: Jolting Feedback + Chain Reaction
- Copy 3: Thresh + Elemental Honing
- Copy 4: Jolting Feedback + En Garde
- Copy 5: Killing Wind + En Garde
- Copy 6: Killing Wind + Flash Counter
- Copy 7: Unrelenting + Flash Counter
- Copy 8: Wellspring + Flash Counter
- Copy 9: Jolting Feedback + One for All
- Copy 10: Jolting Feedback + Redirection
- Copy 11: Jolting Feedback + Surrounded
- Copy 12: Jolting Feedback + Vorpal Weapon

### Judgment of Kelgorath
Glaive · Solar · craftable · GFS 432 · pool 63 combos · 12 copies · 12 combos covered
- Pool col 2 (8): Demolitionist, Empty Traits Socket, Genesis, Immovable Object, Overflow, Pugilist, Shot Swap, Tilting at Windmills
- Pool col 3 (8): Close to Melee, Empty Traits Socket, Harmony, Impulse Amplifier, Incandescent, Surrounded, Unstoppable Force, Wellspring
- Copy 1: Genesis + Close to Melee
- Copy 2: Shot Swap + Close to Melee
- Copy 3: Immovable Object + Empty Traits Socket
- Copy 4: Immovable Object + Harmony
- Copy 5: Tilting at Windmills + Harmony
- Copy 6: Immovable Object + Impulse Amplifier
- Copy 7: Overflow + Impulse Amplifier
- Copy 8: Tilting at Windmills + Impulse Amplifier
- Copy 9: Shot Swap + Unstoppable Force
- Copy 10: Genesis + Impulse Amplifier
- Copy 11: Shot Swap + Impulse Amplifier
- Copy 12: Shot Swap + Incandescent

### Suspectum-4fr
Linear Fusion Rifle · Stasis · obtainable · GFS 139 · pool 36 combos · 12 copies · 12 combos covered
- Pool col 2 (6): Backup Plan, Enlightened Action, Ensemble, Envious Assassin, Headstone, No Distractions
- Pool col 3 (6): Box Breathing, Chill Clip, Firing Line, Fourth Time's the Charm, High Ground, Precision Instrument
- Copy 1: Backup Plan + Box Breathing
- Copy 2: Backup Plan + Chill Clip
- Copy 3: Backup Plan + Firing Line
- Copy 4: Backup Plan + Fourth Time's the Charm
- Copy 5: Backup Plan + High Ground
- Copy 6: Backup Plan + Precision Instrument
- Copy 7: Headstone + Box Breathing
- Copy 8: Envious Assassin + Chill Clip
- Copy 9: Enlightened Action + Fourth Time's the Charm
- Copy 10: Ensemble + Fourth Time's the Charm
- Copy 11: Headstone + Firing Line
- Copy 12: Headstone + High Ground

### Tripwire Canary
Combat Bow · Arc · craftable · GFS 479 · pool 63 combos · 12 copies · 12 combos covered
- Pool col 2 (8): Archer's Tempo, Dragonfly, Empty Traits Socket, Perfect Float, Rapid Hit, Shot Swap, Slickdraw, Sneak Bow
- Pool col 3 (8): Empty Traits Socket, Explosive Head, Frenzy, Harmony, Opening Shot, Successful Warm-Up, Swashbuckler, Under-Over
- Copy 1: Archer's Tempo + Under-Over
- Copy 2: Dragonfly + Under-Over
- Copy 3: Sneak Bow + Empty Traits Socket
- Copy 4: Sneak Bow + Under-Over
- Copy 5: Shot Swap + Explosive Head
- Copy 6: Slickdraw + Explosive Head
- Copy 7: Perfect Float + Successful Warm-Up
- Copy 8: Perfect Float + Under-Over
- Copy 9: Shot Swap + Successful Warm-Up
- Copy 10: Shot Swap + Under-Over
- Copy 11: Sneak Bow + Swashbuckler
- Copy 12: Sneak Bow + Frenzy

### Controlling Vision
Sidearm · Kinetic · obtainable · GFS 118 · pool 36 combos · 11 copies · 11 combos covered
- Pool col 2 (6): Air Assault, Encore, Fragile Focus, Slickdraw, Slideways, Surplus
- Pool col 3 (6): High Ground, Offhand Strike, Osmosis, Surrounded, Threat Detector, Under Pressure
- Copy 1: Air Assault + High Ground
- Copy 2: Air Assault + Offhand Strike
- Copy 3: Air Assault + Threat Detector
- Copy 4: Air Assault + Under Pressure
- Copy 5: Encore + Under Pressure
- Copy 6: Fragile Focus + Under Pressure
- Copy 7: Slickdraw + Offhand Strike
- Copy 8: Surplus + Offhand Strike
- Copy 9: Slickdraw + Threat Detector
- Copy 10: Slickdraw + Under Pressure
- Copy 11: Slideways + Under Pressure

### Cruoris FR4
Fusion Rifle · Arc · obtainable · GFS 165 · pool 36 combos · 11 copies · 11 combos covered
- Pool col 2 (6): Clown Cartridge, Discord, Eddy Current, Recycled Energy, Stats for All, Threat Detector
- Pool col 3 (6): Barrel Constrictor, Elemental Honing, Kickstart, One for All, Rolling Storm, Successful Warm-Up
- Copy 1: Clown Cartridge + Barrel Constrictor
- Copy 2: Eddy Current + Barrel Constrictor
- Copy 3: Recycled Energy + Barrel Constrictor
- Copy 4: Clown Cartridge + Kickstart
- Copy 5: Eddy Current + Kickstart
- Copy 6: Eddy Current + Successful Warm-Up
- Copy 7: Recycled Energy + Kickstart
- Copy 8: Stats for All + Kickstart
- Copy 9: Recycled Energy + Rolling Storm
- Copy 10: Recycled Energy + Successful Warm-Up
- Copy 11: Discord + Barrel Constrictor

### Imperative
Scout Rifle · Kinetic · craftable · GFS 623 · pool 63 combos · 11 copies · 11 combos covered
- Pool col 2 (8): Demolitionist, Empty Traits Socket, Keep Away, No Distractions, Rapid Hit, Subsistence, Triple Tap, Well-Rounded
- Pool col 3 (8): Adrenaline Junkie, Attrition Orbs, Deconstruct, Empty Traits Socket, Explosive Payload, Kinetic Tremors, Opening Shot, Osmosis
- Copy 1: No Distractions + Attrition Orbs
- Copy 2: Triple Tap + Attrition Orbs
- Copy 3: Well-Rounded + Attrition Orbs
- Copy 4: Triple Tap + Deconstruct
- Copy 5: Well-Rounded + Deconstruct
- Copy 6: Rapid Hit + Deconstruct
- Copy 7: Empty Traits Socket + Osmosis
- Copy 8: Well-Rounded + Kinetic Tremors
- Copy 9: Triple Tap + Osmosis
- Copy 10: Well-Rounded + Explosive Payload
- Copy 11: Empty Traits Socket + Deconstruct

### Optative
Hand Cannon · Void · craftable · GFS 621 · pool 71 combos · 11 copies · 11 combos covered
- Pool col 2 (8): Attrition Orbs, Demolitionist, Empty Traits Socket, Hip-Fire Grip, Keep Away, Permeability, Rapid Hit, Repulsor Brace
- Pool col 3 (9): Deconstruct, Empty Traits Socket, Golden Tricorn, Golden Tricorn Enhanced, Kill Clip, Offhand Strike, Under-Over, Wellspring, Zen Moment
- Copy 1: Permeability + Kill Clip
- Copy 2: Permeability + Offhand Strike
- Copy 3: Permeability + Wellspring
- Copy 4: Permeability + Zen Moment
- Copy 5: Hip-Fire Grip + Under-Over
- Copy 6: Repulsor Brace + Under-Over
- Copy 7: Repulsor Brace + Deconstruct
- Copy 8: Permeability + Under-Over
- Copy 9: Permeability + Deconstruct
- Copy 10: Permeability + Golden Tricorn
- Copy 11: Permeability + Golden Tricorn Enhanced

### Red Herring
Rocket Launcher · Void · craftable · GFS 695 · pool 89 combos · 11 copies · 11 combos covered
- Pool col 2 (9): Ambitious Assassin, Cluster Bomb, Empty Traits Socket, Ensemble, Field Prep, Killing Wind, Quickdraw, Reconstruction, Tracking Module
- Pool col 3 (10): Adrenaline Junkie, Elemental Honing, Empty Traits Socket, Explosive Light, Frenzy, Golden Tricorn, Golden Tricorn Enhanced, Lasting Impression, Snapshot Sights, Turnabout
- Copy 1: Cluster Bomb + Adrenaline Junkie
- Copy 2: Cluster Bomb + Golden Tricorn
- Copy 3: Cluster Bomb + Golden Tricorn Enhanced
- Copy 4: Quickdraw + Golden Tricorn Enhanced
- Copy 5: Killing Wind + Lasting Impression
- Copy 6: Reconstruction + Turnabout
- Copy 7: Tracking Module + Snapshot Sights
- Copy 8: Cluster Bomb + Empty Traits Socket
- Copy 9: Killing Wind + Explosive Light
- Copy 10: Tracking Module + Turnabout
- Copy 11: Tracking Module + Empty Traits Socket

### Combined Action
Hand Cannon · Arc · obtainable · GFS 176 · pool 36 combos · 10 copies · 10 combos covered
- Pool col 2 (6): Eddy Current, Hip-Fire Grip, No Distractions, Perfect Float, Tunnel Vision, Zen Moment
- Pool col 3 (6): Adagio, Air Assault, Kill Clip, Offhand Strike, Timed Payload, Voltshot
- Copy 1: Eddy Current + Air Assault
- Copy 2: Hip-Fire Grip + Air Assault
- Copy 3: No Distractions + Air Assault
- Copy 4: Perfect Float + Air Assault
- Copy 5: Tunnel Vision + Air Assault
- Copy 6: Eddy Current + Timed Payload
- Copy 7: No Distractions + Offhand Strike
- Copy 8: No Distractions + Voltshot
- Copy 9: Perfect Float + Timed Payload
- Copy 10: Zen Moment + Timed Payload

### Ignition Code
Grenade Launcher · Kinetic · obtainable · GFS 229 · pool 36 combos · 10 copies · 10 combos covered
- Pool col 2 (6): Ambitious Assassin, Lead from Gold, Permeability, Slideshot, Steady Hands, Unrelenting
- Pool col 3 (6): Frenzy, Harmony, High Ground, Reverberation, Strategist, Vorpal Weapon
- Copy 1: Permeability + Frenzy
- Copy 2: Permeability + Harmony
- Copy 3: Slideshot + High Ground
- Copy 4: Permeability + Reverberation
- Copy 5: Permeability + Strategist
- Copy 6: Permeability + Vorpal Weapon
- Copy 7: Slideshot + Reverberation
- Copy 8: Steady Hands + Reverberation
- Copy 9: Slideshot + Strategist
- Copy 10: Steady Hands + Strategist

### Lethophobia
Combat Bow · Void · craftable · GFS 462 · pool 71 combos · 10 copies · 10 combos covered
- Pool col 2 (8): Empty Traits Socket, Enlightened Action, Impulse Amplifier, Permeability, Repulsor Brace, Slickdraw, Steady Hands, Successful Warm-Up
- Pool col 3 (9): Attrition Orbs, Deconstruct, Disruption Break, Empty Traits Socket, Explosive Head, Golden Tricorn, Golden Tricorn Enhanced, High Ground, Surrounded
- Copy 1: Steady Hands + Attrition Orbs
- Copy 2: Steady Hands + Deconstruct
- Copy 3: Successful Warm-Up + Deconstruct
- Copy 4: Permeability + Disruption Break
- Copy 5: Steady Hands + Disruption Break
- Copy 6: Successful Warm-Up + Disruption Break
- Copy 7: Enlightened Action + Explosive Head
- Copy 8: Permeability + Explosive Head
- Copy 9: Steady Hands + Explosive Head
- Copy 10: Successful Warm-Up + Surrounded

### Line in the Sand
Linear Fusion Rifle · Arc · obtainable · GFS 237 · pool 36 combos · 10 copies · 10 combos covered
- Pool col 2 (6): Genesis, Moving Target, Rangefinder, Rapid Hit, Threat Detector, Under Pressure
- Pool col 3 (6): Auto-Loading Holster, Backup Plan, Clown Cartridge, Dragonfly, Firing Line, Rampage
- Copy 1: Rapid Hit + Auto-Loading Holster
- Copy 2: Genesis + Backup Plan
- Copy 3: Rangefinder + Backup Plan
- Copy 4: Rapid Hit + Backup Plan
- Copy 5: Rapid Hit + Clown Cartridge
- Copy 6: Under Pressure + Clown Cartridge
- Copy 7: Rangefinder + Firing Line
- Copy 8: Threat Detector + Firing Line
- Copy 9: Genesis + Auto-Loading Holster
- Copy 10: Under Pressure + Auto-Loading Holster

### The Eremite
Fusion Rifle · Solar · craftable, obtainable · GFS 433 · pool 71 combos · 10 copies · 10 combos covered
- Pool col 2 (8): Compulsive Reloader, Empty Traits Socket, Envious Assassin, Heal Clip, Lead from Gold, Offhand Strike, Pulse Monitor, Slickdraw
- Pool col 3 (9): Controlled Burst, Cornered, Elemental Capacitor, Empty Traits Socket, Golden Tricorn, Golden Tricorn Enhanced, High Ground, Pugilist, Reservoir Burst
- Copy 1: Compulsive Reloader + High Ground
- Copy 2: Offhand Strike + Controlled Burst
- Copy 3: Pulse Monitor + Controlled Burst
- Copy 4: Envious Assassin + Cornered
- Copy 5: Heal Clip + Cornered
- Copy 6: Pulse Monitor + Cornered
- Copy 7: Slickdraw + Cornered
- Copy 8: Heal Clip + Elemental Capacitor
- Copy 9: Heal Clip + Pugilist
- Copy 10: Pulse Monitor + Reservoir Burst

### Adhortative
Pulse Rifle · Solar · craftable · GFS 532 · pool 71 combos · 9 copies · 9 combos covered
- Pool col 2 (8): Air Assault, Attrition Orbs, Empty Traits Socket, Feeding Frenzy, Heal Clip, Loose Change, Shoot to Loot, Slickdraw
- Pool col 3 (9): Deconstruct, Disruption Break, Empty Traits Socket, Golden Tricorn, Golden Tricorn Enhanced, Harmony, Headseeker, Incandescent, Moving Target
- Copy 1: Air Assault + Deconstruct
- Copy 2: Air Assault + Headseeker
- Copy 3: Air Assault + Moving Target
- Copy 4: Attrition Orbs + Disruption Break
- Copy 5: Heal Clip + Deconstruct
- Copy 6: Loose Change + Disruption Break
- Copy 7: Air Assault + Disruption Break
- Copy 8: Loose Change + Headseeker
- Copy 9: Slickdraw + Headseeker

### Father's Sins
Sniper Rifle · Void · craftable · GFS 692 · pool 80 combos · 9 copies · 9 combos covered
- Pool col 2 (9): Empty Traits Socket, Field Prep, Lead from Gold, Light Touch, Lone Wolf, No Distractions, Shoot to Loot, Triple Tap, Under Pressure
- Pool col 3 (9): Bait and Switch, Empty Traits Socket, Eye of the Storm, Focused Fury, Opening Shot, Rampage, Snapshot Sights, Turnabout, Withering Gaze
- Copy 1: Shoot to Loot + Bait and Switch
- Copy 2: Light Touch + Eye of the Storm
- Copy 3: Field Prep + Withering Gaze
- Copy 4: Light Touch + Focused Fury
- Copy 5: Light Touch + Turnabout
- Copy 6: Lone Wolf + Turnabout
- Copy 7: Triple Tap + Withering Gaze
- Copy 8: Lead from Gold + Withering Gaze
- Copy 9: No Distractions + Withering Gaze

### Swarm of the Raven
Grenade Launcher · Void · obtainable · GFS 210 · pool 49 combos · 9 copies · 9 combos covered
- Pool col 2 (7): Auto-Loading Holster, Clown Cartridge, Demolitionist, Field Prep, Impulse Amplifier, Pulse Monitor, Slickdraw
- Pool col 3 (7): Adagio, Cascade Point, Destabilizing Rounds, Disruption Break, Envious Assassin, Full Court, Genesis
- Copy 1: Field Prep + Adagio
- Copy 2: Pulse Monitor + Cascade Point
- Copy 3: Clown Cartridge + Envious Assassin
- Copy 4: Field Prep + Envious Assassin
- Copy 5: Field Prep + Genesis
- Copy 6: Pulse Monitor + Full Court
- Copy 7: Slickdraw + Full Court
- Copy 8: Pulse Monitor + Genesis
- Copy 9: Slickdraw + Genesis

### Tears of Contrition
Scout Rifle · Kinetic · craftable · GFS 524 · pool 48 combos · 9 copies · 9 combos covered
- Pool col 2 (7): Auto-Loading Holster, Compulsive Reloader, Empty Traits Socket, No Distractions, Perpetual Motion, Triple Tap, Well-Rounded
- Pool col 3 (7): Empty Traits Socket, Explosive Payload, Focused Fury, Fourth Time's the Charm, Mulligan, Opening Shot, Vorpal Weapon
- Copy 1: Auto-Loading Holster + Fourth Time's the Charm
- Copy 2: Auto-Loading Holster + Mulligan
- Copy 3: Compulsive Reloader + Mulligan
- Copy 4: Well-Rounded + Fourth Time's the Charm
- Copy 5: No Distractions + Mulligan
- Copy 6: Perpetual Motion + Mulligan
- Copy 7: Triple Tap + Mulligan
- Copy 8: Well-Rounded + Mulligan
- Copy 9: Compulsive Reloader + Explosive Payload

### The Showrunner
Submachine Gun · Kinetic · obtainable · GFS 180 · pool 36 combos · 9 copies · 9 combos covered
- Pool col 2 (6): Dynamic Sway Reduction, Grave Robber, Heating Up, Overflow, Rangefinder, Well-Rounded
- Pool col 3 (6): Air Assault, Collective Action, Fragile Focus, Kinetic Tremors, Swashbuckler, Target Lock
- Copy 1: Dynamic Sway Reduction + Air Assault
- Copy 2: Grave Robber + Air Assault
- Copy 3: Heating Up + Air Assault
- Copy 4: Overflow + Air Assault
- Copy 5: Well-Rounded + Air Assault
- Copy 6: Grave Robber + Fragile Focus
- Copy 7: Overflow + Fragile Focus
- Copy 8: Grave Robber + Kinetic Tremors
- Copy 9: Overflow + Kinetic Tremors

### Arsenic Bite-4b
Combat Bow · Arc · obtainable · GFS 117 · pool 26 combos · 8 copies · 8 combos covered
- Pool col 2 (9): Archer's Tempo, Dragonfly, Explosive Head, Hip-Fire Grip, Moving Target, Quickdraw, Rampage, Snapshot Sights, Sneak Bow
- Pool col 3 (4): Archer's Tempo, Explosive Head, Rampage, Sneak Bow
- Copy 1: Hip-Fire Grip + Archer's Tempo
- Copy 2: Quickdraw + Archer's Tempo
- Copy 3: Archer's Tempo + Sneak Bow
- Copy 4: Explosive Head + Rampage
- Copy 5: Hip-Fire Grip + Sneak Bow
- Copy 6: Moving Target + Sneak Bow
- Copy 7: Quickdraw + Sneak Bow
- Copy 8: Snapshot Sights + Sneak Bow

### Empirical Evidence
Sidearm · Kinetic · craftable · GFS 742 · pool 80 combos · 8 copies · 8 combos covered
- Pool col 2 (9): Compulsive Reloader, Empty Traits Socket, Encore, Enlightened Action, Ensemble, Lone Wolf, Perpetual Motion, Pulse Monitor, Tunnel Vision
- Pool col 3 (9): Adagio, Empty Traits Socket, Frenzy, Harmony, Kinetic Tremors, Swashbuckler, Thresh, Unrelenting, Wellspring
- Copy 1: Compulsive Reloader + Kinetic Tremors
- Copy 2: Enlightened Action + Thresh
- Copy 3: Enlightened Action + Unrelenting
- Copy 4: Ensemble + Kinetic Tremors
- Copy 5: Pulse Monitor + Kinetic Tremors
- Copy 6: Lone Wolf + Thresh
- Copy 7: Lone Wolf + Unrelenting
- Copy 8: Pulse Monitor + Empty Traits Socket

### Lodbrok-C
Auto Rifle · Kinetic · obtainable · GFS 355 · pool 36 combos · 8 copies · 8 combos covered
- Pool col 2 (6): Demolitionist, Dynamic Sway Reduction, Fourth Time's the Charm, Fragile Focus, Osmosis, Perpetual Motion
- Pool col 3 (6): Adrenaline Junkie, Cascade Point, Kill Clip, Tap the Trigger, Target Lock, Wellspring
- Copy 1: Fragile Focus + Adrenaline Junkie
- Copy 2: Osmosis + Adrenaline Junkie
- Copy 3: Osmosis + Cascade Point
- Copy 4: Fragile Focus + Tap the Trigger
- Copy 5: Osmosis + Kill Clip
- Copy 6: Osmosis + Tap the Trigger
- Copy 7: Osmosis + Wellspring
- Copy 8: Fragile Focus + Cascade Point

### Nezarec's Whisper
Glaive · Arc · craftable · GFS 523 · pool 48 combos · 8 copies · 8 combos covered
- Pool col 2 (7): Compulsive Reloader, Demolitionist, Empty Traits Socket, Genesis, Impulse Amplifier, Lead from Gold, Tilting at Windmills
- Pool col 3 (7): Adaptive Munitions, Adrenaline Junkie, Empty Traits Socket, Frenzy, Turnabout, Unstoppable Force, Vorpal Weapon
- Copy 1: Impulse Amplifier + Adaptive Munitions
- Copy 2: Lead from Gold + Adaptive Munitions
- Copy 3: Tilting at Windmills + Adaptive Munitions
- Copy 4: Tilting at Windmills + Adrenaline Junkie
- Copy 5: Compulsive Reloader + Unstoppable Force
- Copy 6: Tilting at Windmills + Turnabout
- Copy 7: Genesis + Unstoppable Force
- Copy 8: Impulse Amplifier + Turnabout

### Scalar Potential
Pulse Rifle · Arc · craftable · GFS 526 · pool 71 combos · 8 copies · 8 combos covered
- Pool col 2 (8): Empty Traits Socket, Enlightened Action, Hip-Fire Grip, Keep Away, Loose Change, Overflow, Permeability, Slickdraw
- Pool col 3 (9): Attrition Orbs, Deconstruct, Empty Traits Socket, Focused Fury, Golden Tricorn, Golden Tricorn Enhanced, Headseeker, High Ground, Under-Over
- Copy 1: Loose Change + Focused Fury
- Copy 2: Permeability + Focused Fury
- Copy 3: Overflow + Headseeker
- Copy 4: Permeability + Headseeker
- Copy 5: Enlightened Action + Under-Over
- Copy 6: Loose Change + Under-Over
- Copy 7: Slickdraw + Attrition Orbs
- Copy 8: Slickdraw + Under-Over

### Speleologist
Machine Gun · Solar · craftable · GFS 496 · pool 63 combos · 8 copies · 8 combos covered
- Pool col 2 (8): Deconstruct, Empty Traits Socket, Enlightened Action, Envious Assassin, Firmly Planted, Heal Clip, Slideways, Stats for All
- Pool col 3 (8): Adagio, Empty Traits Socket, Incandescent, Killing Tally, One for All, Strategist, Surrounded, Target Lock
- Copy 1: Firmly Planted + Strategist
- Copy 2: Firmly Planted + Target Lock
- Copy 3: Heal Clip + Killing Tally
- Copy 4: Heal Clip + Strategist
- Copy 5: Slideways + Strategist
- Copy 6: Deconstruct + Incandescent
- Copy 7: Slideways + Killing Tally
- Copy 8: Empty Traits Socket + Killing Tally

### Throne-Cleaver
Sword · Solar · craftable · GFS 389 · pool 48 combos · 8 copies · 8 combos covered
- Pool col 2 (7): Duelist's Trance, Empty Traits Socket, Energy Transfer, Flash Counter, Thresh, Tireless Blade, Unrelenting
- Pool col 3 (7): Empty Traits Socket, En Garde, Incandescent, Pugilist, Surrounded, Valiant Charge, Vorpal Weapon
- Copy 1: Duelist's Trance + Pugilist
- Copy 2: Energy Transfer + Pugilist
- Copy 3: Flash Counter + Pugilist
- Copy 4: Thresh + Incandescent
- Copy 5: Tireless Blade + Pugilist
- Copy 6: Energy Transfer + Incandescent
- Copy 7: Flash Counter + Incandescent
- Copy 8: Tireless Blade + Incandescent

### Veleda-F
Sniper Rifle · Void · obtainable · GFS 365 · pool 49 combos · 8 copies · 8 combos covered
- Pool col 2 (7): Air Trigger, Deconstruct, Lone Wolf, No Distractions, Repulsor Brace, Slickdraw, Snapshot Sights
- Pool col 3 (7): Closing Time, Destabilizing Rounds, Firing Line, Focused Fury, Opening Shot, Vorpal Weapon, Withering Gaze
- Copy 1: Air Trigger + Firing Line
- Copy 2: Air Trigger + Withering Gaze
- Copy 3: Deconstruct + Firing Line
- Copy 4: Deconstruct + Opening Shot
- Copy 5: Snapshot Sights + Destabilizing Rounds
- Copy 6: Lone Wolf + Firing Line
- Copy 7: Repulsor Brace + Firing Line
- Copy 8: Slickdraw + Withering Gaze

### Corrasion
Pulse Rifle · Arc · craftable, obtainable · GFS 610 · pool 63 combos · 7 copies · 7 combos covered
- Pool col 2 (8): Air Trigger, Eddy Current, Empty Traits Socket, Enlightened Action, High-Impact Reserves, Perfect Float, Perpetual Motion, Pugilist
- Pool col 3 (8): Empty Traits Socket, Eye of the Storm, Focused Fury, Frenzy, High Ground, One for All, Swashbuckler, Voltshot
- Copy 1: Air Trigger + High Ground
- Copy 2: High-Impact Reserves + Focused Fury
- Copy 3: High-Impact Reserves + Frenzy
- Copy 4: High-Impact Reserves + High Ground
- Copy 5: High-Impact Reserves + One for All
- Copy 6: High-Impact Reserves + Swashbuckler
- Copy 7: Air Trigger + Focused Fury

### Doomed Petitioner
Linear Fusion Rifle · Void · craftable · GFS 585 · pool 71 combos · 7 copies · 7 combos covered
- Pool col 2 (8): Attrition Orbs, Destabilizing Rounds, Empty Traits Socket, Envious Assassin, Keep Away, Permeability, Reconstruction, Threat Detector
- Pool col 3 (9): Deconstruct, Empty Traits Socket, Golden Tricorn, Golden Tricorn Enhanced, High Ground, Loose Change, Moving Target, Precision Instrument, Surrounded
- Copy 1: Keep Away + Loose Change
- Copy 2: Permeability + Loose Change
- Copy 3: Reconstruction + Loose Change
- Copy 4: Threat Detector + Loose Change
- Copy 5: Destabilizing Rounds + Deconstruct
- Copy 6: Threat Detector + Deconstruct
- Copy 7: Permeability + Surrounded

### Fire and Forget
Linear Fusion Rifle · Stasis · craftable · GFS 716 · pool 63 combos · 7 copies · 7 combos covered
- Pool col 2 (8): Empty Traits Socket, Field Prep, Headstone, Killing Wind, Outlaw, Perfect Float, Rangefinder, Surplus
- Pool col 3 (8): Chill Clip, Demolitionist, Empty Traits Socket, Focused Fury, Frenzy, Harmony, High-Impact Reserves, Vorpal Weapon
- Copy 1: Outlaw + Chill Clip
- Copy 2: Perfect Float + Chill Clip
- Copy 3: Rangefinder + Chill Clip
- Copy 4: Headstone + Harmony
- Copy 5: Headstone + Vorpal Weapon
- Copy 6: Perfect Float + High-Impact Reserves
- Copy 7: Empty Traits Socket + High-Impact Reserves

### Friction Fire
Submachine Gun · Kinetic · obtainable · GFS 379 · pool 36 combos · 7 copies · 7 combos covered
- Pool col 2 (6): Auto-Loading Holster, Field Prep, Killing Wind, Subsistence, Threat Detector, Zen Moment
- Pool col 3 (6): Rampage, Slideways, Sympathetic Arsenal, Unrelenting, Vorpal Weapon, Wellspring
- Copy 1: Auto-Loading Holster + Slideways
- Copy 2: Auto-Loading Holster + Sympathetic Arsenal
- Copy 3: Field Prep + Slideways
- Copy 4: Subsistence + Slideways
- Copy 5: Zen Moment + Slideways
- Copy 6: Field Prep + Sympathetic Arsenal
- Copy 7: Threat Detector + Slideways

### Planck's Stride
Machine Gun · Arc · craftable, obtainable · GFS 663 · pool 63 combos · 7 copies · 7 combos covered
- Pool col 2 (8): Compulsive Reloader, Empty Traits Socket, Grave Robber, Heating Up, Killing Wind, Mulligan, Perpetual Motion, Slickdraw
- Pool col 3 (8): Empty Traits Socket, Eye of the Storm, Harmony, One for All, Pugilist, Swashbuckler, Tap the Trigger, Thresh
- Copy 1: Mulligan + Harmony
- Copy 2: Mulligan + One for All
- Copy 3: Mulligan + Tap the Trigger
- Copy 4: Mulligan + Thresh
- Copy 5: Slickdraw + Tap the Trigger
- Copy 6: Mulligan + Pugilist
- Copy 7: Mulligan + Swashbuckler

### Regnant
Grenade Launcher · Void · craftable · GFS 572 · pool 63 combos · 7 copies · 7 combos covered
- Pool col 2 (8): Auto-Loading Holster, Empty Traits Socket, Envious Assassin, Rangefinder, Repulsor Brace, Shot Swap, Stats for All, Thresh
- Pool col 3 (8): Cascade Point, Destabilizing Rounds, Disruption Break, Empty Traits Socket, Explosive Light, One for All, Pugilist, Unrelenting
- Copy 1: Rangefinder + Cascade Point
- Copy 2: Repulsor Brace + Cascade Point
- Copy 3: Thresh + Cascade Point
- Copy 4: Rangefinder + Explosive Light
- Copy 5: Repulsor Brace + Explosive Light
- Copy 6: Repulsor Brace + Pugilist
- Copy 7: Shot Swap + Unrelenting

### Targeted Redaction
Hand Cannon · Void · craftable, obtainable · GFS 534 · pool 63 combos · 7 copies · 7 combos covered
- Pool col 2 (8): Empty Traits Socket, Envious Assassin, Invisible Hand, Outlaw, Perfect Float, Shot Swap, Triple Tap, Well-Rounded
- Pool col 3 (8): Collective Action, Destabilizing Rounds, Empty Traits Socket, Explosive Payload, Focused Fury, Frenzy, Harmony, Keep Away
- Copy 1: Well-Rounded + Destabilizing Rounds
- Copy 2: Envious Assassin + Keep Away
- Copy 3: Invisible Hand + Explosive Payload
- Copy 4: Shot Swap + Explosive Payload
- Copy 5: Invisible Hand + Keep Away
- Copy 6: Perfect Float + Keep Away
- Copy 7: Well-Rounded + Keep Away

### The Domino
Sniper Rifle · Solar · obtainable · GFS 243 · pool 36 combos · 7 copies · 7 combos covered
- Pool col 2 (6): Overflow, Pulse Monitor, Shoot to Loot, Shot Swap, Slideways, Subsistence
- Pool col 3 (6): Harmony, Incandescent, Moving Target, Mulligan, Multikill Clip, Opening Shot
- Copy 1: Pulse Monitor + Incandescent
- Copy 2: Overflow + Mulligan
- Copy 3: Pulse Monitor + Mulligan
- Copy 4: Shoot to Loot + Mulligan
- Copy 5: Shot Swap + Mulligan
- Copy 6: Slideways + Mulligan
- Copy 7: Subsistence + Mulligan

### Blood Feud
Submachine Gun · Stasis · craftable · GFS 618 · pool 63 combos · 6 copies · 6 combos covered
- Pool col 2 (8): Ambitious Assassin, Dynamic Sway Reduction, Empty Traits Socket, Encore, Ensemble, Grave Robber, Pugilist, Triple Tap
- Pool col 3 (8): Elemental Capacitor, Empty Traits Socket, Focused Fury, Frenzy, Headstone, Swashbuckler, Well-Rounded, Wellspring
- Copy 1: Ambitious Assassin + Well-Rounded
- Copy 2: Dynamic Sway Reduction + Well-Rounded
- Copy 3: Encore + Well-Rounded
- Copy 4: Ensemble + Well-Rounded
- Copy 5: Grave Robber + Well-Rounded
- Copy 6: Triple Tap + Well-Rounded

### Chronophage
Trace Rifle · Void · craftable, obtainable · GFS 627 · pool 63 combos · 6 copies · 6 combos covered
- Pool col 2 (8): Auto-Loading Holster, Elemental Capacitor, Empty Traits Socket, Feeding Frenzy, Pugilist, Repulsor Brace, Shoot to Loot, Strategist
- Pool col 3 (8): Demolitionist, Desperate Measures, Destabilizing Rounds, Empty Traits Socket, Fragile Focus, High Ground, One for All, Target Lock
- Copy 1: Auto-Loading Holster + Desperate Measures
- Copy 2: Elemental Capacitor + Desperate Measures
- Copy 3: Elemental Capacitor + High Ground
- Copy 4: Elemental Capacitor + One for All
- Copy 5: Feeding Frenzy + Fragile Focus
- Copy 6: Shoot to Loot + Fragile Focus

### Firefright
Auto Rifle · Kinetic · craftable · GFS 381 · pool 48 combos · 6 copies · 6 combos covered
- Pool col 2 (7): Air Assault, Empty Traits Socket, Fourth Time's the Charm, Fragile Focus, Hip-Fire Grip, Threat Detector, Well-Rounded
- Pool col 3 (7): Adagio, Elemental Capacitor, Empty Traits Socket, Focused Fury, Mulligan, Osmosis, Surrounded
- Copy 1: Fragile Focus + Adagio
- Copy 2: Air Assault + Mulligan
- Copy 3: Fourth Time's the Charm + Mulligan
- Copy 4: Fragile Focus + Mulligan
- Copy 5: Hip-Fire Grip + Mulligan
- Copy 6: Threat Detector + Mulligan

### Fixed Odds
Machine Gun · Solar · craftable · GFS 374 · pool 48 combos · 6 copies · 6 combos covered
- Pool col 2 (7): Empty Traits Socket, Encore, Feeding Frenzy, Field Prep, No Distractions, Quickdraw, Under Pressure
- Pool col 3 (7): Empty Traits Socket, Firing Line, Focused Fury, Incandescent, Killing Tally, Rampage, Rangefinder
- Copy 1: Encore + Killing Tally
- Copy 2: Encore + Rangefinder
- Copy 3: Quickdraw + Focused Fury
- Copy 4: Quickdraw + Killing Tally
- Copy 5: Under Pressure + Killing Tally
- Copy 6: No Distractions + Rangefinder

### Legato-11
Shotgun · Solar · obtainable · GFS 375 · pool 49 combos · 6 copies · 6 combos covered
- Pool col 2 (7): Auto-Loading Holster, Deconstruct, Heal Clip, Killing Wind, Lone Wolf, To the Pain, Triple Tap
- Pool col 3 (7): Cascade Point, Closing Time, Focused Fury, Frenzy, Incandescent, Offhand Strike, Vorpal Weapon
- Copy 1: Deconstruct + Cascade Point
- Copy 2: To the Pain + Cascade Point
- Copy 3: Deconstruct + Offhand Strike
- Copy 4: Triple Tap + Offhand Strike
- Copy 5: Deconstruct + Closing Time
- Copy 6: Deconstruct + Focused Fury

### Marsilion-C
Grenade Launcher · Solar · obtainable · GFS 305 · pool 49 combos · 6 copies · 6 combos covered
- Pool col 2 (7): Envious Assassin, Field Prep, Perpetual Motion, Shot Swap, Snapshot Sights, Stats for All, Turnabout
- Pool col 3 (7): Cascade Point, Danger Zone, Explosive Light, Full Court, Impulse Amplifier, Incandescent, Vorpal Weapon
- Copy 1: Snapshot Sights + Danger Zone
- Copy 2: Field Prep + Impulse Amplifier
- Copy 3: Shot Swap + Full Court
- Copy 4: Turnabout + Full Court
- Copy 5: Perpetual Motion + Impulse Amplifier
- Copy 6: Snapshot Sights + Impulse Amplifier

### Noxious Vetiver
Submachine Gun · Arc · obtainable · GFS 292 · pool 49 combos · 6 copies · 6 combos covered
- Pool col 2 (7): Attrition Orbs, Heating Up, Loose Change, Pugilist, Thresh, To the Pain, Unrelenting
- Pool col 3 (7): Desperate Measures, Frenzy, Jolting Feedback, Rampage, Redirection, Target Lock, Vorpal Weapon
- Copy 1: Thresh + Desperate Measures
- Copy 2: Unrelenting + Desperate Measures
- Copy 3: Heating Up + Redirection
- Copy 4: Thresh + Jolting Feedback
- Copy 5: Loose Change + Target Lock
- Copy 6: Loose Change + Rampage

### Pleiades Corrector
Scout Rifle · Solar · obtainable · GFS 341 · pool 42 combos · 6 copies · 6 combos covered
- Pool col 2 (6): Field Prep, Fourth Time's the Charm, Genesis, Outlaw, Subsistence, Surplus
- Pool col 3 (7): Demolitionist, Elemental Capacitor, Eye of the Storm, Multikill Clip, Shield Disorient, Sympathetic Arsenal, Wellspring
- Copy 1: Fourth Time's the Charm + Shield Disorient
- Copy 2: Fourth Time's the Charm + Sympathetic Arsenal
- Copy 3: Outlaw + Shield Disorient
- Copy 4: Subsistence + Shield Disorient
- Copy 5: Surplus + Shield Disorient
- Copy 6: Field Prep + Shield Disorient

### Prodigal Return
Grenade Launcher · Arc · craftable · GFS 548 · pool 63 combos · 6 copies · 6 combos covered
- Pool col 2 (8): Empty Traits Socket, Envious Assassin, Field Prep, Lead from Gold, Shot Swap, Threat Detector, Thresh, Turnabout
- Pool col 3 (8): Adrenaline Junkie, Danger Zone, Demolitionist, Disruption Break, Empty Traits Socket, Harmony, Rampage, Voltshot
- Copy 1: Thresh + Danger Zone
- Copy 2: Shot Swap + Demolitionist
- Copy 3: Thresh + Voltshot
- Copy 4: Turnabout + Voltshot
- Copy 5: Turnabout + Danger Zone
- Copy 6: Thresh + Rampage

### Royal Executioner
Fusion Rifle · Solar · craftable · GFS 521 · pool 63 combos · 6 copies · 6 combos covered
- Pool col 2 (8): Empty Traits Socket, Envious Assassin, Firmly Planted, Grave Robber, Lead from Gold, Offhand Strike, Slickdraw, Threat Detector
- Pool col 3 (8): Elemental Capacitor, Empty Traits Socket, Incandescent, Killing Wind, Pugilist, Reservoir Burst, Successful Warm-Up, Swashbuckler
- Copy 1: Envious Assassin + Killing Wind
- Copy 2: Envious Assassin + Successful Warm-Up
- Copy 3: Firmly Planted + Killing Wind
- Copy 4: Slickdraw + Killing Wind
- Copy 5: Threat Detector + Successful Warm-Up
- Copy 6: Slickdraw + Successful Warm-Up

### Sailspy Pitchglass
Linear Fusion Rifle · Arc · craftable, obtainable · GFS 694 · pool 63 combos · 6 copies · 6 combos covered
- Pool col 2 (8): Clown Cartridge, Compulsive Reloader, Empty Traits Socket, Ensemble, Moving Target, Outlaw, Rapid Hit, Slideways
- Pool col 3 (8): Empty Traits Socket, Focused Fury, Frenzy, Heating Up, Multikill Clip, Swashbuckler, Voltshot, Vorpal Weapon
- Copy 1: Clown Cartridge + Heating Up
- Copy 2: Ensemble + Heating Up
- Copy 3: Ensemble + Voltshot
- Copy 4: Outlaw + Heating Up
- Copy 5: Rapid Hit + Heating Up
- Copy 6: Compulsive Reloader + Heating Up

### Supercluster
Shotgun · Strand · craftable · GFS 489 · pool 63 combos · 6 copies · 6 combos covered
- Pool col 2 (8): Empty Traits Socket, Fourth Time's the Charm, Lead from Gold, Loose Change, Reconstruction, Slice, Slideshot, Threat Detector
- Pool col 3 (8): Attrition Orbs, Cascade Point, Deconstruct, Empty Traits Socket, Fragile Focus, Hatchling, Surrounded, Vorpal Weapon
- Copy 1: Lead from Gold + Attrition Orbs
- Copy 2: Slideshot + Attrition Orbs
- Copy 3: Slideshot + Deconstruct
- Copy 4: Fourth Time's the Charm + Fragile Focus
- Copy 5: Reconstruction + Fragile Focus
- Copy 6: Slice + Fragile Focus

### Tarnation
Grenade Launcher · Arc · craftable · GFS 640 · pool 80 combos · 6 copies · 6 combos covered
- Pool col 2 (9): Attrition Orbs, Clown Cartridge, Empty Traits Socket, Ensemble, Envious Assassin, Field Prep, Killing Wind, Pulse Monitor, Quickdraw
- Pool col 3 (9): Bait and Switch, Chain Reaction, Danger Zone, Empty Traits Socket, Explosive Light, One for All, Thresh, Turnabout, Wellspring
- Copy 1: Attrition Orbs + Turnabout
- Copy 2: Ensemble + Bait and Switch
- Copy 3: Clown Cartridge + Turnabout
- Copy 4: Pulse Monitor + Explosive Light
- Copy 5: Clown Cartridge + Danger Zone
- Copy 6: Envious Assassin + Danger Zone

### Vantage Point
Pulse Rifle · Arc · obtainable · GFS 309 · pool 49 combos · 6 copies · 6 combos covered
- Pool col 2 (7): Closing Time, Deconstruct, Eddy Current, Keep Away, Lone Wolf, Stats for All, To the Pain
- Pool col 3 (7): Desperado, Focused Fury, Headseeker, High-Impact Reserves, Jolting Feedback, One for All, Swashbuckler
- Copy 1: Deconstruct + Desperado
- Copy 2: Deconstruct + Headseeker
- Copy 3: Deconstruct + High-Impact Reserves
- Copy 4: Deconstruct + Swashbuckler
- Copy 5: To the Pain + High-Impact Reserves
- Copy 6: To the Pain + Jolting Feedback

### Bitter/Sweet
Grenade Launcher · Arc · obtainable · GFS 323 · pool 49 combos · 5 copies · 5 combos covered
- Pool col 2 (7): Attrition Orbs, Envious Arsenal, Loose Change, Perpetual Motion, Reverberation, Stats for All, Unrelenting
- Pool col 3 (7): Bait and Switch, Cascade Point, Explosive Light, Frenzy, Harmony, Jolting Feedback, Killing Tally
- Copy 1: Attrition Orbs + Cascade Point
- Copy 2: Loose Change + Explosive Light
- Copy 3: Reverberation + Harmony
- Copy 4: Perpetual Motion + Killing Tally
- Copy 5: Reverberation + Killing Tally

### Deadpan Delivery
Shotgun · Arc · obtainable · GFS 163 · pool 36 combos · 5 copies · 5 combos covered
- Pool col 2 (6): Air Assault, Discord, Elemental Capacitor, Overflow, Slickdraw, Surplus
- Pool col 3 (6): Barrel Constrictor, Collective Action, Frenzy, Killing Wind, One-Two Punch, Trench Barrel
- Copy 1: Air Assault + Barrel Constrictor
- Copy 2: Overflow + Barrel Constrictor
- Copy 3: Surplus + Barrel Constrictor
- Copy 4: Discord + Killing Wind
- Copy 5: Elemental Capacitor + Trench Barrel

### Deafening Whisper
Grenade Launcher · Void · obtainable · GFS 368 · pool 36 combos · 5 copies · 5 combos covered
- Pool col 2 (6): Ambitious Assassin, Killing Wind, Lead from Gold, Moving Target, Pulse Monitor, Surplus
- Pool col 3 (6): Auto-Loading Holster, Rampage, Snapshot Sights, Threat Detector, Unrelenting, Wellspring
- Copy 1: Surplus + Auto-Loading Holster
- Copy 2: Pulse Monitor + Threat Detector
- Copy 3: Lead from Gold + Auto-Loading Holster
- Copy 4: Lead from Gold + Threat Detector
- Copy 5: Surplus + Threat Detector

### Death's Razor
Sword · Void · craftable · GFS 401 · pool 48 combos · 5 copies · 5 combos covered
- Pool col 2 (7): Counterattack, Duelist's Trance, Empty Traits Socket, Energy Transfer, Relentless Strikes, Thresh, Tireless Blade
- Pool col 3 (7): Demolitionist, Destabilizing Rounds, Empty Traits Socket, Surrounded, Valiant Charge, Vorpal Weapon, Whirlwind Blade
- Copy 1: Counterattack + Destabilizing Rounds
- Copy 2: Counterattack + Surrounded
- Copy 3: Counterattack + Vorpal Weapon
- Copy 4: Counterattack + Whirlwind Blade
- Copy 5: Energy Transfer + Empty Traits Socket

### Distant Tumulus
Sniper Rifle · Solar · obtainable · GFS 134 · pool 25 combos · 5 copies · 5 combos covered
- Pool col 2 (5): Clown Cartridge, Dragonfly, Genesis, Lead from Gold, Pulse Monitor
- Pool col 3 (5): Firing Line, Opening Shot, Outlaw, Quickdraw, Snapshot Sights
- Copy 1: Clown Cartridge + Outlaw
- Copy 2: Pulse Monitor + Firing Line
- Copy 3: Genesis + Outlaw
- Copy 4: Lead from Gold + Outlaw
- Copy 5: Pulse Monitor + Outlaw

### Hollow Denial
Trace Rifle · Void · craftable · GFS 389 · pool 48 combos · 5 copies · 5 combos covered
- Pool col 2 (7): Adaptive Munitions, Empty Traits Socket, Heating Up, Lead from Gold, Rangefinder, Surplus, Well-Rounded
- Pool col 3 (7): Dragonfly, Empty Traits Socket, Killing Tally, Repulsor Brace, Swashbuckler, Unrelenting, Wellspring
- Copy 1: Adaptive Munitions + Swashbuckler
- Copy 2: Lead from Gold + Dragonfly
- Copy 3: Lead from Gold + Killing Tally
- Copy 4: Rangefinder + Killing Tally
- Copy 5: Lead from Gold + Repulsor Brace

### Imperial Needle
Combat Bow · Void · obtainable · GFS 274 · pool 36 combos · 5 copies · 5 combos covered
- Pool col 2 (6): Archer's Tempo, Hip-Fire Grip, Impulse Amplifier, Killing Wind, Quickdraw, Sneak Bow
- Pool col 3 (6): Frenzy, Opening Shot, Swashbuckler, Sympathetic Arsenal, Thresh, Wellspring
- Copy 1: Archer's Tempo + Sympathetic Arsenal
- Copy 2: Impulse Amplifier + Opening Shot
- Copy 3: Impulse Amplifier + Sympathetic Arsenal
- Copy 4: Sneak Bow + Sympathetic Arsenal
- Copy 5: Sneak Bow + Thresh

### Qua Furor V
Machine Gun · Stasis · obtainable · GFS 266 · pool 42 combos · 5 copies · 5 combos covered
- Pool col 2 (6): Feeding Frenzy, Heating Up, Offhand Strike, Recycled Energy, Rimestealer, Triple Tap
- Pool col 3 (7): Dragonfly, Elemental Honing, Golden Tricorn, Golden Tricorn Enhanced, One for All, Rampage, Tap the Trigger
- Copy 1: Recycled Energy + Dragonfly
- Copy 2: Offhand Strike + Elemental Honing
- Copy 3: Recycled Energy + Golden Tricorn
- Copy 4: Recycled Energy + Golden Tricorn Enhanced
- Copy 5: Recycled Energy + Tap the Trigger

### Ros Arago IV
Auto Rifle · Void · obtainable · GFS 226 · pool 42 combos · 5 copies · 5 combos covered
- Pool col 2 (6): Dynamic Sway Reduction, Permeability, Repulsor Brace, Rewind Rounds, Slickdraw, Subsistence
- Pool col 3 (7): Attrition Orbs, Deconstruct, Golden Tricorn, Golden Tricorn Enhanced, Onslaught, Surrounded, Under-Over
- Copy 1: Dynamic Sway Reduction + Under-Over
- Copy 2: Permeability + Onslaught
- Copy 3: Repulsor Brace + Onslaught
- Copy 4: Slickdraw + Onslaught
- Copy 5: Rewind Rounds + Under-Over

### Under Your Skin
Combat Bow · Void · craftable · GFS 324 · pool 48 combos · 5 copies · 5 combos covered
- Pool col 2 (7): Archer's Tempo, Empty Traits Socket, Firmly Planted, Hip-Fire Grip, Perpetual Motion, Tunnel Vision, Unrelenting
- Pool col 3 (7): Adaptive Munitions, Dragonfly, Empty Traits Socket, Explosive Head, Opening Shot, Successful Warm-Up, Turnabout
- Copy 1: Archer's Tempo + Adaptive Munitions
- Copy 2: Hip-Fire Grip + Adaptive Munitions
- Copy 3: Firmly Planted + Explosive Head
- Copy 4: Unrelenting + Explosive Head
- Copy 5: Tunnel Vision + Successful Warm-Up

### Warlord's Spear
Trace Rifle · Arc · obtainable · GFS 170 · pool 36 combos · 5 copies · 5 combos covered
- Pool col 2 (6): Dynamic Sway Reduction, Envious Assassin, High-Impact Reserves, Hip-Fire Grip, Loose Change, Rewind Rounds
- Pool col 3 (6): Desperate Measures, Detonator Beam, Fourth Time's the Charm, Jolting Feedback, Killing Tally, Target Lock
- Copy 1: Loose Change + Detonator Beam
- Copy 2: Dynamic Sway Reduction + Fourth Time's the Charm
- Copy 3: Hip-Fire Grip + Fourth Time's the Charm
- Copy 4: Loose Change + Fourth Time's the Charm
- Copy 5: Envious Assassin + Fourth Time's the Charm

### Without Remorse
Shotgun · Solar · craftable · GFS 501 · pool 48 combos · 5 copies · 5 combos covered
- Pool col 2 (7): Empty Traits Socket, Field Prep, Hip-Fire Grip, Stats for All, Steady Hands, Threat Detector, Well-Rounded
- Pool col 3 (7): Elemental Capacitor, Empty Traits Socket, Fragile Focus, Incandescent, One-Two Punch, Turnabout, Vorpal Weapon
- Copy 1: Field Prep + Fragile Focus
- Copy 2: Stats for All + Fragile Focus
- Copy 3: Steady Hands + Fragile Focus
- Copy 4: Stats for All + One-Two Punch
- Copy 5: Well-Rounded + Fragile Focus

### Annual Skate
Hand Cannon · Solar · obtainable · GFS 328 · pool 36 combos · 4 copies · 4 combos covered
- Pool col 2 (6): No Distractions, Outlaw, Slideshot, Surplus, Triple Tap, Tunnel Vision
- Pool col 3 (6): Dragonfly, Multikill Clip, Opening Shot, Swashbuckler, Timed Payload, Wellspring
- Copy 1: Triple Tap + Multikill Clip
- Copy 2: Slideshot + Timed Payload
- Copy 3: Surplus + Timed Payload
- Copy 4: No Distractions + Timed Payload

### Austringer
Hand Cannon · Kinetic · craftable · GFS 521 · pool 48 combos · 4 copies · 4 combos covered
- Pool col 2 (7): Air Assault, Compulsive Reloader, Empty Traits Socket, Eye of the Storm, Outlaw, Snapshot Sights, Triple Tap
- Pool col 3 (7): Demolitionist, Empty Traits Socket, Frenzy, Opening Shot, Rampage, Rangefinder, Zen Moment
- Copy 1: Air Assault + Demolitionist
- Copy 2: Compulsive Reloader + Zen Moment
- Copy 3: Eye of the Storm + Rampage
- Copy 4: Air Assault + Zen Moment

### Battle Scar
Pulse Rifle · Kinetic · obtainable · GFS 206 · pool 36 combos · 4 copies · 4 combos covered
- Pool col 2 (6): Encore, Keep Away, Perfect Float, Perpetual Motion, Shoot to Loot, Shot Swap
- Pool col 3 (6): Eye of the Storm, Headseeker, High-Impact Reserves, Kinetic Tremors, Multikill Clip, Osmosis
- Copy 1: Shot Swap + High-Impact Reserves
- Copy 2: Keep Away + Multikill Clip
- Copy 3: Shot Swap + Kinetic Tremors
- Copy 4: Perfect Float + Osmosis

### Brya's Love
Scout Rifle · Void · craftable · GFS 743 · pool 71 combos · 4 copies · 4 combos covered
- Pool col 2 (8): Empty Traits Socket, Keep Away, Loose Change, No Distractions, Perfect Float, Perpetual Motion, Rapid Hit, Shoot to Loot
- Pool col 3 (9): Adagio, Destabilizing Rounds, Empty Traits Socket, Explosive Payload, Frenzy, Golden Tricorn, Golden Tricorn Enhanced, Precision Instrument, Pugilist
- Copy 1: Loose Change + Explosive Payload
- Copy 2: No Distractions + Pugilist
- Copy 3: No Distractions + Adagio
- Copy 4: No Distractions + Empty Traits Socket

### Cantata-57
Hand Cannon · Arc · obtainable · GFS 344 · pool 36 combos · 4 copies · 4 combos covered
- Pool col 2 (6): Compulsive Reloader, Eye of the Storm, Heating Up, Hip-Fire Grip, Rapid Hit, Steady Hands
- Pool col 3 (6): Focused Fury, Moving Target, Opening Shot, Rangefinder, Timed Payload, Vorpal Weapon
- Copy 1: Compulsive Reloader + Timed Payload
- Copy 2: Eye of the Storm + Timed Payload
- Copy 3: Heating Up + Timed Payload
- Copy 4: Rapid Hit + Timed Payload

### Dark Decider
Auto Rifle · Arc · obtainable · GFS 174 · pool 36 combos · 4 copies · 4 combos covered
- Pool col 2 (6): Auto-Loading Holster, Dynamic Sway Reduction, Iron Grip, Offhand Strike, Subsistence, Well-Rounded
- Pool col 3 (6): Dragonfly, Golden Tricorn, Gutshot Straight, Iron Reach, Rangefinder, Voltshot
- Copy 1: Iron Grip + Dragonfly
- Copy 2: Iron Grip + Gutshot Straight
- Copy 3: Iron Grip + Rangefinder
- Copy 4: Iron Grip + Voltshot

### Dire Promise
Hand Cannon · Kinetic · obtainable · GFS 146 · pool 25 combos · 4 copies · 4 combos covered
- Pool col 2 (5): Auto-Loading Holster, Opening Shot, Overflow, Snapshot Sights, Triple Tap
- Pool col 3 (5): Elemental Capacitor, Osmosis, Rangefinder, Swashbuckler, Under Pressure
- Copy 1: Auto-Loading Holster + Osmosis
- Copy 2: Snapshot Sights + Osmosis
- Copy 3: Overflow + Rangefinder
- Copy 4: Overflow + Under Pressure

### Enyo-D
Submachine Gun · Kinetic · obtainable · GFS 258 · pool 36 combos · 4 copies · 4 combos covered
- Pool col 2 (6): Encore, Feeding Frenzy, Fragile Focus, Steady Hands, Tunnel Vision, Well-Rounded
- Pool col 3 (6): Multikill Clip, Rampage, Surrounded, Sympathetic Arsenal, Vorpal Weapon, Wellspring
- Copy 1: Fragile Focus + Sympathetic Arsenal
- Copy 2: Tunnel Vision + Sympathetic Arsenal
- Copy 3: Well-Rounded + Sympathetic Arsenal
- Copy 4: Encore + Multikill Clip

### Exuviae
Hand Cannon · Stasis · obtainable · GFS 412 · pool 49 combos · 4 copies · 4 combos covered
- Pool col 2 (7): Encore, Keep Away, Lone Wolf, Rimestealer, Stats for All, To the Pain, Triple Tap
- Pool col 3 (7): Desperate Measures, Explosive Payload, Frenzy, Headstone, One for All, Precision Instrument, Redirection
- Copy 1: Encore + Explosive Payload
- Copy 2: Encore + Redirection
- Copy 3: Rimestealer + Redirection
- Copy 4: Stats for All + Redirection

### Faith-Keeper
Rocket Launcher · Void · craftable, obtainable · GFS 558 · pool 63 combos · 4 copies · 4 combos covered
- Pool col 2 (8): Auto-Loading Holster, Clown Cartridge, Danger Zone, Empty Traits Socket, Field Prep, Impulse Amplifier, Repulsor Brace, Strategist
- Pool col 3 (8): Bipod, Demolitionist, Destabilizing Rounds, Empty Traits Socket, Explosive Light, Frenzy, Lasting Impression, Reverberation
- Copy 1: Repulsor Brace + Bipod
- Copy 2: Strategist + Bipod
- Copy 3: Repulsor Brace + Lasting Impression
- Copy 4: Strategist + Lasting Impression

### Farewell
Sidearm · Kinetic · obtainable · GFS 384 · pool 36 combos · 4 copies · 4 combos covered
- Pool col 2 (6): Full Auto Trigger System, Heating Up, Moving Target, Rangefinder, Subsistence, Tunnel Vision
- Pool col 3 (6): Adrenaline Junkie, Frenzy, Multikill Clip, Thresh, Unrelenting, Vorpal Weapon
- Copy 1: Full Auto Trigger System + Adrenaline Junkie
- Copy 2: Full Auto Trigger System + Frenzy
- Copy 3: Full Auto Trigger System + Unrelenting
- Copy 4: Full Auto Trigger System + Thresh

### Goldtusk
Sword · Arc · craftable · GFS 409 · pool 55 combos · 4 copies · 4 combos covered
- Pool col 2 (7): Assassin's Blade, Duelist's Trance, Empty Traits Socket, Relentless Strikes, Tireless Blade, Unrelenting, Valiant Charge
- Pool col 3 (8): Adrenaline Junkie, Chain Reaction, Cold Steel, Counterattack, Empty Traits Socket, Harmony, One for All, Whirlwind Blade
- Copy 1: Assassin's Blade + Adrenaline Junkie
- Copy 2: Assassin's Blade + Cold Steel
- Copy 3: Assassin's Blade + Counterattack
- Copy 4: Assassin's Blade + Harmony

### IKELOS_SG_v1.0.3
Shotgun · Solar · craftable · GFS 714 · pool 63 combos · 4 copies · 4 combos covered
- Pool col 2 (8): Empty Traits Socket, Feeding Frenzy, Grave Robber, Offhand Strike, Pugilist, Subsistence, Threat Detector, Turnabout
- Pool col 3 (8): Cascade Point, Empty Traits Socket, Incandescent, One-Two Punch, Surrounded, Swashbuckler, Trench Barrel, Vorpal Weapon
- Copy 1: Turnabout + One-Two Punch
- Copy 2: Turnabout + Trench Barrel
- Copy 3: Turnabout + Cascade Point
- Copy 4: Empty Traits Socket + Trench Barrel

### Marcato-45
Machine Gun · Strand · obtainable · GFS 272 · pool 42 combos · 4 copies · 4 combos covered
- Pool col 2 (6): Attrition Orbs, Demolitionist, Slice, Steady Hands, Threat Detector, Triple Tap
- Pool col 3 (7): Adagio, Golden Tricorn, Golden Tricorn Enhanced, Hatchling, Onslaught, Surrounded, Under-Over
- Copy 1: Attrition Orbs + Hatchling
- Copy 2: Steady Hands + Onslaught
- Copy 3: Triple Tap + Onslaught
- Copy 4: Threat Detector + Under-Over

### Pizzicato-22
Submachine Gun · Kinetic · obtainable · GFS 311 · pool 49 combos · 4 copies · 4 combos covered
- Pool col 2 (7): Ambitious Assassin, Ensemble, Eye of the Storm, Fragile Focus, Hip-Fire Grip, Mulligan, Perpetual Motion
- Pool col 3 (7): Demolitionist, Multikill Clip, Osmosis, Pugilist, Rangefinder, Swashbuckler, Threat Detector
- Copy 1: Ensemble + Threat Detector
- Copy 2: Mulligan + Multikill Clip
- Copy 3: Perpetual Motion + Threat Detector
- Copy 4: Fragile Focus + Rangefinder

### Raconteur
Combat Bow · Stasis · craftable · GFS 453 · pool 63 combos · 4 copies · 4 combos covered
- Pool col 2 (8): Archer's Tempo, Empty Traits Socket, Perfect Float, Shoot to Loot, Shot Swap, Stats for All, Surplus, Wellspring
- Pool col 3 (8): Empty Traits Socket, Explosive Head, Eye of the Storm, Gutshot Straight, Headstone, Pugilist, Rampage, Successful Warm-Up
- Copy 1: Archer's Tempo + Headstone
- Copy 2: Archer's Tempo + Pugilist
- Copy 3: Wellspring + Successful Warm-Up
- Copy 4: Archer's Tempo + Gutshot Straight

### Razor's Edge
Sword · Void · obtainable · GFS 271 · pool 36 combos · 4 copies · 4 combos covered
- Pool col 2 (6): Duelist's Trance, Energy Transfer, Relentless Strikes, Tireless Blade, Unrelenting, Wellspring
- Pool col 3 (6): Assassin's Blade, Chain Reaction, Counterattack, Frenzy, One for All, Thresh
- Copy 1: Duelist's Trance + Thresh
- Copy 2: Relentless Strikes + Thresh
- Copy 3: Tireless Blade + Thresh
- Copy 4: Wellspring + Thresh

### Sojourner's Tale
Shotgun · Solar · obtainable · GFS 297 · pool 36 combos · 4 copies · 4 combos covered
- Pool col 2 (6): Auto-Loading Holster, Discord, Heal Clip, Moving Target, Offhand Strike, Quickdraw
- Pool col 3 (6): Air Trigger, Harmony, Incandescent, Opening Shot, Precision Instrument, Swashbuckler
- Copy 1: Discord + Air Trigger
- Copy 2: Heal Clip + Air Trigger
- Copy 3: Quickdraw + Air Trigger
- Copy 4: Auto-Loading Holster + Precision Instrument

### Sovereignty
Sniper Rifle · Void · obtainable · GFS 335 · pool 49 combos · 4 copies · 4 combos covered
- Pool col 2 (7): Demolitionist, Discord, Dragonfly, Enlightened Action, Explosive Payload, No Distractions, Steady Hands
- Pool col 3 (7): Adrenaline Junkie, Box Breathing, Desperate Measures, Firing Line, Harmony, Precision Instrument, Withering Gaze
- Copy 1: Explosive Payload + Adrenaline Junkie
- Copy 2: No Distractions + Desperate Measures
- Copy 3: Steady Hands + Precision Instrument
- Copy 4: Enlightened Action + Box Breathing

### Subjunctive
Submachine Gun · Arc · craftable · GFS 765 · pool 71 combos · 4 copies · 4 combos covered
- Pool col 2 (8): Empty Traits Socket, Grave Robber, Hip-Fire Grip, Shoot to Loot, Stats for All, Subsistence, Threat Detector, Under Pressure
- Pool col 3 (9): Attrition Orbs, Disruption Break, Empty Traits Socket, Golden Tricorn, Golden Tricorn Enhanced, One for All, Permeability, Swashbuckler, Voltshot
- Copy 1: Hip-Fire Grip + Permeability
- Copy 2: Shoot to Loot + Permeability
- Copy 3: Threat Detector + Permeability
- Copy 4: Under Pressure + Permeability

### The Epicurean
Fusion Rifle · Void · craftable · GFS 352 · pool 48 combos · 4 copies · 4 combos covered
- Pool col 2 (7): Empty Traits Socket, Ensemble, Feeding Frenzy, Quickdraw, Snapshot Sights, Surplus, Well-Rounded
- Pool col 3 (7): Backup Plan, Cornered, Empty Traits Socket, Moving Target, Rangefinder, Repulsor Brace, Swashbuckler
- Copy 1: Ensemble + Backup Plan
- Copy 2: Well-Rounded + Backup Plan
- Copy 3: Snapshot Sights + Cornered
- Copy 4: Quickdraw + Repulsor Brace

### The Vision
Sidearm · Arc · obtainable · GFS 332 · pool 36 combos · 4 copies · 4 combos covered
- Pool col 2 (6): Ambitious Assassin, Full Auto Trigger System, Grave Robber, Killing Wind, Pulse Monitor, Surplus
- Pool col 3 (6): Disruption Break, Elemental Capacitor, Kill Clip, One for All, Swashbuckler, Sympathetic Arsenal
- Copy 1: Ambitious Assassin + Sympathetic Arsenal
- Copy 2: Full Auto Trigger System + Disruption Break
- Copy 3: Full Auto Trigger System + One for All
- Copy 4: Full Auto Trigger System + Sympathetic Arsenal

### Wolftone Draw
Combat Bow · Arc · obtainable · GFS 234 · pool 36 combos · 4 copies · 4 combos covered
- Pool col 2 (6): Archer's Tempo, Ensemble, Impulse Amplifier, Shoot to Loot, Sneak Bow, Threat Detector
- Pool col 3 (6): Adagio, Cornered, Demolitionist, Dragonfly, Frenzy, Harmony
- Copy 1: Sneak Bow + Adagio
- Copy 2: Archer's Tempo + Demolitionist
- Copy 3: Threat Detector + Cornered
- Copy 4: Sneak Bow + Demolitionist

### Appetence
Trace Rifle · Stasis · craftable · GFS 487 · pool 63 combos · 3 copies · 3 combos covered
- Pool col 2 (8): Clown Cartridge, Demolitionist, Empty Traits Socket, Enlightened Action, Hip-Fire Grip, Loose Change, Overflow, Slideways
- Pool col 3 (8): Attrition Orbs, Deconstruct, Empty Traits Socket, Headstone, High Ground, Killing Tally, One for All, Wellspring
- Copy 1: Slideways + Attrition Orbs
- Copy 2: Clown Cartridge + Killing Tally
- Copy 3: Loose Change + Killing Tally

### Beloved
Sniper Rifle · Solar · craftable · GFS 424 · pool 48 combos · 3 copies · 3 combos covered
- Pool col 2 (7): Compulsive Reloader, Empty Traits Socket, Firmly Planted, Fourth Time's the Charm, No Distractions, Snapshot Sights, Surplus
- Pool col 3 (7): Box Breathing, Empty Traits Socket, Incandescent, Moving Target, Quickdraw, Rampage, Turnabout
- Copy 1: Fourth Time's the Charm + Quickdraw
- Copy 2: Snapshot Sights + Turnabout
- Copy 3: Compulsive Reloader + Quickdraw

### Berenger's Memory
Grenade Launcher · Void · obtainable · GFS 287 · pool 30 combos · 3 copies · 3 combos covered
- Pool col 2 (5): Clown Cartridge, Field Prep, Pulse Monitor, Quickdraw, Threat Detector
- Pool col 3 (6): Auto-Loading Holster, Demolitionist, Disruption Break, Elemental Capacitor, Rampage, Shield Disorient
- Copy 1: Clown Cartridge + Shield Disorient
- Copy 2: Pulse Monitor + Shield Disorient
- Copy 3: Quickdraw + Shield Disorient

### Boudica-C
Sidearm · Kinetic · obtainable · GFS 508 · pool 49 combos · 3 copies · 3 combos covered
- Pool col 2 (7): Ambitious Assassin, Hip-Fire Grip, Moving Target, Pugilist, Slickdraw, Stats for All, Threat Detector
- Pool col 3 (7): Frenzy, Gutshot Straight, Multikill Clip, One for All, Osmosis, Surrounded, Swashbuckler
- Copy 1: Stats for All + Osmosis
- Copy 2: Slickdraw + Gutshot Straight
- Copy 3: Slickdraw + Multikill Clip

### Brigand's Law
Sidearm · Arc · craftable, obtainable · GFS 742 · pool 63 combos · 3 copies · 3 combos covered
- Pool col 2 (8): Empty Traits Socket, Feeding Frenzy, Hip-Fire Grip, Killing Wind, Perpetual Motion, Pugilist, Steady Hands, Threat Detector
- Pool col 3 (8): Adagio, Demolitionist, Empty Traits Socket, Rangefinder, Surrounded, Swashbuckler, Sympathetic Arsenal, Voltshot
- Copy 1: Empty Traits Socket + Sympathetic Arsenal
- Copy 2: Steady Hands + Sympathetic Arsenal
- Copy 3: Threat Detector + Sympathetic Arsenal

### CALUS Mini-Tool
Submachine Gun · Solar · craftable · GFS 429 · pool 48 combos · 3 copies · 3 combos covered
- Pool col 2 (7): Air Assault, Empty Traits Socket, Grave Robber, Moving Target, Slideways, Threat Detector, Unrelenting
- Pool col 3 (7): Disruption Break, Empty Traits Socket, Eye of the Storm, Feeding Frenzy, Incandescent, Surrounded, Tap the Trigger
- Copy 1: Air Assault + Feeding Frenzy
- Copy 2: Air Assault + Tap the Trigger
- Copy 3: Slideways + Feeding Frenzy

### Coronach-22
Auto Rifle · Solar · obtainable · GFS 197 · pool 36 combos · 3 copies · 3 combos covered
- Pool col 2 (6): Envious Assassin, Feeding Frenzy, Perfect Float, Shot Swap, Surplus, Zen Moment
- Pool col 3 (6): Adagio, Adrenaline Junkie, Cascade Point, Incandescent, Target Lock, Under-Over
- Copy 1: Envious Assassin + Under-Over
- Copy 2: Feeding Frenzy + Under-Over
- Copy 3: Zen Moment + Under-Over

### Disparity
Pulse Rifle · Stasis · craftable · GFS 694 · pool 63 combos · 3 copies · 3 combos covered
- Pool col 2 (8): Empty Traits Socket, Eye of the Storm, Heating Up, Moving Target, No Distractions, Outlaw, Pugilist, Rapid Hit
- Pool col 3 (8): Desperado, Empty Traits Socket, Frenzy, Headseeker, Headstone, Kill Clip, One for All, Swashbuckler
- Copy 1: Eye of the Storm + Desperado
- Copy 2: No Distractions + Desperado
- Copy 3: No Distractions + Headseeker

### Fioritura-59
Sidearm · Void · obtainable · GFS 348 · pool 36 combos · 3 copies · 3 combos covered
- Pool col 2 (6): Hip-Fire Grip, Killing Wind, Pugilist, Threat Detector, Tunnel Vision, Zen Moment
- Pool col 3 (6): Golden Tricorn, Kill Clip, Moving Target, Offhand Strike, Repulsor Brace, Swashbuckler
- Copy 1: Hip-Fire Grip + Repulsor Brace
- Copy 2: Tunnel Vision + Offhand Strike
- Copy 3: Threat Detector + Repulsor Brace

### Hand in Hand
Shotgun · Arc · obtainable · GFS 190 · pool 36 combos · 3 copies · 3 combos covered
- Pool col 2 (6): Dual Loader, Ensemble, Fragile Focus, Hip-Fire Grip, Shot Swap, Slideshot
- Pool col 3 (6): Cascade Point, Elemental Capacitor, Golden Tricorn, One-Two Punch, Pugilist, Trench Barrel
- Copy 1: Dual Loader + Pugilist
- Copy 2: Fragile Focus + Trench Barrel
- Copy 3: Shot Swap + One-Two Punch

### Hollow Words
Fusion Rifle · Arc · obtainable · GFS 282 · pool 36 combos · 3 copies · 3 combos covered
- Pool col 2 (6): Ambitious Assassin, Feeding Frenzy, Lead from Gold, Loose Change, Slickdraw, Steady Hands
- Pool col 3 (6): Multikill Clip, Rampage, Rolling Storm, Successful Warm-Up, Swashbuckler, Vorpal Weapon
- Copy 1: Loose Change + Successful Warm-Up
- Copy 2: Slickdraw + Rolling Storm
- Copy 3: Steady Hands + Rolling Storm

### Honor's Edge
Sword · Arc · obtainable · GFS 148 · pool 19 combos · 3 copies · 3 combos covered
- Pool col 2 (4): En Garde, Energy Transfer, Relentless Strikes, Tireless Blade
- Pool col 3 (5): Counterattack, En Garde, Flash Counter, Shattering Blade, Surrounded
- Copy 1: Energy Transfer + Shattering Blade
- Copy 2: Relentless Strikes + Shattering Blade
- Copy 3: Tireless Blade + Shattering Blade

### IKELOS_SR_v1.0.3
Sniper Rifle · Solar · craftable · GFS 512 · pool 63 combos · 3 copies · 3 combos covered
- Pool col 2 (8): Empty Traits Socket, Fourth Time's the Charm, Fragile Focus, Moving Target, No Distractions, Overflow, Perpetual Motion, Surplus
- Pool col 3 (8): Box Breathing, Elemental Capacitor, Empty Traits Socket, Focused Fury, High-Impact Reserves, Incandescent, Slickdraw, Under-Over
- Copy 1: Perpetual Motion + Box Breathing
- Copy 2: Fourth Time's the Charm + Slickdraw
- Copy 3: Overflow + Slickdraw

### Iota Draconis
Fusion Rifle · Solar · obtainable · GFS 280 · pool 36 combos · 3 copies · 3 combos covered
- Pool col 2 (6): Ensemble, Feeding Frenzy, Heating Up, Lead from Gold, Surplus, Under Pressure
- Pool col 3 (6): Adagio, Cornered, Frenzy, Harmony, High-Impact Reserves, Kickstart
- Copy 1: Ensemble + Kickstart
- Copy 2: Heating Up + Kickstart
- Copy 3: Lead from Gold + High-Impact Reserves

### Jian 7 Rifle
Pulse Rifle · Arc · obtainable · GFS 161 · pool 25 combos · 3 copies · 3 combos covered
- Pool col 2 (5): Disruption Break, Firmly Planted, Full Auto Trigger System, Grave Robber, Zen Moment
- Pool col 3 (5): Dragonfly, Outlaw, Rampage, Rangefinder, Swashbuckler
- Copy 1: Disruption Break + Rampage
- Copy 2: Disruption Break + Swashbuckler
- Copy 3: Firmly Planted + Outlaw

### Lost Signal
Grenade Launcher · Stasis · craftable, obtainable · GFS 822 · pool 63 combos · 3 copies · 3 combos covered
- Pool col 2 (8): Auto-Loading Holster, Empty Traits Socket, Feeding Frenzy, Lead from Gold, Quickdraw, Stats for All, Strategist, Threat Detector
- Pool col 3 (8): Demolitionist, Empty Traits Socket, High Ground, One for All, Reverberation, Unrelenting, Vorpal Weapon, Wellspring
- Copy 1: Lead from Gold + Reverberation
- Copy 2: Strategist + Unrelenting
- Copy 3: Strategist + Wellspring

### Martyr's Retribution
Grenade Launcher · Solar · obtainable · GFS 230 · pool 25 combos · 3 copies · 3 combos covered
- Pool col 2 (5): Auto-Loading Holster, Field Prep, Genesis, Pulse Monitor, Threat Detector
- Pool col 3 (5): Demolitionist, Elemental Capacitor, Lead from Gold, Moving Target, Rangefinder
- Copy 1: Genesis + Lead from Gold
- Copy 2: Genesis + Rangefinder
- Copy 3: Pulse Monitor + Lead from Gold

### Negative Space
Sword · Solar · obtainable · GFS 151 · pool 15 combos · 3 copies · 3 combos covered
- Pool col 2 (3): Energy Transfer, Relentless Strikes, Tireless Blade
- Pool col 3 (5): Counterattack, Disruption Break, Flash Counter, Surrounded, Whirlwind Blade
- Copy 1: Energy Transfer + Disruption Break
- Copy 2: Relentless Strikes + Disruption Break
- Copy 3: Tireless Blade + Disruption Break

### Psi Hermetic V
Pulse Rifle · Stasis · obtainable · GFS 365 · pool 42 combos · 3 copies · 3 combos covered
- Pool col 2 (6): Elemental Capacitor, Encore, Enlightened Action, Heating Up, Moving Target, Outlaw
- Pool col 3 (7): Frenzy, Golden Tricorn, Golden Tricorn Enhanced, Headseeker, Headstone, Kill Clip, Perpetual Motion
- Copy 1: Enlightened Action + Perpetual Motion
- Copy 2: Heating Up + Perpetual Motion
- Copy 3: Outlaw + Perpetual Motion

### Recurrent Impact
Machine Gun · Stasis · craftable · GFS 628 · pool 48 combos · 3 copies · 3 combos covered
- Pool col 2 (7): Empty Traits Socket, Field Prep, Firmly Planted, Genesis, Perpetual Motion, Stats for All, Subsistence
- Pool col 3 (7): Empty Traits Socket, Firing Line, Focused Fury, Frenzy, Headstone, One for All, Tap the Trigger
- Copy 1: Field Prep + Headstone
- Copy 2: Genesis + Headstone
- Copy 3: Genesis + Tap the Trigger

### Royal Chase
Scout Rifle · Void · obtainable · GFS 166 · pool 30 combos · 3 copies · 3 combos covered
- Pool col 2 (6): Auto-Loading Holster, Field Prep, Full Auto Trigger System, Grave Robber, No Distractions, Slideways
- Pool col 3 (5): Dragonfly, Multikill Clip, Quickdraw, Threat Detector, Thresh
- Copy 1: Full Auto Trigger System + Quickdraw
- Copy 2: No Distractions + Threat Detector
- Copy 3: Slideways + Quickdraw

### Shattered Cipher
Machine Gun · Void · obtainable · GFS 282 · pool 36 combos · 3 copies · 3 combos covered
- Pool col 2 (6): Auto-Loading Holster, Field Prep, Heating Up, Slideways, Tunnel Vision, Under Pressure
- Pool col 3 (6): Adrenaline Junkie, Rampage, Snapshot Sights, Surrounded, Unrelenting, Zen Moment
- Copy 1: Field Prep + Zen Moment
- Copy 2: Heating Up + Zen Moment
- Copy 3: Tunnel Vision + Zen Moment

### Tarantula
Linear Fusion Rifle · Arc · obtainable · GFS 328 · pool 36 combos · 3 copies · 3 combos covered
- Pool col 2 (6): Feeding Frenzy, Field Prep, Firmly Planted, Genesis, Moving Target, Pulse Monitor
- Pool col 3 (6): Box Breathing, Dragonfly, Kill Clip, Rampage, Snapshot Sights, Wellspring
- Copy 1: Feeding Frenzy + Box Breathing
- Copy 2: Pulse Monitor + Box Breathing
- Copy 3: Genesis + Kill Clip

### The Guiding Sight
Scout Rifle · Strand · obtainable · GFS 346 · pool 36 combos · 3 copies · 3 combos covered
- Pool col 2 (6): Demolitionist, Enlightened Action, Gutshot Straight, Moving Target, Perpetual Motion, Tunnel Vision
- Pool col 3 (6): Adrenaline Junkie, Cascade Point, Encore, Hatchling, Kill Clip, Precision Instrument
- Copy 1: Gutshot Straight + Encore
- Copy 2: Tunnel Vision + Encore
- Copy 3: Gutshot Straight + Precision Instrument

### Boondoggle Mk. 55
Submachine Gun · Kinetic · obtainable · GFS 276 · pool 36 combos · 2 copies · 2 combos covered
- Pool col 2 (6): Closing Time, Encore, Hip-Fire Grip, Pugilist, Subsistence, To the Pain
- Pool col 3 (6): Adagio, Harmony, Killing Wind, Offhand Strike, Swashbuckler, Tap the Trigger
- Copy 1: Closing Time + Tap the Trigger
- Copy 2: To the Pain + Killing Wind

### Bump in the Night
Rocket Launcher · Stasis · craftable · GFS 634 · pool 48 combos · 2 copies · 2 combos covered
- Pool col 2 (7): Auto-Loading Holster, Demolitionist, Empty Traits Socket, Field Prep, Stats for All, Steady Hands, Tracking Module
- Pool col 3 (7): Chain Reaction, Chill Clip, Empty Traits Socket, Frenzy, Turnabout, Unrelenting, Vorpal Weapon
- Copy 1: Tracking Module + Chill Clip
- Copy 2: Tracking Module + Unrelenting

### Caretaker
Sword · Solar · craftable · GFS 325 · pool 35 combos · 2 copies · 2 combos covered
- Pool col 2 (6): Duelist's Trance, Empty Traits Socket, Energy Transfer, Flash Counter, Relentless Strikes, Tireless Blade
- Pool col 3 (6): Assassin's Blade, Empty Traits Socket, Incandescent, One for All, Surrounded, Valiant Charge
- Copy 1: Duelist's Trance + Incandescent
- Copy 2: Relentless Strikes + Incandescent

### Code Duello
Rocket Launcher · Solar · obtainable · GFS 267 · pool 30 combos · 2 copies · 2 combos covered
- Pool col 2 (5): Auto-Loading Holster, Field Prep, Impulse Amplifier, Quickdraw, Surplus
- Pool col 3 (6): Ambitious Assassin, Chain Reaction, Cluster Bomb, Frenzy, Lasting Impression, Unrelenting
- Copy 1: Surplus + Ambitious Assassin
- Copy 2: Surplus + Cluster Bomb

### Enigma's Draw
Sidearm · Kinetic · obtainable · GFS 205 · pool 25 combos · 2 copies · 2 combos covered
- Pool col 2 (5): Full Auto Trigger System, Grave Robber, Opening Shot, Triple Tap, Zen Moment
- Pool col 3 (5): Demolitionist, Elemental Capacitor, Rangefinder, Rapid Hit, Swashbuckler
- Copy 1: Full Auto Trigger System + Rapid Hit
- Copy 2: Grave Robber + Rapid Hit

### Forge's Pledge
Pulse Rifle · Solar · obtainable · GFS 578 · pool 56 combos · 2 copies · 2 combos covered
- Pool col 2 (7): Auto-Loading Holster, Heating Up, Quickdraw, Stats for All, Surplus, Tunnel Vision, Zen Moment
- Pool col 3 (8): Elemental Capacitor, Iron Grip, Multikill Clip, One for All, Rampage, Snapshot Sights, Unrelenting, Wellspring
- Copy 1: Auto-Loading Holster + Iron Grip
- Copy 2: Surplus + Iron Grip

### Harsh Language
Grenade Launcher · Void · obtainable · GFS 238 · pool 36 combos · 2 copies · 2 combos covered
- Pool col 2 (6): Envious Assassin, Field Prep, Shot Swap, Stats for All, Threat Detector, Wellspring
- Pool col 3 (6): Adrenaline Junkie, Destabilizing Rounds, Disruption Break, Golden Tricorn, Repulsor Brace, Unrelenting
- Copy 1: Wellspring + Disruption Break
- Copy 2: Envious Assassin + Repulsor Brace

### Hoosegow
Rocket Launcher · Arc · obtainable · GFS 262 · pool 30 combos · 2 copies · 2 combos covered
- Pool col 2 (6): Auto-Loading Holster, Field Prep, Pulse Monitor, Snapshot Sights, Threat Detector, Tracking Module
- Pool col 3 (5): Cluster Bomb, Demolitionist, Kill Clip, Quickdraw, Rangefinder
- Copy 1: Tracking Module + Demolitionist
- Copy 2: Tracking Module + Rangefinder

### IKELOS_HC_v1.0.3
Hand Cannon · Void · craftable · GFS 836 · pool 71 combos · 2 copies · 2 combos covered
- Pool col 2 (8): Air Assault, Empty Traits Socket, Offhand Strike, Rapid Hit, Stats for All, Subsistence, Triple Tap, Well-Rounded
- Pool col 3 (9): Adaptive Munitions, Empty Traits Socket, Focused Fury, Frenzy, Golden Tricorn, Golden Tricorn Enhanced, One for All, Rampage, Repulsor Brace
- Copy 1: Air Assault + Adaptive Munitions
- Copy 2: Offhand Strike + Repulsor Brace

### Path of Least Resistance
Trace Rifle · Arc · craftable · GFS 683 · pool 63 combos · 2 copies · 2 combos covered
- Pool col 2 (8): Adaptive Munitions, Dynamic Sway Reduction, Empty Traits Socket, Hip-Fire Grip, Shoot to Loot, Stats for All, Subsistence, Triple Tap
- Pool col 3 (8): Dragonfly, Empty Traits Socket, Focused Fury, Gutshot Straight, Harmony, One for All, Tap the Trigger, Voltshot
- Copy 1: Adaptive Munitions + Gutshot Straight
- Copy 2: Adaptive Munitions + Voltshot

### Perpetualis
Auto Rifle · Strand · craftable · GFS 671 · pool 71 combos · 2 copies · 2 combos covered
- Pool col 2 (8): Elemental Capacitor, Empty Traits Socket, Envious Assassin, Hip-Fire Grip, Keep Away, Killing Wind, Perfect Float, Zen Moment
- Pool col 3 (9): Cascade Point, Demolitionist, Empty Traits Socket, Eye of the Storm, Golden Tricorn, Golden Tricorn Enhanced, Hatchling, Offhand Strike, Target Lock
- Copy 1: Hip-Fire Grip + Hatchling
- Copy 2: Zen Moment + Offhand Strike

### Persuader
Sniper Rifle · Void · obtainable · GFS 320 · pool 36 combos · 2 copies · 2 combos covered
- Pool col 2 (6): Discord, Keep Away, Perfect Float, Rapid Hit, Repulsor Brace, Surplus
- Pool col 3 (6): Destabilizing Rounds, High Ground, Moving Target, Opening Shot, Precision Instrument, Triple Tap
- Copy 1: Perfect Float + Triple Tap
- Copy 2: Surplus + Triple Tap

### Piece of Mind
Pulse Rifle · Kinetic · craftable · GFS 693 · pool 48 combos · 2 copies · 2 combos covered
- Pool col 2 (7): Auto-Loading Holster, Compulsive Reloader, Empty Traits Socket, Heating Up, Overflow, Perpetual Motion, Stats for All
- Pool col 3 (7): Adrenaline Junkie, Elemental Capacitor, Empty Traits Socket, Focused Fury, Harmony, Moving Target, Vorpal Weapon
- Copy 1: Overflow + Moving Target
- Copy 2: Overflow + Elemental Capacitor

### Snorri FR5
Fusion Rifle · Void · obtainable · GFS 356 · pool 36 combos · 2 copies · 2 combos covered
- Pool col 2 (6): Compulsive Reloader, Firmly Planted, Heating Up, Stats for All, Steady Hands, Surplus
- Pool col 3 (6): Frenzy, High-Impact Reserves, One for All, Reservoir Burst, Successful Warm-Up, Wellspring
- Copy 1: Steady Hands + Reservoir Burst
- Copy 2: Surplus + Reservoir Burst

### Typhon GL5
Grenade Launcher · Stasis · obtainable · GFS 433 · pool 36 combos · 2 copies · 2 combos covered
- Pool col 2 (6): Demolitionist, Genesis, Impulse Amplifier, Stats for All, Steady Hands, Unrelenting
- Pool col 3 (6): Adrenaline Junkie, Chill Clip, Explosive Light, Frenzy, One for All, Wellspring
- Copy 1: Genesis + Chill Clip
- Copy 2: Steady Hands + Explosive Light

### Until Its Return
Shotgun · Strand · craftable · GFS 630 · pool 63 combos · 2 copies · 2 combos covered
- Pool col 2 (8): Auto-Loading Holster, Empty Traits Socket, Ensemble, Offhand Strike, Overflow, Steady Hands, Threat Detector, Well-Rounded
- Pool col 3 (8): Adrenaline Junkie, Cascade Point, Collective Action, Empty Traits Socket, Harmony, Surrounded, Trench Barrel, Vorpal Weapon
- Copy 1: Offhand Strike + Trench Barrel
- Copy 2: Well-Rounded + Collective Action

### Whispering Slab
Combat Bow · Kinetic · obtainable · GFS 431 · pool 36 combos · 2 copies · 2 combos covered
- Pool col 2 (6): Archer's Tempo, Demolitionist, Hip-Fire Grip, Lone Wolf, Perpetual Motion, Pugilist
- Pool col 3 (6): Adrenaline Junkie, Gutshot Straight, High Ground, Opening Shot, Swashbuckler, Vorpal Weapon
- Copy 1: Archer's Tempo + High Ground
- Copy 2: Lone Wolf + Gutshot Straight

### Blast Battue
Grenade Launcher · Arc · obtainable · GFS 368 · pool 36 combos · 1 copy · 1 combo covered
- Pool col 2 (6): Clown Cartridge, Killing Wind, Moving Target, Pulse Monitor, Quickdraw, Threat Detector
- Pool col 3 (6): Auto-Loading Holster, Chain Reaction, Disruption Break, Rampage, Snapshot Sights, Wellspring
- Copy 1: Clown Cartridge + Disruption Break

### Breachlight
Sidearm · Kinetic · obtainable · GFS 387 · pool 36 combos · 1 copy · 1 combo covered
- Pool col 2 (6): Demolitionist, Hip-Fire Grip, Outlaw, Pulse Monitor, Threat Detector, Under Pressure
- Pool col 3 (6): Elemental Capacitor, Multikill Clip, Osmosis, Quickdraw, Rampage, Vorpal Weapon
- Copy 1: Outlaw + Quickdraw

### Escape Velocity
Submachine Gun · Kinetic · obtainable · GFS 221 · pool 25 combos · 1 copy · 1 combo covered
- Pool col 2 (5): Grave Robber, Hip-Fire Grip, Overflow, Threat Detector, Zen Moment
- Pool col 3 (5): Elemental Capacitor, Osmosis, Quickdraw, Surrounded, Vorpal Weapon
- Copy 1: Overflow + Osmosis

### Eternity's Edge
Sword · Solar · obtainable · GFS 216 · pool 20 combos · 1 copy · 1 combo covered
- Pool col 2 (4): Energy Transfer, Relentless Strikes, Thresh, Tireless Blade
- Pool col 3 (5): Assassin's Blade, Counterattack, Flash Counter, Surrounded, Whirlwind Blade
- Copy 1: Thresh + Flash Counter

### False Promises
Auto Rifle · Stasis · obtainable · GFS 268 · pool 36 combos · 1 copy · 1 combo covered
- Pool col 2 (6): Ambitious Assassin, Dynamic Sway Reduction, Enlightened Action, Feeding Frenzy, Loose Change, Surplus
- Pool col 3 (6): Cascade Point, Headstone, High Ground, Rampage, Swashbuckler, Zen Moment
- Copy 1: Surplus + Zen Moment

### Fugue-55
Sniper Rifle · Void · obtainable · GFS 372 · pool 36 combos · 1 copy · 1 combo covered
- Pool col 2 (6): Auto-Loading Holster, Compulsive Reloader, Fourth Time's the Charm, Lead from Gold, No Distractions, Steady Hands
- Pool col 3 (6): Box Breathing, Firing Line, Focused Fury, Moving Target, Snapshot Sights, Vorpal Weapon
- Copy 1: Lead from Gold + Box Breathing

### Funnelweb
Submachine Gun · Void · obtainable · GFS 470 · pool 36 combos · 1 copy · 1 combo covered
- Pool col 2 (6): Auto-Loading Holster, Killing Wind, Perpetual Motion, Pulse Monitor, Steady Hands, Subsistence
- Pool col 3 (6): Adrenaline Junkie, Elemental Capacitor, Focused Fury, Frenzy, Rangefinder, Thresh
- Copy 1: Pulse Monitor + Rangefinder

### Gallu RR3
Sniper Rifle · Arc · obtainable · GFS 318 · pool 36 combos · 1 copy · 1 combo covered
- Pool col 2 (6): Ensemble, Heating Up, No Distractions, Overflow, Shoot to Loot, Steady Hands
- Pool col 3 (6): Dragonfly, Focused Fury, Golden Tricorn, Harmony, Snapshot Sights, Turnabout
- Copy 1: Overflow + Turnabout

### Geodetic HSm
Sword · Void · obtainable · GFS 348 · pool 36 combos · 1 copy · 1 combo covered
- Pool col 2 (6): Duelist's Trance, Energy Transfer, Flash Counter, Relentless Strikes, Repulsor Brace, Tireless Blade
- Pool col 3 (6): Assassin's Blade, Collective Action, Destabilizing Rounds, En Garde, One for All, Whirlwind Blade
- Copy 1: Repulsor Brace + En Garde

### Interference VI
Grenade Launcher · Arc · obtainable · GFS 170 · pool 16 combos · 1 copy · 1 combo covered
- Pool col 2 (4): Auto-Loading Holster, Clown Cartridge, Field Prep, Grave Robber
- Pool col 3 (4): Demolitionist, Full Court, Swashbuckler, Threat Detector
- Copy 1: Clown Cartridge + Swashbuckler

### Irukandji
Sniper Rifle · Stasis · obtainable · GFS 390 · pool 36 combos · 1 copy · 1 combo covered
- Pool col 2 (6): Envious Assassin, Fourth Time's the Charm, Keep Away, Rapid Hit, Shoot to Loot, Under Pressure
- Pool col 3 (6): Eye of the Storm, Firing Line, Focused Fury, Harmony, Headstone, Opening Shot
- Copy 1: Fourth Time's the Charm + Firing Line

### Jararaca-3sr
Scout Rifle · Stasis · obtainable · GFS 362 · pool 36 combos · 1 copy · 1 combo covered
- Pool col 2 (6): Fourth Time's the Charm, Hip-Fire Grip, Perfect Float, Perpetual Motion, Rapid Hit, Tunnel Vision
- Pool col 3 (6): Focused Fury, Golden Tricorn, Gutshot Straight, Headstone, Kill Clip, Snapshot Sights
- Copy 1: Perfect Float + Snapshot Sights

### Just in Case
Sword · Solar · obtainable · GFS 228 · pool 36 combos · 1 copy · 1 combo covered
- Pool col 2 (6): Energy Transfer, Flash Counter, Relentless Strikes, Tireless Blade, Unrelenting, Wellspring
- Pool col 3 (6): Collective Action, En Garde, Incandescent, Thresh, Valiant Charge, Whirlwind Blade
- Copy 1: Energy Transfer + Thresh

### Krait
Auto Rifle · Stasis · obtainable · GFS 429 · pool 36 combos · 1 copy · 1 combo covered
- Pool col 2 (6): Auto-Loading Holster, Compulsive Reloader, Overflow, Stats for All, Steady Hands, Subsistence
- Pool col 3 (6): Adagio, Focused Fury, Headstone, Moving Target, One for All, Vorpal Weapon
- Copy 1: Overflow + Adagio

### Memory Interdict
Grenade Launcher · Void · obtainable · GFS 368 · pool 42 combos · 1 copy · 1 combo covered
- Pool col 2 (6): Auto-Loading Holster, Clown Cartridge, Impulse Amplifier, Pulse Monitor, Quickdraw, Surplus
- Pool col 3 (7): Chain Reaction, Danger Zone, Disruption Break, Elemental Capacitor, Rampage, Unrelenting, Wellspring
- Copy 1: Impulse Amplifier + Elemental Capacitor

### Nature of the Beast
Hand Cannon · Arc · obtainable · GFS 256 · pool 25 combos · 1 copy · 1 combo covered
- Pool col 2 (5): Hip-Fire Grip, Quickdraw, Snapshot Sights, Subsistence, Under Pressure
- Pool col 3 (5): Demolitionist, Dragonfly, High-Impact Reserves, Rangefinder, Vorpal Weapon
- Copy 1: Snapshot Sights + Dragonfly

### Nature Reclaimed
Scout Rifle · Solar · obtainable · GFS 366 · pool 36 combos · 1 copy · 1 combo covered
- Pool col 2 (6): Heal Clip, Killing Wind, Lone Wolf, Outlaw, Rapid Hit, Shoot to Loot
- Pool col 3 (6): Box Breathing, Desperate Measures, Explosive Payload, Incandescent, Kill Clip, Precision Instrument
- Copy 1: Killing Wind + Box Breathing

### Perses-D
Scout Rifle · Stasis · obtainable · GFS 482 · pool 36 combos · 1 copy · 1 combo covered
- Pool col 2 (6): Compulsive Reloader, Perpetual Motion, Rapid Hit, Shoot to Loot, Stats for All, Tunnel Vision
- Pool col 3 (6): Explosive Payload, Focused Fury, Headstone, One for All, Opening Shot, Vorpal Weapon
- Copy 1: Stats for All + Explosive Payload

### Quickfang
Sword · Void · obtainable · GFS 151 · pool 16 combos · 1 copy · 1 combo covered
- Pool col 2 (4): Energy Transfer, Relentless Strikes, Thresh, Tireless Blade
- Pool col 3 (4): Assassin's Blade, En Garde, Flash Counter, One for All
- Copy 1: Energy Transfer + Flash Counter

### Retrofit Escapade
Machine Gun · Void · craftable · GFS 910 · pool 71 combos · 1 copy · 1 combo covered
- Pool col 2 (8): Empty Traits Socket, Feeding Frenzy, Field Prep, Fourth Time's the Charm, Heating Up, Stats for All, Turnabout, Zen Moment
- Pool col 3 (9): Empty Traits Socket, Frenzy, Golden Tricorn, Golden Tricorn Enhanced, One for All, Rampage, Tap the Trigger, Target Lock, Vorpal Weapon
- Copy 1: Turnabout + Rampage

### Revoker
Sniper Rifle · Kinetic · obtainable · GFS 1 · pool 1 combos · 1 copy · 1 combo covered
- Pool col 2 (1): Snapshot Sights
- Pool col 3 (1): Reversal of Fortune
- Copy 1: Snapshot Sights + Reversal of Fortune

### Senuna SI6
Sidearm · Stasis · obtainable · GFS 197 · pool 36 combos · 1 copy · 1 combo covered
- Pool col 2 (6): Envious Assassin, Feeding Frenzy, Grave Robber, Perfect Float, Slickdraw, Under Pressure
- Pool col 3 (6): Elemental Capacitor, Golden Tricorn, Gutshot Straight, Headseeker, Headstone, Pugilist
- Copy 1: Envious Assassin + Gutshot Straight

### Shepherd's Watch
Sniper Rifle · Kinetic · obtainable · GFS 375 · pool 36 combos · 1 copy · 1 combo covered
- Pool col 2 (6): Lead from Gold, Moving Target, No Distractions, Outlaw, Tunnel Vision, Under Pressure
- Pool col 3 (6): Demolitionist, Firing Line, Frenzy, Opening Shot, Osmosis, Snapshot Sights
- Copy 1: Tunnel Vision + Firing Line

### Staccato-46
Scout Rifle · Solar · obtainable · GFS 297 · pool 36 combos · 1 copy · 1 combo covered
- Pool col 2 (6): Compulsive Reloader, Outlaw, Shoot to Loot, Triple Tap, Under Pressure, Well-Rounded
- Pool col 3 (6): Adaptive Munitions, Dragonfly, Explosive Payload, Focused Fury, Incandescent, Rampage
- Copy 1: Compulsive Reloader + Incandescent

### Stochastic Variable
Submachine Gun · Arc · obtainable · GFS 332 · pool 36 combos · 1 copy · 1 combo covered
- Pool col 2 (6): Ambitious Assassin, Feeding Frenzy, Killing Wind, Surplus, Under Pressure, Zen Moment
- Pool col 3 (6): Dragonfly, Elemental Capacitor, Multikill Clip, Quickdraw, Unrelenting, Wellspring
- Copy 1: Zen Moment + Wellspring

### Sweet Sorrow
Auto Rifle · Arc · craftable · GFS 739 · pool 48 combos · 1 copy · 1 combo covered
- Pool col 2 (7): Auto-Loading Holster, Empty Traits Socket, Killing Wind, Perpetual Motion, Pulse Monitor, Stats for All, Triple Tap
- Pool col 3 (7): Demolitionist, Empty Traits Socket, Focused Fury, One for All, Tap the Trigger, Turnabout, Vorpal Weapon
- Copy 1: Triple Tap + Turnabout

### The Number
Auto Rifle · Arc · obtainable · GFS 365 · pool 36 combos · 1 copy · 1 combo covered
- Pool col 2 (6): Field Prep, Killing Wind, Pulse Monitor, Surplus, Threat Detector, Under Pressure
- Pool col 3 (6): High-Impact Reserves, Multikill Clip, One for All, Sympathetic Arsenal, Unrelenting, Wellspring
- Copy 1: Pulse Monitor + Sympathetic Arsenal

### Thoughtless
Sniper Rifle · Stasis · craftable · GFS 422 · pool 48 combos · 1 copy · 1 combo covered
- Pool col 2 (7): Compulsive Reloader, Empty Traits Socket, Firmly Planted, Overflow, Perpetual Motion, Rapid Hit, Steady Hands
- Pool col 3 (7): Adagio, Empty Traits Socket, Firing Line, Focused Fury, Headstone, Quickdraw, Snapshot Sights
- Copy 1: Steady Hands + Quickdraw

### Threaded Needle
Linear Fusion Rifle · Void · obtainable · GFS 473 · pool 36 combos · 1 copy · 1 combo covered
- Pool col 2 (6): Auto-Loading Holster, Clown Cartridge, Field Prep, Killing Wind, Rangefinder, Rapid Hit
- Pool col 3 (6): Demolitionist, Dragonfly, Frenzy, Multikill Clip, Thresh, Vorpal Weapon
- Copy 1: Clown Cartridge + Multikill Clip

### Yarovit MG4
Submachine Gun · Stasis · obtainable · GFS 207 · pool 36 combos · 1 copy · 1 combo covered
- Pool col 2 (6): Air Trigger, Dynamic Sway Reduction, Encore, Enlightened Action, Rewind Rounds, Strategist
- Pool col 3 (6): Collective Action, Deconstruct, Desperate Measures, Headstone, Surrounded, Zen Moment
- Copy 1: Encore + Zen Moment
