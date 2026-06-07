import streamlit as st
import pandas as pd
import os
import uuid
import json
import time
from pathlib import Path
from datetime import datetime
from login_ui_style import set_bg

# ============================================================
# CONFIG
# ============================================================

IDLE_TIMEOUT = 300  # 5 minutes

BASE_DIR = Path(__file__).resolve().parent
USER_DIR = BASE_DIR / "User"
CRED_FILE = USER_DIR / "Credential.csv"
BG_IMAGE = USER_DIR / "background.png"

SESSION_FILE = "active_sessions.json"


# ============================================================
# SESSION STORE (SERVER SIDE)
# ============================================================

def load_sessions():
    if not os.path.exists(SESSION_FILE):
        return {}
    with open(SESSION_FILE, "r") as f:
        return json.load(f)


def save_sessions(data):
    with open(SESSION_FILE, "w") as f:
        json.dump(data, f)


def is_user_logged_in(username):
    return username in load_sessions()


def add_session(username, session_id):
    sessions = load_sessions()
    sessions[username] = {
        "session_id": session_id,
        "login_time": str(datetime.now())
    }
    save_sessions(sessions)


def remove_session(username):
    sessions = load_sessions()
    if username in sessions:
        del sessions[username]
        save_sessions(sessions)


# ============================================================
# IDLE HANDLING
# ============================================================

def update_activity():
    st.session_state["last_activity"] = time.time()


def check_idle_timeout():

    if "auth" not in st.session_state:
        return

    if "last_activity" not in st.session_state:
        st.session_state["last_activity"] = time.time()
        return

    elapsed = time.time() - st.session_state["last_activity"]

    if elapsed > IDLE_TIMEOUT:

        user = st.session_state.auth["username"]

        remove_session(user)

        st.session_state.clear()

        st.error("⏳ Session expired due to inactivity (5 min)")
        st.stop()


# ============================================================
# EXP PARSER
# ============================================================

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

def load_users_from_csv():

    os.makedirs(USER_DIR, exist_ok=True)

    if not os.path.exists(CRED_FILE):

        df = pd.DataFrame([{
            "UNAME": "admin",
            "PWD": "welcome123",
            "EXP": "12/31/2026 18:00",
            "ROLE": "admin",
            "ENABLED": "TRUE"
        }])

        df.to_csv(CRED_FILE, index=False)

    df = pd.read_csv(CRED_FILE, engine="python", encoding="utf-8-sig")
    df.columns = df.columns.str.upper().str.strip()

    df["ENABLED"] = df["ENABLED"].astype(str).str.upper().isin(["TRUE", "1", "YES"])

    return df


# ============================================================
# AUTH CHECK
# ============================================================

def authenticate(username, password, df):

    user = df[df["UNAME"] == username]

    if user.empty:
        return False, "Username not found"

    row = user.iloc[0]

    if not row["ENABLED"]:
        return False, "User disabled"

    if password != row["PWD"]:
        return False, "Incorrect password"

    expiry = parse_expiry(row["EXP"])

    if not expiry or datetime.now() > expiry:
        return False, "Account expired"

    return True, row


# ============================================================
# LOGIN SCREEN
# ============================================================

def login_screen():

    if "users_df" not in st.session_state:
        st.session_state.users_df = load_users_from_csv()

    df = st.session_state.users_df

    # ========================================================
    # LOGIN PAGE
    # ========================================================

    if "auth" not in st.session_state:

        set_bg(BG_IMAGE)

        st.markdown('<div class="login-wrapper">', unsafe_allow_html=True)
        st.markdown('<div class="login-title">🔐 Login</div>', unsafe_allow_html=True)

        st.markdown('<div class="custom-label">Username</div>', unsafe_allow_html=True)
        username = st.text_input("", key="user", label_visibility="collapsed")

        st.markdown('<div class="custom-label">Password</div>', unsafe_allow_html=True)
        password = st.text_input("", type="password", key="pass", label_visibility="collapsed")

        if st.button("Login"):

            ok, result = authenticate(username, password, df)

            if not ok:
                st.error(f"❌ {result}")
                st.stop()

            user = result["UNAME"]

            # ====================================================
            # MULTI LOGIN BLOCK
            # ====================================================

            if is_user_logged_in(user):
                st.error(
                    "❌ User already logged in on another device. "
                    "Please logout first."
                )
                st.stop()

            # ====================================================
            # CREATE SESSION
            # ====================================================

            session_id = str(uuid.uuid4())

            add_session(user, session_id)

            st.session_state.auth = {
                "username": user,
                "role": result["ROLE"],
                "expiry": result["EXP"],
                "session_id": session_id
            }

            st.session_state["last_activity"] = time.time()

            st.success("✅ Login successful")
            st.rerun()

        st.markdown("</div></div>", unsafe_allow_html=True)
        st.stop()

    # ========================================================
    # SESSION VALIDATION (NO REFRESH LOGOUT ISSUE FIXED)
    # ========================================================

    user = st.session_state.auth["username"]
    sid = st.session_state.auth["session_id"]

    sessions = load_sessions()

    if user not in sessions or sessions[user]["session_id"] != sid:

        st.session_state.clear()
        st.error("❌ Session expired or logged in elsewhere")
        st.stop()

    # ========================================================
    # IDLE CHECK (5 MIN AUTO LOGOUT)
    # ========================================================

    check_idle_timeout()

    update_activity()

    # ========================================================
    # EXPIRY CHECK
    # ========================================================

    expiry = parse_expiry(st.session_state.auth["expiry"])

    if not expiry or expiry < datetime.now():

        remove_session(user)
        st.session_state.clear()

        st.error("⏳ Session expired")
        st.stop()

    # ========================================================
    # SIDEBAR
    # ========================================================

    st.sidebar.success(f"👤 {user}")
    st.sidebar.info(f"🔒 Role: {st.session_state.auth['role']}")
    st.sidebar.warning(f"⏳ Expires: {st.session_state.auth['expiry']}")

    if st.sidebar.button("🚪 Logout"):

        remove_session(user)
        st.session_state.clear()
        st.rerun()

    # ========================================================
    # ADMIN PANEL
    # ========================================================

    if st.session_state.auth["role"] == "admin":
        st.sidebar.subheader("👥 Users")
        st.sidebar.dataframe(df[["UNAME", "ROLE", "EXP", "ENABLED"]], use_container_width=True)