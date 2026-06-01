"""
TODO (Next Steps):
1. Delete existing weapon_perks.db
2. Run migration to create fresh database with only legendary weapons
3. Verify perk display in app.py and frontend
4. Test that all perks show correctly in their respective columns

Last modified: Simplified to only include essential weapon data
"""

import sqlite3
import json
import time

from config import get_manifest_db_path, manifest_db_exists, resolve_watermark_season

MANIFEST_DB_PATH = get_manifest_db_path()

def row_value(row, key, default=None):
    """Read a sqlite3.Row column (never use `'key' in row` — that always fails)."""
    try:
        value = row[key]
    except (KeyError, IndexError):
        return default
    return default if value is None else value

# DestinySocketCategoryDefinition hash for rollable perk columns
WEAPON_PERKS_SOCKET_CATEGORY = 4241085061

def is_rollable_plug_name(name):
    """Exclude cosmetics, stat tiers, and mod-socket items when using raw reusable plugs."""
    if not name:
        return False
    lower = name.lower()
    if any(x in lower for x in ('keepsake', 'shader', 'ornament')):
        return False
    if name.startswith('Tier '):
        return False
    if 'adept' in lower and ('mod' in lower or 'enhancement' in lower or 'targeting' in lower):
        return False
    if 'finder enhancement' in lower or 'surge' in lower and 'resonance' in lower:
        return False
    return True

def get_weapon_perk_socket_indexes(socket_categories_json, socket_entries_json):
    """Socket indexes for WEAPON PERKS, in left-to-right display order."""
    if socket_categories_json:
        for category in json.loads(socket_categories_json):
            if convert_hash(category.get('socketCategoryHash')) == WEAPON_PERKS_SOCKET_CATEGORY:
                return category.get('socketIndexes', [])
    if not socket_entries_json:
        return []
    entries = json.loads(socket_entries_json)
    fallback = []
    for index, socket_entry in enumerate(entries):
        if not socket_entry:
            continue
        if socket_entry.get('randomizedPlugSetHash') or socket_entry.get('reusablePlugSetHash'):
            fallback.append(index)
    return fallback

def get_plug_hashes_from_plug_set(manifest_db, plug_set_hash):
    plug_set_hash = convert_hash(plug_set_hash)
    row = manifest_db.execute(
        """
        SELECT json_extract(json, '$.reusablePlugItems') as reusablePlugItems
        FROM DestinyPlugSetDefinition
        WHERE json_extract(json, '$.hash') = ?
        """,
        (plug_set_hash,),
    ).fetchone()
    if not row or not row['reusablePlugItems']:
        return []
    plug_hashes = []
    for plug_item in json.loads(row['reusablePlugItems']):
        plug_hash = convert_hash(plug_item.get('plugItemHash'))
        if plug_hash:
            plug_hashes.append(plug_hash)
    return plug_hashes

def get_rollable_plug_hashes_for_socket(socket_entry, manifest_db):
    """Plugs that can roll in this socket (plug set pools, not mod/cosmetic sockets)."""
    if socket_entry.get('randomizedPlugSetHash'):
        return get_plug_hashes_from_plug_set(manifest_db, socket_entry['randomizedPlugSetHash'])
    if socket_entry.get('reusablePlugSetHash'):
        return get_plug_hashes_from_plug_set(manifest_db, socket_entry['reusablePlugSetHash'])
    plug_hashes = []
    for plug in socket_entry.get('reusablePlugItems', []):
        plug_hash = convert_hash(plug.get('plugItemHash'))
        if plug_hash:
            plug_hashes.append(plug_hash)
    return plug_hashes

def convert_hash(hash_value):
    """Convert hash to signed 32-bit integer if needed"""
    if isinstance(hash_value, str):
        return int(hash_value) & 0xFFFFFFFF
    return hash_value

def migrate_data():
    print("Starting migration...")
    start_time = time.time()
    
    try:
        if not manifest_db_exists():
            raise FileNotFoundError(
                f"Manifest database not found at: {MANIFEST_DB_PATH}\n"
                "Set DESTINY_MANIFEST_DB to the path of your Bungie world content .sqlite3 file."
            )

        # Connect to databases
        print("Connecting to databases...")
        print(f"Using manifest: {MANIFEST_DB_PATH}")
        manifest_db = sqlite3.connect(MANIFEST_DB_PATH)
        manifest_db.row_factory = sqlite3.Row
        print("Connected to manifest database")
        weapon_db = sqlite3.connect("weapon_perks.db")
        print("Connected to weapon database")
        
        # Enable WAL mode and optimize settings
        print("Configuring database settings...")
        weapon_db.execute("PRAGMA journal_mode=WAL")
        weapon_db.execute("PRAGMA synchronous=NORMAL")
        weapon_db.execute("PRAGMA cache_size=-2000")
        
        # Create database schema
        print("Creating database schema...")
        weapon_db.execute("""
        CREATE TABLE IF NOT EXISTS weapons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hash INTEGER UNIQUE NOT NULL,
            name TEXT NOT NULL,
            type TEXT,
            damage_type TEXT,
            ammo_type TEXT,
            icon TEXT,
            description TEXT,
            flavor_text TEXT,
            tier TEXT,
            season INTEGER,
            is_current BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        weapon_db.execute("""
        CREATE TABLE IF NOT EXISTS weapon_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weapon_hash INTEGER NOT NULL,
            stat_name TEXT NOT NULL,
            stat_value INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (weapon_hash) REFERENCES weapons(hash),
            UNIQUE(weapon_hash, stat_name)
        )
        """)
        
        weapon_db.execute("""
        CREATE TABLE IF NOT EXISTS perks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hash INTEGER UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            icon TEXT,
            usage_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        weapon_db.execute("""
        CREATE TABLE IF NOT EXISTS weapon_perks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weapon_hash INTEGER NOT NULL,
            perk_hash INTEGER NOT NULL,
            column_name TEXT NOT NULL,
            socket_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (weapon_hash) REFERENCES weapons(hash),
            FOREIGN KEY (perk_hash) REFERENCES perks(hash)
        )
        """)
        try:
            weapon_db.execute(
                "ALTER TABLE weapon_perks ADD COLUMN socket_order INTEGER NOT NULL DEFAULT 0"
            )
        except sqlite3.OperationalError:
            pass
        
        # Create indexes
        weapon_db.execute("CREATE INDEX IF NOT EXISTS idx_weapon_type ON weapons(type)")
        weapon_db.execute("CREATE INDEX IF NOT EXISTS idx_perk_type ON perks(name)")
        weapon_db.execute("CREATE INDEX IF NOT EXISTS idx_weapon_perks ON weapon_perks(weapon_hash, perk_hash)")
        weapon_db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_weapon_perk_column
            ON weapon_perks(weapon_hash, perk_hash, column_name)
        """)

        print("Clearing perks and stats tables for fresh migration...")
        weapon_db.execute("DELETE FROM weapon_perks")
        weapon_db.execute("DELETE FROM perks")
        weapon_db.execute("DELETE FROM weapon_stats")
        weapon_db.commit()
        
        # Pre-load all perks into memory
        print("Pre-loading perks into memory...")
        perk_cache = {}
        perk_query = """
        SELECT json_extract(json, '$.hash') as hash,
               json_extract(json, '$.displayProperties.name') as name,
               json_extract(json, '$.displayProperties.description') as description,
               json_extract(json, '$.displayProperties.icon') as icon
        FROM DestinyInventoryItemDefinition
        WHERE json_extract(json, '$.displayProperties.name') IS NOT NULL
        AND (
            json_extract(json, '$.itemType') = 19  -- Perk type
            OR json_extract(json, '$.itemType') = 20  -- Mod type
            OR json_extract(json, '$.itemType') = 3  -- Weapon type with perks
        )
        AND json_extract(json, '$.displayProperties.name') NOT LIKE '%Shader%'
        AND json_extract(json, '$.displayProperties.name') NOT LIKE '%Keepsake%'
        """
        
        for row in manifest_db.execute(perk_query):
            try:
                hash_val = convert_hash(row['hash'])
                if hash_val and row['name']:
                    perk_cache[hash_val] = {
                        'name': row['name'],
                        'description': row['description'] or '',
                        'icon': row['icon'] or ''
                    }
            except Exception as e:
                print(f"Error processing perk: {str(e)}")
                continue
                
        print(f"Loaded {len(perk_cache)} perks into memory")
        
        # Get weapons count
        print("Counting weapons...")
        count_query = """
        SELECT COUNT(*) as count
        FROM DestinyInventoryItemDefinition
        WHERE json_extract(json, '$.itemType') = 3
        AND json_extract(json, '$.inventory.tierType') = 5  -- Legendary tier
        AND json_extract(json, '$.equippingBlock.ammoType') IS NOT NULL
        AND json_extract(json, '$.defaultDamageType') IS NOT NULL
        AND json_extract(json, '$.displayProperties.name') IS NOT NULL
        """
        total_weapons = manifest_db.execute(count_query).fetchone()['count']
        print(f"Found {total_weapons} weapons to process")
        
        # Process weapons in batches
        batch_size = 400
        offset = 0
        
        while True:
            print(f"\nFetching batch {offset//batch_size + 1}...")
            # Get batch of weapons
            weapon_query = f"""
            SELECT json_extract(json, '$.hash') as hash,
                   json_extract(json, '$.displayProperties.name') as name,
                   json_extract(json, '$.itemTypeDisplayName') as itemType,
                   json_extract(json, '$.defaultDamageType') as defaultDamageType,
                   json_extract(json, '$.equippingBlock.ammoType') as ammoType,
                   json_extract(json, '$.displayProperties.icon') as icon,
                   json_extract(json, '$.displayProperties.description') as description,
                   json_extract(json, '$.flavorText') as flavorText,
                   json_extract(json, '$.inventory.tierType') as tierType,
                   json_extract(json, '$.sockets.socketEntries') as socketEntries,
                   json_extract(json, '$.sockets.socketCategories') as socketCategories,
                   json_extract(json, '$.iconWatermark') as iconWatermark,
                   json_extract(json, '$.stats.stats') as weaponStats
            FROM DestinyInventoryItemDefinition
            WHERE json_extract(json, '$.itemType') = 3
            AND json_extract(json, '$.inventory.tierType') = 5  -- Legendary tier
            AND json_extract(json, '$.equippingBlock.ammoType') IS NOT NULL
            AND json_extract(json, '$.defaultDamageType') IS NOT NULL
            AND json_extract(json, '$.displayProperties.name') IS NOT NULL
            LIMIT {batch_size} OFFSET {offset}
            """
            
            try:
                weapons = manifest_db.execute(weapon_query).fetchall()
                if not weapons:
                    break
                    
                print(f"Processing batch {offset//batch_size + 1} with {len(weapons)} weapons...")
                
                # Prepare bulk inserts
                weapon_inserts = []
                perk_inserts = []
                weapon_perk_inserts = []
                weapon_stat_inserts = []
                
                # Process batch
                for weapon in weapons:
                    try:
                        weapon_hash = convert_hash(row_value(weapon, 'hash'))
                        weapon_type = row_value(weapon, 'itemType') or "Unknown"
                        season_number = resolve_watermark_season(
                            row_value(weapon, 'iconWatermark'),
                            manifest_db,
                        )
                        
                        # Add weapon to bulk insert
                        weapon_inserts.append((
                            weapon_hash,
                            row_value(weapon, 'name'),
                            weapon_type,
                            get_damage_type_name(row_value(weapon, 'defaultDamageType')),
                            get_ammo_type_name(row_value(weapon, 'ammoType')),
                            row_value(weapon, 'icon', ''),
                            row_value(weapon, 'description', ''),
                            row_value(weapon, 'flavorText', ''),
                            "Legendary" if row_value(weapon, 'tierType') == 5 else "Unknown",
                            season_number,
                            1
                        ))

                        # Process stats
                        weapon_stats_json = row_value(weapon, 'weaponStats')
                        if weapon_stats_json:
                            try:
                                stats_by_hash = json.loads(weapon_stats_json)
                                for stat_hash, stat_data in stats_by_hash.items():
                                    if not stat_data:
                                        continue
                                    stat_value = stat_data.get('value')
                                    if stat_value is None:
                                        continue
                                    weapon_stat_inserts.append((
                                        weapon_hash,
                                        str(stat_hash),
                                        int(stat_value),
                                    ))
                            except json.JSONDecodeError as e:
                                print(f"Error parsing stats for {row_value(weapon, 'name')}: {e}")
                        
                        # Process rollable perks (WEAPON PERKS sockets only, in column order)
                        socket_entries_json = row_value(weapon, 'socketEntries')
                        socket_categories_json = row_value(weapon, 'socketCategories')
                        if socket_entries_json:
                            try:
                                socket_entries = json.loads(socket_entries_json)
                                perk_socket_indexes = get_weapon_perk_socket_indexes(
                                    socket_categories_json,
                                    socket_entries_json,
                                )
                                seen_weapon_plugs = set()

                                for socket_order, socket_index in enumerate(perk_socket_indexes):
                                    if socket_index >= len(socket_entries):
                                        continue
                                    socket_entry = socket_entries[socket_index]
                                    if not socket_entry:
                                        continue

                                    socket_type_hash = socket_entry.get('socketTypeHash')
                                    if not socket_type_hash:
                                        continue

                                    column_name = str(socket_type_hash)
                                    uses_plug_set = bool(
                                        socket_entry.get('randomizedPlugSetHash')
                                        or socket_entry.get('reusablePlugSetHash')
                                    )
                                    plug_hashes = get_rollable_plug_hashes_for_socket(
                                        socket_entry, manifest_db
                                    )

                                    for plug_hash in plug_hashes:
                                        if plug_hash not in perk_cache:
                                            continue
                                        perk = perk_cache[plug_hash]
                                        if not perk['name']:
                                            continue
                                        if not uses_plug_set and not is_rollable_plug_name(perk['name']):
                                            continue

                                        link_key = (weapon_hash, plug_hash, column_name)
                                        if link_key in seen_weapon_plugs:
                                            continue
                                        seen_weapon_plugs.add(link_key)

                                        if not any(p[0] == plug_hash for p in perk_inserts):
                                            perk_inserts.append((
                                                plug_hash,
                                                perk['name'],
                                                perk['description'],
                                                perk['icon'],
                                            ))
                                        weapon_perk_inserts.append((
                                            weapon_hash,
                                            plug_hash,
                                            column_name,
                                            socket_order,
                                        ))
                            except json.JSONDecodeError as e:
                                print(f"Error parsing socket entries for {row_value(weapon, 'name')}: {str(e)}")
                                continue
                            except Exception as e:
                                print(f"Error processing perks for {row_value(weapon, 'name')}: {str(e)}")
                                continue
                    
                    except Exception as e:
                        print(f"Error processing weapon {weapon['name']}: {str(e)}")
                        continue
                
                # Execute bulk inserts
                print("Executing bulk inserts...")
                if weapon_inserts:
                    print(f"Inserting {len(weapon_inserts)} weapons")
                    weapon_db.executemany("""
                    INSERT OR REPLACE INTO weapons (
                        hash, name, type, damage_type, ammo_type, icon, description, flavor_text, tier, season, is_current
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, weapon_inserts)
                
                if perk_inserts:
                    print(f"Inserting {len(perk_inserts)} perks")
                    weapon_db.executemany("""
                    INSERT OR REPLACE INTO perks (
                        hash, name, description, icon
                    ) VALUES (?, ?, ?, ?)
                    """, perk_inserts)
                
                if weapon_perk_inserts:
                    print(f"Inserting {len(weapon_perk_inserts)} weapon-perk relationships")
                    weapon_db.executemany("""
                    INSERT OR REPLACE INTO weapon_perks (
                        weapon_hash, perk_hash, column_name, socket_order
                    ) VALUES (?, ?, ?, ?)
                    """, weapon_perk_inserts)

                if weapon_stat_inserts:
                    print(f"Inserting {len(weapon_stat_inserts)} weapon stats")
                    weapon_db.executemany("""
                    INSERT OR REPLACE INTO weapon_stats (
                        weapon_hash, stat_name, stat_value
                    ) VALUES (?, ?, ?)
                    """, weapon_stat_inserts)
                
                # Commit batch
                weapon_db.commit()
                offset += batch_size
                
                # Show progress
                elapsed = time.time() - start_time
                print(f"Processed {min(offset, total_weapons)}/{total_weapons} weapons ({elapsed:.1f}s elapsed)")
                
            except Exception as e:
                print(f"Error processing batch: {str(e)}")
                raise
        
        # Print summary
        print("\nMigration Summary:")
        print(f"Total weapons processed: {offset}")
        
        # Cleanup
        manifest_db.close()
        weapon_db.close()
        
        elapsed = time.time() - start_time
        print(f"\nMigration completed successfully in {elapsed:.1f} seconds!")
        
    except Exception as e:
        print(f"\nError during migration: {str(e)}")
        raise

def get_damage_type_name(damage_type):
    """Convert damage type hash to name"""
    damage_types = {
        1: "Kinetic",
        2: "Arc",
        3: "Solar",
        4: "Void",
        6: "Stasis",
        7: "Strand"
    }
    return damage_types.get(damage_type, "Unknown")

def get_ammo_type_name(ammo_type):
    """Convert ammo type hash to name"""
    ammo_types = {
        1: "Primary",
        2: "Special",
        3: "Heavy",
    }
    return ammo_types.get(ammo_type, "Unknown")

if __name__ == "__main__":
    migrate_data() 