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
from collections import defaultdict

def convert_hash(hash_value):
    """Convert hash to signed 32-bit integer if needed"""
    if isinstance(hash_value, str):
        return int(hash_value) & 0xFFFFFFFF
    return hash_value

def get_season_number(season_hash):
    """Convert season hash to season number"""
    if not season_hash:
        print(f"Warning: Empty season hash provided")
        return None
        
    try:
        print(f"\nAttempting to determine season for hash: {season_hash}")
        manifest_db = sqlite3.connect("world_sql_content_4bc957fe614b9ca05b3a93fc27458ae4 - Copy.sqlite3")
        manifest_db.row_factory = sqlite3.Row
        
        # First try to get season from DestinySeasonDefinition
        season_query = """
        SELECT json_extract(json, '$.seasonNumber') as seasonNumber,
               json_extract(json, '$.displayProperties.name') as seasonName
        FROM DestinySeasonDefinition
        WHERE json_extract(json, '$.hash') = ?
        """
        
        result = manifest_db.execute(season_query, (season_hash,)).fetchone()
        if result and result['seasonNumber']:
            print(f"Found season in DestinySeasonDefinition: {result['seasonName']} (Season {result['seasonNumber']})")
            manifest_db.close()
            return int(result['seasonNumber'])
            
        print(f"Season not found in DestinySeasonDefinition, checking season mapping...")
            
        # If not found, try to get it from the season hash mapping
        season_mapping = {
            "31445f1891ce9eb464ed1dcf28f43613": 1,  # Red War
            "b12630659223b53634e9f97c0a0a8305": 2,  # Curse of Osiris
            "2c024f088557ca6cceae1e8030c67169": 3,  # Warmind
            "e775dcb3d47e3d54e0e24fbdb64b5763": 4,  # Forsaken
            "0337ec21962f67c7c493fedb447c4a9b": 5,  # Black Armory
            "1b6c8b94cec61ea42edb1e2cb6b45a31": 6,  # Season of the Drifter
            "2352f9d04dc842cfcdda77636335ded9": 7,  # Season of Opulence
            "fb50cd68a9850bd323872be4f6be115c": 8,  # Shadowkeep
            "ed6c4762c48bd132d538ced83c1699a6": 9,  # Season of Dawn
            "23968435c2095c0f8119d82ee222c672": 10, # Season of the Worthy
            "a3923ae7d2376a1c4eb0f1f154da7565": 11, # Season of Arrivals
            "448f071a7637fcefb2fccf76902dcf7d": 12, # Beyond Light
            "af00bdcd3e3b89e6e85c1f63ebc0b4e4": 13, # Season of the Hunt
            "a2fb48090c8bc0e5785975fab9596ab5": 14, # Season of the Chosen
            "ab075a3679d69f40b8c2a319635d60a9": 15, # Season of the Splicer
            "1448dde4efdb57b07f5473f87c4fccd7": 16, # Season of the Lost
            "5586f6a4193e34acc035209b5e9204d8": 17, # The Witch Queen
            "3543d23d9063fbf7332c7f129a74ada2": 18, # Season of the Risen
            "be3c0a95a8d1abc6e7c875d4294ba233": 19, # Season of the Haunted
            "4c25426263cacf963777cd4988340838": 20, # Season of Plunder
            "428c962c15612ea89693349d1b84531a": 21, # Season of the Seraph
            "d5a3f4d7d20fefc781fea3c60bde9434": 22, # Lightfall
            "b973f89ecd631a3e3d294e98268f7134": 23, # Season of Defiance
            "f80e39c767f309f0b2be625dae0e3744": 24, # Season of the Deep
            "3de52d90db7ee2feb086ef6665b736b6": 25, # Season of the Witch
            "e8fe681196baf74917fa3e6f125349b0": 26, # Season of the Wish
            "52523b49e5965f6f33ab86710215c676": 27  # Latest
        }
        
        season_number = season_mapping.get(season_hash)
        if season_number:
            print(f"Found season in mapping: Season {season_number}")
        else:
            print(f"Warning: Season hash {season_hash} not found in mapping")
            
        manifest_db.close()
        return season_number
    except Exception as e:
        print(f"Error getting season number for hash {season_hash}: {str(e)}")
        return None

def migrate_data():
    print("Starting migration...")
    start_time = time.time()
    
    try:
        # Connect to databases
        print("Connecting to databases...")
        manifest_db = sqlite3.connect("world_sql_content_4bc957fe614b9ca05b3a93fc27458ae4 - Copy.sqlite3")
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (weapon_hash) REFERENCES weapons(hash),
            FOREIGN KEY (perk_hash) REFERENCES perks(hash)
        )
        """)
        
        # Create indexes
        weapon_db.execute("CREATE INDEX IF NOT EXISTS idx_weapon_type ON weapons(type)")
        weapon_db.execute("CREATE INDEX IF NOT EXISTS idx_perk_type ON perks(name)")
        weapon_db.execute("CREATE INDEX IF NOT EXISTS idx_weapon_perks ON weapon_perks(weapon_hash, perk_hash)")
        
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
        AND json_extract(json, '$.displayProperties.description') IS NOT NULL
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
                if hash_val and row['name'] and row['description']:
                    perk_cache[hash_val] = {
                        'name': row['name'],
                        'description': row['description'],
                        'icon': row['icon'] if row['icon'] else ''
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
                   json_extract(json, '$.iconWatermark') as iconWatermark
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
                
                # Process batch
                for weapon in weapons:
                    try:
                        weapon_hash = convert_hash(weapon['hash'])
                        weapon_type = weapon['itemType'] or "Unknown"
                        
                        # Get season number from icon watermark
                        icon_watermark = weapon['iconWatermark']
                        season_number = 0
                        if icon_watermark:
                            # Extract the hash from the icon watermark path
                            watermark_hash = icon_watermark.split('/')[-1].split('.')[0]
                            print(f"\nProcessing weapon: {weapon['name']}")
                            print(f"Watermark path: {icon_watermark}")
                            print(f"Extracted hash: {watermark_hash}")
                            season_number = get_season_number(watermark_hash) or 0
                            if not season_number:
                                print(f"Warning: Could not determine season for weapon {weapon['name']} with watermark {watermark_hash}")
                            else:
                                print(f"Successfully determined season {season_number} for {weapon['name']}")
                        
                        # Add weapon to bulk insert
                        weapon_inserts.append((
                            weapon_hash,
                            weapon['name'],
                            weapon_type,
                            get_damage_type_name(weapon['defaultDamageType']),
                            weapon['ammoType'] if 'ammoType' in weapon else 'Unknown',
                            weapon['icon'] if 'icon' in weapon else '',
                            weapon['description'] if 'description' in weapon else '',
                            weapon['flavorText'] if 'flavorText' in weapon else '',
                            "Legendary" if weapon['tierType'] == 5 else "Unknown",
                            season_number,
                            1
                        ))
                        
                        # Process perks
                        if 'socketEntries' in weapon and weapon['socketEntries']:
                            try:
                                socket_entries = json.loads(weapon['socketEntries'])
                                for socket_entry in socket_entries:
                                    if not socket_entry:
                                        continue
                                        
                                    socket_type_hash = socket_entry.get('socketTypeHash')
                                    if not socket_type_hash:
                                        continue
                                        
                                    column_name = f"{socket_type_hash}"
                                    
                                    # Process reusable plugs
                                    if 'reusablePlugItems' in socket_entry:
                                        for plug in socket_entry['reusablePlugItems']:
                                            plug_hash = convert_hash(plug.get('plugItemHash'))
                                            if plug_hash and plug_hash in perk_cache:
                                                perk = perk_cache[plug_hash]
                                                if perk['name'] and perk['description']:  # Only add valid perks
                                                    # Add perk to inserts if not already added
                                                    if not any(p[0] == plug_hash for p in perk_inserts):
                                                        perk_inserts.append((
                                                            plug_hash,
                                                            perk['name'],
                                                            perk['description'],
                                                            perk['icon']
                                                        ))
                                                    # Add weapon-perk relationship
                                                    weapon_perk_inserts.append((
                                                        weapon_hash,
                                                        plug_hash,
                                                        column_name
                                                    ))
                                    
                                    # Process random plugs
                                    if 'randomizedPlugSetHash' in socket_entry:
                                        plug_set_hash = convert_hash(socket_entry['randomizedPlugSetHash'])
                                        plug_set_query = """
                                        SELECT json_extract(json, '$.reusablePlugItems') as reusablePlugItems
                                        FROM DestinyPlugSetDefinition
                                        WHERE json_extract(json, '$.hash') = ?
                                        """
                                        plug_set = manifest_db.execute(plug_set_query, (plug_set_hash,)).fetchone()
                                        
                                        if plug_set and plug_set['reusablePlugItems']:
                                            try:
                                                plug_items = json.loads(plug_set['reusablePlugItems'])
                                                for plug_item in plug_items:
                                                    plug_hash = convert_hash(plug_item.get('plugItemHash'))
                                                    if plug_hash and plug_hash in perk_cache:
                                                        perk = perk_cache[plug_hash]
                                                        if perk['name'] and perk['description']:  # Only add valid perks
                                                            # Add perk to inserts if not already added
                                                            if not any(p[0] == plug_hash for p in perk_inserts):
                                                                perk_inserts.append((
                                                                    plug_hash,
                                                                    perk['name'],
                                                                    perk['description'],
                                                                    perk['icon']
                                                                ))
                                                            # Add weapon-perk relationship
                                                            weapon_perk_inserts.append((
                                                                weapon_hash,
                                                                plug_hash,
                                                                column_name
                                                            ))
                                            except json.JSONDecodeError:
                                                print(f"Error parsing plug items for weapon {weapon['name']}")
                                                continue
                            except json.JSONDecodeError as e:
                                print(f"Error parsing socket entries for {weapon['name']}: {str(e)}")
                                continue
                            except Exception as e:
                                print(f"Error processing perks for {weapon['name']}: {str(e)}")
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
                        weapon_hash, perk_hash, column_name
                    ) VALUES (?, ?, ?)
                    """, weapon_perk_inserts)
                
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

if __name__ == "__main__":
    migrate_data() 