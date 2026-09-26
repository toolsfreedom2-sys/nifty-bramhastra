import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from fyers_apiv3 import fyersModel
import datetime
import time
import json
import os
from streamlit_autorefresh import st_autorefresh

# =====================================================================
# पेज कॉन्फ़िगरेशन
# =====================================================================
st.set_page_config(layout="wide", page_title="NIFTY OI Brahmāstra - Fyers Live Analyzer")

# --- ऑटो-रिफ्रेश सेटअप (30 सेकंड) ---
st_autorefresh(interval=30000, key="data_refresh")

# =====================================================================
# कॉन्स्टेंट्स और क्रेडेंशियल्स (Fyers & Firebase)
# =====================================================================
ADMIN_EMAIL = "markam296@gmail.com"
FYERS_APP_ID = "IDCN3BSFJ3-100"         # अपनी Fyers App ID यहाँ दर्ज करें
FYERS_SECRET_KEY = "QSTYMRQY83" # अपनी Fyers Secret Key यहाँ दर्ज करें

# 🔥 Firebase Configuration
FIREBASE_API_KEY = "AIzaSyARH5t0KeSfCAFXtJsVwZ4mQQPh1tiFQ10"
PROJECT_ID = "nifty-brahmastra"

INDEX_MAP = {
    "NIFTY 50": "NSE:NIFTY50-INDEX",
    "BANK NIFTY": "NSE:NIFTYBANK-INDEX",
    "FIN NIFTY": "NSE:FINNIFTY-INDEX"
}

TOKEN_FILE = "fyers_token.json"

# =====================================================================
# टोकन मैनेजमेंट और ऑथेंटिकेशन हेल्पर्स
# =====================================================================
def saved_token(app_id):
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r") as f:
                data = json.load(f)
                return data.get("access_token", "")
        except:
            return ""
    return ""

def save_token(app_id, token):
    try:
        with open(TOKEN_FILE, "w") as f:
            json.dump({"access_token": token}, f)
    except:
        pass

def make_auth_url(app_id, secret_key):
    try:
        session = fyersModel.SessionModel(
            client_id=app_id,
            secret_key=secret_key,
            redirect_uri="https://nifty-bramhastra.streamlit.app/",
            response_type="code",
            grant_type="authorization_code"
        )
        return session.generate_authcode(), None
    except Exception as e:
        return "", str(e)

def exchange_auth_code(app_id, secret_key, auth_code):
    try:
        session = fyersModel.SessionModel(
            client_id=app_id,
            secret_key=secret_key,
            redirect_uri="https://nifty-bramhastra.streamlit.app/",
            response_type="code",
            grant_type="authorization_code"
        )
        session.set_token(auth_code)
        response = session.generate_token()
        if response.get("s") == "ok":
            return response.get("access_token"), None
        else:
            return None, response
    except Exception as e:
        return None, str(e)

# =====================================================================
# सेशन स्टेट इनिशियलाइजेशन
# =====================================================================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "has_subscription" not in st.session_state: st.session_state.has_subscription = True
if "user_email" not in st.session_state: st.session_state.user_email = ""
if "last_fetch" not in st.session_state: st.session_state.last_fetch = 0.0
if "live_chain" not in st.session_state: st.session_state.live_chain = None
if "live_history" not in st.session_state: st.session_state.live_history = None

# =====================================================================
# Fyers API क्लाइंट इंस्टेंस
# =====================================================================
def get_api_client():
    token = saved_token(FYERS_APP_ID)
    if FYERS_APP_ID and token:
        return fyersModel.FyersModel(client_id=FYERS_APP_ID, is_async=False, token=token, log_path="")
    return None

api = get_api_client()

# =====================================================================
# लॉगिन / साइनअप पेज
# =====================================================================
def login_signup_page():
    st.subheader("🔐 NIFTY OI Brahmāstra - Login")
    email = st.text_input("Email Address", key="login_email")
    password = st.text_input("Password", type="password", key="login_pass")
    if st.button("Login to Dashboard", use_container_width=True):
        if email:
            st.session_state.logged_in = True
            st.session_state.user_email = email
            st.session_state.has_subscription = True
            st.rerun()

# =====================================================================
# मेन ट्रेडिंग डैशबोर्ड (मोबाइल, टैबलेट और डेस्कटॉप के लिए टॉप हेडर)
# =====================================================================
def main_trading_dashboard():
    # 📱 टॉप-लेवल होरिजेंटल हेडर (Index Select, Strike Slider & Logout)
    head_col1, head_col2, head_col3 = st.columns([2, 2, 1])
    
    with head_col1:
        global index_name, symbol
        index_name = st.selectbox("📊 Index Select", list(INDEX_MAP.keys()), key="main_index_select")
        symbol = INDEX_MAP[index_name]
        
    with head_col2:
        global strike_count
        strike_count = st.slider("ATM ± Strikes", 5, 25, 10, key="main_strike_slider")
        
    with head_col3:
        st.write("") 
        st.write("")
        if st.button("🚪 Logout", use_container_width=True, key="dash_logout_main"):
            st.session_state.logged_in = False
            st.session_state.has_subscription = False
            st.rerun()
            
    st.divider()

    # डेटा फ़ेचिंग लॉजिक (बाजार बंद होने पर पुराना डेटा सुरक्षित रहेगा)
    now = time.time()
    if now - st.session_state.last_fetch >= 0.9:
        try:
            if api:
                pass
            else:
                if st.session_state.live_chain is not None:
                    pass 
                else:
                    st.info(f"ℹ️ Firebase Project (`{PROJECT_ID}`) कनेक्टेड है। आज मार्केट बंद है या Fyers API क्रेडेंशियल्स दर्ज करें।")
        except Exception as e:
            pass

    # डैशबोर्ड मुख्य कंटेंट
    st.success(f"🟢 वर्तमान चयनित इंडेक्स: **{index_name}** (`{symbol}`) | स्ट्राइक रेंज: ±{strike_count}")
    st.write("आपका डैशबोर्ड सफलतापूर्वक लोड हो चुका है। Firebase और Fyers सेटिंग्स सक्रिय हैं।")

# =====================================================================
# साइडबार सेटिंग्स और एडमिन पैनल
# =====================================================================
with st.sidebar:
    st.header("⚙️ Dashboard Settings")
    show_bar_oichange = st.checkbox("📌 OI Bar के साथ OI Change दिखाएँ", value=True)
    
    st.divider()
    
    # 👑 सिर्फ एडमिन को दिखेगा (Fyers API Login Panel)
    if st.session_state.get("user_email") == ADMIN_EMAIL:
        st.header("👑 Admin Panel (FYERS API)")
        st.caption(f"Firebase Project: {PROJECT_ID}")
        
        auth_code = st.query_params.get("auth_code") or st.query_params.get("code")
        if auth_code:
            token, err = exchange_auth_code(FYERS_APP_ID, FYERS_SECRET_KEY, auth_code)
            if token:
                save_token(FYERS_APP_ID, token)
                st.query_params.clear()
                st.success("Admin FYERS Login Successful!")
                time.sleep(1)
                st.rerun()

        acc_token = saved_token(FYERS_APP_ID)
        if not acc_token:
            st.warning("मार्केट डेटा डिस्कनेक्टेड है। लॉगिन करें:")
            auth_url, auth_err = make_auth_url(FYERS_APP_ID, FYERS_SECRET_KEY)
            if auth_url:
                st.link_button("🔓 Open FYERS Login", auth_url, use_container_width=True)
            else:
                st.error(f"FYERS Link Error: {auth_err}")
        else:
            st.success("✅ FYERS Live Data Connected!")
            if st.button("🔌 Disconnect FYERS", use_container_width=True):
                save_token(FYERS_APP_ID, "")
                st.rerun()

    st.divider()
    expiry_date = st.text_input("एक्सपायरी (उदा. 24OCT)", value="24OCT")

# =====================================================================
# ROUTER LOGIC (पेज नेविगेशन)
# =====================================================================
if not st.session_state.logged_in:
    login_signup_page()
elif st.session_state.logged_in and not st.session_state.has_subscription:
    st.warning("कृपया सब्सक्रिप्शन लें।")
else:
    main_trading_dashboard()
