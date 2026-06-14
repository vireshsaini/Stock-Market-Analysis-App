import streamlit as st
import pandas as pd
import numpy as np

import plotly.graph_objects as go
from plotly.subplots import make_subplots


# =====================================================
# TRADING DASHBOARD (FINAL FIXED VERSION)
# =====================================================
@st.cache_data
def render_trading_dashboard(hist: pd.DataFrame):

    st.subheader("📈 Professional Trading Dashboard " )

    # -------------------------
    # SYMBOL SELECT
    # -------------------------
    symbols = sorted(hist["SYMBOL"].dropna().unique())

    selected_symbol = st.selectbox(
        "Select Stock",
        symbols,
        key="final_fixed_dashboard"
    )

    # -------------------------
    # FILTER DATA
    # -------------------------
    trade_df = (
        hist[hist["SYMBOL"] == selected_symbol]
        .copy()
        .sort_values("DATE1")
    )

    trade_df["DATE1"] = pd.to_datetime(trade_df["DATE1"])

    if trade_df.empty:
        st.warning("No data available")
        return

    # =====================================================
    # INDICATORS
    # =====================================================

    tp = (
        trade_df["HIGH_PRICE"]
        + trade_df["LOW_PRICE"]
        + trade_df["CLOSE_PRICE"]
    ) / 3

    trade_df["VWAP"] = (
        (tp * trade_df["TTL_TRD_QNTY"]).cumsum()
        / trade_df["TTL_TRD_QNTY"].cumsum()
    )

    # trade_df["EMA20"] = trade_df["CLOSE_PRICE"].ewm(span=20).mean()
    # trade_df["EMA50"] = trade_df["CLOSE_PRICE"].ewm(span=50).mean()
    # trade_df["EMA200"] = trade_df["CLOSE_PRICE"].ewm(span=200).mean()

    # ema12 = trade_df["CLOSE_PRICE"].ewm(span=12).mean()
    # ema26 = trade_df["CLOSE_PRICE"].ewm(span=26).mean()

    trade_df["EMA20"] = (trade_df.groupby("SYMBOL")["CLOSE_PRICE"].transform(lambda x: x.ewm(span=20, adjust=False).mean()))
    trade_df["EMA50"] = (trade_df.groupby("SYMBOL")["CLOSE_PRICE"].transform(lambda x: x.ewm(span=50, adjust=False).mean()))
    trade_df["EMA200"] = (trade_df.groupby("SYMBOL")["CLOSE_PRICE"].transform(lambda x: x.ewm(span=200, adjust=False).mean()))
    
    
    ema12 = (trade_df.groupby("SYMBOL")["CLOSE_PRICE"].transform(lambda x: x.ewm(span=12, adjust=False).mean()))
    ema26 = (trade_df.groupby("SYMBOL")["CLOSE_PRICE"].transform(lambda x: x.ewm(span=26, adjust=False).mean()))

    trade_df["MACD"] = ema12 - ema26
    #trade_df["Signal"] = trade_df["MACD"].ewm(span=9).mean()
    trade_df["Signal"] = (trade_df.groupby("SYMBOL")["MACD"].transform(lambda x: x.ewm(span=9,adjust=False).mean()))
    trade_df["Histogram"] = trade_df["MACD"] - trade_df["Signal"]

    # Volume colors
    volume_colors = np.where(
        trade_df["CLOSE_PRICE"] >= trade_df["OPEN_PRICE"],
        "#16a34a",
        "#ef4444"
    )

    hist_colors = np.where(
        trade_df["Histogram"] >= 0,
        "#16a34a",
        "#ef4444"
    )

    # =====================================================
    # SUBPLOTS (NO subplot_titles to avoid overlap)
    # =====================================================

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.10,   # IMPORTANT FIX
        row_heights=[0.6, 0.2, 0.2]
    )

    # =====================================================
    # PRICE CHART
    # =====================================================

    fig.add_trace(
        go.Candlestick(
            x=trade_df["DATE1"],
            open=trade_df["OPEN_PRICE"],
            high=trade_df["HIGH_PRICE"],
            low=trade_df["LOW_PRICE"],
            close=trade_df["CLOSE_PRICE"],
            name="Price",
            increasing_line_color="#16a34a",
            decreasing_line_color="#ef4444"
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=trade_df["DATE1"],
            y=trade_df["VWAP"],
            name="VWAP",
            line=dict(color="#6366f1", dash="dash")
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=trade_df["DATE1"],
            y=trade_df["EMA20"],
            name="EMA20",
            line=dict(color="#10b981")
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=trade_df["DATE1"],
            y=trade_df["EMA50"],
            name="EMA50",
            line=dict(color="#f59e0b")
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=trade_df["DATE1"],
            y=trade_df["EMA200"],
            name="EMA200",
            line=dict(color="#ef4444")
        ),
        row=1, col=1
    )

    # =====================================================
    # VOLUME
    # =====================================================

    fig.add_trace(
        go.Bar(
            x=trade_df["DATE1"],
            y=trade_df["TTL_TRD_QNTY"],
            marker_color=volume_colors,
            name="Volume"
        ),
        row=2, col=1
    )

    # =====================================================
    # MACD
    # =====================================================

    fig.add_trace(
        go.Scatter(
            x=trade_df["DATE1"],
            y=trade_df["MACD"],
            name="MACD",
            line=dict(color="#3b82f6")
        ),
        row=3, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=trade_df["DATE1"],
            y=trade_df["Signal"],
            name="Signal",
            line=dict(color="#f59e0b")
        ),
        row=3, col=1
    )

    fig.add_trace(
        go.Bar(
            x=trade_df["DATE1"],
            y=trade_df["Histogram"],
            marker_color=hist_colors,
            name="Histogram"
        ),
        row=3, col=1
    )

    # =====================================================
    # TITLE (SAFE - NO OVERLAP)
    # =====================================================
    
      # =========================
# PRICE PANEL LABEL
# =========================
    fig.add_annotation(
        text="<b>Price Action</b>",
        x=0.01,
        y=0.99,
        xref="paper",
        yref="paper",
        showarrow=False,
        align="left",
        font=dict(
            size=12,
            color="#555",
            family="Arial"
        )
    )

    # =========================
    # VOLUME PANEL LABEL
    # =========================
    fig.add_annotation(
        text="<b>Volume</b>",
        x=0.01,
        y=0.40,
        xref="paper",
        yref="paper",
        showarrow=False,
        align="left",
        font=dict(
            size=12,
            color="#555",
            family="Arial"
        )
    )

    # =========================
    # MACD PANEL LABEL
    # =========================
    fig.add_annotation(
        text="<b>MACD</b>",
        x=0.01,
        y=0.12,
        xref="paper",
        yref="paper",
        showarrow=False,
        align="left",
        font=dict(
            size=12,
            color="#555",
            family="Arial"
        )
    )  
    # =====================================================
    # FINAL LAYOUT FIX (CRITICAL)
    # =====================================================

    fig.update_layout(
        height=950,
        template="plotly_white",

        hovermode="x unified",
        xaxis_rangeslider_visible=False,

        paper_bgcolor="#ffffff",
        plot_bgcolor="#f8fafc",

        margin=dict(
            l=30,
            r=30,
            t=90,   # CRITICAL FIX FOR OVERLAP
            b=30
        ),

        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.08,   # PUSH LEGEND ABOVE
            xanchor="center",
            x=0.5,
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="rgba(0,0,0,0.1)",
            borderwidth=1
        )
    )

    # CLEAN GRID BOUNDARY
    fig.update_xaxes(
        showline=True,
        linewidth=1,
        linecolor="rgba(0,0,0,0.15)",
        mirror=True,
        showgrid=True,
        gridcolor="rgba(0,0,0,0.06)"
    )

    fig.update_yaxes(
        showline=True,
        linewidth=1,
        linecolor="rgba(0,0,0,0.15)",
        mirror=True,
        showgrid=True,
        gridcolor="rgba(0,0,0,0.06)"
    )

    # =====================================================
    # RENDER
    # =====================================================

    st.plotly_chart(fig, use_container_width=True)

    # =====================================================
    # METRICS
    # =====================================================

    latest = trade_df.iloc[-1]

    st.markdown("### 📊 Technical Summary")

    html = f"""
    <table style="width:100%; border-collapse:collapse;">
        <tr style="background-color:#f5f5f5;">
            <th>Close</th>
            <th>VWAP</th>
            <th>EMA20</th>
            <th>EMA50</th>
            <th>EMA200</th>
        </tr>
        <tr style="text-align:left;">
            <td>{latest['CLOSE_PRICE']:.2f}</td>
            <td>{latest['VWAP']:.2f}</td>
            <td>{latest['EMA20']:.2f}</td>
            <td>{latest['EMA50']:.2f}</td>
            <td>{latest['EMA200']:.2f}</td>
        </tr>
    </table>
    """

    st.markdown(html, unsafe_allow_html=True)