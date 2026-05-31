import sqlite3
import json

def get_type_mappings():
    return {
        'weapon_types': {
            6: 'Auto Rifle',
            7: 'Shotgun',
            8: 'Machine Gun',
            9: 'Hand Cannon',
            10: 'Rocket Launcher',
            11: 'Fusion Rifle',
            12: 'Sniper Rifle',
            13: 'Pulse Rifle',
            14: 'Scout Rifle',
            17: 'Sidearm',
            18: 'Sword',
            22: 'Grenade Launcher',
            23: 'Submachine Gun',
            24: 'Linear Fusion Rifle',
            25: 'Trace Rifle',
            31: 'Bow',
            33: 'Glaive'
        },
        'damage_types': {
            1: 'Kinetic',
            2: 'Arc',
            3: 'Solar',
            4: 'Void',
            6: 'Stasis',
            7: 'Strand'
        },
        'ammo_types': {
            1: 'Primary',
            2: 'Special',
            3: 'Heavy'
        }
    }

def explore_weapons():
    # Connect to the database
    db_path = "weapon_perks.db"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print(f"Successfully connected to database: {db_path}")
        
        # First, let's check the table structure
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("\nAvailable tables:", [table[0] for table in tables])
        
        # Let's examine the weapons table
        cursor.execute("SELECT * FROM weapons LIMIT 1")
        columns = [description[0] for description in cursor.description]
        print("\nTable columns:", columns)
        
        # Now query the weapons with their damage types
        cursor.execute("""
            SELECT name, type, damage_type, ammo_type
            FROM weapons
            ORDER BY name;
        """)
        
        weapons = cursor.fetchall()
        print(f"\nTotal weapons found: {len(weapons)}")
        
        # Analyze the results
        weapon_types = set()
        damage_types = set()
        ammo_types = set()
        
        for weapon in weapons:
            name, w_type, d_type, a_type = weapon
            weapon_types.add(w_type)
            damage_types.add(d_type)
            ammo_types.add(a_type)
            
            if d_type == 'Unknown':
                print(f"Weapon with unknown damage type: {name} ({w_type})")
        
        print("\nWeapon Types found:")
        for wtype in sorted(weapon_types):
            print(f"- {wtype}")
            
        print("\nDamage Types found:")
        for dtype in sorted(damage_types):
            print(f"- {dtype}")
            
        print("\nAmmo Types found:")
        for atype in sorted(ammo_types):
            print(f"- {atype}")
            
    except sqlite3.Error as e:
        print(f"Error working with database: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    explore_weapons()