import sqlite3
import json

from config import get_manifest_db_path, manifest_db_exists

def get_weapon_type_name(type_id):
    weapon_type_mapping = {
        0: None,  # None
        6: "Auto Rifle",
        7: "Shotgun",
        8: "Machine Gun",
        9: "Hand Cannon",
        10: "Rocket Launcher",
        11: "Fusion Rifle",
        12: "Sniper Rifle",
        13: "Pulse Rifle",
        14: "Scout Rifle",
        17: "Sidearm",
        18: "Sword",
        22: "Linear Fusion Rifle",  # Changed from Grenade Launcher
        23: "Submachine Gun",
        24: "Grenade Launcher",  # Changed from Linear Fusion Rifle
        25: "Trace Rifle",
        31: "Bow",
        33: "Glaive"
    }
    return weapon_type_mapping.get(type_id)

def main():
    db_path = get_manifest_db_path()
    if not manifest_db_exists():
        print(f"Manifest database not found at: {db_path}")
        print("Set DESTINY_MANIFEST_DB to your Bungie world content .sqlite3 file.")
        return
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Query for Linear Fusion Rifles specifically
        cursor.execute("""
            SELECT id, json 
            FROM DestinyInventoryItemDefinition 
            WHERE json LIKE '%Linear Fusion%'
            AND json LIKE '%"tierType":5%'
        """)
        weapons = cursor.fetchall()
        
        print(f"\nFound {len(weapons)} potential Linear Fusion Rifles")
        
        for weapon in weapons:
            try:
                weapon_data = json.loads(weapon[1])
                name = weapon_data.get('displayProperties', {}).get('name', 'Unknown')
                item_sub_type = weapon_data.get('itemSubType')
                weapon_type = get_weapon_type_name(item_sub_type)
                
                print(f"\nWeapon: {name}")
                print(f"itemSubType: {item_sub_type}")
                print(f"Mapped weapon type: {weapon_type}")
                
                # Get slot type
                if 'equippingBlock' in weapon_data:
                    slot_hash = weapon_data['equippingBlock'].get('equipmentSlotTypeHash', 0)
                    slot_type = None
                    if slot_hash == 1498876634:
                        slot_type = 'Kinetic'
                    elif slot_hash == 2465295065:
                        slot_type = 'Energy'
                    elif slot_hash == 953998645:
                        slot_type = 'Power'
                    print(f"Slot type: {slot_type}")
                
                # Get ammo type
                ammo_type = weapon_data.get('equippingBlock', {}).get('ammoType')
                print(f"Ammo type: {ammo_type}")
                
            except json.JSONDecodeError:
                continue
            
    except sqlite3.OperationalError as e:
        print(f"Error querying weapons: {e}")
    
    conn.close()

if __name__ == "__main__":
    main() 