from flask import Flask, render_template, request, jsonify
import sqlite3
import json
import os
from datetime import datetime
import re

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('weapon_perks.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_all_weapons():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all weapons with their perks
    cursor.execute('''
        SELECT w.*, 
               GROUP_CONCAT(p.name, '||') FILTER (WHERE p.name IS NOT NULL AND p.name NOT LIKE '%Shader%' AND p.name NOT LIKE '%Keepsake%') as perk_names,
               GROUP_CONCAT(p.icon, '||') FILTER (WHERE p.name IS NOT NULL AND p.name NOT LIKE '%Shader%' AND p.name NOT LIKE '%Keepsake%') as perk_icons,
               GROUP_CONCAT(p.description, '||') FILTER (WHERE p.name IS NOT NULL AND p.name NOT LIKE '%Shader%' AND p.name NOT LIKE '%Keepsake%') as perk_descriptions,
               GROUP_CONCAT(wp.column_name, '||') FILTER (WHERE p.name IS NOT NULL AND p.name NOT LIKE '%Shader%' AND p.name NOT LIKE '%Keepsake%') as perk_columns
        FROM weapons w
        LEFT JOIN weapon_perks wp ON w.hash = wp.weapon_hash
        LEFT JOIN perks p ON wp.perk_hash = p.hash
        WHERE w.tier = 'Legendary' AND w.is_current = 1
        GROUP BY w.hash, w.name
        ORDER BY w.name
    ''')
    
    weapons = cursor.fetchall()
    conn.close()
    
    result = []
    for weapon in weapons:
        # Process perks by column
        perks_by_column = {}
        if weapon['perk_names']:
            names = weapon['perk_names'].split('||')
            icons = weapon['perk_icons'].split('||')
            descriptions = weapon['perk_descriptions'].split('||')
            columns = weapon['perk_columns'].split('||')
            
            for name, icon, desc, col in zip(names, icons, descriptions, columns):
                column_key = f"Column_{col}"
                if column_key not in perks_by_column:
                    perks_by_column[column_key] = []
                perks_by_column[column_key].append({
                    'name': name,
                    'icon_url': f"https://www.bungie.net{icon}" if icon else "",
                    'description': desc
                })
        
        result.append({
            'hash': weapon['hash'],
            'name': weapon['name'],
            'type': weapon['type'],
            'damage_type': weapon['damage_type'],
            'icon_url': f"https://www.bungie.net{weapon['icon']}" if weapon['icon'] else "",
            'perks': perks_by_column,
            'season': weapon['season']
        })
    
    return result

def get_weapon_perks(weapon_hash):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get weapon details including stats
    cursor.execute('''
        SELECT w.*, 
               GROUP_CONCAT(p.name, '||') FILTER (WHERE p.name IS NOT NULL AND p.name NOT LIKE '%Shader%' AND p.name NOT LIKE '%Keepsake%') as perk_names,
               GROUP_CONCAT(p.icon, '||') FILTER (WHERE p.name IS NOT NULL AND p.name NOT LIKE '%Shader%' AND p.name NOT LIKE '%Keepsake%') as perk_icons,
               GROUP_CONCAT(p.description, '||') FILTER (WHERE p.name IS NOT NULL AND p.name NOT LIKE '%Shader%' AND p.name NOT LIKE '%Keepsake%') as perk_descriptions,
               GROUP_CONCAT(wp.column_name, '||') FILTER (WHERE p.name IS NOT NULL AND p.name NOT LIKE '%Shader%' AND p.name NOT LIKE '%Keepsake%') as perk_columns,
               GROUP_CONCAT(ws.stat_name || ':' || ws.stat_value, '||') as stats
        FROM weapons w
        LEFT JOIN weapon_perks wp ON w.hash = wp.weapon_hash
        LEFT JOIN perks p ON wp.perk_hash = p.hash
        LEFT JOIN weapon_stats ws ON w.hash = ws.weapon_hash
        WHERE w.hash = ? AND w.tier = 'Legendary' AND w.is_current = 1
        GROUP BY w.hash, w.name
    ''', (weapon_hash,))
    
    weapon = cursor.fetchone()
    conn.close()
    
    if not weapon:
        return None
    
    # Process perks by column
    perks_by_column = {}
    if weapon['perk_names']:
        names = weapon['perk_names'].split('||')
        icons = weapon['perk_icons'].split('||')
        descriptions = weapon['perk_descriptions'].split('||')
        columns = weapon['perk_columns'].split('||')
        
        for name, icon, desc, col in zip(names, icons, descriptions, columns):
            column_key = f"Column_{col}"
            if column_key not in perks_by_column:
                perks_by_column[column_key] = []
            perks_by_column[column_key].append({
                'name': name,
                'icon_url': f"https://www.bungie.net{icon}" if icon else "",
                'description': desc
            })
    
    # Process stats
    stats = {}
    if weapon['stats']:
        for stat in weapon['stats'].split('||'):
            name, value = stat.split(':')
            stats[name] = int(value)
    
    return {
        'name': weapon['name'],
        'type': weapon['type'],
        'damage_type': weapon['damage_type'],
        'ammo_type': weapon['ammo_type'],
        'icon_url': f"https://www.bungie.net{weapon['icon']}" if weapon['icon'] else "",
        'description': weapon['description'],
        'flavor_text': weapon['flavor_text'],
        'perks': perks_by_column,
        'stats': stats,
        'season': weapon['season']
    }

def find_duplicate_weapons():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Find weapons with the same name (only Legendary weapons)
        cursor.execute('''
            SELECT name, COUNT(*) as count, 
                   GROUP_CONCAT(hash) as hashes,
                   GROUP_CONCAT(COALESCE(type, 'Unknown')) as types,
                   GROUP_CONCAT(COALESCE(damage_type, 'Unknown')) as damage_types,
                   GROUP_CONCAT(COALESCE(season, 0)) as seasons
            FROM weapons
            WHERE tier = 'Legendary'
            GROUP BY name
            HAVING COUNT(*) > 1
            ORDER BY count DESC, name ASC
        ''')
        
        duplicates = cursor.fetchall()
        conn.close()
        
        result = []
        for dup in duplicates:
            hashes = dup['hashes'].split(',')
            types = dup['types'].split(',')
            damage_types = dup['damage_types'].split(',')
            seasons = [int(s) for s in (dup['seasons'] or '0').split(',')]
            
            # Create list of weapons with their seasons
            weapons = []
            for i in range(len(hashes)):
                weapons.append({
                    'hash': hashes[i],
                    'type': types[i],
                    'damage_type': damage_types[i],
                    'season': seasons[i]
                })
            
            # Sort weapons by season (newest first)
            weapons.sort(key=lambda x: x['season'], reverse=True)
            
            result.append({
                'name': dup['name'],
                'count': dup['count'],
                'weapons': weapons
            })
        
        return result
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return {'error': 'Database error occurred'}
    except Exception as e:
        print(f"Error: {e}")
        return {'error': 'An unexpected error occurred'}

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
    return jsonify(weapon)

@app.route('/duplicates')
def get_duplicates():
    duplicates = find_duplicate_weapons()
    return jsonify(duplicates)

@app.route('/watermarks')
def get_watermarks():
    # Connect to the world database
    world_db = sqlite3.connect('world_sql_content_4bc957fe614b9ca05b3a93fc27458ae4 - Copy.sqlite3')
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
    app.run(debug=True) 