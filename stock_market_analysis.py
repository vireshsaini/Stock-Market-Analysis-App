# ============================================================
# NSE INSTITUTIONAL SMART MONEY TERMINAL – FULL COMBINED VERSION
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import glob, os,hashlib
from datetime import datetime
import plotly.express as px
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from pathlib import Path
from auth import login_screen

st.set_page_config(page_title="Simple Login", layout="centered")

# LOGIN
login_screen()
# ================= END AUTH 30 APR 26 =================

# ================= CONFIG =================
#BHAVCOPY_DIR = r"D:\MLearning\NSE\Bhavcopy"
#BASE_DIR = Path(__file__).resolve().parent

#BHAVCOPY_DIR = BASE_DIR / "Bhavcopy"
# User folder
#USER_DIR = BASE_DIR / "Bhavcopy"

# --- BASIC SECTOR MAP (extend anytime) ---
SECTOR_MAP = {
    "RELIANCE": "ENERGY",
    "TCS": "IT",
    "INFY": "IT",
    "HDFCBANK": "BANKING",
    "ICICIBANK": "BANKING",
    "ITC": "FMCG",
    "LT": "INFRA"
}

# ================= STREAMLIT =================
st.set_page_config("NSE Institutional Terminal", layout="wide")
st.title("🚀 NSE Institutional Smart Money Terminal")
st.caption(
    "All analysis is based on historical data and should not be considered financial advice. Invest at your own risk."
)
# ================= SIDEBAR =================
st.sidebar.header("📅 Institutional Controls")
window_days = st.sidebar.selectbox(
    "Rolling Window (Trading Days)",
    options=[5,10,20,50,100,200],
    index=1
)

# ================= RSI =================
@st.cache_data(ttl=300)
@st.fragment(run_every="5m")
def calculate_rsi_14(close):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ============================================================
# LOAD BHAVCOPY DATA
# ============================================================
BASE_DIR = Path(__file__).resolve().parent
BHAVCOPY_DIR = BASE_DIR / "Bhavcopy"


@st.cache_data(ttl=600, show_spinner=True)
def load_price_history(limit_files=360):
    """
    Render-safe version:
    - loads limited files to avoid memory crash
    - processes incrementally
    - avoids huge concat spikes
    """

    files = sorted(BHAVCOPY_DIR.glob("sec_bhavdata_full_*.csv"))

    if not files:
        return pd.DataFrame()

    # LIMIT FILES (CRITICAL FOR RENDER)
    #files = files[-limit_files:]
    limit_files = 360
    files = sorted(files)[-min(limit_files, len(files)):]
    

    REQUIRED_COLS = {
        "SYMBOL", "SERIES",
        "PREV_CLOSE", "OPEN_PRICE", "HIGH_PRICE", "LOW_PRICE",
        "LAST_PRICE", "CLOSE_PRICE", "AVG_PRICE",
        "TTL_TRD_QNTY", "TURNOVER_LACS", "NO_OF_TRADES",
        "DELIV_QTY", "DELIV_PER"
    }

    hist_chunks = []

    for f in files:
        try:
            trade_date = datetime.strptime(
                f.name.split("_")[-1].replace(".csv", ""),
                "%d%m%Y"
            )

            df = pd.read_csv(f)
            df.columns = df.columns.str.upper().str.strip()

            if "SERIES" not in df.columns:
                continue

            df["SERIES"] = df["SERIES"].astype(str).str.upper().str.strip()
            #df = df[df["SERIES"].str.startswith("EQ", na=False)]
            df = df[df["SERIES"].astype(str).str.upper().str.strip().eq("EQ")]

            missing_cols = REQUIRED_COLS - set(df.columns)
            if len(missing_cols) > 0:
                continue

            df = df[list(REQUIRED_COLS)].copy()
            df["DATE1"] = trade_date

            hist_chunks.append(df)

            # IMPORTANT: free memory immediately
            del df

        except Exception:
            continue

    if not hist_chunks:
        return pd.DataFrame()

    # safer concat (still OK because limited files)
    hist = pd.concat(hist_chunks, ignore_index=True, copy=False)

    hist.sort_values(["SYMBOL", "DATE1"], inplace=True)

    # ========================================================
    # RSI (SAFE VERSION - avoids full groupby transform crash)
    # ========================================================

    def rsi_group(x):
        return calculate_rsi_14(x)

    hist["RSI"] = hist.groupby("SYMBOL", group_keys=False)["CLOSE_PRICE"].apply(rsi_group)

    # 14-day return (safe per group)
    hist["RET_14D"] = hist.groupby("SYMBOL")["CLOSE_PRICE"].pct_change(14) * 100

    return hist
# ================= LOAD DATA =================
hist = load_price_history()
if hist.empty:
    st.error("❌ No valid bhavcopy EQ data found")
    st.stop()

# ================= NUMERIC SAFETY =================
num_cols = [
    "PREV_CLOSE","OPEN_PRICE","HIGH_PRICE","LOW_PRICE",
    "LAST_PRICE","CLOSE_PRICE","AVG_PRICE",
    "TTL_TRD_QNTY","TURNOVER_LACS","NO_OF_TRADES",
    "DELIV_QTY","DELIV_PER"
]
for c in num_cols:
    hist[c] = pd.to_numeric(hist[c], errors="coerce")

# ================= LATEST SNAPSHOT =================
latest = (
    hist.dropna(subset=["RSI","RET_14D"])
        .groupby("SYMBOL", as_index=False)
        .tail(1)
)

# ================= STOCK SNAPSHOT =================
st.subheader("📊 Market Wealth Insights -Summary")
st.dataframe(
    latest[
        [
            "SYMBOL","SERIES","DATE1",
            "PREV_CLOSE","OPEN_PRICE","HIGH_PRICE","LOW_PRICE",
            "LAST_PRICE","CLOSE_PRICE","AVG_PRICE",
            "TTL_TRD_QNTY","TURNOVER_LACS","NO_OF_TRADES",
            "DELIV_QTY","DELIV_PER","RSI","RET_14D"
        ]
    ].sort_values("TURNOVER_LACS", ascending=False),
    use_container_width=True
)

# ================= ROLLING WINDOW =================
rolling_dates = (
    hist["DATE1"]
    .drop_duplicates()
    .sort_values(ascending=False)
    .head(window_days)
)

hist_nd = hist[hist["DATE1"].isin(rolling_dates)].copy()
hist_nd["VALUE_TRADED"] = hist_nd["DELIV_QTY"] * hist_nd["CLOSE_PRICE"]

# ================= TOP BUY =================
st.subheader(f"📈 Top Institutional BUY – Last {window_days} Days")

top_buy = (
    hist_nd.groupby("SYMBOL", as_index=False)
    .agg(
        TOTAL_DELIV_QTY=("DELIV_QTY","sum"),
        VALUE_TRADED=("VALUE_TRADED","sum"),
        AVG_DELIV_PER=("DELIV_PER","mean")
    )
    .sort_values("VALUE_TRADED", ascending=False)
    .head(20)
)

st.dataframe(top_buy, use_container_width=True)

st.plotly_chart(
    px.pie(top_buy, names="SYMBOL", values="VALUE_TRADED",
           title="Top BUY (Delivery Value)", hole=0.4),
    use_container_width=True
)

# ================= TOP SELL =================
st.subheader(f"📉 Top Institutional SELL – Last {window_days} Days")

ret_nd = (
    hist_nd.sort_values(["SYMBOL","DATE1"])
    .groupby("SYMBOL")
    .apply(lambda x:
        (x["CLOSE_PRICE"].iloc[-1] - x["CLOSE_PRICE"].iloc[0]) /
        x["CLOSE_PRICE"].iloc[0] * 100 if len(x) > 1 else np.nan
    )
    .reset_index(name="RET_ND")
)

top_sell = (
    hist_nd.groupby("SYMBOL", as_index=False)
    .agg(TOTAL_DELIV_QTY=("DELIV_QTY","sum"))
    .merge(ret_nd, on="SYMBOL")
    .sort_values("RET_ND")
    .head(20)
)

st.dataframe(top_sell, use_container_width=True)

st.plotly_chart(
    px.pie(top_sell, names="SYMBOL", values="TOTAL_DELIV_QTY",
           title="Top SELL (Delivery Pressure)", hole=0.4),
    use_container_width=True
)

# ================= VWAP ACCUMULATION =================
st.subheader("📍 VWAP Accumulation Zones")

vwap = (
    hist_nd.groupby("SYMBOL")
    .apply(lambda x: (x["CLOSE_PRICE"] * x["DELIV_QTY"]).sum() / x["DELIV_QTY"].sum())
    .reset_index(name="VWAP")
)

vwap_zone = latest.merge(vwap, on="SYMBOL", how="left")
vwap_zone = vwap_zone[
    (vwap_zone["CLOSE_PRICE"] >= vwap_zone["VWAP"]) &
    (vwap_zone["DELIV_PER"] > 50)
]

st.dataframe(
    vwap_zone[["SYMBOL","CLOSE_PRICE","VWAP","DELIV_PER","RSI"]],
    use_container_width=True
)

# ================= CPR BREAKOUT =================
st.subheader("🚀 CPR + Institutional Breakouts")

cpr = latest.copy()
cpr["PIVOT"] = (cpr["HIGH_PRICE"] + cpr["LOW_PRICE"] + cpr["CLOSE_PRICE"]) / 3
cpr["BC"] = (cpr["HIGH_PRICE"] + cpr["LOW_PRICE"]) / 2
cpr["TC"] = 2 * cpr["PIVOT"] - cpr["BC"]

breakout = cpr[(cpr["CLOSE_PRICE"] > cpr["TC"]) & (cpr["DELIV_PER"] > 60)]
st.dataframe(breakout[["SYMBOL","CLOSE_PRICE","TC","DELIV_PER","RSI"]],
             use_container_width=True)

# ================= SECTOR ROTATION =================
st.subheader("🔄 Sector Capital Rotation")

hist_nd["SECTOR"] = hist_nd["SYMBOL"].map(SECTOR_MAP).fillna("OTHERS")

sector_flow = (
    hist_nd.groupby("SECTOR", as_index=False)
    .agg(VALUE_TRADED=("VALUE_TRADED","sum"))
    .sort_values("VALUE_TRADED", ascending=False)
)

st.plotly_chart(
    px.bar(sector_flow, x="SECTOR", y="VALUE_TRADED",
           title="Sector Capital Flow"),
    use_container_width=True
)

# ================= FII vs DII – SECTOR BAR CHART (PROXY) =================

st.subheader("🏦 FII vs DII Sector Flow (Institutional Proxy)")

# Map sector (already exists above)
hist_nd["SECTOR"] = hist_nd["SYMBOL"].map(SECTOR_MAP).fillna("OTHERS")

# Separate FII & DII proxy
fii_proxy = hist_nd[hist_nd["DELIV_PER"] >= 60].copy()
dii_proxy = hist_nd[(hist_nd["DELIV_PER"] < 60) & (hist_nd["DELIV_PER"] >= 30)].copy()

fii_sector = (
    fii_proxy.groupby("SECTOR", as_index=False)
    .agg(FII_VALUE=("VALUE_TRADED", "sum"))
)

dii_sector = (
    dii_proxy.groupby("SECTOR", as_index=False)
    .agg(DII_VALUE=("VALUE_TRADED", "sum"))
)

# Merge
sector_fii_dii = (
    fii_sector.merge(dii_sector, on="SECTOR", how="outer")
    .fillna(0)
)

# Melt for bar chart
sector_melted = sector_fii_dii.melt(
    id_vars="SECTOR",
    value_vars=["FII_VALUE", "DII_VALUE"],
    var_name="Institution",
    value_name="Value"
)

# Plot
st.plotly_chart(
    px.bar(
        sector_melted,
        x="SECTOR",
        y="Value",
        color="Institution",
        barmode="group",
        title="FII vs DII Sector-wise Institutional Flow "
    ),
    use_container_width=True
)

# ================= EXPLANATION =================
st.info(
    "ℹ️ This chart is an **institutional proxy** based on delivery behavior:\n\n"
    "🔵 FII  → High delivery conviction (DELIV% ≥ 60)\n"
    "🟠 DII  → Moderate delivery accumulation (30 ≤ DELIV% < 60)\n\n"
    "Used widely to detect **sector capital rotation & smart money strength**."
)

# ============================================================
# FII & DII SELLING – SECTOR WISE (SEPARATE BAR CHARTS)
# ============================================================

st.subheader("🏦 Institutional Selling – Sector Wise Overview")

# -------- FII SELLING PROXY (Distribution) --------
fii_sell = hist_nd[
    (hist_nd["DELIV_PER"] < 30) &
    (hist_nd["CLOSE_PRICE"] < hist_nd["PREV_CLOSE"])
].groupby("SECTOR", as_index=False).agg(
    FII_SELL_VALUE=("VALUE_TRADED", "sum")
)

fii_sell = fii_sell.sort_values("FII_SELL_VALUE", ascending=False)

# -------- DII SELLING PROXY (Support Exit) --------
dii_sell = hist_nd[
    (hist_nd["DELIV_PER"] >= 30) &
    (hist_nd["DELIV_PER"] < 60) &
    (hist_nd["CLOSE_PRICE"] < hist_nd["PREV_CLOSE"])
].groupby("SECTOR", as_index=False).agg(
    DII_SELL_VALUE=("VALUE_TRADED", "sum")
)

dii_sell = dii_sell.sort_values("DII_SELL_VALUE", ascending=False)

# ================= FII SECTOR SELLING CHART =================
st.subheader("🔵 FII Selling – Sector Wise (Distribution)")

if not fii_sell.empty:
    st.plotly_chart(
        px.bar(
            fii_sell,
            x="SECTOR",
            y="FII_SELL_VALUE",
            color="FII_SELL_VALUE",
            title="FII Selling by Sector",
            labels={
                "SECTOR": "Sector",
                "FII_SELL_VALUE": "FII Sell Value"
            }
        ),
        use_container_width=True
    )
    st.dataframe(fii_sell, use_container_width=True)
else:
    st.info("No strong FII selling detected in this window.")

# ================= DII SECTOR SELLING CHART =================
st.subheader("🟠 DII Selling – Sector Wise (Exit / Rebalancing)")

if not dii_sell.empty:
    st.plotly_chart(
        px.bar(
            dii_sell,
            x="SECTOR",
            y="DII_SELL_VALUE",
            color="DII_SELL_VALUE",
            title="DII Selling by Sector ()",
            labels={
                "SECTOR": "Sector",
                "DII_SELL_VALUE": "DII Sell Value"
            }
        ),
        use_container_width=True
    )
    st.dataframe(dii_sell, use_container_width=True)
else:
    st.info("No strong DII selling detected in this window.")

# ================= USER INTERPRETATION GUIDE =================
st.info(
    "🧠 Interpretation Guide:\n\n"
    "🔵 FII Selling → Sector losing foreign conviction (Risk-Off)\n"
    "🟠 DII Selling → Domestic rebalancing or profit booking\n\n"
    "Best signals:\n"
    "✅ BUY when FII BUY ↑ & SELL ↓\n"
    "❌ AVOID when FII SELL ↑ sharply\n"
    "⚠️ WATCH when DII SELL > FII SELL"
)

# ============================================================
# BREAKDOWN OF "OTHERS" – STOCK LEVEL (FII & DII)
# ============================================================

st.subheader("🔎 Breakdown of 'OTHERS' Sector – Stock Level View")

others_df = hist_nd[hist_nd["SECTOR"] == "OTHERS"].copy()

if others_df.empty:
    st.info("No stocks fall under OTHERS in the selected window.")
else:
    # ================= FII BUY – OTHERS =================
    fii_buy_others = (
        others_df[others_df["DELIV_PER"] >= 60]
        .groupby("SYMBOL", as_index=False)
        .agg(VALUE_TRADED=("VALUE_TRADED", "sum"))
        .sort_values("VALUE_TRADED", ascending=False)
        .head(20)
    )

    st.subheader("🔵 FII BUY – OTHERS (Stock-wise)")

    if not fii_buy_others.empty:
        st.plotly_chart(
            px.bar(
                fii_buy_others,
                x="SYMBOL",
                y="VALUE_TRADED",
                color="VALUE_TRADED",
                title="FII Buying (OTHERS) – Stock-wise",
                labels={"SYMBOL": "Stock", "VALUE_TRADED": "Buy Value"}
            ),
            use_container_width=True
        )
        st.dataframe(fii_buy_others, use_container_width=True)
    else:
        st.info("No FII buying detected in OTHERS.")

    # ================= FII SELL – OTHERS =================
    fii_sell_others = (
        others_df[
            (others_df["DELIV_PER"] < 30) &
            (others_df["CLOSE_PRICE"] < others_df["PREV_CLOSE"])
        ]
        .groupby("SYMBOL", as_index=False)
        .agg(VALUE_TRADED=("VALUE_TRADED", "sum"))
        .sort_values("VALUE_TRADED", ascending=False)
        .head(20)
    )

    st.subheader("🔵 FII SELL – OTHERS (Stock-wise)")

    if not fii_sell_others.empty:
        st.plotly_chart(
            px.bar(
                fii_sell_others,
                x="SYMBOL",
                y="VALUE_TRADED",
                color="VALUE_TRADED",
                title="FII Selling (OTHERS) – Stock-wise",
                labels={"SYMBOL": "Stock", "VALUE_TRADED": "Sell Value"}
            ),
            use_container_width=True
        )
        st.dataframe(fii_sell_others, use_container_width=True)
    else:
        st.info("No FII selling detected in OTHERS.")

    # ================= DII BUY – OTHERS =================
    dii_buy_others = (
        others_df[
            (others_df["DELIV_PER"] >= 30) &
            (others_df["DELIV_PER"] < 60)
        ]
        .groupby("SYMBOL", as_index=False)
        .agg(VALUE_TRADED=("VALUE_TRADED", "sum"))
        .sort_values("VALUE_TRADED", ascending=False)
        .head(20)
    )

    st.subheader("🟠 DII BUY – OTHERS (Stock-wise)")

    if not dii_buy_others.empty:
        st.plotly_chart(
            px.bar(
                dii_buy_others,
                x="SYMBOL",
                y="VALUE_TRADED",
                color="VALUE_TRADED",
                title="DII Buying (OTHERS) – Stock-wise",
                labels={"SYMBOL": "Stock", "VALUE_TRADED": "Buy Value"}
            ),
            use_container_width=True
        )
        st.dataframe(dii_buy_others, use_container_width=True)
    else:
        st.info("No DII buying detected in OTHERS.")

    # ================= DII SELL – OTHERS =================
# ============================================================
# BREAKDOWN OF "OTHERS" – STOCK LEVEL WITH DATE CONTEXT
# ============================================================

st.subheader("🔎 Breakdown of 'OTHERS' Sector – Stock Level (Date-wise Context)")

others_df = hist_nd[hist_nd["SECTOR"] == "OTHERS"].copy()

if others_df.empty:
    st.info("No stocks fall under OTHERS in the selected window.")
else:

    # ================= FII BUY – OTHERS =================
    fii_buy_others = (
        others_df[others_df["DELIV_PER"] > 60]
        .groupby("SYMBOL", as_index=False)
        .agg(
            VALUE_TRADED=("VALUE_TRADED", "sum"),
            LAST_ACTIVITY_DATE=("DATE1", "max")
        )
        .sort_values("VALUE_TRADED", ascending=False)
        .head(40)
    )

    st.subheader("🔵 FII BUY – OTHERS (Stock-wise with Date)")

    st.plotly_chart(
        px.bar(
            fii_buy_others,
            x="SYMBOL",
            y="VALUE_TRADED",
            color="LAST_ACTIVITY_DATE",
            title="FII Buying (OTHERS) – Stock-wise with Date",
            labels={
                "SYMBOL": "Stock",
                "VALUE_TRADED": "Buy Value",
                "LAST_ACTIVITY_DATE": "Last Buy Date"
            }
        ),
        use_container_width=True
    )

    st.dataframe(fii_buy_others, use_container_width=True)

    # ================= FII SELL – OTHERS =================
    fii_sell_others = (
        others_df[
            (others_df["DELIV_PER"] < 30) &
            (others_df["CLOSE_PRICE"] < others_df["PREV_CLOSE"])
        ]
        .groupby("SYMBOL", as_index=False)
        .agg(
            VALUE_TRADED=("VALUE_TRADED", "sum"),
            LAST_ACTIVITY_DATE=("DATE1", "max")
        )
        .sort_values("VALUE_TRADED", ascending=False)
        .head(40)
    )

    st.subheader("🔵 FII SELL – OTHERS (Stock-wise with Date)")

    st.plotly_chart(
        px.bar(
            fii_sell_others,
            x="SYMBOL",
            y="VALUE_TRADED",
            color="LAST_ACTIVITY_DATE",
            title="FII Selling (OTHERS) – Stock-wise with Date",
            labels={
                "SYMBOL": "Stock",
                "VALUE_TRADED": "Sell Value",
                "LAST_ACTIVITY_DATE": "Last Sell Date"
            }
        ),
        use_container_width=True
    )

    st.dataframe(fii_sell_others, use_container_width=True)

    # ================= DII BUY – OTHERS =================
    dii_buy_others = (
        others_df[
            (others_df["DELIV_PER"] >= 30) &
            (others_df["DELIV_PER"] < 60)
        ]
        .groupby("SYMBOL", as_index=False)
        .agg(
            VALUE_TRADED=("VALUE_TRADED", "sum"),
            LAST_ACTIVITY_DATE=("DATE1", "max")
        )
        .sort_values("VALUE_TRADED", ascending=False)
        .head(20)
    )

    st.subheader("🟠 DII BUY – OTHERS (Stock-wise with Date)")

    st.plotly_chart(
        px.bar(
            dii_buy_others,
            x="SYMBOL",
            y="VALUE_TRADED",
            color="LAST_ACTIVITY_DATE",
            title="DII Buying (OTHERS) – Stock-wise with Date",
            labels={
                "SYMBOL": "Stock",
                "VALUE_TRADED": "Buy Value",
                "LAST_ACTIVITY_DATE": "Last Buy Date"
            }
        ),
        use_container_width=True
    )

    st.dataframe(dii_buy_others, use_container_width=True)

    # ================= DII SELL – OTHERS =================
    dii_sell_others = (
        others_df[
            (others_df["DELIV_PER"] >= 30) &
            (others_df["DELIV_PER"] < 60) &
            (others_df["CLOSE_PRICE"] < others_df["PREV_CLOSE"])
        ]
        .groupby("SYMBOL", as_index=False)
        .agg(
            VALUE_TRADED=("VALUE_TRADED", "sum"),
            LAST_ACTIVITY_DATE=("DATE1", "max")
        )
        .sort_values("VALUE_TRADED", ascending=False)
        .head(20)
    )

    st.subheader("🟠 DII SELL – OTHERS (Stock-wise with Date)")

    st.plotly_chart(
        px.bar(
            dii_sell_others,
            x="SYMBOL",
            y="VALUE_TRADED",
            color="LAST_ACTIVITY_DATE",
            title="DII Selling (OTHERS) – Stock-wise with Date",
            labels={
                "SYMBOL": "Stock",
                "VALUE_TRADED": "Sell Value",
                "LAST_ACTIVITY_DATE": "Last Sell Date"
            }
        ),
        use_container_width=True
    )

    st.dataframe(dii_sell_others, use_container_width=True)

# ================= USER NOTE =================
st.info(
    "📅 DATE CONTEXT: The 'Last Activity Date' column shows the most recent date "
    "when institutional buying or selling occurred within the selected rolling window. "
    "This helps distinguish **fresh accumulation** from **older activity**, aiding better decisions."
)

# ============================================================
# 📈 TRADER VIEW DASHBOARD – SYMBOL | PRICE | VOLUME | TIME
# ============================================================

st.subheader("📊 Trader View – Price | Volume | Time")

# --- Stock selector ---
trade_symbol = st.selectbox(
    "Select Stock (Trader View)",
    sorted(hist["SYMBOL"].unique())
)

trade_df = hist[hist["SYMBOL"] == trade_symbol].sort_values("DATE1")

# ================= VWAP CALCULATION (TRADER VIEW – SAFE) =================

# Cumulative VWAP for selected stock
trade_df["VWAP"] = (
    (trade_df["CLOSE_PRICE"] * trade_df["DELIV_QTY"]).cumsum() /
    trade_df["DELIV_QTY"].cumsum()
)

# ================= PRICE VS TIME =================
st.subheader("📈 Price vs Time")

st.plotly_chart(
    px.line(
        trade_df,
        x="DATE1",
        y="CLOSE_PRICE",
        title=f"{trade_symbol} – Price Trend",
        labels={"DATE1": "Time", "CLOSE_PRICE": "Price"},
    ).add_scatter(
        x=trade_df["DATE1"],
        y=trade_df["VWAP"],
        mode="lines",
        name="VWAP",
        line=dict(dash="dash")
    ),
    use_container_width=True
)

# ================= VOLUME VS TIME =================
st.subheader("📊 Volume vs Time")

vol_df = trade_df.rename(
    columns={
        "TTL_TRD_QNTY": "Total_Volume",
        "DELIV_QTY": "Delivery_Volume"
    }
)

st.plotly_chart(
    px.bar(
        vol_df,
        x="DATE1",
        y="Total_Volume",
        title=f"{trade_symbol} – Total Volume",
        labels={"DATE1": "Time", "Total_Volume": "Volume"},
        opacity=0.7
    ),
    use_container_width=True
)

st.plotly_chart(
    px.bar(
        vol_df,
        x="DATE1",
        y="Delivery_Volume",
        title=f"{trade_symbol} – Delivery Volume (Institutional)",
        labels={"DATE1": "Time", "Delivery_Volume": "Delivery Volume"},
        color="Delivery_Volume"
    ),
    use_container_width=True
)

# ================= TRADER SNAPSHOT TABLE =================
st.subheader("📋 Trader Snapshot (Price | Volume | Time)")
@st.cache_data(ttl=300)
@st.fragment(run_every="5m")
def trader_signal(row):
    if row["CLOSE_PRICE"] > row["VWAP"] and row["DELIV_PER"] > 60:
        return "🟢 Accumulation (Bullish)"
    elif row["CLOSE_PRICE"] < row["VWAP"] and row["DELIV_PER"] < 30:
        return "🔴 Distribution (Bearish)"
    else:
        return "🟡 Balance / Wait"

trade_df["Trader_View"] = trade_df.apply(trader_signal, axis=1)

st.dataframe(
    trade_df[
        [   
            "SYMBOL",
            "DATE1",
            "CLOSE_PRICE",
            "VWAP",
            "TTL_TRD_QNTY",
            "DELIV_QTY",
            "DELIV_PER",
            "Trader_View"
        ]
    ].sort_values("DATE1", ascending=False),
    use_container_width=True
)

# ============================================================
# 📊 TRADER MARKET SCANNER – TOP 50 STOCKS (LIQUIDITY VIEW)
# ============================================================

st.subheader("📈 Trader Market Scanner – Top 50 Stocks by Liquidity")

# Use latest available trading day
latest_date = hist["DATE1"].max()

scanner_df = (
    hist[hist["DATE1"] == latest_date]
    .copy()
)

# Liquidity metric (what traders really care about)
scanner_df["LIQUIDITY_VALUE"] = scanner_df["CLOSE_PRICE"] * scanner_df["TTL_TRD_QNTY"]

# Trader signal logic
@st.cache_data(ttl=300)
@st.fragment(run_every="5m")
def trader_signal(row):
    if row["DELIV_PER"] >= 60:
        return "🟢 Accumulation - Bullish"
    elif row["DELIV_PER"] < 30:
        return "🔴 Distribution - Bearish"
    else:
        return "🟡 Active Trading - Balanced"

scanner_df["TRADER_VIEW"] = scanner_df.apply(trader_signal, axis=1)

# Select Top 50 most liquid stocks
top50 = (
    scanner_df
    .sort_values("LIQUIDITY_VALUE", ascending=False)
    .head(50)
)

st.dataframe(
    top50[
        [
            "SYMBOL",
            "DATE1",
            "CLOSE_PRICE",
            "TTL_TRD_QNTY",
            "DELIV_QTY",
            "DELIV_PER",
            "LIQUIDITY_VALUE",
            "TRADER_VIEW"
        ]
    ],
    use_container_width=True
)

st.caption(
    "📌 Top 50 stocks ranked by liquidity (Price × Volume) for the latest trading day. "
    "This is the primary **stock selection view for traders**."
)


# # Custom hover to show stock, date & price
# pie_fig.update_traces(
#     hovertemplate=(
#         "<b>%{label}</b><br><br>"
#         "Stock: %{customdata[0]}<br>"
#         "Date: %{customdata[1]}<br>"
#         "Close Price: ₹%{customdata[2]:,.2f}"
#         "<extra></extra>"
#     ),
#     customdata=top50[["SYMBOL", "DATE1", "CLOSE_PRICE"]].values,
#     textinfo="percent+label"
# )

# st.plotly_chart(pie_fig, use_container_width=True)
#==================Added 29-APR-26 END ==============================
# ================= QUICK LEGEND =================
st.info(
    "🧠 Trader Interpretation Guide:\n\n"
    "🟢 Accumulation → Price above VWAP + High delivery\n"
    "🔴 Distribution → Price below VWAP + Low delivery\n"
    "🟡 Balance → No clear institutional control\n\n"
    "VWAP = Institutional fair value\n"
    "Delivery Volume = Smart money participation"
)
# ================= VWAP STATUS CLASSIFICATION =================

# Tolerance for "VWAP flattening" (±0.5%)
VWAP_TOL = 0.005
@st.cache_data(ttl=300)
@st.fragment(run_every="5m")
def vwap_status(row):
    if row["CLOSE_PRICE"] > row["VWAP"] * (1 + VWAP_TOL):
        return "🟢⬆️ Bullish / Accumulation"
    elif row["CLOSE_PRICE"] < row["VWAP"] * (1 - VWAP_TOL):
        return "🔴⬇️ Bearish / Distribution"
    else:
        return "🟡➡️ Balanced / Consolidation"

vwap_zone["VWAP_STATUS"] = vwap_zone.apply(vwap_status, axis=1)

st.subheader("📍 VWAP Status – Smart Money View")

st.dataframe(
    vwap_zone[
        [
            "SYMBOL",
            "CLOSE_PRICE",
            "VWAP",
            "VWAP_STATUS",
            "DELIV_PER",
            "RSI"
        ]
    ].sort_values("DELIV_PER", ascending=False),
    use_container_width=True
)

# ================= VWAP INSIGHT – TABLE VIEW =================

st.subheader("🧭 Volume Weighted Average Price(VWAP) Insight – Stock Decision Table")

# Friendly interpretation column
@st.cache_data(ttl=300)
@st.fragment(run_every="5m")
def smart_money_view(status):
    if "Bullish" in status:
        return "✅ Accumulating"
    elif "Bearish" in status:
        return "❌ Distribution"
    else:
        return "⚠️ Wait / Consolidation"

vwap_table = vwap_zone.copy()

vwap_table["Stock_Name"] = vwap_table["SYMBOL"]
vwap_table["Smart_Money_View"] = vwap_table["VWAP_STATUS"].apply(smart_money_view)

# Select & order columns for customer clarity
vwap_table_display = vwap_table[
    [
        "Stock_Name",
        "VWAP_STATUS",
        "CLOSE_PRICE",
        "VWAP",
        "DELIV_PER",
        "RSI",
        "Smart_Money_View"
    ]
].sort_values(["VWAP_STATUS", "DELIV_PER"], ascending=[False, False])

st.dataframe(
    vwap_table_display,
    use_container_width=True
)

#===================29-APR-2026 start===========================
# ---------- 1️⃣ BUY PROXY – BAR CHART ----------
latest["VALUE_TRADED"] = latest["DELIV_QTY"] * latest["CLOSE_PRICE"]

top_buy_stocks = (
    latest.sort_values("VALUE_TRADED", ascending=False)
    .head(20)[["SYMBOL","DELIV_QTY","CLOSE_PRICE","VALUE_TRADED","DATE1"]]
)

top_sell_stocks = (
    latest.sort_values("RET_14D")
    .head(20)[["SYMBOL","DELIV_QTY","CLOSE_PRICE","RET_14D","DATE1"]]
)

st.plotly_chart(
    px.bar(
        top_buy_stocks,
        x="SYMBOL",
        y="DELIV_QTY",
        color="VALUE_TRADED",
        text="VALUE_TRADED",
        hover_data={
            "DATE1": True,
            "DELIV_QTY": True,
            "CLOSE_PRICE": True,
            "VALUE_TRADED": True
        },
        title="📊 Top Institutional BUY Stocks (SYMBOL vs DELIV_QTY & VALUE_TRADED)",
        labels={"DELIV_QTY": "Delivery Qty", "VALUE_TRADED": "Value Traded","DATE1": "Date"}
    ).update_layout(xaxis_tickangle=-45),
    use_container_width=True
)

st.plotly_chart(
    px.bar(
        top_sell_stocks,
        x="SYMBOL",
        y="DELIV_QTY",
        color="CLOSE_PRICE",
        text="CLOSE_PRICE",
        hover_data={
            "DATE1": True,
            "DELIV_QTY": True,
            "CLOSE_PRICE": True,
            "RET_14D": True
        },
        title="📉 Top Institutional SELL Stocks (SYMBOL vs DELIV_QTY & CLOSE)",
        labels={"DELIV_QTY": "Delivery Qty", "CLOSE_PRICE": "Close Price","DATE1": "Date"}
    ).update_layout(xaxis_tickangle=-45),
    use_container_width=True
)
#===================29-APR-2026 End===========================

import plotly.express as px

st.subheader("🥧 Market Sentiment Snapshot (Latest Trading Day)")

# ---------- CREATE THE PIE FIGURE ----------
pie_fig = px.pie(
    top50,
    names="TRADER_VIEW",
    values="LIQUIDITY_VALUE",
    color="TRADER_VIEW",
    color_discrete_map={
        "Bullish": "#2ECC71",     # Green
        "Balanced": "#F1C40F",    # Yellow
        "Bearish": "#E74C3C",     # Red
    },
    title=f"Market State – {latest_date.date()}",
)

# ---------- ADD HOVER DETAILS ----------
pie_fig.update_traces(
    textinfo="percent+label",
    hovertemplate=(
        "<b>%{label}</b><br><br>"
        "Stock: %{customdata[0]}<br>"
        "Date: %{customdata[1]}<br>"
        "Close Price: ₹%{customdata[2]:,.2f}"
        "<extra></extra>"
    ),
    customdata=top50[["SYMBOL", "DATE1", "CLOSE_PRICE"]].values
)

# ---------- DISPLAY ----------
st.plotly_chart(pie_fig, use_container_width=True)

######## START - CODE ADDED BASED ON FEEDBACK  29-APR-2026########################

import pandas as pd
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os

# =========================================================
# CONFIG
# =========================================================
ACCOUNT_CAPITAL = 1_000_000
MAX_PORTFOLIO_SIZE = 500
MAX_SERIES_WEIGHT = 0.40
PDF_DIR = "PDF_Reports"
os.makedirs(PDF_DIR, exist_ok=True)

# =========================================================
# BASIC PREP
# =========================================================
hist["DATE1"] = pd.to_datetime(hist["DATE1"])
latest_date = hist["DATE1"].max()
latest = hist[hist["DATE1"] == latest_date].copy()

if "SERIES" not in latest.columns:
    latest["SERIES"] = "EQ"

# =========================================================
# NORMALIZATION
# =========================================================
@st.cache_data(ttl=300)
@st.fragment(run_every="5m")
def normalize(series):
    if series.max() == series.min():
        return pd.Series(50, index=series.index)
    return 100 * (series - series.min()) / (series.max() - series.min())

# =========================================================
# INSTITUTIONAL FEATURES (FII/DII PROXY)
# =========================================================
latest["VALUE_TRADED"] = latest["CLOSE_PRICE"] * latest["TTL_TRD_QNTY"]

latest["DELIVERY_SCORE"]  = normalize(latest["DELIV_PER"])
latest["VALUE_SCORE"]     = normalize(latest["VALUE_TRADED"])
latest["MOMENTUM_SCORE"]  = normalize(latest["RSI"] + latest["RET_14D"])
latest["LIQUIDITY_SCORE"] = normalize(latest["TURNOVER_LACS"])

# =========================================================
# CPR LOGIC (UNCHANGED ✅)
# =========================================================
latest["PIVOT"] = (latest["HIGH_PRICE"] + latest["LOW_PRICE"] + latest["PREV_CLOSE"]) / 3
latest["BC"] = (latest["HIGH_PRICE"] + latest["LOW_PRICE"]) / 2
latest["TC"] = 2 * latest["PIVOT"] - latest["BC"]

# =========================================================
# ✅ INSTITUTIONAL REGIME CLASSIFICATION (NEW)
# =========================================================
@st.cache_data(ttl=300)
@st.fragment(run_every="5m")
def institutional_regime(row):
    # Bullish accumulation
    if row["CLOSE_PRICE"] > row["TC"] and row["DELIV_PER"] >= 60:
        return "🟢 Bullish (Accumulation)"

    # Bearish distribution
    elif row["CLOSE_PRICE"] < row["BC"] and row["DELIV_PER"] < 40:
        return "🔴 Bearish (Distribution)"

    # Balance / waiting
    else:
        return "🟡 Hold / Neutral"

latest["INST_REGIME"] = latest.apply(institutional_regime, axis=1)

# ✅ Valid for portfolio deployment
latest["CPR_INST_VALID"] = (
    (latest["INST_REGIME"] == "🟢 Bullish (Accumulation)")
)

# =========================================================
# AI SCORES (1M / 6M / 1Y)
# =========================================================
latest["AI_1M"] = (
    0.35 * latest["MOMENTUM_SCORE"] +
    0.35 * latest["DELIVERY_SCORE"] +
    0.20 * latest["VALUE_SCORE"] +
    0.10 * latest["LIQUIDITY_SCORE"]
)

latest["AI_6M"] = (
    0.40 * latest["DELIVERY_SCORE"] +
    0.30 * latest["VALUE_SCORE"] +
    0.20 * latest["MOMENTUM_SCORE"] +
    0.10 * latest["LIQUIDITY_SCORE"]
)

latest["AI_1Y"] = (
    0.45 * latest["DELIVERY_SCORE"] +
    0.30 * latest["VALUE_SCORE"] +
    0.15 * latest["LIQUIDITY_SCORE"] +
    0.10 * latest["MOMENTUM_SCORE"]
)

# =========================================================
# TARGETS & PROBABILITY
# =========================================================
@st.cache_data(ttl=300)
@st.fragment(run_every="5m")
def target_prob(price, ai, div):
    tgt = price * (1 + ai / div)
    prob = min(95, 40 + ai * 0.7)
    return round(tgt, 2), round(prob, 1)

latest[["TARGET_1M", "PROB_1M"]] = latest.apply(
    lambda r: target_prob(r["CLOSE_PRICE"], r["AI_1M"], 400),
    axis=1, result_type="expand"
)
latest[["TARGET_6M", "PROB_6M"]] = latest.apply(
    lambda r: target_prob(r["CLOSE_PRICE"], r["AI_6M"], 250),
    axis=1, result_type="expand"
)
latest[["TARGET_1Y", "PROB_1Y"]] = latest.apply(
    lambda r: target_prob(r["CLOSE_PRICE"], r["AI_1Y"], 200),
    axis=1, result_type="expand"
)

# =========================================================
# RISK & ALLOCATION
# =========================================================
latest["STOP_LOSS"] = latest["CLOSE_PRICE"] * 0.92
latest["RISK_WEIGHT"] = 1 / (100 - latest["AI_1Y"] + 10)
latest["POSITION_PCT"] = latest["RISK_WEIGHT"] / latest["RISK_WEIGHT"].sum()
latest["CAPITAL_ALLOC"] = latest["POSITION_PCT"] * ACCOUNT_CAPITAL

# =========================================================
# ✅ SERIES BALANCED ALPHA PORTFOLIO (BULLISH ONLY)
# =========================================================
portfolio = []
series_alloc = {}

for _, row in latest.sort_values("AI_1Y", ascending=False).iterrows():

    if not row["CPR_INST_VALID"]:
        continue

    ser = row["SERIES"]
    if series_alloc.get(ser, 0) >= MAX_SERIES_WEIGHT:
        continue

    portfolio.append(row)
    series_alloc[ser] = series_alloc.get(ser, 0) + row["POSITION_PCT"]

    if len(portfolio) >= MAX_PORTFOLIO_SIZE:
        break

portfolio = pd.DataFrame(portfolio)

# =========================================================
# STREAMLIT UI
# =========================================================
st.set_page_config(layout="wide")
st.title("🏦 AI Enabled Market Regime Dashboard")

# st.metric("Bullish Portfolio Size", len(portfolio))
# st.metric("As of Date", latest_date.strftime("%d-%b-%Y"))
# =========================================================
# DASHBOARD SUMMARY (TABLE FORMAT)
# =========================================================
st.subheader("📊 Portfolio Summary Dashboard")

summary_df = pd.DataFrame(
    {
        "Metric": [
            "Bullish Portfolio Size",
            "Hold / Neutral Stocks",
            "Bearish Stocks",
            "As of Date"
        ],
        "Value": [
            len(portfolio),
            (latest["INST_REGIME"] == "🟡 Hold / Neutral").sum(),
            (latest["INST_REGIME"] == "🔴 Bearish (Distribution)").sum(),
            latest_date.strftime("%d-%b-%Y")
        ]
    }
)

st.dataframe(summary_df, use_container_width=True)
# -----------------------
st.subheader("🟢 Bullish – Institutional Accumulation")
st.dataframe(portfolio, use_container_width=True)

st.subheader("🟡 Hold – Wait & Watch")
st.dataframe(
    latest[latest["INST_REGIME"] == "🟡 Hold / Neutral"],
    use_container_width=True
)

st.subheader("🔴 Bearish – Distribution / Avoid")
st.dataframe(
    latest[latest["INST_REGIME"] == "🔴 Bearish (Distribution)"],
    use_container_width=True
)

######## START - CODE ADDED BASED ON FEEDBACK  29-APR-2026########################
from datetime import datetime
@st.cache_data(ttl=300)
@st.fragment(run_every="5m")
def generate_pdf(latest_df):
    """
    Generates a customer-friendly PDF with
    Bullish, Hold, and Bearish sections
    """

    timestamp = datetime.now().strftime("%H%M%S")
    file = f"{PDF_DIR}/Institutional_Market_Report_{latest_date.strftime('%Y-%m-%d')}_{timestamp}.pdf"

    c = canvas.Canvas(file, pagesize=A4)
    text = c.beginText(40, 800)
    text.setFont("Helvetica", 10)

    # =========================================================
    # HEADER
    # =========================================================
    text.textLine("Institutional Market Regime Report")
    text.textLine(f"Analysis Date: {latest_date.strftime('%d-%b-%Y')}")
    text.textLine("")
    text.textLine("This report classifies stocks based on institutional buying")
    text.textLine("and selling behavior derived from delivery, volume, and price structure.")
    text.textLine("-" * 95)
    text.textLine("")

    # =========================================================
    # SECTION 1: BULLISH
    # =========================================================
    text.setFont("Helvetica-Bold", 11)
    text.textLine("🟢 SECTION 1: BULLISH – INSTITUTIONAL ACCUMULATION")
    text.setFont("Helvetica", 9)
    text.textLine("Stocks showing strong accumulation; suitable for medium to long-term holding.")
    text.textLine("")

    bullish = latest_df[latest_df["INST_REGIME"] == "🟢 Bullish (Accumulation)"]

    if bullish.empty:
        text.textLine("No stocks currently qualify under Bullish institutional criteria.")
        text.textLine("")
    else:
        for _, r in bullish.iterrows():
            upside = ((r["TARGET_1Y"] - r["CLOSE_PRICE"]) / r["CLOSE_PRICE"]) * 100
            text.textLine(f"{r['SYMBOL']} ({r['SERIES']})")
            text.textLine(f"  Current Price   : ₹{r['CLOSE_PRICE']}")
            text.textLine(f"  1-Year Target   : ₹{r['TARGET_1Y']}")
            text.textLine(f"  Expected Upside : {upside:.1f}%")
            text.textLine(f"  Confidence      : {r['PROB_1Y']}%")
            text.textLine("")

    # =========================================================
    # SECTION 2: HOLD
    # =========================================================
    text.setFont("Helvetica-Bold", 11)
    text.textLine("🟡 SECTION 2: HOLD – NEUTRAL / CONSOLIDATION")
    text.setFont("Helvetica", 9)
    text.textLine("Stocks in balance zone; monitor for breakout or breakdown.")
    text.textLine("")

    hold = latest_df[latest_df["INST_REGIME"] == "🟡 Hold / Neutral"]

    if hold.empty:
        text.textLine("No stocks currently in Hold / Neutral regime.")
        text.textLine("")
    else:
        for _, r in hold.head(40).iterrows():  # limit for readability
            text.textLine(f"{r['SYMBOL']} ({r['SERIES']}) | Close: ₹{r['CLOSE_PRICE']}")

        text.textLine("")

    # =========================================================
    # SECTION 3: BEARISH
    # =========================================================
    text.setFont("Helvetica-Bold", 11)
    text.textLine("🔴 SECTION 3: BEARISH – INSTITUTIONAL DISTRIBUTION")
    text.setFont("Helvetica", 9)
    text.textLine("Stocks showing distribution; avoid fresh buying or consider exit.")
    text.textLine("")

    bearish = latest_df[latest_df["INST_REGIME"] == "🔴 Bearish (Distribution)"]

    if bearish.empty:
        text.textLine("No stocks currently qualify under Bearish institutional criteria.")
        text.textLine("")
    else:
        for _, r in bearish.head(40).iterrows():
            text.textLine(f"{r['SYMBOL']} ({r['SERIES']}) | Close: ₹{r['CLOSE_PRICE']}")

        text.textLine("")

    # =========================================================
    # FOOTER / NOTES
    # =========================================================
    text.setFont("Helvetica", 9)
    text.textLine("-" * 95)
    text.textLine("Important Notes:")
    text.textLine("• This is a data-driven research output, not a trading advisory.")
    text.textLine("• Bullish does not mean guaranteed returns; risk management is essential.")
    text.textLine("• Review Hold stocks for potential transitions.")
    text.textLine("• Avoid or reduce exposure when stocks enter Bearish regime.")
    text.textLine("")
    text.textLine("Generated using Institutional Alpha Engine.")

    c.drawText(text)
    c.save()

    return file

#pdf_path = generate_pdf(portfolio)
#st.success(f"✅ PDF generated: {pdf_path}")

######## END - CODE ADDED BASED ON FEEDBACK  29-APR-2026########################

# ================= REPORT DOWNLOAD =================
st.subheader("📄 Daily Institutional Reports")

report_date = hist["DATE1"].max().strftime("%d-%m-%Y")

excel_name = f"nse_institutional_report_{report_date}.xlsx"

with pd.ExcelWriter(excel_name, engine="xlsxwriter") as writer:

    latest.to_excel(writer, sheet_name="Snapshot", index=False)

    top_buy.to_excel(writer, sheet_name="Top_Buy", index=False)

    top_sell.to_excel(writer, sheet_name="Top_Sell", index=False)

    vwap_zone.to_excel(writer, sheet_name="VWAP_Zones", index=False)

    sector_flow.to_excel(writer, sheet_name="Sector_Rotation", index=False)

st.download_button(
    "⬇️ Download Excel Report",
    open(excel_name, "rb").read(),
    excel_name
)

# PDF
# pdf_name = f"nse_institutional_report_{report_date}.pdf"
# c = canvas.Canvas(pdf_name, pagesize=A4)
# c.drawString(1*inch, 11*inch, "NSE Institutional Smart Money Report")
# c.drawString(1*inch, 10.6*inch, f"Date: {report_date}")
# y = 10*inch
# for sym in top_buy["SYMBOL"].head(15):
#     c.drawString(1*inch, y, f"- {sym}")
#     y -= 0.25*inch
# c.showPage()
# c.save()

# st.download_button(
#     "⬇️ Download PDF Report",
#     open(pdf_name, "rb").read(),
#     pdf_name
# )
