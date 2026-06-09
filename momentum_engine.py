# =====================================================================
# MOMENTUM ENGINE
# =====================================================================

import pandas as pd
import numpy as np
from data_loader import get_latest_snapshot


# =====================================================================
# RSI FUNCTION
# =====================================================================

def rsi(series, period=14):

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    return 100 - (100 / (1 + rs))


# =====================================================================
# WEEKLY RSI
# =====================================================================

def compute_weekly_rsi(hist_nd):

    df = hist_nd.copy()

    df["DATE1"] = pd.to_datetime(df["DATE1"], errors="coerce")
    df["CLOSE_PRICE"] = pd.to_numeric(df["CLOSE_PRICE"], errors="coerce")

    df = df.dropna(subset=["CLOSE_PRICE", "DATE1"])

    weekly_data = (
        df.set_index("DATE1")
        .groupby("SYMBOL")["CLOSE_PRICE"]
        .resample("W-FRI")
        .last()
        .reset_index()
        .sort_values(["SYMBOL", "DATE1"])
    )

    weekly_data["RSI_WEEKLY"] = (
        weekly_data.groupby("SYMBOL")["CLOSE_PRICE"]
        .transform(rsi)
    )

    latest_weekly_rsi = (
        weekly_data
        .dropna(subset=["RSI_WEEKLY"])
        .groupby("SYMBOL")
        .tail(1)[["SYMBOL", "RSI_WEEKLY"]]
    )

    return latest_weekly_rsi


# =====================================================================
# MAIN MOMENTUM ENGINE
# =====================================================================

def build_momentum_universe(hist, rolling_dates):

    # =========================================================
    # FILTER DATA
    # =========================================================

    hist_nd = hist[hist["DATE1"].isin(rolling_dates)].copy()
    hist_nd["DATE1"] = pd.to_datetime(hist_nd["DATE1"], errors="coerce")

    cols = [
        "CLOSE_PRICE",
        "OPEN_PRICE",
        "HIGH_PRICE",
        "LOW_PRICE",
        "TTL_TRD_QNTY",
        "DELIV_QTY",
        "DELIV_PER"
    ]

    for c in cols:
        hist_nd[c] = (
            hist_nd[c].astype(str).str.replace(",", "", regex=False)
        )
        hist_nd[c] = pd.to_numeric(hist_nd[c], errors="coerce")

    hist_nd = hist_nd.dropna(subset=["SYMBOL", "DATE1", "CLOSE_PRICE"])
    hist_nd = hist_nd.sort_values(["SYMBOL", "DATE1"])

    # =========================================================
    # VALUE TRADED
    # =========================================================

    hist_nd["VALUE_TRADED"] = hist_nd["TTL_TRD_QNTY"] * hist_nd["CLOSE_PRICE"]

    # =========================================================
    # WEEKLY RSI
    # =========================================================

    latest_weekly_rsi = compute_weekly_rsi(hist_nd)

    # =========================================================
    # LATEST SNAPSHOT
    # =========================================================

    latest = get_latest_snapshot(hist)

    latest = latest.rename(columns={"RSI": "RSI_DAILY"})

    latest["DAILY_VALUE_TRADED"] = (
        latest["TTL_TRD_QNTY"] * latest["CLOSE_PRICE"]
    )

    latest = latest.drop(columns=["VALUE_TRADED"], errors="ignore")

    latest = latest.merge(latest_weekly_rsi, on="SYMBOL", how="left")

    # =========================================================
    # VWAP
    # =========================================================

    vwap = (
        hist_nd.groupby("SYMBOL")
        .apply(
            lambda x: (
                (x["CLOSE_PRICE"] * x["DELIV_QTY"]).sum()
                / x["DELIV_QTY"].sum()
                if x["DELIV_QTY"].sum() != 0 else np.nan
            )
        )
        .reset_index(name="VWAP")
    )

    # =========================================================
    # VALUE TRADED AGG
    # =========================================================

    value_traded_df = (
        hist_nd.groupby("SYMBOL", as_index=False)
        .agg(VALUE_TRADED=("VALUE_TRADED", "sum"))
    )

    # =========================================================
    # MERGE
    # =========================================================

    rank_df = latest.merge(vwap, on="SYMBOL", how="left")
    rank_df = rank_df.merge(value_traded_df, on="SYMBOL", how="left")

    # =========================================================
    # SAFE FILL
    # =========================================================

    for col in ["RSI_DAILY", "RSI_WEEKLY", "VALUE_TRADED", "DAILY_VALUE_TRADED"]:
        if col not in rank_df:
            rank_df[col] = 0
        else:
            rank_df[col] = rank_df[col].fillna(0)

    # =========================================================
    # CPR
    # =========================================================

    rank_df["PIVOT"] = (
        rank_df["HIGH_PRICE"] + rank_df["LOW_PRICE"] + rank_df["CLOSE_PRICE"]
    ) / 3

    rank_df["BC"] = (
        rank_df["HIGH_PRICE"] + rank_df["LOW_PRICE"]
    ) / 2

    rank_df["TC"] = (2 * rank_df["PIVOT"]) - rank_df["BC"]

    # =========================================================
    # FILTER
    # =========================================================

    filtered = rank_df[
        (rank_df["CLOSE_PRICE"] > rank_df["VWAP"]) &
        (rank_df["CLOSE_PRICE"] > 10) &
        (rank_df["DELIV_PER"] > 30) &
        (rank_df["RSI_DAILY"] > 35) &
        (rank_df["RSI_DAILY"] < 50) &
        (rank_df["RSI_WEEKLY"] > 60) &
        (rank_df["DAILY_VALUE_TRADED"] > 10_000_000) &
        (rank_df["VALUE_TRADED"] > 10_000_000)
    ].copy()

    # =========================================================
    # SCORING
    # =========================================================

    denom_vol = filtered["TTL_TRD_QNTY"].max()
    denom_raw = filtered["RAW_SCORE"].max() if "RAW_SCORE" in filtered else None

    filtered["VWAP_STRENGTH"] = (
        (filtered["CLOSE_PRICE"] - filtered["VWAP"]) / filtered["VWAP"]
    ) * 100

    filtered["CPR_STRENGTH"] = (
        (filtered["CLOSE_PRICE"] - filtered["TC"]) / filtered["TC"]
    ) * 100

    filtered["VOL_STRENGTH"] = (
        filtered["TTL_TRD_QNTY"] / denom_vol * 100
        if denom_vol not in [0, np.nan] else 0
    )

    filtered["RSI"] = filtered["RSI_DAILY"]

    filtered["RAW_SCORE"] = (
        filtered["VWAP_STRENGTH"] * 0.20 +
        filtered["DELIV_PER"] * 0.25 +
        filtered["RSI"] * 0.20 +
        filtered["CPR_STRENGTH"] * 0.15 +
        filtered["VOL_STRENGTH"] * 0.20
    )

    max_score = filtered["RAW_SCORE"].max()

    filtered["RANK"] = (
        (filtered["RAW_SCORE"] / max_score * 10)
        if max_score != 0 else 0
    )

    filtered["RANK"] = (
        filtered["RANK"]
        .fillna(0)
        .round()
        .clip(1, 10)
        .astype(int)
    )

    # =========================================================
    # SIGNAL
    # =========================================================

    filtered["SIGNAL"] = filtered["RANK"].apply(
        lambda x:
        "🔥 SUPER BUY" if x >= 9 else
        "🟢 STRONG BUY" if x >= 8 else
        "🟡 BUY" if x >= 7 else
        "⚠ WATCH"
    )

    # =========================================================
    # FORMATTING
    # =========================================================

    filtered["DAILY_VALUE_TRADED (Cr)"] = (
        filtered["DAILY_VALUE_TRADED"] / 10_000_000
    ).round(2)

    filtered["VALUE_TRADED (Cr)"] = (
        filtered["VALUE_TRADED"] / 10_000_000
    ).round(2)

    filtered["RSI_DAILY"] = filtered["RSI_DAILY"].round(2)
    filtered["RSI_WEEKLY"] = filtered["RSI_WEEKLY"].round(2)

    # =========================================================
    # SORT
    # =========================================================

    return filtered.sort_values(
        by=["RANK", "DELIV_PER", "RSI_DAILY", "TTL_TRD_QNTY"],
        ascending=False
    )