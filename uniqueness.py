"""Weapon uniqueness scoring (frame, perk pool, total).

Design doc socket 3+4 = socket_order 2+3 (Perk 1 + Perk 2 columns).

Scoring population: most recent release per weapon family only.
Frame inverse-frequency counts are scoped within weapon type.
Perk inverse-frequency counts are global across all recent releases.
"""

import re
import sqlite3
from collections import defaultdict

from config import get_manifest_db_path, manifest_db_exists

# Design doc perk-trait sockets (0-based socket_order in weapon_perks).
PERK_TRAIT_SOCKET_ORDERS = (2, 3)

SLOT_BY_HASH = {
    1498876634: 'Kinetic',
    2465295065: 'Energy',
    953998645: 'Power',
}


def normalize_weapon_family(name):
    """Group variants like 'Fatebringer (Timelost)' under 'Fatebringer'."""
    return re.sub(r'\s*\([^)]+\)\s*$', '', name).strip()


def normalize_item_hash(hash_val):
    if hash_val is None:
        return None
    return int(hash_val) & 0xFFFFFFFF


def _safe_inverse_count(count):
    return 1.0 / max(int(count or 0), 1)


def _round_score(value):
    return round(float(value), 2)


def _select_most_recent_releases(weapon_rows):
    """Keep one row per family: highest season, then hash tie-break."""
    by_family = {}
    for row in weapon_rows:
        family = normalize_weapon_family(row['name'])
        season = row['season'] or 0
        item_hash = row['hash']
        existing = by_family.get(family)
        if not existing or (season, item_hash) > (existing['season'], existing['hash']):
            by_family[family] = row
    return list(by_family.values())


_frame_metadata_cache = None


def load_frame_metadata_cache(weapon_db_path='weapon_perks.db'):
    """Load weapon hash -> {archetype, slot} from manifest intrinsic plug."""
    global _frame_metadata_cache
    if _frame_metadata_cache is not None:
        return _frame_metadata_cache

    conn = sqlite3.connect(weapon_db_path)
    weapon_hashes = {
        normalize_item_hash(row[0])
        for row in conn.execute(
            "SELECT hash FROM weapons WHERE tier = 'Legendary' AND is_current = 1"
        )
    }
    conn.close()

    _frame_metadata_cache = UniquenessEngine()._load_frame_metadata(weapon_hashes)
    return _frame_metadata_cache


def get_weapon_archetype(weapon_hash):
    meta = load_frame_metadata_cache().get(normalize_item_hash(weapon_hash), {})
    return meta.get('archetype') or 'Unknown'


def attach_frame_fields(payload, weapon_hash):
    payload['archetype'] = get_weapon_archetype(weapon_hash)
    return payload


class UniquenessEngine:
    """Compute and cache uniqueness scores for each family's most recent release."""

    def __init__(self):
        self._scores_by_hash = {}
        self._recent_hashes = set()
        self._built = False

    def build(self, weapon_db_path='weapon_perks.db'):
        if self._built:
            return

        conn = sqlite3.connect(weapon_db_path)
        conn.row_factory = sqlite3.Row
        weapons = conn.execute(
            """
            SELECT hash, name, type, damage_type, season
            FROM weapons
            WHERE tier = 'Legendary' AND is_current = 1
            """
        ).fetchall()

        frame_meta = load_frame_metadata_cache(weapon_db_path)

        all_weapon_rows = []
        for row in weapons:
            item_hash = normalize_item_hash(row['hash'])
            meta = frame_meta.get(item_hash, {})
            all_weapon_rows.append({
                'hash': item_hash,
                'name': row['name'],
                'season': row['season'] or 0,
                'type': row['type'] or 'Unknown',
                'damage_type': row['damage_type'] or 'Unknown',
                'slot': meta.get('slot') or 'Unknown',
                'archetype': meta.get('archetype') or 'Unknown',
            })

        weapon_rows = _select_most_recent_releases(all_weapon_rows)
        self._recent_hashes = {row['hash'] for row in weapon_rows}

        # Frame counts: each dimension counted only among same weapon type.
        peers_by_type = defaultdict(list)
        for row in weapon_rows:
            peers_by_type[row['type']].append(row)

        perk_rows = conn.execute(
            """
            SELECT wp.weapon_hash, wp.perk_hash, w.type
            FROM weapon_perks wp
            JOIN weapons w ON w.hash = wp.weapon_hash
            WHERE wp.socket_order IN (?, ?)
            AND w.tier = 'Legendary'
            AND w.is_current = 1
            """,
            PERK_TRAIT_SOCKET_ORDERS,
        ).fetchall()

        perk_hash_to_name = {
            normalize_item_hash(row['hash']): row['name']
            for row in conn.execute("SELECT hash, name FROM perks").fetchall()
        }
        conn.close()

        # Perk counts are global across all recent releases; pool keyed by perk name (socket-agnostic).
        perk_weapon_counts = defaultdict(set)
        weapon_perk_pool = defaultdict(set)

        for weapon_hash, perk_hash, _weapon_type in perk_rows:
            item_hash = normalize_item_hash(weapon_hash)
            if item_hash not in self._recent_hashes:
                continue
            perk_name = perk_hash_to_name.get(normalize_item_hash(perk_hash))
            if not perk_name:
                continue
            perk_weapon_counts[perk_name].add(item_hash)
            weapon_perk_pool[item_hash].add(perk_name)

        for row in weapon_rows:
            item_hash = row['hash']
            peers = peers_by_type[row['type']]

            count_type = len(peers)
            count_archetype = sum(
                1 for peer in peers if peer['archetype'] == row['archetype']
            )
            count_slot = sum(1 for peer in peers if peer['slot'] == row['slot'])
            count_element = sum(
                1 for peer in peers if peer['damage_type'] == row['damage_type']
            )
            count_arch_elem = sum(
                1 for peer in peers
                if peer['archetype'] == row['archetype']
                and peer['damage_type'] == row['damage_type']
            )

            frame_uniqueness = (
                _safe_inverse_count(count_type)
                + _safe_inverse_count(count_archetype)
                + _safe_inverse_count(count_slot)
                + _safe_inverse_count(count_element)
                + _safe_inverse_count(count_arch_elem)
            ) * 10.0

            perk_uniqueness = 0.0
            for perk_name in weapon_perk_pool.get(item_hash, ()):
                weapon_count = len(perk_weapon_counts[perk_name])
                perk_uniqueness += _safe_inverse_count(weapon_count)
            perk_uniqueness *= 10.0

            total_uniqueness = (frame_uniqueness * perk_uniqueness) / 10.0

            self._scores_by_hash[item_hash] = {
                'frame_uniqueness': _round_score(frame_uniqueness),
                'perk_uniqueness': _round_score(perk_uniqueness),
                'total_uniqueness': _round_score(total_uniqueness),
            }

        self._built = True

    def _load_frame_metadata(self, weapon_hashes):
        meta = {}
        if not manifest_db_exists() or not weapon_hashes:
            return meta

        conn = sqlite3.connect(get_manifest_db_path())
        rows = conn.execute(
            """
            SELECT json_extract(json, '$.hash') as hash,
                   json_extract(json, '$.equippingBlock.equipmentSlotTypeHash') as slot_hash,
                   json_extract(json, '$.sockets.socketEntries[0].singleInitialItemHash') as frame_plug_hash
            FROM DestinyInventoryItemDefinition
            WHERE json_extract(json, '$.itemType') = 3
            AND json_extract(json, '$.inventory.tierType') = 5
            """
        ).fetchall()

        plug_hashes = set()
        raw_meta = {}
        for hash_val, slot_hash, frame_plug_hash in rows:
            item_hash = normalize_item_hash(hash_val)
            if item_hash not in weapon_hashes:
                continue
            frame_plug = normalize_item_hash(frame_plug_hash) if frame_plug_hash else None
            if frame_plug:
                plug_hashes.add(frame_plug)
            raw_meta[item_hash] = {
                'slot_hash': slot_hash,
                'frame_plug': frame_plug,
            }

        plug_names = {}
        if plug_hashes:
            placeholders = ','.join('?' for _ in plug_hashes)
            plug_rows = conn.execute(
                f"""
                SELECT json_extract(json, '$.hash') as hash,
                       json_extract(json, '$.displayProperties.name') as name
                FROM DestinyInventoryItemDefinition
                WHERE json_extract(json, '$.hash') IN ({placeholders})
                """,
                tuple(plug_hashes),
            ).fetchall()
            for plug_hash, plug_name in plug_rows:
                plug_names[normalize_item_hash(plug_hash)] = plug_name or 'Unknown'

        conn.close()

        for item_hash, values in raw_meta.items():
            slot = SLOT_BY_HASH.get(values['slot_hash'], 'Unknown')
            plug_name = plug_names.get(values['frame_plug'], 'Unknown')
            archetype = plug_name.replace(' Frame', '').strip() or 'Unknown'
            meta[item_hash] = {
                'slot': slot,
                'archetype': archetype,
            }

        return meta

    def is_recent_release(self, weapon_hash):
        if not self._built:
            self.build()
        return normalize_item_hash(weapon_hash) in self._recent_hashes

    def get_scores(self, weapon_hash):
        if not self._built:
            self.build()
        item_hash = normalize_item_hash(weapon_hash)
        return self._scores_by_hash.get(item_hash, {
            'frame_uniqueness': 0.0,
            'perk_uniqueness': 0.0,
            'total_uniqueness': 0.0,
        })


_engine = None


def get_uniqueness_engine():
    global _engine
    if _engine is None:
        _engine = UniquenessEngine()
        _engine.build()
    return _engine


def get_weapon_uniqueness(weapon_hash):
    return get_uniqueness_engine().get_scores(weapon_hash)


def attach_uniqueness_fields(payload, weapon_hash):
    scores = get_weapon_uniqueness(weapon_hash)
    payload.update(scores)
    return payload
