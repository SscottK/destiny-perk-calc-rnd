from flask import Flask, render_template, request, jsonify
import os
import sqlite3
import re

from config import get_manifest_db_path, manifest_db_exists, stat_display_name
from uniqueness import attach_frame_fields, attach_uniqueness_fields
from perfect_vault import get_perfect_vault

app = Flask(__name__)

PERK_COLUMN_LABELS = ['Barrel', 'Magazine', 'Perk 1', 'Perk 2', 'Origin Trait']
_weapon_season_icon_cache = None
_weapon_icon_watermark_cache = None
_icon_watermark_to_badge_cache = None
_season_badge_by_season_cache = None
_watermark_shadow_url = None


def normalize_item_hash(hash_val):
    if hash_val is None:
        return None
    return int(hash_val) & 0xFFFFFFFF

def normalize_weapon_family(name):
    """Group variants like 'Fatebringer (Timelost)' under 'Fatebringer'."""
    return re.sub(r'\s*\([^)]+\)\s*$', '', name).strip()


def parse_weapon_variant(name):
    """Return (family name, variant label e.g. Timelost or Standard)."""
    match = re.match(r'^(.*?)\s*\(([^)]+)\)\s*$', name)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return name, 'Standard'


def parse_weapon_stats(stats_concat):
    stats = {}
    if not stats_concat:
        return stats
    for stat in stats_concat.split('||'):
        stat_hash, value = stat.split(':', 1)
        value = int(value)
        label = stat_display_name(stat_hash)
        if label.startswith('Stat ') or (value == 0 and label in ('Attack', 'Power')):
            continue
        stats[label] = value
    return stats


def get_watermark_shadow_url():
    """Full-size watermark stripe used behind the season badge (same as DIM)."""
    global _watermark_shadow_url
    if _watermark_shadow_url is not None:
        return _watermark_shadow_url

    _watermark_shadow_url = ""
    if not manifest_db_exists():
        return _watermark_shadow_url

    conn = sqlite3.connect(get_manifest_db_path())
    row = conn.execute(
        """
        SELECT json_extract(json, '$.watermarkDropShadowPath')
        FROM DestinyInventoryItemConstantsDefinition
        LIMIT 1
        """
    ).fetchone()
    conn.close()
    if row and row[0]:
        _watermark_shadow_url = f"https://www.bungie.net{row[0]}"
    return _watermark_shadow_url


def get_season_badge_by_season_cache():
    """Map season number -> small season badge path from manifest icon definitions."""
    global _season_badge_by_season_cache
    if _season_badge_by_season_cache is not None:
        return _season_badge_by_season_cache

    _season_badge_by_season_cache = {}
    if not manifest_db_exists():
        return _season_badge_by_season_cache

    conn = sqlite3.connect(get_manifest_db_path())
    rows = conn.execute(
        """
        SELECT json_extract(json, '$.secondaryBackground') as badge
        FROM DestinyIconDefinition
        WHERE json_extract(json, '$.secondaryBackground') IS NOT NULL
        AND json_extract(json, '$.secondaryBackground') != ''
        """
    ).fetchall()
    conn.close()

    for (badge,) in rows:
        match = re.search(r'season(\d+)', badge, re.IGNORECASE)
        if match:
            _season_badge_by_season_cache[int(match.group(1))] = badge

    return _season_badge_by_season_cache


def get_weapon_icon_watermark_cache():
    """Load weapon hash -> iconWatermark path from manifest."""
    global _weapon_icon_watermark_cache
    if _weapon_icon_watermark_cache is not None:
        return _weapon_icon_watermark_cache

    _weapon_icon_watermark_cache = {}
    if not manifest_db_exists():
        return _weapon_icon_watermark_cache

    conn = sqlite3.connect(get_manifest_db_path())
    rows = conn.execute(
        """
        SELECT json_extract(json, '$.hash') as hash,
               json_extract(json, '$.iconWatermark') as icon_watermark
        FROM DestinyInventoryItemDefinition
        WHERE json_extract(json, '$.itemType') = 3
        AND json_extract(json, '$.inventory.tierType') = 5
        """
    ).fetchall()
    conn.close()

    for hash_val, icon_watermark in rows:
        if hash_val is None or not icon_watermark:
            continue
        _weapon_icon_watermark_cache[normalize_item_hash(hash_val)] = icon_watermark

    return _weapon_icon_watermark_cache


def get_icon_watermark_to_badge_cache():
    """Map full iconWatermark sprite -> small season badge via items that define both."""
    global _icon_watermark_to_badge_cache
    if _icon_watermark_to_badge_cache is not None:
        return _icon_watermark_to_badge_cache

    _icon_watermark_to_badge_cache = {}
    if not manifest_db_exists():
        return _icon_watermark_to_badge_cache

    conn = sqlite3.connect(get_manifest_db_path())
    rows = conn.execute(
        """
        SELECT json_extract(w.json, '$.iconWatermark') as icon_watermark,
               json_extract(icon.json, '$.secondaryBackground') as season_icon
        FROM DestinyInventoryItemDefinition w
        JOIN DestinyIconDefinition icon
            ON icon.id = json_extract(w.json, '$.displayProperties.iconHash')
        WHERE json_extract(w.json, '$.iconWatermark') IS NOT NULL
        AND json_extract(icon.json, '$.secondaryBackground') IS NOT NULL
        AND json_extract(icon.json, '$.secondaryBackground') != ''
        """
    ).fetchall()
    conn.close()

    for icon_watermark, season_icon in rows:
        if icon_watermark and season_icon:
            _icon_watermark_to_badge_cache[icon_watermark] = season_icon

    return _icon_watermark_to_badge_cache


def get_weapon_season_icon_cache():
    """Load weapon hash -> season badge path from IconDefinition.secondaryBackground."""
    global _weapon_season_icon_cache
    if _weapon_season_icon_cache is not None:
        return _weapon_season_icon_cache

    _weapon_season_icon_cache = {}
    if not manifest_db_exists():
        return _weapon_season_icon_cache

    conn = sqlite3.connect(get_manifest_db_path())
    rows = conn.execute(
        """
        SELECT json_extract(w.json, '$.hash') as hash,
               json_extract(icon.json, '$.secondaryBackground') as season_icon
        FROM DestinyInventoryItemDefinition w
        LEFT JOIN DestinyIconDefinition icon
            ON icon.id = json_extract(w.json, '$.displayProperties.iconHash')
        WHERE json_extract(w.json, '$.itemType') = 3
        AND json_extract(w.json, '$.inventory.tierType') = 5
        """
    ).fetchall()
    conn.close()

    for hash_val, season_icon in rows:
        if hash_val is None or not season_icon:
            continue
        _weapon_season_icon_cache[normalize_item_hash(hash_val)] = season_icon

    return _weapon_season_icon_cache


def resolve_weapon_season_icon(weapon_hash, season=None):
    """
    Resolve the small season badge icon for a weapon hash.
    Matches DIM's secondaryBackground when available, with fallbacks for newer items
    whose icon definitions are missing from the manifest.
    """
    item_hash = normalize_item_hash(weapon_hash)
    if item_hash is None:
        return None

    direct = get_weapon_season_icon_cache().get(item_hash)
    if direct:
        return direct

    season_num = int(season or 0)
    if season_num > 0:
        badge = get_season_badge_by_season_cache().get(season_num)
        if badge:
            return badge

    icon_watermark = get_weapon_icon_watermark_cache().get(item_hash)
    if icon_watermark:
        badge = get_icon_watermark_to_badge_cache().get(icon_watermark)
        if badge:
            return badge

    return None


def build_watermark_fields(weapon_hash, season=None):
    season_icon_path = resolve_weapon_season_icon(weapon_hash, season)
    if not season_icon_path:
        return "", ""
    return (
        f"https://www.bungie.net{season_icon_path}",
        get_watermark_shadow_url(),
    )


def attach_weapon_fields(payload, weapon_hash):
    attach_frame_fields(payload, weapon_hash)
    attach_uniqueness_fields(payload, weapon_hash)
    return payload


def build_weapon_version(cursor, weapon_row):
    """Full detail payload for one weapon hash/version."""
    _, variant = parse_weapon_variant(weapon_row['name'])
    season = weapon_row['season'] or 0
    season_label = f'Season {season}' if season else 'Unknown season'

    season_icon_url, watermark_shadow_url = build_watermark_fields(weapon_row['hash'], season)
    payload = {
        'hash': weapon_row['hash'],
        'display_name': weapon_row['name'],
        'family_name': normalize_weapon_family(weapon_row['name']),
        'variant': variant,
        'type': weapon_row['type'],
        'damage_type': weapon_row['damage_type'],
        'ammo_type': weapon_row['ammo_type'],
        'icon_url': f"https://www.bungie.net{weapon_row['icon']}" if weapon_row['icon'] else "",
        'watermark_url': season_icon_url,
        'watermark_shadow_url': watermark_shadow_url,
        'description': weapon_row['description'] or '',
        'flavor_text': weapon_row['flavor_text'] or '',
        'season': season,
        'version_label': f'{season_label} — {variant}',
        'perk_columns': build_perk_columns(cursor, weapon_row['hash']),
        'stats': parse_weapon_stats(weapon_row['stats']),
    }
    return attach_weapon_fields(payload, weapon_row['hash'])

def get_db_connection():
    conn = sqlite3.connect('weapon_perks.db')
    conn.row_factory = sqlite3.Row
    return conn

def _dedupe_versions_by_perk_pool(versions):
    """
    Collapse multiple hashes from the same season + damage type that share
    an identical perk pool into a single logical release.
    """
    groups = {}
    for v in versions:
        cols = v.get('perk_columns') or []
        col_sigs = []
        for col in cols:
            perk_names = sorted({p['name'] for p in col.get('perks', [])})
            col_sigs.append((col.get('label'), tuple(perk_names)))
        key = (
            v.get('season') or 0,
            v.get('damage_type'),
            tuple(col_sigs),
        )
        if key not in groups:
            groups[key] = {
                'versions': [],
            }
        groups[key]['versions'].append(v)

    deduped = []
    for group in groups.values():
        reps = group['versions']
        primary = reps[0].copy()
        internal_hashes = [r['hash'] for r in reps]
        internal_names = [r['display_name'] for r in reps]
        primary['internal_hashes'] = internal_hashes
        primary['internal_display_names'] = internal_names
        primary['variant_count'] = len(internal_hashes)
        if primary['variant_count'] > 1:
            primary['version_label'] = f"{primary['version_label']} (x{primary['variant_count']})"
        deduped.append(primary)

    deduped.sort(key=lambda v: (v.get('season') or 0, v.get('display_name', '')), reverse=True)
    return deduped


def build_weapon_families(include_single=True):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT hash, name, type, damage_type, season, icon
        FROM weapons
        WHERE tier = 'Legendary' AND is_current = 1
    ''')

    families = {}
    for row in cursor.fetchall():
        family_name = normalize_weapon_family(row['name'])
        if family_name not in families:
            families[family_name] = {
                'family_name': family_name,
                'type': row['type'],
                'damage_type': row['damage_type'],
                'icon_url': "",
                'versions': [],
            }
        season_icon_url, watermark_shadow_url = build_watermark_fields(row['hash'], row['season'])
        version_payload = attach_weapon_fields({
            'hash': row['hash'],
            'display_name': row['name'],
            'variant': parse_weapon_variant(row['name'])[1],
            'type': row['type'],
            'damage_type': row['damage_type'],
            'season': row['season'] or 0,
            'icon_url': f"https://www.bungie.net{row['icon']}" if row['icon'] else "",
            'watermark_url': season_icon_url,
            'watermark_shadow_url': watermark_shadow_url,
        }, row['hash'])
        families[family_name]['versions'].append(version_payload)

    conn.close()

    result = []
    for family in families.values():
        # For summaries we collapse purely by season/damage, not full perk pool,
        # to avoid the cost of loading perks for every row.
        if not include_single and len(family['versions']) <= 1:
            continue
        family['versions'].sort(key=lambda v: (v['season'], v['display_name']), reverse=True)
        primary_version = family['versions'][0]
        if primary_version.get('icon_url'):
            family['icon_url'] = primary_version['icon_url']
        family['list_watermark_url'] = primary_version.get('watermark_url', '')
        family['list_watermark_shadow_url'] = primary_version.get('watermark_shadow_url', '')
        family['frame_uniqueness'] = primary_version.get('frame_uniqueness', 0)
        family['perk_uniqueness'] = primary_version.get('perk_uniqueness', 0)
        family['total_uniqueness'] = primary_version.get('total_uniqueness', 0)
        family['archetype'] = primary_version.get('archetype', 'Unknown')
        seasons = sorted({v['season'] for v in family['versions'] if v['season']}, reverse=True)
        variants = sorted({v['variant'] for v in family['versions']})
        # Count unique (season, damage_type) combos for display so that multiple
        # hashes from the same season aren't shown as separate releases.
        unique_releases = {(v['season'], v['damage_type']) for v in family['versions']}
        family['count'] = len(unique_releases)
        family['seasons'] = seasons
        family['variants'] = variants
        family['seasons_label'] = ', '.join(f'S{s}' for s in seasons) if seasons else 'Unknown'
        family['variants_label'] = ', '.join(variants)
        family['has_multiple_versions'] = family['count'] > 1
        result.append(family)

    result.sort(key=lambda f: f['family_name'].lower())
    return result


def get_weapon_family_summaries():
    return build_weapon_families(include_single=True)


def get_all_weapons():
    return get_weapon_family_summaries()

def build_perk_columns(cursor, weapon_hash):
    """Ordered roll columns (left to right) with perks for one weapon."""
    cursor.execute('''
        SELECT wp.column_name, wp.socket_order, p.name, p.icon, p.description
        FROM weapon_perks wp
        JOIN perks p ON wp.perk_hash = p.hash
        WHERE wp.weapon_hash = ?
        AND p.name IS NOT NULL
        AND p.name NOT LIKE '%Shader%'
        AND p.name NOT LIKE '%Keepsake%'
        ORDER BY wp.socket_order, p.name
    ''', (weapon_hash,))

    columns_by_key = {}
    names_by_key = {}
    column_order = []
    for row in cursor.fetchall():
        key = (row['socket_order'], row['column_name'])
        if key not in columns_by_key:
            columns_by_key[key] = []
            names_by_key[key] = set()
            column_order.append(key)

        name = row['name']
        if name in names_by_key[key]:
            # Skip duplicate perk names within the same column to avoid
            # showing the same perk twice when multiple plugs map to it.
            continue

        names_by_key[key].add(name)
        columns_by_key[key].append({
            'name': name,
            'icon_url': f"https://www.bungie.net{row['icon']}" if row['icon'] else "",
            'description': row['description'] or '',
        })

    perk_columns = []
    for index, key in enumerate(column_order):
        label = PERK_COLUMN_LABELS[index] if index < len(PERK_COLUMN_LABELS) else f'Slot {index + 1}'
        perk_columns.append({
            'label': label,
            'socket_type': key[1],
            'perks': columns_by_key[key],
        })
    return perk_columns

def get_weapon_perks(weapon_hash):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT w.*,
               GROUP_CONCAT(ws.stat_name || ':' || ws.stat_value, '||') as stats
        FROM weapons w
        LEFT JOIN weapon_stats ws ON w.hash = ws.weapon_hash
        WHERE w.hash = ? AND w.tier = 'Legendary' AND w.is_current = 1
        GROUP BY w.hash, w.name
    ''', (weapon_hash,))

    weapon = cursor.fetchone()
    if not weapon:
        conn.close()
        return None

    version = build_weapon_version(cursor, weapon)
    conn.close()
    return version


def get_weapon_family(family_name):
    """All released versions of a weapon family, newest first."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT w.*,
               GROUP_CONCAT(ws.stat_name || ':' || ws.stat_value, '||') as stats
        FROM weapons w
        LEFT JOIN weapon_stats ws ON w.hash = ws.weapon_hash
        WHERE w.tier = 'Legendary' AND w.is_current = 1
        GROUP BY w.hash, w.name
        ORDER BY w.season DESC, w.name ASC
    ''')

    versions = []
    for row in cursor.fetchall():
        if normalize_weapon_family(row['name']) != family_name:
            continue
        versions.append(build_weapon_version(cursor, row))

    conn.close()

    if not versions:
        return None

    versions = _dedupe_versions_by_perk_pool(versions)

    return {
        'family_name': family_name,
        'version_count': len(versions),
        'versions': versions,
    }


def find_duplicate_families():
    try:
        return build_weapon_families(include_single=False)
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return {'error': 'Database error occurred'}
    except Exception as e:
        print(f"Error: {e}")
        return {'error': 'An unexpected error occurred'}


def find_duplicate_weapons():
    """Backward-compatible alias for duplicate families."""
    return find_duplicate_families()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/weapons')
def get_weapons():
    weapons = get_all_weapons()
    return jsonify(weapons)

@app.route('/weapon/<weapon_hash>')
def get_weapon(weapon_hash):
    weapon = get_weapon_perks(weapon_hash)
    if weapon is None:
        return jsonify({'error': 'Weapon not found'}), 404
    return jsonify(weapon)


@app.route('/weapon-family/<path:family_name>')
def get_weapon_family_route(family_name):
    family = get_weapon_family(family_name)
    if family is None:
        return jsonify({'error': 'Weapon family not found'}), 404
    return jsonify(family)


def _perfect_vault_mode():
    mode = (request.args.get('mode') or 'full').strip().lower()
    if mode in ('preferred', 'preferred_only', '3x3'):
        return 'preferred_only'
    if mode in ('pos_gfs', 'pos-gfs', 'posgfs'):
        return 'pos_gfs'
    return 'full'


@app.route('/perfect-vault')
def perfect_vault_route():
    force = request.args.get('refresh', '').lower() in ('1', 'true', 'yes')
    mode = _perfect_vault_mode()
    try:
        result = get_perfect_vault(force_refresh=force, mode=mode)
    except RuntimeError as exc:
        return jsonify({'error': str(exc)}), 503
    # Keep response lighter for the list view; full copy plan on demand.
    return jsonify({
        'mode': result['mode'],
        'plane_size': result['plane_size'],
        'pairs_unsolved': result['pairs_unsolved'],
        'lower_bound': result['lower_bound'],
        'total_copies': result['total_copies'],
        'preferred_copies': result['preferred_copies'],
        'fallback_copies': result['fallback_copies'],
        'preferred_weapon_models': result['preferred_weapon_models'],
        'fallback_weapon_models': result['fallback_weapon_models'],
        'eligible_weapon_models': result['eligible_weapon_models'],
        'craftable_weapon_models': result['craftable_weapon_models'],
        'obtainable_weapon_models': result['obtainable_weapon_models'],
        'unique_models_in_vault': result['unique_models_in_vault'],
        'duplicated_models': result.get('duplicated_models'),
        'max_copies_one_model': result.get('max_copies_one_model'),
        'full_plane_size': result.get('full_plane_size'),
        'combos_only_on_fallback': result.get('combos_only_on_fallback'),
        'duplicate_copies': result.get('duplicate_copies'),
        'combos_explicit': result.get('combos_explicit'),
        'combos_credited': result.get('combos_credited'),
        'pos_histogram': result.get('pos_histogram'),
        'top_gfs': result.get('top_gfs'),
        'weapons': result['weapons'],
    })


@app.route('/perfect-vault/copies')
def perfect_vault_copies_route():
    force = request.args.get('refresh', '').lower() in ('1', 'true', 'yes')
    mode = _perfect_vault_mode()
    try:
        result = get_perfect_vault(force_refresh=force, mode=mode)
    except RuntimeError as exc:
        return jsonify({'error': str(exc)}), 503
    return jsonify({
        'mode': result['mode'],
        'total_copies': result['total_copies'],
        'copies': result['copies'],
    })


@app.route('/duplicates')
def get_duplicates():
    duplicates = find_duplicate_weapons()
    if isinstance(duplicates, dict) and 'error' in duplicates:
        return jsonify(duplicates), 500
    return jsonify(duplicates)

@app.route('/watermarks')
def get_watermarks():
    if not manifest_db_exists():
        return jsonify({
            'error': (
                'Manifest database not found. '
                'Set DESTINY_MANIFEST_DB to your Bungie world content .sqlite3 file.'
            )
        }), 503

    world_db = sqlite3.connect(get_manifest_db_path())
    world_db.row_factory = sqlite3.Row
    
    # Get all watermarks with their associated items and details
    cursor = world_db.execute('''
        SELECT 
            json_extract(json, '$.iconWatermark') as path,
            json_extract(json, '$.displayProperties.name') as item_name,
            json_extract(json, '$.itemType') as item_type,
            json_extract(json, '$.displayProperties.icon') as item_icon,
            json_extract(json, '$.collectibleHash') as collectible_hash,
            json_extract(json, '$.hash') as item_hash,
            json_extract(json, '$.displayProperties.description') as item_description,
            (
                SELECT json_extract(w.json, '$.displayProperties.description') 
                FROM DestinyInventoryItemDefinition w 
                WHERE json_extract(w.json, '$.iconWatermark') = json_extract(json, '$.iconWatermark') 
                AND json_extract(w.json, '$.displayProperties.description') IS NOT NULL 
                AND json_extract(w.json, '$.displayProperties.description') != ''
                LIMIT 1
            ) as watermark_description,
            (
                SELECT json_extract(w.json, '$.displayProperties.description') 
                FROM DestinyInventoryItemDefinition w 
                WHERE json_extract(w.json, '$.iconWatermark') = json_extract(json, '$.iconWatermark') 
                AND json_extract(w.json, '$.displayProperties.description') LIKE '%Season%'
                LIMIT 1
            ) as season_description
        FROM DestinyInventoryItemDefinition
        WHERE json_extract(json, '$.iconWatermark') IS NOT NULL 
        AND json_extract(json, '$.iconWatermark') != ''
        ORDER BY 
            CASE WHEN json_extract(json, '$.itemType') = 3 THEN 0 ELSE 1 END,  -- Weapons first
            json_extract(json, '$.displayProperties.name')
    ''')
    
    watermarks = cursor.fetchall()
    world_db.close()
    
    # Process watermarks and categorize them
    result = []
    processed_watermarks = set()  # Track which watermarks we've processed
    
    # Season watermarks mapping
    season_mapping = {
        '2c024f088557ca6cceae1e8030c67169': {'season': 3, 'name': 'Season 3'},
        '0337ec21962f67c7c493fedb447c4a9b': {'season': 5, 'name': 'Season 5'},
        '5ac4a1d48a5221993a41a5bb524eda1b': {'season': 13, 'name': 'Season 13'},
        '671a19eca92ad9dcf39d4e9c92fcdf75': {'season': 15, 'name': 'Season 15'},
        '04de56db6d59127239ed51e82d16c06c': {'season': 16, 'name': 'Season 16'},
        '6e4fdb4800c34ccac313dd1598bd7589': {'season': 16, 'name': 'Season 16'},
        'ad7fdb049d430c1fac1d20cf39059702': {'season': 19, 'name': 'Season 19'},
        'd92e077d544925c4f37e564158f8f76a': {'season': 19, 'name': 'Season 19'},
        'e3ea0bd2e889b605614276876667759c': {'season': 20, 'name': 'Season 20'},
        '6026e9d64e8c2b19f302dafb0286897b': {'season': 20, 'name': 'Season 20'},
        '1f9f59c8cb44': {'season': 21, 'name': 'Season 21'},
        '0aa66ed6af2fe3519b7bd656e760b243': {'season': 22, 'name': 'Season 22'},
        '0d9992493b70af4a882bad79f60ead63': {'season': 23, 'name': 'Season 23'},
        '0e396ee456b82fd189ddecef1c7c9b41': {'season': 24, 'name': 'Season 24'},
        '5586fea4193e34acc835209': {'season': 17, 'name': 'Season 17'},
        'af00bdcd3e3b896e85c1f6': {'season': 17, 'name': 'Season 17'},
        'fb58cd68a9858bd323872be': {'season': 17, 'name': 'Season 17'},
        '5364cc3908dc3615cb0c4b0': {'season': 18, 'name': 'Season 18'},
        'e775dcb3d47e3d54ede24fb': {'season': 18, 'name': 'Season 18'},
        'f80e39c767f399f0b2be625': {'season': 18, 'name': 'Season 18'},
        'b973f89ecd631a3e3d294e9': {'season': 19, 'name': 'Season 19'},
        '525230d9e59656f633ab867': {'season': 19, 'name': 'Season 19'},
        '428c962c15612ea89693349': {'season': 20, 'name': 'Season 20'},
        '4c25426263cacf963777cd4': {'season': 20, 'name': 'Season 20'},
        '448f871a7637fcefb2fccf7': {'season': 21, 'name': 'Season 21'},
        'a3923ae7d2376a1c4eb0f1f': {'season': 21, 'name': 'Season 21'},
        'efdb35540cd169fa6e33499': {'season': 22, 'name': 'Season 22'},
        'ab075a3679d69f40b8c2a31': {'season': 22, 'name': 'Season 22'},
        '23968435c2095c0f81119d82': {'season': 23, 'name': 'Season 23'},
        'ed6c4762c48bd132d538ced': {'season': 23, 'name': 'Season 23'},
        '2352f9d04dc842cfcdda776': {'season': 24, 'name': 'Season 24'}
    }
    
    # Activity watermarks
    activity_mapping = {
        '087085770c064cfce02e4e2cf05e3ee9': 'Trials of Osiris',
        '1448dde4efdb57b07f5473f87c4fccd7': 'Iron Banner',
        '1a4d626ca0a3480878ad124c0b147a75': 'Nightfall',
        '1b6c8b94cec61ea42edb1e2cb6b45a31': 'Raid',
        '1b8a377c3674c2d8b155676a6b72db20': 'Dungeon',
        '10f0303fb149c3e0700a64e642f62ac4': 'Gambit',
        '07999be135e44eb0affc112ebdba4cac': 'Crucible'
    }
    
    def extract_season_from_description(desc):
        if not desc:
            return None
        # Look for patterns like "Season 12", "Season of the Hunt", etc.
        season_number_match = re.search(r'Season (\d+)', desc)
        if season_number_match:
            return int(season_number_match.group(1))
        return None
    
    for watermark in watermarks:
        path = watermark['path']
        hash_val = path.split('/')[-1].split('.')[0]
        is_weapon = watermark['item_type'] == 3
        
        # Determine watermark type and description
        watermark_type = "Other"
        description = ""
        season_number = 0
        
        # Try to get season from hash mapping first
        if hash_val in season_mapping:
            watermark_type = "Season"
            description = season_mapping[hash_val]['name']
            season_number = season_mapping[hash_val]['season']
        elif hash_val in activity_mapping:
            watermark_type = "Activity"
            description = activity_mapping[hash_val]
        
        # If no season number found, try to extract from descriptions
        if season_number == 0:
            # Check item description
            desc_season = extract_season_from_description(watermark['item_description'])
            if desc_season:
                watermark_type = "Season"
                season_number = desc_season
                description = f"Season {desc_season}"
            
            # Check watermark description
            if not desc_season:
                desc_season = extract_season_from_description(watermark['watermark_description'])
                if desc_season:
                    watermark_type = "Season"
                    season_number = desc_season
                    description = f"Season {desc_season}"
            
            # Check season description
            if not desc_season:
                desc_season = extract_season_from_description(watermark['season_description'])
                if desc_season:
                    watermark_type = "Season"
                    season_number = desc_season
                    description = f"Season {desc_season}"
        
        # Skip if:
        # 1. Not a weapon AND not a season/activity watermark
        # 2. Already processed this watermark (for any type)
        if (not is_weapon and watermark_type == "Other") or hash_val in processed_watermarks:
            continue
        
        # Add watermark to processed set
        processed_watermarks.add(hash_val)
        
        result.append({
            'watermark_path': path,
            'watermark_hash': hash_val,
            'type': watermark_type,
            'description': description,
            'season_number': season_number,
            'item_name': watermark['item_name'],
            'item_type': watermark['item_type'],
            'item_icon': watermark['item_icon'],
            'item_hash': watermark['item_hash'],
            'collectible_hash': watermark['collectible_hash'],
            'watermark_description': watermark['watermark_description'],
            'item_description': watermark['item_description'],
            'season_description': watermark['season_description']
        })
    
    # Sort results by type, season number, and description
    result.sort(key=lambda x: (
        {'Season': 0, 'Activity': 1, 'Other': 2}[x['type']],
        x['season_number'] or 999,
        x['description'] or x['type'],
        0 if x['item_type'] == 3 else 1,  # Weapons first within each category
        x['item_name'] or ''
    ))
    
    return jsonify(result)

if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes')
    app.run(debug=debug) 