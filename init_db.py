import os, sqlite3, json, time

DB_PATH = os.path.join("db", "smart_irrigation.db")
os.makedirs("db", exist_ok=True)

DDL = r"""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS farmer (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  phone_hash CHAR(64) NOT NULL UNIQUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS plot (
  id INTEGER PRIMARY KEY,
  farmer_id INTEGER NOT NULL REFERENCES farmer(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  crop TEXT NOT NULL,
  region TEXT NOT NULL,
  lat REAL,
  lon REAL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS factors_snapshot (
  id INTEGER PRIMARY KEY,
  plot_id INTEGER NOT NULL REFERENCES plot(id) ON DELETE CASCADE,
  payload_json TEXT NOT NULL,
  device_id TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recommendation (
  id INTEGER PRIMARY KEY,
  snapshot_id INTEGER NOT NULL UNIQUE REFERENCES factors_snapshot(id) ON DELETE CASCADE,
  decision TEXT NOT NULL,
  amount_mm REAL NOT NULL,
  amount_l REAL NOT NULL,
  weather_json TEXT,
  model_version TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_version (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  version TEXT NOT NULL,
  path TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_plot_farmer   ON plot(farmer_id);
CREATE INDEX IF NOT EXISTS idx_snap_plot     ON factors_snapshot(plot_id, created_at);
CREATE INDEX IF NOT EXISTS idx_reco_created  ON recommendation(created_at);
"""

def main():
  con = sqlite3.connect(DB_PATH)
  try:
    con.executescript(DDL)
    con.commit()
    # sanity check
    cur = con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    print("Tables:", [r[0] for r in cur.fetchall()])
  finally:
    con.close()

if __name__ == "__main__":
  main()
