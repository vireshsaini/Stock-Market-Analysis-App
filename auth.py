import streamlit as st
import pandas as pd
import os
from pathlib import Path
from datetime import datetime
from login_ui_style import set_bg

# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

USER_DIR = BASE_DIR / "User"
CRED_FILE = USER_DIR / "Credential.csv"
BG_IMAGE = USER_DIR / "background.png"

# ============================================================
# SAFE EXPIRY PARSER
# ============================================================

@st.cache_data(ttl=300)
def parse_expiry(value):

    value = str(value).strip()

    for fmt in ("%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M"):

        try:
            return datetime.strptime(value, fmt)

        except ValueError:
            pass

    return None


# ============================================================
# LOAD USERS
# ============================================================

@st.cache_data(ttl=300)
def load_users_from_csv():

    os.makedirs(USER_DIR, exist_ok=True)

    # Create default admin if file missing
    if not os.path.exists(CRED_FILE):

        df = pd.DataFrame([{
            "UNAME": "admin",
            "PWD": "welcome123",
            "EXP": "12/31/2026 18:00",
            "ROLE": "admin",
            "ENABLED": "TRUE"
        }])

        df.to_csv(CRED_FILE, index=False)

    df = pd.read_csv(
        CRED_FILE,
        sep=None,
        engine="python",
        encoding="utf-8-sig"
    )

    # Normalize headers
    df.columns = (
        df.columns
        .str.replace("\ufeff", "", regex=False)
        .str.upper()
        .str.strip()
    )

    required = {"UNAME", "PWD", "EXP", "ROLE", "ENABLED"}

    if not required.issubset(df.columns):

        st.error(
            f"Credential.csv missing columns: "
            f"{required - set(df.columns)}"
        )

        st.stop()

    # Normalize values
    for col in required:

        df[col] = df[col].astype(str).str.strip()

    df["ENABLED"] = (
        df["ENABLED"]
        .str.upper()
        .isin(["TRUE", "1", "YES"])
    )

    return df


# ============================================================
# AUTHENTICATION
# ============================================================

def authenticate(username, password, df):

    username = username.strip()
    password = password.strip()

    user = df[df["UNAME"] == username]

    if user.empty:
        return False, "Username not found"

    row = user.iloc[0]

    if not row["ENABLED"]:
        return False, "User is disabled"

    if password != row["PWD"]:
        return False, "Incorrect password"

    expiry = parse_expiry(row["EXP"])

    if not expiry or datetime.now() > expiry:
        return False, "Account expired"

    return True, row


# ============================================================
# LOGIN MANAGER
# ============================================================
def login_screen():

    if "users_df" not in st.session_state:

        st.session_state.users_df = load_users_from_csv()

    df = st.session_state.users_df

    # ========================================================
    # LOGIN PAGE
    # ========================================================

    if "auth" not in st.session_state:

        st.title("🔐 Login")

        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):

            ok, result = authenticate(username, password, df)

            if not ok:

                st.error(f"❌ {result}")
                st.stop()

            st.session_state.auth = {
                "username": result["UNAME"],
                "role": result["ROLE"],
                "expiry": result["EXP"]
            }

            st.success("✅ Login successful")
            st.rerun()

        st.stop()


    # ========================================================
    # AUTO LOGOUT ON EXPIRY
    # ========================================================

    expiry = parse_expiry(
        st.session_state.auth["expiry"]
    )

    if not expiry or expiry < datetime.now():

        st.session_state.clear()

        st.error("⏳ Session expired")

        st.stop()

    # ========================================================
    # SIDEBAR
    # ========================================================

    st.sidebar.success(
        f"👤 {st.session_state.auth['username']}"
    )

    st.sidebar.info(
        f"🔒 Role: {st.session_state.auth['role']}"
    )

    st.sidebar.warning(
        f"⏳ Expires: {st.session_state.auth['expiry']}"
    )

    if st.sidebar.button("🚪 Logout"):

        st.session_state.clear()
        st.rerun()

    # ========================================================
    # ADMIN VIEW
    # ========================================================

    if st.session_state.auth["role"] == "admin":

        st.sidebar.subheader("👥 Users")

        st.sidebar.dataframe(
            df[["UNAME", "ROLE", "EXP", "ENABLED"]],
            use_container_width=True
        )
