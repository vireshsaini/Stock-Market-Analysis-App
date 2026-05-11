import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime
import gc


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
BHAVCOPY_DIR = BASE_DIR / "Bhavcopy"


# ============================================================
# RSI FUNCTION
# ============================================================

def calculate_rsi_14(series, period=14):

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss.replace(0, pd.NA)

    rsi = 100 - (100 / (1 + rs))

    return rsi


# ============================================================
# LOAD CURRENT YEAR DATA ONLY
# ============================================================

@st.cache_data(ttl=1800, show_spinner=True)
def load_dashboard_data(current_year=2026):

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

            # ====================================================
            # EXTRACT DATE FROM FILENAME
            # ====================================================

            trade_date = datetime.strptime(
                f.name.split("_")[-1].replace(".csv", ""),
                "%d%m%Y"
            )

            # ====================================================
            # LOAD ONLY CURRENT YEAR
            # ====================================================

            if trade_date.year != current_year:
                continue

            # ====================================================
            # READ CSV
            # ====================================================

            df = pd.read_csv(
                f,
                low_memory=False
            )

            df.columns = (
                df.columns
                .str.upper()
                .str.strip()
            )

            # ====================================================
            # VALIDATION
            # ====================================================

            if "SERIES" not in df.columns:
                continue

            missing = set(REQUIRED_COLS) - set(df.columns)

            if missing:
                continue

            # ====================================================
            # FILTER EQ SERIES
            # ====================================================

            df["SERIES"] = (
                df["SERIES"]
                .astype(str)
                .str.upper()
                .str.strip()
            )

            df = df[
                df["SERIES"].eq("EQ")
            ]

            if df.empty:
                continue

            # ====================================================
            # KEEP ONLY REQUIRED COLS
            # ====================================================

            df = df[REQUIRED_COLS].copy()

            # ====================================================
            # ADD DATE
            # ====================================================

            df["DATE1"] = trade_date

            # ====================================================
            # NUMERIC CONVERSION
            # ====================================================

            numeric_cols = [
                "PREV_CLOSE", "OPEN_PRICE",
                "HIGH_PRICE", "LOW_PRICE",
                "LAST_PRICE", "CLOSE_PRICE",
                "AVG_PRICE", "TTL_TRD_QNTY",
                "TURNOVER_LACS", "NO_OF_TRADES",
                "DELIV_QTY", "DELIV_PER"
            ]

            for col in numeric_cols:

                df[col] = pd.to_numeric(
                    df[col],
                    errors="coerce"
                )

            chunks.append(df)

            # free memory immediately
            del df
            gc.collect()

        except Exception:
            continue

    # ============================================================
    # NO DATA
    # ============================================================

    if not chunks:
        return pd.DataFrame()

    # ============================================================
    # CONCAT
    # ============================================================

    hist = pd.concat(
        chunks,
        ignore_index=True,
        copy=False
    )

    del chunks
    gc.collect()

    # ============================================================
    # SORT
    # ============================================================

    hist.sort_values(
        ["SYMBOL", "DATE1"],
        inplace=True
    )

    # ============================================================
    # RSI
    # ============================================================

    hist["RSI"] = (
        hist.groupby("SYMBOL")["CLOSE_PRICE"]
        .apply(calculate_rsi_14)
        .reset_index(level=0, drop=True)
    )

    # ============================================================
    # 14-DAY RETURN
    # ============================================================

    hist["RET_14D"] = (
        hist.groupby("SYMBOL")["CLOSE_PRICE"]
        .pct_change(14) * 100
    )

    return hist


# ============================================================
# LATEST SNAPSHOT
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