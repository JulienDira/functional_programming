import pandas as pd
import pandas_ta as ta

def enrich_indicators_pd(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["EMA_SHORT"] = ta.ema(df["close"], length=5).round(2)
    df["EMA_LONG"] = ta.ema(df["close"], length=20).round(2)
    df["RSI"] = ta.rsi(df["close"], length=14).round(2)
    df["ADX"] = ta.adx(df["high"], df["low"], df["close"], length=14)["ADX_14"].round(2)
    return df
