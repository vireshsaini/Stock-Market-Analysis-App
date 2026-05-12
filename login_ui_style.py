# ============================================================
# UI STYLES / BACKGROUND
# ============================================================

import streamlit as st
import base64


# ============================================================
# BACKGROUND FUNCTION
# ============================================================

def set_bg(image_file=None):

    # REMOVE BACKGROUND
    if image_file is None:

        st.markdown(
            """
            <style>

            .stApp {
                background: none !important;
            }

            </style>
            """,
            unsafe_allow_html=True
        )

    # APPLY BACKGROUND
    else:

        with open(image_file, "rb") as f:

            data = f.read()

        encoded = base64.b64encode(data).decode()

        st.markdown(
            f"""
            <style>

            /* ====================================================
               MAIN BACKGROUND
            ==================================================== */

            .stApp {{
                background-image: url("data:image/png;base64,{encoded}");
                background-size: cover;
                background-position: center;
                background-repeat: no-repeat;
            }}

            /* ====================================================
               DARK OVERLAY
            ==================================================== */

            .stApp::before {{
                content: "";
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0, 0, 0, 0.70);
                z-index: -1;
            }}

            /* ====================================================
               REMOVE STREAMLIT SPACING
            ==================================================== */

            .block-container {{
                padding-top: 0rem !important;
            }}

            header, footer {{
                visibility: hidden;
            }}

            /* ====================================================
               CENTER LOGIN WRAPPER
            ==================================================== */

            .login-wrapper {{
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: 100%;
                max-width: 320px;

                display: flex;
                flex-direction: column;

                z-index: 9999;
            }}

            /* ====================================================
               LOGIN CARD
            ==================================================== */

            .login-box {{

                background: rgba(10, 10, 10, 0.92);

                padding: 30px;

                border-radius: 14px;

                border: 1.5px solid rgba(31, 119, 255, 0.6);

                box-shadow:
                    0px 8px 25px rgba(0, 0, 0, 0.9),
                    0px 0px 15px rgba(31, 119, 255, 0.3);

                color: white;
            }}

            .login-box:hover {{

                transform: translateY(-4px);

                box-shadow:
                    0px 12px 35px rgba(0, 0, 0, 1),
                    0px 0px 20px rgba(31, 119, 255, 0.6);
            }}

            /* ====================================================
               TITLE
            ==================================================== */

            .login-title {{

                color: #1f77ff;

                font-size: 28px;

                font-weight: bold;

                margin-bottom: 2px;

                text-align: left;
            }}

            /* ====================================================
               DIVIDER
            ==================================================== */

            .login-divider {{

                height: 2px;

                width: 40px;

                background: #1f77ff;

                margin-bottom: 10px;
            }}

            /* ====================================================
               LABELS
            ==================================================== */

            .custom-label {{

                color: #1f77ff;

                font-size: 14px;

                font-weight: bold;

                margin-top: 8px;

                margin-bottom: 2px;
            }}

            /* ====================================================
               INPUT BOX
            ==================================================== */

            .stTextInput input {{

                background-color: rgba(0, 85, 255, 0.15) !important;

                color: blue !important;

                border: 1px solid #1f77ff !important;

                border-radius: 6px;

                padding: 6px;

                width: 100% !important;

                margin: 0 auto;
            }}

            /* FIX INPUT SPACING */

            div[data-baseweb="input"] {{
                margin-top: -4px;
            }}

            /* ====================================================
               BUTTON
            ==================================================== */

            .stButton button {{

                background: linear-gradient(
                    90deg,
                    #1f77ff,
                    #0056d2
                );

                color: white;

                border-radius: 6px;

                width: 100%;

                font-weight: bold;

                padding: 10px;

                margin-top: 12px;

                border: none;
            }}

            .stButton button:hover {{

                background: linear-gradient(
                    90deg,
                    #0056d2,
                    #003f9e
                );
            }}

            </style>
            """,
            unsafe_allow_html=True
        )
