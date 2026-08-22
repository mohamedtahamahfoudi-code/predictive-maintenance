"""
load_to_db.py

Loads the AI4I 2020 Predictive Maintenance dataset from data/raw/ai4i2020.csv
into a Postgres table (Neon), using a single bulk upsert instead of
row-by-row inserts. Safe to re-run: upserts on the UDI primary key.

Usage:
    python src/load_to_db.py
"""

import os
import sys
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

CSV_PATH = "data/raw/ai4i2020.csv"
TABLE_NAME = "machine_readings"

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("DATABASE_URL not found in .env — aborting.")
    sys.exit(1)

print(f"Reading {CSV_PATH} ...")
df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")

df.columns = (
    df.columns.str.strip()
    .str.lower()
    .str.replace(r"[\[\]]", "", regex=True)
    .str.replace(" ", "_")
)

print(f"Loaded {len(df)} rows.")

engine = create_engine(DATABASE_URL, connect_args={"connect_timeout": 10})

create_table_sql = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    udi INTEGER PRIMARY KEY,
    product_id TEXT,
    type TEXT,
    air_temperature_k FLOAT,
    process_temperature_k FLOAT,
    rotational_speed_rpm INTEGER,
    torque_nm FLOAT,
    tool_wear_min INTEGER,
    machine_failure INTEGER,
    twf INTEGER,
    hdf INTEGER,
    pwf INTEGER,
    osf INTEGER,
    rnf INTEGER,
    loaded_at TIMESTAMP DEFAULT NOW()
);
"""

print("Connecting to database...")
with engine.begin() as conn:
    conn.execute(text(create_table_sql))
print(f"Table '{TABLE_NAME}' ready.")

# ---- Step 1: load into a TEMP staging table (fast bulk insert) ----
print("Uploading data to a staging table...")
df.to_sql("staging_machine_readings", engine, if_exists="replace", index=False)

# ---- Step 2: upsert from staging into the real table in ONE statement ----
upsert_sql = text(f"""
INSERT INTO {TABLE_NAME} (
    udi, product_id, type, air_temperature_k, process_temperature_k,
    rotational_speed_rpm, torque_nm, tool_wear_min, machine_failure,
    twf, hdf, pwf, osf, rnf
)
SELECT
    udi, product_id, type, air_temperature_k, process_temperature_k,
    rotational_speed_rpm, torque_nm, tool_wear_min, machine_failure,
    twf, hdf, pwf, osf, rnf
FROM staging_machine_readings
ON CONFLICT (udi) DO UPDATE SET
    product_id = EXCLUDED.product_id,
    type = EXCLUDED.type,
    air_temperature_k = EXCLUDED.air_temperature_k,
    process_temperature_k = EXCLUDED.process_temperature_k,
    rotational_speed_rpm = EXCLUDED.rotational_speed_rpm,
    torque_nm = EXCLUDED.torque_nm,
    tool_wear_min = EXCLUDED.tool_wear_min,
    machine_failure = EXCLUDED.machine_failure,
    twf = EXCLUDED.twf,
    hdf = EXCLUDED.hdf,
    pwf = EXCLUDED.pwf,
    osf = EXCLUDED.osf,
    rnf = EXCLUDED.rnf;
""")

print("Upserting from staging into main table...")
with engine.begin() as conn:
    conn.execute(upsert_sql)

# ---- Step 3: clean up staging table ----
with engine.begin() as conn:
    conn.execute(text("DROP TABLE IF EXISTS staging_machine_readings;"))

print("Done.")

# ---- Verification ----
with engine.connect() as conn:
    count = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE_NAME};")).scalar()
    failures = conn.execute(
        text(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE machine_failure = 1;")
    ).scalar()

print(f"Row count in DB: {count}")
print(f"Failure rows in DB: {failures}")