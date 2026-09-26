# -*- coding: utf-8 -*-
"""
NIFTY OI BRAHMĀSTRA (FINAL SAAS VERSION WITH EXPIRY LOGIC)
Python 3.12 + Streamlit + FYERS API v3
"""

import json
import time
import requests
import hashlib
import webbrowser
from pathlib import Path
from datetime import datetime, timedelta
from collections import deque

import numpy as np
import pandas as pd
import streamlit as st

try:
    from fyers_apiv3 import fyersModel
except Exception as exc:
    fyersModel = None
    FYERS_IMPORT_ERROR = str(exc)

# ---------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------
st.set_page_config(page_title="NIFTY OI Brahmastra", page_icon="📊", layout="wide")

APP_DIR = Path.home() / ".fyers_streamlit_nifty"
APP_DIR.mkdir(parents=True, exist_ok=True)
TOKEN_FILE = APP_DIR / "token.json"

REDIRECT_URI = "https://nifty-bramhastra.streamlit.app/"
STATE = "nifty_oi_brahmastra"

# =====================================================================
# 👑 ADMIN SAAS CONFIGURATION (यहाँ अपनी डिटेल्स भरें)
# =====================================================================
ADMIN_EMAIL = "markam296@gmail.com"  # यहाँ अपना वह ईमेल डालें जिससे आप एडमिन बनेंगे
FYERS_APP_ID = "IDCN3BSFJ3-100" # यहाँ अपना FYERS APP ID डालें (जैसे: ABCD123-100)
FYERS_SECRET_KEY = "QSTYMRQY83" # यहाँ अपना FYERS Secret Key डालें


# =====================================================================
# 🔥 FIREBASE CONFIGURATION (AUTH & FIRESTORE)
# =====================================================================
FIREBASE_API_KEY = "AIzaSyARH5t0KeSfCAFXtJsVwZ4mQQPh1tiFQ10" 
PROJECT_ID = "nifty-brahmastra"  

INDEX_MAP = {
    "NIFTY 50": "NSE:NIFTY50-INDEX",
    "BANK NIFTY": "NSE:NIFTYBANK-INDEX",
    "FINNIFTY": "NSE:FINNIFTY-INDEX",
    "MIDCPNIFTY": "NSE:MIDCPNIFTY-INDEX",
}
TIME_WEIGHTS = {15: 0.50, 30: 0.30, 60: 0.20}

# 1. Authentication Functions
def sign_up_with_email_and_password(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    r = requests.post(url, json=payload)
    return r.json()

def sign_in_with_email_and_password(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    r = requests.post(url, json=payload)
    return r.json()

# 2. Firestore Database Functions (WITH EXPIRY LOGIC)
def format_email_for_db(email):
    return email.replace('@', '_at_').replace('.', '_dot_')

def update_subscription_in_db(email, plan_name, days_valid):
    doc_id = format_email_for_db(email)
    
    if days_valid == 0:
        has_sub = False
        expiry_date_str = ""
    else:
        has_sub = True
        expiry_date = datetime.now() + timedelta(days=days_valid)
        expiry_date_str = expiry_date.isoformat()
        
    url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/users/{doc_id}?key={FIREBASE_API_KEY}"
    payload = {
        "fields": {
            "email": {"stringValue": email},
            "has_subscription": {"booleanValue": has_sub},
            "plan_name": {"stringValue": plan_name},
            "expiry_date": {"stringValue": expiry_date_str}
        }
    }
    requests.patch(url, json=payload)

def check_subscription_from_db(email):
    doc_id = format_email_for_db(email)
    url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/users/{doc_id}?key={FIREBASE_API_KEY}"
    r = requests.get(url)
    
    if r.status_code == 200:
        data = r.json()
        fields = data.get("fields", {})
        has_sub = fields.get("has_subscription", {}).get("booleanValue", False)
        expiry_str = fields.get("expiry_date", {}).get("stringValue", "")
        
        if has_sub and expiry_str:
            try:
                expiry_date = datetime.fromisoformat(expiry_str)
                if datetime.now() > expiry_date:
                    update_subscription_in_db(email, "Expired", 0)
                    return False
                return True
            except:
                return False
    return False

# ---------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top:.7rem;padding-bottom:1rem}
.trend { border-radius:14px; padding:14px; text-align:center; font-size:25px; font-weight:800; margin-bottom:12px; }
.box { border:2px solid; border-radius:12px; padding:12px; min-height:95px; }
.entry {border-color:#16a34a;background:rgba(22,163,74,.08)}
.exit {border-color:#dc2626;background:rgba(220,38,38,.08)}
.big {font-size:25px;font-weight:800}
.muted {font-size:12px;color:#9ca3af}
.blinking-alert { padding: 15px; font-size: 20px; font-weight: bold; text-align: center; border-radius: 10px; border: 3px solid; animation: blinker 1.5s linear infinite; margin-bottom: 20px; }
@keyframes blinker { 50% { opacity: 0.6; } }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------
# SESSION STATE SETUP (For Login)
# ---------------------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "has_subscription" not in st.session_state:
    st.session_state.has_subscription = False

# =====================================================================
# PAGE 1: LOGIN & SIGNUP
# =====================================================================
def login_signup_page():
    st.title("🔐 NIFTY OI Brahmāstra - Login")
    st.write("सॉफ्टवेयर इस्तेमाल करने के लिए लॉग इन या साइन अप करें।")
    
    tab1, tab2 = st.tabs(["Log In", "Sign Up (नया अकाउंट)"])
    
    with tab1:
        st.subheader("लॉग इन करें")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pass")
        
        if st.button("Log In", use_container_width=True):
            if not email or not password:
                st.warning("ईमेल और पासवर्ड दोनों डालें।")
            else:
                with st.spinner("लॉग इन हो रहा है..."):
                    user = sign_in_with_email_and_password(email, password)
                    if "idToken" in user:
                        sub_status = check_subscription_from_db(email)
                        if email == ADMIN_EMAIL:
                            sub_status = True
                        
                        st.session_state.logged_in = True
                        st.session_state.user_email = email
                        st.session_state.has_subscription = sub_status
                        st.rerun()
                    else:
                        st.error("ईमेल या पासवर्ड गलत है!")

    with tab2:
        st.subheader("नया अकाउंट बनाएं")
        new_email = st.text_input("New Email", key="signup_email")
        new_password = st.text_input("New Password (कम से कम 6 अक्षर)", type="password", key="signup_pass")
        
        if st.button("Sign Up", use_container_width=True):
            if not new_email or len(new_password) < 6:
                st.warning("ईमेल सही डालें और पासवर्ड कम से कम 6 अक्षरों का रखें।")
            else:
                with st.spinner("अकाउंट बन रहा है..."):
                    user = sign_up_with_email_and_password(new_email, new_password)
                    if "idToken" in user:
                        update_subscription_in_db(new_email, "None", 0)
                        st.success("अकाउंट बन गया! अब आप 'Log In' टैब से लॉग इन कर सकते हैं।")
                    else:
                        st.error("यह ईमेल पहले से रजिस्टर्ड है या कोई एरर है!")

# =====================================================================
# PAGE 2: PRICING (PAYMENT GATEWAY)
# =====================================================================
def pricing_page():
    st.title("💎 सब्सक्रिप्शन प्लान चुनें")
    st.write(f"Welcome, **{st.session_state.user_email}**! सॉफ्टवेयर इस्तेमाल करने के लिए एक्टिव प्लान होना जरुरी है:")
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🥉 Monthly Plan")
        st.markdown("<h2>₹499 / month</h2>", unsafe_allow_html=True)
        st.write("✔️ Live Option Chain\n✔️ Advanced Proximity Alerts\n✔️ 15/30/60m OI Shift Data\n✔️ Delta & Theta Analysis")
        
        st.link_button("👉 Pay ₹499 (Monthly)", "https://rzp.io/rzp/DOV54Zg", use_container_width=True)
        
        st.caption("पेमेंट करने के बाद नीचे Verify बटन दबाएं:")
        if st.button("✅ मैंने पेमेंट कर दिया है (Verify)", use_container_width=True, key="verify_monthly"):
            with st.spinner("डेटाबेस अपडेट हो रहा है..."):
                update_subscription_in_db(st.session_state.user_email, "Monthly", 30)
                st.session_state.has_subscription = True
                time.sleep(1)
                st.success("Verification Successful! आपको 30 दिन का एक्सेस मिल गया है.")
                time.sleep(1)
                st.rerun()
            
    with col2:
        st.markdown("### 🥇 Yearly Plan")
        st.markdown("<h2>₹4999 / year</h2>", unsafe_allow_html=True)
        st.write("✔️ All Monthly Features\n✔️ 2 Months Free (Save ₹989)\n✔️ Priority Email Support\n✔️ VIP Updates")
        st.button("Pay ₹4999 (Coming Soon)", disabled=True, use_container_width=True)

    st.divider()
    if st.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.has_subscription = False
        st.rerun()

# =====================================================================
# PAGE 3: MAIN TRADING DASHBOARD
# =====================================================================
def main_trading_dashboard():
    # -- HELPERS --
    def sf(v, default=0.0):
        try: return float(v)
        except: return default

    def si(v, default=0):
        try: return int(float(v))
        except: return default

    def fmt_num(v):
        try:
            v = float(v)
            a = abs(v)
            if a >= 10_000_000: return f"{v/10_000_000:.2f} Cr"
            if a >= 100_000: return f"{v/100_000:.2f} L"
            if a >= 1_000: return f"{v/1_000:.1f} K"
            return f"{v:,.0f}"
        except: return "-"

    def fmt_price(v):
        try: return f"₹{float(v):,.2f}"
        except: return "-"

    def fmt_bar_value(v):
        try:
            v = float(v)
            sign = "-" if v < 0 else ""
            a = abs(v)
            if a >= 10_000_000: return f"{sign}{a / 10_000_000:.2f} Cr"
            if a >= 100_000: return f"{sign}{a / 100_000:.2f} L"
            if a >= 1_000: return f"{sign}{a / 1_000:.2f} K"
            return f"{v:,.0f}"
        except: return "-"

    def key_for(strike, typ):
        return f"{typ}:{float(strike):g}"

    def make_auth_url(client_id, secret_key):
        try:
            session = fyersModel.SessionModel(client_id=client_id.strip(), secret_key=secret_key.strip(), redirect_uri=REDIRECT_URI, response_type="code", grant_type="authorization_code", state=STATE)
            url = session.generate_authcode()
            if isinstance(url, str): return url, None
            return None, f"Unexpected URL: {url}"
        except Exception as exc: return None, str(exc)

    def exchange_auth_code(client_id, secret_key, auth_code):
        try:
            session = fyersModel.SessionModel(client_id=client_id.strip(), secret_key=secret_key.strip(), redirect_uri=REDIRECT_URI, response_type="code", grant_type="authorization_code", state=STATE)
            session.set_token(str(auth_code))
            result = session.generate_token()
            if isinstance(result, dict) and result.get("access_token"):
                return result.get("access_token"), None
            return None, f"Token error: {result}"
        except Exception as exc: return None, str(exc)

    def saved_token(client_id):
        if TOKEN_FILE.exists():
            try:
                data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
                if data.get("client_id") == client_id: return data.get("access_token")
            except:
                pass
        return None

    def save_token(client_id, token):
        TOKEN_FILE.write_text(json.dumps({"client_id": client_id, "access_token": token, "saved_at": datetime.now().isoformat()}, ensure_ascii=False), encoding="utf-8")

    # =====================================================================
    # SIDEBAR: SETTINGS (For Everyone) & FYERS ADMIN (For Admin Only)
    # =====================================================================
    with st.sidebar:
        st.header("⚙️ Dashboard Settings")
        index_name = st.selectbox("Index Select", list(INDEX_MAP.keys()))
        symbol = INDEX_MAP[index_name]
        strike_count = st.slider("ATM ± Strikes", 5, 25, 10)
        show_bar_oichange = st.checkbox("📌 OI Bar के साथ OI Change दिखाएँ", value=True)
        
        st.divider()
        
        # 👑 सिर्फ एडमिन को दिखेगा
        if st.session_state.user_email == ADMIN_EMAIL:
            st.header("👑 Admin Panel (FYERS API)")
            
            # Catch Auth Code from URL
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
                st.warning("मार्केट डेटा बंद है. लॉगिन करें:")
                auth_url, auth_err = make_auth_url(FYERS_APP_ID, FYERS_SECRET_KEY)
                if auth_url:
                    st.link_button("🔓 Open FYERS Login", auth_url, use_container_width=True)
                else:
                    st.error(f"FYERS Link Error: {auth_err}")  # यह लाइन आपको बताएगी कि बटन क्यों नहीं आ रहा
            else:
                st.success("🟢 FYERS Live Data Connected!")
                if st.button("🔌 Disconnect FYERS", use_container_width=True):
                    TOKEN_FILE.unlink(missing_ok=True)
                    st.rerun()
            st.divider()

        if st.button("🚪 Logout", use_container_width=True, key="dash_logout_sb"):
            st.session_state.logged_in = False
            st.session_state.has_subscription = False
            st.rerun()

    # =====================================================================
    # MAIN LOGIC - FETCH DATA FOR EVERYONE USING ADMIN'S TOKEN
    # =====================================================================
    access_token = saved_token(FYERS_APP_ID)
    if not access_token:
        st.title("📊 NIFTY OI BRAHMĀSTRA")
        st.warning("⚠️ लाइव मार्केट डेटा अभी कनेक्ट नहीं हुआ है। कृपया कुछ समय बाद दोबारा प्रयास करें या एडमिन से संपर्क करें।")
        st.stop()

    @st.cache_resource(show_spinner=False)
    def fyers_client(client_id, token):
        return fyersModel.FyersModel(client_id=client_id, token=token, is_async=False, log_path="")

    api = fyers_client(FYERS_APP_ID, access_token)

    def option_chain(api, symbol, strike_count):
        data = {"symbol": symbol, "strikecount": int(strike_count), "greeks": "1"}
        try: return api.optionchain(data=data)
        except TypeError:
            data["greeks"] = True
            return api.optionchain(data=data)
        except Exception as exc: return {"s": "error", "message": str(exc)}

    def history(api, symbol):
        now = int(time.time())
        data = {"symbol": symbol, "resolution": "1", "date_format": "0", "range_from": str(now - 3*60*60), "range_to": str(now), "cont_flag": "1"}
        try: return api.history(data=data)
        except Exception as exc: return {"s": "error", "message": str(exc)}

    def parse_chain(resp):
        if not isinstance(resp, dict) or str(resp.get("s", "")).lower() != "ok":
            return None, [], {}, f"Error: {resp}"
        data = resp.get("data", {})
        chain = data.get("optionsChain", [])
        spot = None; rows = []
        for x in chain:
            typ = str(x.get("option_type", "")).upper()
            if typ not in ("CE", "PE"):
                if x.get("ltp") is not None: spot = sf(x.get("ltp"))
                continue
            g = x.get("greeks") or {}
            rows.append({
                "strike": sf(x.get("strike_price")), "type": typ, "ltp": sf(x.get("ltp")), "oi": si(x.get("oi")),
                "oich": si(x.get("oich")), "oichp": sf(x.get("oichp")), "iv": sf(x.get("iv", g.get("iv"))),
                "delta": sf(g.get("delta")), "theta": sf(g.get("theta"))
            })
        vix = data.get("indiavixData") or {}
        meta = {"call_oi": si(data.get("callOi")), "put_oi": si(data.get("putOi")), "vix": sf(vix.get("ltp")), "vix_change_pct": sf(vix.get("ltchp", vix.get("ltpchp")))}
        return spot, rows, meta, None

    def make_df(rows):
        ce = {r["strike"]: r for r in rows if r["type"] == "CE"}
        pe = {r["strike"]: r for r in rows if r["type"] == "PE"}
        strikes = sorted(set(ce) | set(pe))
        res = []
        for s in strikes:
            c = ce.get(s, {}); p = pe.get(s, {})
            res.append({
                "strike": s, "ce_ltp": c.get("ltp", 0), "ce_oi": c.get("oi", 0), "ce_oich": c.get("oich", 0),
                "ce_oichp": c.get("oichp", 0), "ce_iv": c.get("iv", 0), "ce_delta": c.get("delta", 0), "ce_theta": c.get("theta", 0),
                "pe_theta": p.get("theta", 0), "pe_delta": p.get("delta", 0), "pe_iv": p.get("iv", 0), "pe_oichp": p.get("oichp", 0),
                "pe_oich": p.get("oich", 0), "pe_oi": p.get("oi", 0), "pe_ltp": p.get("ltp", 0)
            })
        return pd.DataFrame(res)

    def take_snapshot(rows): return {key_for(r["strike"], r["type"]): {"oi": r["oi"], "oich": r["oich"], "ltp": r["ltp"]} for r in rows}
    
    def add_snapshot(rows):
        now = time.time()
        if "oi_history" not in st.session_state: st.session_state.oi_history = deque(maxlen=7200)
        st.session_state.oi_history.append((now, take_snapshot(rows)))
        cutoff = now - 75 * 60
        while st.session_state.oi_history and st.session_state.oi_history[0][0] < cutoff: st.session_state.oi_history.popleft()
    
    def old_snapshot(minutes):
        target = time.time() - minutes * 60
        found = None
        for ts, snap in st.session_state.get("oi_history", deque()):
            if ts <= target: found = (ts, snap)
            else: break
        return found
    
    def shifts(rows, minutes):
        old = old_snapshot(minutes)
        if old is None: return {}, False
        _, prev = old
        res = {}
        for r in rows:
            k = key_for(r["strike"], r["type"]); p = prev.get(k, {})
            res[k] = {"oi_shift": r["oi"] - si(p.get("oi")), "oich_shift": r["oich"] - si(p.get("oich")), "ltp_shift": r["ltp"] - sf(p.get("ltp"))}
        return res, True
    
    def trend_data(rows):
        details = {}; weighted = 0.0; total_weight = 0.0
        for mins in (15, 30, 60):
            shift, ready = shifts(rows, mins)
            ce_oi = 0; pe_oi = 0; ce_oich = 0; pe_oich = 0
            if ready:
                for r in rows:
                    x = shift.get(key_for(r["strike"], r["type"]), {})
                    if r["type"] == "CE": ce_oi += x.get("oi_shift", 0); ce_oich += x.get("oich_shift", 0)
                    else: pe_oi += x.get("oi_shift", 0); pe_oich += x.get("oich_shift", 0)
                oi_den = max(abs(ce_oi) + abs(pe_oi), 1); ch_den = max(abs(ce_oich) + abs(pe_oich), 1)
                score = 0.65 * ((pe_oi - ce_oi)/oi_den) + 0.35 * ((pe_oich - ce_oich)/ch_den)
                w = TIME_WEIGHTS[mins]; weighted += w * score; total_weight += w
            else: score = 0
            details[mins] = {"ready": ready, "score": score, "ce_oi": ce_oi, "pe_oi": pe_oi}
        if total_weight == 0: return "LOADING", 0, details
        score = weighted / total_weight
        if score >= 0.18: return "BULLISH", score, details
        elif score <= -0.18: return "BEARISH", score, details
        return "SIDEWAYS", score, details

    def max_pain(df):
        if df.empty: return None
        strikes = sorted(df["strike"].unique())
        call = df.set_index("strike")["ce_oi"].to_dict()
        put = df.set_index("strike")["pe_oi"].to_dict()
        best = None; best_val = None
        for settle in strikes:
            val = sum(max(settle - k, 0) * call.get(k, 0) + max(k - settle, 0) * put.get(k, 0) for k in strikes)
            if best_val is None or val < best_val: best_val = val; best = settle
        return best

    def support_resistance(df, spot):
        if df.empty or spot is None: return None, None
        below = df[df["strike"] <= spot]; above = df[df["strike"] >= spot]
        sup = res = None
        if not below.empty:
            x = below.copy(); x["s"] = x["pe_oi"].clip(lower=0) + 0.5 * x["pe_oich"].clip(lower=0)
            sup = float(x.sort_values(["s", "strike"], ascending=[False, False]).iloc[0]["strike"])
        if not above.empty:
            x = above.copy(); x["s"] = x["ce_oi"].clip(lower=0) + 0.5 * x["ce_oich"].clip(lower=0)
            res = float(x.sort_values(["s", "strike"], ascending=[False, True]).iloc[0]["strike"])
        return sup, res

    def entry_exit(spot, sup, res, score):
        if spot is None: return None, None, "WAIT"
        if score >= 0.18: return sup or spot, res or spot, "BULLISH SETUP"
        elif score <= -0.18: return res or spot, sup or spot, "BEARISH SETUP"
        return sup or spot, res or spot, "RANGE / SIDEWAYS"

    # -- NATIVE STREAMLIT CHARTS --
    def candle_chart(history_response, spot):
        if not isinstance(history_response, dict) or str(history_response.get("s", "")).lower() != "ok": return
        candles = history_response.get("candles", [])
        if not candles: return
        data = []
        for c in candles[-120:]:
            if len(c) >= 5: data.append({"Time": datetime.fromtimestamp(c[0]).strftime("%H:%M"), "Open": sf(c[1]), "High": sf(c[2]), "Low": sf(c[3]), "Close": sf(c[4])})
        if not data: return
        st.line_chart(pd.DataFrame(data).set_index("Time")[["Open", "High", "Low", "Close"]], height=400)

    def double_bar(df, oi=True, spot=None, show_oi_change=False):
        if df.empty: return
        cols = ["strike", "ce_oi", "pe_oi", "ce_oich", "pe_oich"]
        temp = df[cols].copy()
        temp["total"] = temp["ce_oi"].abs() + temp["pe_oi"].abs()
        temp = temp.nlargest(min(15, len(temp)), "total").sort_values("strike")

        atm_strike = float(df["strike"].astype(float).iloc[(df["strike"].astype(float) - float(spot)).abs().argmin()]) if spot is not None else 0

        if oi:
            long_df = temp.melt(id_vars=["strike"], value_vars=["ce_oi", "pe_oi"], var_name="Side", value_name="Value")
            long_df["Side"] = long_df["Side"].map({"ce_oi": "CALL OI", "pe_oi": "PUT OI"})
            title = "CALL / PUT OI — Double Bar"
        else:
            long_df = temp.melt(id_vars=["strike"], value_vars=["ce_oich", "pe_oich"], var_name="Side", value_name="Value")
            long_df["Side"] = long_df["Side"].map({"ce_oich": "CALL OI Change", "pe_oich": "PUT OI Change"})
            title = "CALL / PUT OI Change — Double Bar"

        st.markdown(f"### {title}")
        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "width": "container", "height": 430,
            "transform": [
                {"calculate": ("abs(datum.Value) >= 10000000 ? format(datum.Value/10000000, '.2f') + ' Cr' : abs(datum.Value) >= 100000 ? format(datum.Value/100000, '.2f') + ' L' : abs(datum.Value) >= 1000 ? format(datum.Value/1000, '.2f') + ' K' : format(datum.Value, ',.0f')"), "as": "CompactValue"}
            ],
            "layer": [
                {
                    "transform": [
                        {"joinaggregate": [{"op": "max", "field": "Value", "as": "MaxVal"}, {"op": "min", "field": "Value", "as": "MinVal"}]},
                        {"calculate": "min(0, datum.MinVal)", "as": "ChartMin"}, {"calculate": "max(0, datum.MaxVal)", "as": "ChartMax"},
                        {"filter": "datum.Side == 'CALL OI' || datum.Side == 'CALL OI Change'"}
                    ],
                    "mark": {"type": "bar", "opacity": 0.12, "tooltip": False},
                    "encoding": {
                        "x": {"field": "strike", "type": "ordinal", "title": "Strike Price", "sort": "ascending"},
                        "y": {"field": "ChartMax", "type": "quantitative"}, "y2": {"field": "ChartMin"},
                        "color": {"condition": {"test": f"datum.strike <= {atm_strike}", "value": "#22c55e"}, "value": "#ef4444"}
                    }
                },
                {
                    "mark": {"type": "bar", "cornerRadiusTopLeft": 3, "cornerRadiusTopRight": 3},
                    "encoding": {
                        "x": {"field": "strike", "type": "ordinal", "title": "Strike Price", "sort": "ascending"},
                        "xOffset": {"field": "Side", "type": "nominal"},
                        "y": {"field": "Value", "type": "quantitative", "title": "Open Interest / OI Change"},
                        "color": {
                            "field": "Side", "type": "nominal",
                            "scale": {"domain": (["CALL OI", "PUT OI"] if oi else ["CALL OI Change", "PUT OI Change"]), "range": ["#22c55e", "#ef4444"]},
                            "legend": {"title": None, "orient": "top"}
                        },
                        "tooltip": [
                            {"field": "strike", "type": "quantitative", "title": "Strike", "format": ".0f"},
                            {"field": "Side", "type": "nominal", "title": "Type"},
                            {"field": "CompactValue", "type": "nominal", "title": "Value"}
                        ]
                    }
                }
            ]
        }
        st.vega_lite_chart(long_df, spec={**spec, "data": {"name": "source"}}, use_container_width=True)

        if spot is not None:
            s1, s2 = st.columns(2)
            s1.metric("🟢 LIVE ATM SPOT", fmt_price(spot))
            s2.metric("🟢 ATM STRIKE", f"{atm_strike:.0f}")

        if show_oi_change and oi:
            ch = temp.set_index("strike")[["ce_oich", "pe_oich"]].copy()
            ch.columns = ["CALL OI Change", "PUT OI Change"]
            st.caption("OI Change — K / L / Cr format:")
            ch_display = ch.copy()
            for col in ch_display.columns:
                ch_display[col] = ch_display[col].map(lambda x: ("+" if float(x) >= 0 else "") + fmt_bar_value(x))
            
            def style_mini_chain(row):
                styles = [''] * len(row)
                strike = float(row.name)
                for i, col in enumerate(row.index):
                    if 'CALL' in col and strike <= atm_strike: styles[i] = 'background-color: rgba(34, 197, 94, 0.15)'
                    elif 'PUT' in col and strike >= atm_strike: styles[i] = 'background-color: rgba(239, 68, 68, 0.15)'
                return styles
                
            st.dataframe(ch_display.style.apply(style_mini_chain, axis=1), use_container_width=True, height=min(360, 45 + len(ch_display) * 35))

    if "last_fetch" not in st.session_state: st.session_state.last_fetch = 0.0
    if "live_chain" not in st.session_state: st.session_state.live_chain = None
    if "live_history" not in st.session_state: st.session_state.live_history = None

    def dashboard():
        now = time.time()
        if now - st.session_state.last_fetch >= 0.9:
            try:
                resp = option_chain(api, symbol, strike_count)
                spot, rows, meta, err = parse_chain(resp)
                if not err:
                    st.session_state.live_chain = (spot, rows, meta)
                    st.session_state.live_history = history(api, symbol)
                    st.session_state.last_fetch = now
                    add_snapshot(rows)
            except Exception as e: pass

        st.title("📊 NIFTY OI BRAHMĀSTRA — LIVE")
        if not st.session_state.live_chain: st.info("डेटा लोड हो रहा है, कृपया प्रतीक्षा करें..."); return
        spot, rows, meta = st.session_state.live_chain
        df = make_df(rows)
        trend, score, details = trend_data(rows)
        support, resistance = support_resistance(df, spot)
        pain = max_pain(df)
        entry, exit_level, mode = entry_exit(spot, support, resistance, score)

        alert_html = ""
        if spot and support and resistance:
            if abs(spot - support) <= 15 and score >= -0.10:
                alert_html = f"<div class='blinking-alert' style='background-color:#dcfce7; color:#166534; border-color:#22c55e;'>🚀 BUY ALERT: Market Support ({support:.0f}) के करीब है! Entry: {support:.0f} | Target: {support+50:.0f} | SL: {support-20:.0f}</div>"
            elif abs(spot - resistance) <= 15 and score <= 0.10:
                alert_html = f"<div class='blinking-alert' style='background-color:#fee2e2; color:#991b1b; border-color:#ef4444;'>⚠️ SELL ALERT: Market Resistance ({resistance:.0f}) के करीब है! Entry: {resistance:.0f} | Target: {resistance-50:.0f} | SL: {resistance+20:.0f}</div>"
        if alert_html: st.markdown(alert_html, unsafe_allow_html=True)

        a, b, c, d, e = st.columns(5)
        a.metric("NIFTY Spot", fmt_price(spot))
        b.metric("CALL OI", fmt_num(meta["call_oi"]))
        c.metric("PUT OI", fmt_num(meta["put_oi"]))
        d.metric("PCR", f"{(meta['put_oi']/meta['call_oi'] if meta['call_oi'] else 0):.2f}")
        e.metric("MAX PAIN", f"{pain:.0f}" if pain else "-")

        bg = {"BULLISH": "#16a34a", "BEARISH": "#dc2626", "SIDEWAYS": "#eab308"}.get(trend, "#6b7280")
        st.markdown(f"<div class='trend' style='background:{bg};color:white'>TREND: {trend} | SCORE: {score:+.3f}</div>", unsafe_allow_html=True)

        c15, c30, c60 = st.columns(3)
        for col, mins in zip((c15, c30, c60), (15, 30, 60)):
            d = details[mins]
            with col:
                if d["ready"]: st.metric(f"⏱️ {mins}m Score", f"{d['score']:+.3f}")
                else: st.info(f"{mins}m history loading...")

        x1, x2, x3, x4 = st.columns(4)
        x1.markdown(f"<div class='box entry'><b>ENTRY LEVEL</b><div class='big'>{fmt_price(entry)}</div><div class='muted'>{mode}</div></div>", unsafe_allow_html=True)
        x2.markdown(f"<div class='box exit'><b>EXIT / TARGET</b><div class='big'>{fmt_price(exit_level)}</div><div class='muted'>Analytical Level</div></div>", unsafe_allow_html=True)
        x3.metric("SUPPORT", fmt_price(support))
        x4.metric("RESISTANCE", fmt_price(resistance))

        st.subheader("🕯️ High-Level Price Chart")
        candle_chart(st.session_state.live_history, spot)

        double_bar(df, oi=True, spot=spot, show_oi_change=show_bar_oichange)
        double_bar(df, oi=False, spot=spot, show_oi_change=True)

        st.subheader("🔗 LIVE OPTION CHAIN (DELTA & THETA)")
        atm_strike = float(df["strike"].iloc[(df["strike"] - spot).abs().argmin()])
        out = []
        for _, r in df.iterrows():
            s = float(r["strike"])
            label = f"🟢 {s:.0f}" if (support and abs(s-support)<0.1) else (f"🔴 {s:.0f}" if (resistance and abs(s-resistance)<0.1) else f"{s:.0f}")
            out.append({
                "CALL THETA": f"{r['ce_theta']:.2f}", "CALL DELTA": f"{r['ce_delta']:.2f}", "CALL IV": f"{r['ce_iv']:.1f}", "CALL LTP": f"{r['ce_ltp']:.2f}",
                "CALL OI": fmt_num(r["ce_oi"]), "CALL ΔOI": fmt_num(r["ce_oich"]), "STRIKE": label,
                "PUT ΔOI": fmt_num(r["pe_oich"]), "PUT OI": fmt_num(r["pe_oi"]),
                "PUT LTP": f"{r['pe_ltp']:.2f}", "PUT IV": f"{r['pe_iv']:.1f}", "PUT DELTA": f"{r['pe_delta']:.2f}", "PUT THETA": f"{r['pe_theta']:.2f}"
            })
        
        out_df = pd.DataFrame(out)
        def style_chain(row):
            styles = [''] * len(row)
            strike = df["strike"].iloc[row.name]
            for i, col in enumerate(row.index):
                if 'CALL' in col and strike <= atm_strike: styles[i] = 'background-color: rgba(34, 197, 94, 0.15)'
                elif 'PUT' in col and strike >= atm_strike: styles[i] = 'background-color: rgba(239, 68, 68, 0.15)'
            return styles
        st.dataframe(out_df.style.apply(style_chain, axis=1), use_container_width=True, hide_index=True)

    if hasattr(st, "fragment"):
        @st.fragment(run_every="1s")
        def live_fragment(): dashboard()
        live_fragment()
    else: dashboard()

# =====================================================================
# ROUTER LOGIC
# =====================================================================
if not st.session_state.logged_in:
    login_signup_page()
elif st.session_state.logged_in and not st.session_state.has_subscription:
    pricing_page()
elif st.session_state.logged_in and st.session_state.has_subscription:
    main_trading_dashboard()
