from fundamental_loder import latest_mc
import streamlit as st

filtered_df = latest_mc[
    (latest_mc["MARKET_CAP_CR"] >= 1000) &
    (latest_mc["MARKET_CAP_CR"] <= 15000)
]

st.dataframe(filtered_df)