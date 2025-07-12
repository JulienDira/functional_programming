from typing import Dict, Any
from toolz import curry
import polars as pl
import pandas as pd
from .indicators import enrich_indicators_pd

@curry
def clean_and_type(entry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "coin": entry["coin"],
        "timestamp": int(entry["timestamp"]),
        "open": float(entry["open"]),
        "high": float(entry["high"]),
        "low": float(entry["low"]),
        "close": float(entry["close"]),
        "volume": float(entry.get("volume", 0.0))
    }

@curry
def is_valid(entry: Dict[str, Any]) -> bool:
    keys = ["coin", "timestamp", "open", "high", "low", "close"]
    return all(k in entry for k in keys)

def polars_from_batch(batch: list[Dict[str, Any]]) -> pl.DataFrame:
    return pl.DataFrame(batch).with_column(pl.col("timestamp").cast(pl.Int64))

def enrich_polars(df: pl.DataFrame) -> pl.DataFrame:
    # Transform polars to pandas to use pandas-ta indicators
    pdf = df.to_pandas()
    pdf2 = enrich_indicators_pd(pdf)
    return pl.from_pandas(pdf2)

def window_aggregate(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df
        .with_column((pl.col("close").rolling_mean(5)).alias("MA5"))
        .with_column((pl.col("volume").sum().over("coin")).alias("sum_vol"))
    )
