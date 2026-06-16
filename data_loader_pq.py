import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime
import gc
import os

# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
BHAVCOPY_DIR = BASE_DIR / "Bhavcopy"

# PARQUET CACHE FILE (NEW)
PARQUET_FILE = BHAVCOPY_DIR / "hist_master.parquet"

# ============================================================
# RSI FUNCTION
# ============================================================

def calculate_rsi(series, period=14):

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()

    rs = avg_gain / avg_loss

    rsi = 100 - (100 / (1 + rs))

    return rsi


# ============================================================
# CSV ENGINE (YOUR ORIGINAL LOGIC - UNCHANGED)
# ============================================================

def _load_from_csv(current_year):

    files = sorted(
        BHAVCOPY_DIR.glob("sec_bhavdata_full_*.csv")
    )

    if not files:
        return pd.DataFrame()

    REQUIRED_COLS = [
        "SYMBOL", "SERIES",
        "PREV_CLOSE", "OPEN_PRICE",
        "HIGH_PRICE", "LOW_PRICE",
        "LAST_PRICE", "CLOSE_PRICE",
        "AVG_PRICE", "TTL_TRD_QNTY",
        "TURNOVER_LACS", "NO_OF_TRADES",
        "DELIV_QTY", "DELIV_PER"
    ]

    chunks = []

    for f in files:

        try:

            trade_date = datetime.strptime(
                f.name.split("_")[-1].replace(".csv", ""),
                "%d%m%Y"
            )

            if trade_date.year not in current_year:
                continue

            df = pd.read_csv(f, low_memory=False)

            df.columns = df.columns.str.upper().str.strip()

            if "SERIES" not in df.columns:
                continue

            missing = set(REQUIRED_COLS) - set(df.columns)
            if missing:
                continue

            df["SERIES"] = df["SERIES"].astype(str).str.upper().str.strip()
            df = df[df["SERIES"].eq("EQ")]

            if df.empty:
                continue

            df = df[REQUIRED_COLS].copy()
            df["DATE1"] = trade_date

            numeric_cols = [
                "PREV_CLOSE", "OPEN_PRICE",
                "HIGH_PRICE", "LOW_PRICE",
                "LAST_PRICE", "CLOSE_PRICE",
                "AVG_PRICE", "TTL_TRD_QNTY",
                "TURNOVER_LACS", "NO_OF_TRADES",
                "DELIV_QTY", "DELIV_PER"
            ]

            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            chunks.append(df)

            del df
            gc.collect()

        except Exception:
            continue

    if not chunks:
        return pd.DataFrame()

    hist = pd.concat(chunks, ignore_index=True, copy=False)

    del chunks
    gc.collect()

    hist.sort_values(["SYMBOL", "DATE1"], inplace=True)

    hist["RSI"] = (
        hist.groupby("SYMBOL")["CLOSE_PRICE"]
        .apply(calculate_rsi)
        .reset_index(level=0, drop=True)
    )

    hist["RET_14D"] = (
        hist.groupby("SYMBOL")["CLOSE_PRICE"]
        .pct_change(14) * 100
    )

    return hist


# ============================================================
# MAIN LOADER (PARQUET LAYER ADDED HERE)
# ============================================================

@st.cache_data(ttl=2800, show_spinner=True)
def load_dashboard_data(current_year=[2025, 2026]):

    # ========================================================
    # 1️⃣ FAST PATH: PARQUET EXISTS
    # ========================================================

    if PARQUET_FILE.exists():

        hist = pd.read_parquet(PARQUET_FILE)

        # safety filter
        hist = hist[hist["DATE1"].notna()]

        return hist

    # ========================================================
    # 2️⃣ FALLBACK: CSV LOAD (YOUR ORIGINAL ENGINE)
    # ========================================================

    hist = _load_from_csv(current_year)

    if hist.empty:
        return pd.DataFrame()

    # ========================================================
    # 3️⃣ SAVE PARQUET FOR FUTURE SPEED BOOST
    # ========================================================

    try:
        PARQUET_FILE.parent.mkdir(parents=True, exist_ok=True)

        hist.to_parquet(
            PARQUET_FILE,
            engine="pyarrow",
            compression="snappy",
            index=False
        )
    except Exception as e:
        print("Parquet save failed:", e)

    return hist


# ============================================================
# LATEST SNAPSHOT (UNCHANGED)
# ============================================================

@st.cache_data(ttl=1800)
def get_latest_snapshot(hist):

    if hist.empty:
        return pd.DataFrame()

    latest = (
        hist.dropna(subset=["RSI", "RET_14D"])
        .groupby("SYMBOL", as_index=False)
        .tail(1)
    )

    return latest