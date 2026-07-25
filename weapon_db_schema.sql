-- Create weapons table with all weapon details
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
    is_tiered INTEGER NOT NULL DEFAULT 0,
    is_adept INTEGER NOT NULL DEFAULT 0,
    is_craftable INTEGER NOT NULL DEFAULT 0,
    is_obtainable INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create weapon_stats table to store all weapon stats
CREATE TABLE IF NOT EXISTS weapon_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    weapon_hash INTEGER NOT NULL,
    stat_name TEXT NOT NULL,
    stat_value INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (weapon_hash) REFERENCES weapons(hash),
    UNIQUE(weapon_hash, stat_name)
);

-- Create perks table
CREATE TABLE IF NOT EXISTS perks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash INTEGER UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    icon TEXT,
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create weapon_perks table to link weapons with their perks
CREATE TABLE IF NOT EXISTS weapon_perks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    weapon_hash INTEGER NOT NULL,
    perk_hash INTEGER NOT NULL,
    column_name TEXT NOT NULL,
    socket_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (weapon_hash) REFERENCES weapons(hash),
    FOREIGN KEY (perk_hash) REFERENCES perks(hash)
);

CREATE INDEX IF NOT EXISTS idx_weapon_type ON weapons(type);
CREATE INDEX IF NOT EXISTS idx_perk_type ON perks(name);
CREATE INDEX IF NOT EXISTS idx_weapon_perks ON weapon_perks(weapon_hash, perk_hash);
