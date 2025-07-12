import os
import json
import duckdb
import polars as pl

RAW_DIR = "raw_data"
CURATED_DIR = "curated_data"
DB_PATH = "realtime.duckdb"
TABLE = "stream_data"

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(CURATED_DIR, exist_ok=True)

def save_raw(entry: dict):
    fname = f"{RAW_DIR}/{entry['coin']}_{entry['timestamp']}.json"
    with open(fname, "w") as f:
        json.dump(entry, f)

def save_curated(df: pl.DataFrame):
    fname = f"{CURATED_DIR}/batch_{df['timestamp'][0]}.parquet"
    df.write_parquet(fname)

def save_to_duck(df: pl.DataFrame):
    con = duckdb.connect(DB_PATH)
    pdf = df.to_pandas()
    con.execute(f"CREATE TABLE IF NOT EXISTS {TABLE} AS SELECT * FROM pdf LIMIT 0")
    con.execute("INSERT INTO stream_data SELECT * FROM pdf")
    con.close()
