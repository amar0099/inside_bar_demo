"""
Inside Bar Breakout Terminal — Nifty 15 Min
Single-file Streamlit app · Fyers API v3 · Streamlit Secrets
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, date, timedelta, time as dtime
from dataclasses import dataclass, field
from typing import Optional
import time


# ═══════════════════════════════════════════════════════════
#  PAGE CONFIG
# ═══════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Inside Bar Terminal",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.stApp { background: #ffffff; color: #1a1a2e; }
[data-testid="stSidebar"] { background: #f5f7fa !important; border-right: 1px solid #dde3ec; }

h1, h2, h3 { color: #0d1117 !important; font-family: 'IBM Plex Mono', monospace !important; }
h1 { font-size: 1.3rem !important; letter-spacing: 0.08em; }
h2 { font-size: 1.0rem !important; letter-spacing: 0.06em; color: #1a56db !important; }

[data-testid="stMetric"] { background:#f0f4fa; border:1px solid #d0daea; border-radius:4px; padding:12px 16px; }
[data-testid="stMetricLabel"] { color:#5a7a9a !important; font-size:0.7rem !important; letter-spacing:0.1em; text-transform:uppercase; font-family:'IBM Plex Mono',monospace; }
[data-testid="stMetricValue"] { color:#0d1117 !important; font-family:'IBM Plex Mono',monospace !important; font-size:1.4rem !important; }

.stButton > button { background:#e8f0fe !important; color:#1a56db !important; border:1px solid #c0d0f0 !important; border-radius:3px !important; font-family:'IBM Plex Mono',monospace !important; font-size:0.75rem !important; letter-spacing:0.08em !important; text-transform:uppercase !important; padding:6px 16px !important; transition:all 0.15s !important; }
.stButton > button:hover { background:#d0e2ff !important; border-color:#1a56db !important; color:#0d3bbf !important; }

.stSelectbox > div > div, .stNumberInput > div > div { background:#f5f7fa !important; border-color:#d0daea !important; color:#1a1a2e !important; font-family:'IBM Plex Mono',monospace !important; font-size:0.8rem !important; }
.stRadio label { color:#444e60 !important; font-size:0.8rem !important; }
hr { border-color:#dde3ec !important; }
.dataframe { background:#ffffff !important; font-family:'IBM Plex Mono',monospace !important; font-size:0.72rem !important; border:1px solid #dde3ec !important; }
.dataframe th { background:#f0f4fa !important; color:#5a7a9a !important; }
.dataframe td { color:#1a1a2e !important; border-color:#e0e8f0 !important; }

.section-label { font-family:'IBM Plex Mono',monospace; font-size:0.65rem; color:#7a9ab8; letter-spacing:0.15em; text-transform:uppercase; border-bottom:1px solid #dde3ec; padding-bottom:4px; margin-bottom:10px; margin-top:14px; }
.trade-card { background:#f8faff; border:1px solid #d0daea; border-left:3px solid #2a6090; padding:10px 14px; margin:6px 0; border-radius:3px; font-family:'IBM Plex Mono',monospace; font-size:0.75rem; color:#1a1a2e; }
.trade-card-win  { border-left-color:#3ddc84 !important; }
.trade-card-loss { border-left-color:#ff6b6b !important; }
.live-dot { display:inline-block; width:7px; height:7px; background:#3ddc84; border-radius:50%; margin-right:5px; animation:pulse 1.5s infinite; }
.sim-dot  { display:inline-block; width:7px; height:7px; background:#f0b840; border-radius:50%; margin-right:5px; }
@keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:0.3;} }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
#  CONSTANTS & TIME RULES
# ═══════════════════════════════════════════════════════════

NIFTY_SPOT_SYMBOL  = "NSE:NIFTY50-INDEX"
NIFTY_STRIKE_STEP  = 50
NO_ENTRY_AFTER     = dtime(15, 0)
FORCE_CLOSE_TIME   = dtime(15, 10)
MARKET_OPEN_TIME   = dtime(9, 15)
BREAKOUT_WINDOW    = 2   # candles


def is_first_candle(dt: pd.Timestamp) -> bool:
    return dt.time() == MARKET_OPEN_TIME

def can_enter(dt: pd.Timestamp) -> bool:
    return dt.time() <= NO_ENTRY_AFTER

def must_close(dt: pd.Timestamp) -> bool:
    return dt.time() >= FORCE_CLOSE_TIME


# ═══════════════════════════════════════════════════════════
#  FYERS AUTH — FULLY AUTOMATED (no manual token paste)
# ═══════════════════════════════════════════════════════════
#
#  Reads from .streamlit/secrets.toml  (local)
#  or Streamlit Cloud → Settings → Secrets:
#
#  [fyers]
#  client_id  = "XJ12345-100"
#  secret_key = "your_secret_key"
#  username   = "XJ12345"
#  pin        = "1234"
#  totp_key   = "XXXXXXXXXXXXX"   ← base32 key from Fyers 2FA setup
#
# ═══════════════════════════════════════════════════════════

def _generate_totp(totp_key: str) -> str:
    """Generate current 6-digit TOTP from base32 secret."""
    import hmac, hashlib, struct, base64
    key   = base64.b32decode(totp_key.upper().replace(" ", ""))
    ts    = int(time.time()) // 30
    msg   = struct.pack(">Q", ts)
    h     = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code  = struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % 1_000_000).zfill(6)


@st.cache_resource(ttl=3600)   # cache token for 1 hour; Fyers tokens are valid for the full day
def _get_access_token(client_id: str, secret_key: str,
                      username: str, pin: str, totp_key: str) -> str:
    """
    Full Fyers API v3 automated login flow:
      1. Generate auth URL
      2. POST login with username + TOTP
      3. POST verify PIN
      4. Extract auth_code from redirect URL
      5. Exchange auth_code for access_token
    Returns access_token string.
    """
    import requests, urllib.parse

    session_url   = "https://api-t2.fyers.in/vagator/v2"
    token_url     = "https://api-t1.fyers.in/api/v3/token"
    redirect_uri  = "https://trade.fyers.in/api-login/redirect-uri/index.html"

    # ── Step 1: send_login_otp (get request_key) ──────────
    r1 = requests.post(f"{session_url}/send_login_otp",
                       json={"fy_id": username, "app_id": "2"}, timeout=10)
    r1.raise_for_status()
    d1 = r1.json()
    if d1.get("s") != "ok":
        raise RuntimeError(f"send_login_otp failed: {d1}")
    request_key = d1["request_key"]

    # ── Step 2: verify_otp (TOTP) ─────────────────────────
    totp = _generate_totp(totp_key)
    r2   = requests.post(f"{session_url}/verify_otp",
                         json={"request_key": request_key, "otp": totp}, timeout=10)
    r2.raise_for_status()
    d2 = r2.json()
    if d2.get("s") != "ok":
        raise RuntimeError(f"verify_otp failed: {d2}")
    request_key2 = d2["request_key"]

    # ── Step 3: verify_pin ────────────────────────────────
    r3 = requests.post(f"{session_url}/verify_pin",
                       json={"request_key": request_key2,
                             "identity_type": "pin", "identifier": pin}, timeout=10)
    r3.raise_for_status()
    d3 = r3.json()
    if d3.get("s") != "ok":
        raise RuntimeError(f"verify_pin failed: {d3}")
    access_token_stage1 = d3["data"]["access_token"]

    # ── Step 4: get auth_code via token API ───────────────
    # app_id is the full client_id string e.g. "0Z0FI0BJS0-100"
    r4 = requests.post(token_url,
                       json={
                           "fyers_id":      username,
                           "app_id":        client_id.split("-")[0],
                           "redirect_uri":  redirect_uri,
                           "appType":       "100",
                           "code_challenge":"",
                           "state":         "None",
                           "scope":         "",
                           "nonce":         "",
                           "response_type": "code",
                           "create_cookie": "True",
                       },
                       headers={"Authorization": f"Bearer {access_token_stage1}"},
                       timeout=10)
    if not r4.ok:
        raise RuntimeError(f"auth_code step HTTP {r4.status_code}: {r4.text}")
    d4 = r4.json()
    if d4.get("s") != "ok":
        raise RuntimeError(f"auth_code step failed: {d4}")

    # data["auth"] IS the auth_code — pass directly to validate-authcode
    data4     = d4.get("data", {})
    auth_code = data4.get("auth", "")
    if not auth_code:
        raise RuntimeError(f"auth_code not found in data.auth. Full response: {d4}")

    # ── Step 5: exchange auth_code for access_token ───────
    import hashlib
    app_hash = hashlib.sha256(f"{client_id}:{secret_key}".encode()).hexdigest()
    r5 = requests.post("https://api-t1.fyers.in/api/v3/validate-authcode",
                       json={
                           "grant_type": "authorization_code",
                           "appIdHash":  app_hash,
                           "code":       auth_code,
                       }, timeout=10)
    if not r5.ok:
        raise RuntimeError(f"validate-authcode HTTP {r5.status_code}: {r5.text}")
    d5 = r5.json()
    if d5.get("s") != "ok":
        raise RuntimeError(f"validate-authcode failed: {d5}")

    return d5["access_token"]


def get_fyers_client():
    """
    Auto-login using hardcoded credentials (fallback to st.secrets if available).
    Token is cached for 1 hour (Fyers tokens are valid all day).
    """
    # ── Hardcoded credentials (override secrets if set) ──
    _HARDCODED = dict(
        client_id  = "CGWZXNCRYX-100",
        secret_key = "3RL83O1MT8",
        username   = "XA03074",
        pin        = "9518",
        totp_key   = "MM3N4EAJDKRHPNEPFQXJ74LBHYLR74NK",
    )
    try:
        from fyers_apiv3 import fyersModel
        # Try secrets first, fall back to hardcoded
        try:
            cfg = dict(st.secrets["fyers"])
        except Exception:
            cfg = _HARDCODED

        access_token = _get_access_token(
            client_id  = cfg["client_id"],
            secret_key = cfg["secret_key"],
            username   = cfg["username"],
            pin        = str(cfg["pin"]),
            totp_key   = cfg["totp_key"],
        )
        return fyersModel.FyersModel(
            client_id=cfg["client_id"],
            is_async=False,
            token=access_token,
            log_path=""
        )
    except ImportError:
        raise RuntimeError("fyers-apiv3 not installed. Add it to requirements.txt")


def fetch_ohlc_live(fyers, symbol: str, days_back: int = 3) -> pd.DataFrame:
    today     = date.today()
    from_date = today - timedelta(days=days_back * 2 + 5)
    resp = fyers.history({
        "symbol":     symbol,
        "resolution": "15",
        "date_format":"1",
        "range_from": from_date.strftime("%Y-%m-%d"),
        "range_to":   today.strftime("%Y-%m-%d"),
        "cont_flag":  "1",
    })
    if resp.get("s") != "ok":
        raise RuntimeError(f"Fyers history error for {symbol}: {resp}")

    df = pd.DataFrame(resp["candles"], columns=["ts","open","high","low","close","volume"])
    df["datetime"] = (
        pd.to_datetime(df["ts"], unit="s", utc=True)
        .dt.tz_convert("Asia/Kolkata")
        .dt.tz_localize(None)
    )
    df = df.drop(columns=["ts"]).sort_values("datetime").reset_index(drop=True)
    cutoff = pd.Timestamp(today - timedelta(days=days_back * 2))
    return df[df["datetime"] >= cutoff].reset_index(drop=True)


def fetch_ltp_live(fyers, symbol: str) -> float:
    resp = fyers.quotes({"symbols": symbol})
    if resp.get("s") != "ok":
        raise RuntimeError(f"LTP fetch failed for {symbol}: {resp}")
    return float(resp["d"][0]["v"]["lp"])


def get_next_thursday(from_date: date | None = None) -> date:
    if from_date is None:
        from_date = date.today()
    days_ahead = 3 - from_date.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return from_date + timedelta(days=days_ahead)


def round_to_strike(price: float, step: int = NIFTY_STRIKE_STEP) -> int:
    return int(round(price / step) * step)


def build_option_symbol(strike: int, opt_type: str, expiry: date) -> str:
    exp_str = expiry.strftime("%d%b%y").upper()
    return f"NSE:NIFTY{exp_str}{strike}{opt_type.upper()}"


def load_live_data() -> dict:
    """Fetch spot + ATM CE/PE from Fyers. Returns dict of DataFrames + meta."""
    fyers      = get_fyers_client()
    spot_df    = fetch_ohlc_live(fyers, NIFTY_SPOT_SYMBOL, days_back=3)
    ltp        = float(spot_df["close"].iloc[-1])
    atm_strike = round_to_strike(ltp)
    expiry     = get_next_thursday()
    ce_sym     = build_option_symbol(atm_strike, "CE", expiry)
    pe_sym     = build_option_symbol(atm_strike, "PE", expiry)

    ce_df = fetch_ohlc_live(fyers, ce_sym, days_back=3)
    pe_df = fetch_ohlc_live(fyers, pe_sym, days_back=3)

    return dict(spot_df=spot_df, ce_df=ce_df, pe_df=pe_df,
                ce_symbol=ce_sym, pe_symbol=pe_sym,
                atm_strike=atm_strike, expiry=expiry)


# ═══════════════════════════════════════════════════════════
#  SIMULATED DATA
# ═══════════════════════════════════════════════════════════

def generate_sim_nifty(days: int = 2, seed: int | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed if seed is not None else int(time.time()) % 9999)
    base = 22350.0
    records = []
    today = date.today()
    trading_days: list[date] = []
    d = today
    while len(trading_days) < days:
        if d.weekday() < 5:
            trading_days.append(d)
        d -= timedelta(days=1)
    trading_days = sorted(trading_days)

    for td in trading_days:
        start = datetime(td.year, td.month, td.day, 9, 15)
        for i in range(25):
            dt  = start + timedelta(minutes=15 * i)
            o   = base + rng.standard_normal() * 8
            h   = o + abs(rng.standard_normal() * 14)
            l   = o - abs(rng.standard_normal() * 14)
            c   = l + (h - l) * rng.uniform(0.2, 0.8)
            vol = int(rng.uniform(50_000, 200_000))
            records.append(dict(datetime=pd.Timestamp(dt),
                                open=round(o,2), high=round(h,2),
                                low=round(l,2),  close=round(c,2), volume=vol))
            base = c + rng.standard_normal() * 5

    return pd.DataFrame(records)


def generate_sim_option(spot_df: pd.DataFrame, strike: int, opt_type: str,
                        seed: int = 77) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df  = spot_df.copy()
    for col in ["open", "high", "low", "close"]:
        if opt_type.upper() == "CE":
            intrinsic = np.maximum(df[col].values - strike, 0)
        else:
            intrinsic = np.maximum(strike - df[col].values, 0)
        tv        = rng.uniform(40, 140, len(df))
        df[col]   = np.round(intrinsic + tv, 2)
    return df


def load_sim_data() -> dict:
    seed       = int(time.time()) % 9999
    spot_df    = generate_sim_nifty(days=2, seed=seed)
    ltp        = float(spot_df["close"].iloc[-1])
    atm_strike = round_to_strike(ltp)
    expiry     = get_next_thursday()
    ce_sym     = build_option_symbol(atm_strike, "CE", expiry)
    pe_sym     = build_option_symbol(atm_strike, "PE", expiry)
    ce_df      = generate_sim_option(spot_df, atm_strike, "CE", seed=seed + 1)
    pe_df      = generate_sim_option(spot_df, atm_strike, "PE", seed=seed + 2)

    return dict(spot_df=spot_df, ce_df=ce_df, pe_df=pe_df,
                ce_symbol=ce_sym, pe_symbol=pe_sym,
                atm_strike=atm_strike, expiry=expiry)


# ═══════════════════════════════════════════════════════════
#  STRATEGY — PATTERN DETECTION & SIGNALS
# ═══════════════════════════════════════════════════════════

@dataclass
class InsideBarSetup:
    mother_idx: int
    baby_idx:   int
    mother_high: float
    mother_low:  float
    baby_high:   float
    baby_low:    float
    timestamp:   pd.Timestamp


@dataclass
class TradeSignal:
    setup:             InsideBarSetup
    direction:         str       # 'LONG' | 'SHORT'
    entry_trigger:     float
    stop_loss:         float
    target:            float
    signal_candle_idx: int
    timestamp:         pd.Timestamp


def detect_inside_bar(df: pd.DataFrame) -> list[InsideBarSetup]:
    setups = []
    for i in range(1, len(df)):
        m = df.iloc[i - 1]
        b = df.iloc[i]
        if is_first_candle(m["datetime"]) or is_first_candle(b["datetime"]):
            continue
        if b["high"] < m["high"] and b["low"] > m["low"]:
            setups.append(InsideBarSetup(
                mother_idx=i - 1, baby_idx=i,
                mother_high=float(m["high"]), mother_low=float(m["low"]),
                baby_high=float(b["high"]),   baby_low=float(b["low"]),
                timestamp=b["datetime"],
            ))
    return setups


def generate_signals(df: pd.DataFrame,
                     setups: list[InsideBarSetup]) -> list[TradeSignal]:
    signals = []
    n = len(df)
    for setup in setups:
        for k in range(setup.baby_idx + 1,
                       min(setup.baby_idx + BREAKOUT_WINDOW + 1, n)):
            c = df.iloc[k]
            if not can_enter(c["datetime"]):
                break
            if c["high"] > setup.mother_high:
                entry = setup.mother_high
                sl    = setup.mother_low
                tgt   = entry + 2 * (entry - sl)
                signals.append(TradeSignal(setup, "LONG",  entry, sl, tgt, k, c["datetime"]))
                break
            elif c["low"] < setup.mother_low:
                entry = setup.mother_low
                sl    = setup.mother_high
                tgt   = entry - 2 * (sl - entry)
                signals.append(TradeSignal(setup, "SHORT", entry, sl, tgt, k, c["datetime"]))
                break
    return signals


def run_backtest(df: pd.DataFrame) -> pd.DataFrame:
    setups  = detect_inside_bar(df)
    signals = generate_signals(df, setups)
    trades  = []
    n       = len(df)

    for sig in signals:
        exit_price = exit_reason = exit_time = None
        for j in range(sig.signal_candle_idx + 1, n):
            c = df.iloc[j]
            if must_close(c["datetime"]):
                exit_price, exit_reason, exit_time = float(c["open"]), "TIME_EXIT", c["datetime"]
                break
            if sig.direction == "LONG":
                if c["low"] <= sig.stop_loss:
                    exit_price, exit_reason, exit_time = sig.stop_loss, "SL_HIT", c["datetime"]; break
                if c["high"] >= sig.target:
                    exit_price, exit_reason, exit_time = sig.target, "TARGET_HIT", c["datetime"]; break
            else:
                if c["high"] >= sig.stop_loss:
                    exit_price, exit_reason, exit_time = sig.stop_loss, "SL_HIT", c["datetime"]; break
                if c["low"] <= sig.target:
                    exit_price, exit_reason, exit_time = sig.target, "TARGET_HIT", c["datetime"]; break

        if exit_price is None:
            exit_price  = float(df.iloc[-1]["close"])
            exit_reason = "EOD"
            exit_time   = df.iloc[-1]["datetime"]

        ep  = sig.entry_trigger
        pnl = (exit_price - ep) if sig.direction == "LONG" else (ep - exit_price)
        trades.append(dict(
            entry_time=sig.timestamp,  exit_time=exit_time,
            direction=sig.direction,   entry_price=round(ep, 2),
            sl=round(sig.stop_loss, 2), target=round(sig.target, 2),
            exit_price=round(exit_price, 2), exit_reason=exit_reason,
            pnl_pts=round(pnl, 2),
            mother_high=sig.setup.mother_high, mother_low=sig.setup.mother_low,
        ))
    return pd.DataFrame(trades)


# ═══════════════════════════════════════════════════════════
#  DEMO TRADE ENGINE
# ═══════════════════════════════════════════════════════════

class TradeState:
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


@dataclass
class LiveTrade:
    signal:      TradeSignal
    state:       str   = TradeState.ACTIVE
    entry_price: float = 0.0
    entry_time:  Optional[pd.Timestamp] = None
    exit_price:  Optional[float]        = None
    exit_time:   Optional[pd.Timestamp] = None
    exit_reason: Optional[str]          = None
    pnl_pts:     Optional[float]        = None
    instrument:  str   = "SPOT"


@dataclass
class DemoEngine:
    active_trades: list = field(default_factory=list)
    closed_trades: list = field(default_factory=list)

    def reset(self):
        self.active_trades = []
        self.closed_trades = []

    def add_signal(self, signal: TradeSignal, instrument: str = "SPOT"):
        t = LiveTrade(signal=signal, state=TradeState.ACTIVE,
                      entry_price=signal.entry_trigger,
                      entry_time=signal.timestamp, instrument=instrument)
        self.active_trades.append(t)

    def update(self, candle: pd.Series):
        done = []
        for t in self.active_trades:
            sig  = t.signal
            c_hi = float(candle["high"])
            c_lo = float(candle["low"])
            ct   = candle["datetime"]
            if must_close(ct):
                self._close(t, float(candle["open"]), ct, "TIME_EXIT"); done.append(t); continue
            if sig.direction == "LONG":
                if c_lo <= sig.stop_loss:
                    self._close(t, sig.stop_loss, ct, "SL_HIT");    done.append(t)
                elif c_hi >= sig.target:
                    self._close(t, sig.target,    ct, "TARGET_HIT"); done.append(t)
            else:
                if c_hi >= sig.stop_loss:
                    self._close(t, sig.stop_loss, ct, "SL_HIT");    done.append(t)
                elif c_lo <= sig.target:
                    self._close(t, sig.target,    ct, "TARGET_HIT"); done.append(t)
        for t in done:
            self.active_trades.remove(t)
            self.closed_trades.append(t)

    def _close(self, t: LiveTrade, price: float, ts: pd.Timestamp, reason: str):
        t.exit_price  = price
        t.exit_time   = ts
        t.exit_reason = reason
        t.state       = TradeState.CLOSED
        ep = t.entry_price
        t.pnl_pts = round((price - ep) if t.signal.direction == "LONG"
                          else (ep - price), 2)

    def summary(self) -> dict:
        c = self.closed_trades
        if not c:
            return dict(total=0, wins=0, losses=0, net_pnl=0.0, win_rate=0.0)
        wins = [t for t in c if (t.pnl_pts or 0) > 0]
        net  = sum(t.pnl_pts or 0 for t in c)
        return dict(total=len(c), wins=len(wins), losses=len(c)-len(wins),
                    net_pnl=round(net, 2),
                    win_rate=round(len(wins) / len(c) * 100, 1))


# ═══════════════════════════════════════════════════════════
#  SESSION STATE INIT
# ═══════════════════════════════════════════════════════════

_defaults: dict = dict(
    spot_df=None, ce_df=None, pe_df=None,
    ce_symbol=None, pe_symbol=None, atm_strike=None, expiry=None,
    setups=[], signals=[],
    engine_spot=DemoEngine(), engine_ce=DemoEngine(), engine_pe=DemoEngine(),
    backtest_df=None, candle_cursor=2,
    log_msgs=[], demo_mode=True,
)
for _k, _v in _defaults.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ═══════════════════════════════════════════════════════════
#  UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════

def log(msg: str, level: str = "INFO"):
    icons = dict(INFO="ℹ", SIGNAL="⚡", TRADE="🔄", EXIT="✅", ERROR="❌")
    ts    = datetime.now().strftime("%H:%M:%S")
    st.session_state.log_msgs.insert(0, f"[{ts}] {icons.get(level,'·')} {msg}")
    st.session_state.log_msgs = st.session_state.log_msgs[:80]


def _apply_data(data: dict):
    for k, v in data.items():
        st.session_state[k] = v
    df = st.session_state.spot_df
    st.session_state.setups  = detect_inside_bar(df)
    st.session_state.signals = generate_signals(df, st.session_state.setups)
    st.session_state.candle_cursor = 2
    _reset_engines()


def _reset_engines():
    st.session_state.engine_spot = DemoEngine()
    st.session_state.engine_ce   = DemoEngine()
    st.session_state.engine_pe   = DemoEngine()
    st.session_state.candle_cursor = 2


def step_sim(n: int = 1):
    df     = st.session_state.spot_df
    ce_df  = st.session_state.ce_df
    pe_df  = st.session_state.pe_df
    if df is None:
        return
    cursor = st.session_state.candle_cursor
    end    = min(cursor + n, len(df))

    for i in range(cursor, end):
        candle = df.iloc[i]
        st.session_state.engine_spot.update(candle)
        if ce_df is not None and i < len(ce_df):
            st.session_state.engine_ce.update(ce_df.iloc[i])
        if pe_df is not None and i < len(pe_df):
            st.session_state.engine_pe.update(pe_df.iloc[i])

        for sig in st.session_state.signals:
            if sig.signal_candle_idx == i:
                st.session_state.engine_spot.add_signal(sig, "SPOT")
                if ce_df is not None and sig.direction == "LONG":
                    st.session_state.engine_ce.add_signal(sig, "CE")
                if pe_df is not None and sig.direction == "SHORT":
                    st.session_state.engine_pe.add_signal(sig, "PE")
                log(f"{sig.direction} @ {candle['datetime'].strftime('%H:%M')} "
                    f"entry={sig.entry_trigger:.2f} SL={sig.stop_loss:.2f} TGT={sig.target:.2f}",
                    "SIGNAL")

    st.session_state.candle_cursor = end


# ═══════════════════════════════════════════════════════════
#  CHART BUILDERS
# ═══════════════════════════════════════════════════════════

def build_ohlc_chart(df: pd.DataFrame, setups: list[InsideBarSetup],
                     signals: list[TradeSignal], title: str,
                     cursor: int) -> go.Figure:
    ddf = df.iloc[:cursor]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.78, 0.22], vertical_spacing=0.03)

    fig.add_trace(go.Candlestick(
        x=ddf["datetime"], open=ddf["open"], high=ddf["high"],
        low=ddf["low"],    close=ddf["close"], name="OHLC",
        increasing=dict(line=dict(color="#3ddc84", width=1), fillcolor="#3ddc84"),
        decreasing=dict(line=dict(color="#ff6b6b", width=1), fillcolor="#ff6b6b"),
    ), row=1, col=1)

    vol_colors = ["#3ddc84" if ddf["close"].iloc[i] >= ddf["open"].iloc[i]
                  else "#ff6b6b" for i in range(len(ddf))]
    fig.add_trace(go.Bar(x=ddf["datetime"], y=ddf["volume"],
                         marker_color=vol_colors, showlegend=False), row=2, col=1)

    # Pattern overlays
    for s in setups:
        if s.baby_idx >= cursor or s.mother_idx >= cursor:
            continue
        fig.add_shape(type="rect",
            x0=df.iloc[s.mother_idx]["datetime"], x1=df.iloc[s.baby_idx]["datetime"],
            y0=s.mother_low, y1=s.mother_high,
            fillcolor="rgba(126,184,247,0.05)", line=dict(color="#2a4a6a", width=1, dash="dot"),
            row=1, col=1)
        fig.add_trace(go.Scatter(
            x=[df.iloc[s.baby_idx]["datetime"]],
            y=[(s.mother_high + s.mother_low) / 2],
            mode="markers",
            marker=dict(symbol="diamond", size=7, color="#7eb8f7", opacity=0.7),
            showlegend=False,
        ), row=1, col=1)

    # Signal arrows + SL/TGT lines
    for sig in signals:
        if sig.signal_candle_idx >= cursor:
            continue
        clr  = "#3ddc84" if sig.direction == "LONG" else "#ff6b6b"
        sym  = "triangle-up" if sig.direction == "LONG" else "triangle-down"
        ypos = sig.entry_trigger - 6 if sig.direction == "LONG" else sig.entry_trigger + 6
        fig.add_trace(go.Scatter(
            x=[df.iloc[sig.signal_candle_idx]["datetime"]], y=[ypos],
            mode="markers+text",
            marker=dict(symbol=sym, size=13, color=clr),
            text=[sig.direction], textposition="bottom center" if sig.direction == "LONG" else "top center",
            textfont=dict(size=9, color=clr, family="IBM Plex Mono"),
            showlegend=False,
        ), row=1, col=1)
        fig.add_hline(y=sig.stop_loss, line=dict(color="#ff6b6b", width=1, dash="dash"),
                      annotation_text=f"SL {sig.stop_loss:.0f}",
                      annotation_font=dict(size=9, color="#ff6b6b"), row=1, col=1)
        fig.add_hline(y=sig.target, line=dict(color="#3ddc84", width=1, dash="dash"),
                      annotation_text=f"TGT {sig.target:.0f}",
                      annotation_font=dict(size=9, color="#3ddc84"), row=1, col=1)

    fig.update_layout(
        title=dict(text=title, font=dict(family="IBM Plex Mono", size=11, color="#5a7a9a")),
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        font=dict(family="IBM Plex Mono", color="#5a7a9a", size=10),
        xaxis_rangeslider_visible=False, showlegend=False,
        margin=dict(l=10, r=90, t=36, b=10), height=490,
    )
    for ax in [fig.layout.xaxis, fig.layout.xaxis2,
               fig.layout.yaxis, fig.layout.yaxis2]:
        ax.gridcolor = "#e8edf5"
        ax.linecolor = "#dde3ec"
        if hasattr(ax, "tickfont"):
            ax.tickfont = dict(family="IBM Plex Mono", size=9, color="#5a7a9a")
    return fig


def build_pnl_chart(closed: list[LiveTrade]) -> go.Figure | None:
    if not closed:
        return None
    pnls = [t.pnl_pts or 0 for t in closed]
    cum  = list(np.cumsum(pnls))
    clrs = ["#3ddc84" if p >= 0 else "#ff6b6b" for p in pnls]
    fig  = go.Figure()
    fig.add_trace(go.Bar(x=list(range(len(pnls))), y=pnls, marker_color=clrs,
                         name="Trade P&L", text=[f"{p:+.1f}" for p in pnls],
                         textposition="outside",
                         textfont=dict(size=9, family="IBM Plex Mono", color="#1a1a2e")))
    fig.add_trace(go.Scatter(x=list(range(len(cum))), y=cum, mode="lines",
                             name="Cumulative", line=dict(color="#1a56db", width=2)))
    fig.update_layout(plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
                      font=dict(family="IBM Plex Mono", color="#5a7a9a", size=10),
                      height=230, margin=dict(l=10, r=10, t=10, b=30),
                      legend=dict(font=dict(size=9), bgcolor="#f5f7fa", bordercolor="#dde3ec"))
    fig.update_xaxes(gridcolor="#e8edf5")
    fig.update_yaxes(gridcolor="#e8edf5", ticksuffix=" pts")
    return fig


# ═══════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown('<div style="font-family:IBM Plex Mono;font-size:0.65rem;color:#7a9ab8;'
                'letter-spacing:0.2em;text-transform:uppercase;padding:4px 0 14px 0;">'
                '▣ INSIDE BAR TERMINAL</div>', unsafe_allow_html=True)

    src = st.radio("Data Source", ["📊 Simulated Demo", "🔴 Live (Fyers API)"], index=0)
    is_demo = "Simulated" in src
    st.session_state.demo_mode = is_demo

    st.markdown('<div class="section-label">Data Controls</div>', unsafe_allow_html=True)

    if is_demo:
        if st.button("⟳  Load / Refresh Data", use_container_width=True):
            with st.spinner("Generating simulated data…"):
                _apply_data(load_sim_data())
            log("Simulated data loaded.", "INFO")
            st.rerun()
    else:
        st.markdown(
            '<div style="font-family:IBM Plex Mono;font-size:0.67rem;color:#4a6a8a;'
            'line-height:1.85;margin-bottom:8px;">'
            'Auto-login via secrets — no token paste needed.<br>'
            '<span style="color:#9ab8d0">─────────────────────</span><br>'
            '<b style="color:#1a1a2e">[fyers]</b><br>'
            'client_id &nbsp;= "XJ12345-100"<br>'
            'secret_key = "your_secret_key"<br>'
            'username &nbsp;= "XJ12345"<br>'
            'pin &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;= "1234"<br>'
            'totp_key &nbsp;= "BASE32SECRET"<br>'
            '<span style="color:#9ab8d0">─────────────────────</span><br>'
            '<span style="color:#5a7a9a;font-size:0.63rem;">'
            'totp_key = base32 key from<br>'
            'Fyers 2FA setup page</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        if st.button("🔌  Connect & Load Live", use_container_width=True):
            with st.spinner("Connecting to Fyers API…"):
                try:
                    _apply_data(load_live_data())
                    log("Live data loaded from Fyers.", "INFO")
                    st.success("Connected!")
                except Exception as e:
                    st.error(str(e))
                    log(str(e), "ERROR")
            st.rerun()

    st.markdown('<div class="section-label">Strategy Rules</div>', unsafe_allow_html=True)
    st.markdown(
        '<div style="font-family:IBM Plex Mono;font-size:0.68rem;color:#4a6a8a;line-height:1.9;">'
        'TF &nbsp;&nbsp;: 15 min<br>'
        'ENTRY : Break of Mother H/L<br>'
        'WIN &nbsp;: Breakout ≤ 2 candles<br>'
        'SL &nbsp;&nbsp;: Mother Low / High<br>'
        'TGT &nbsp;: 1:2 RR (100% exit)<br>'
        'CUT &nbsp;: No entry after 15:00<br>'
        'EXIT : Force close @ 15:10'
        '</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.atm_strike:
        st.markdown('<div class="section-label">Loaded Instruments</div>', unsafe_allow_html=True)
        exp_str = st.session_state.expiry.strftime("%d %b %y") if st.session_state.expiry else "—"
        st.markdown(
            f'<div style="font-family:IBM Plex Mono;font-size:0.7rem;color:#1a1a2e;line-height:2.1;">'
            f'NIFTY 50 SPOT<br>'
            f'<span style="color:#3ddc84">ATM CE &nbsp;{st.session_state.atm_strike}</span><br>'
            f'<span style="color:#ff6b6b">ATM PE &nbsp;{st.session_state.atm_strike}</span><br>'
            f'<span style="color:#5a7a9a">Expiry : {exp_str}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-label">Actions</div>', unsafe_allow_html=True)
    if st.button("📋  Run Full Backtest", use_container_width=True):
        df = st.session_state.spot_df
        if df is not None:
            st.session_state.backtest_df = run_backtest(df)
            log(f"Backtest: {len(st.session_state.backtest_df)} trades.", "INFO")
            st.rerun()
    if st.button("⟳  Reset Demo Engine", use_container_width=True):
        _reset_engines()
        log("Demo engine reset.", "INFO")
        st.rerun()


# ═══════════════════════════════════════════════════════════
#  MAIN — HEADER
# ═══════════════════════════════════════════════════════════

dot   = '<span class="sim-dot"></span>' if st.session_state.demo_mode else '<span class="live-dot"></span>'
label = "SIMULATED" if st.session_state.demo_mode else "LIVE"
st.markdown(
    f'<div style="font-family:IBM Plex Mono;font-size:1.1rem;color:#0d1117;'
    f'font-weight:600;padding:4px 0 10px 0;">'
    f'{dot} NIFTY &nbsp;'
    f'<span style="color:#5a7a9a;font-size:0.85rem;font-weight:400;">'
    f'INSIDE BAR BREAKOUT &nbsp;·&nbsp; 15 MIN &nbsp;·&nbsp; {label}</span></div>',
    unsafe_allow_html=True,
)

# ── Metric strip ──────────────────────────────────────────
df_s = st.session_state.spot_df
if df_s is not None:
    ltp   = float(df_s["close"].iloc[-1])
    prev  = float(df_s["close"].iloc[-2]) if len(df_s) > 1 else ltp
    chg   = ltp - prev
    sm    = st.session_state.engine_spot.summary()
    m1,m2,m3,m4,m5,m6 = st.columns(6)
    m1.metric("NIFTY LTP",    f"{ltp:,.2f}", f"{chg:+.2f}")
    m2.metric("Patterns",     str(len(st.session_state.setups)))
    m3.metric("Signals",      str(len(st.session_state.signals)))
    m4.metric("Trades Closed",str(sm["total"]))
    m5.metric("Win Rate",     f"{sm['win_rate']}%")
    m6.metric("Net P&L (pts)",f"{sm['net_pnl']:+.2f}")
    st.markdown("---")

# ═══════════════════════════════════════════════════════════
#  TABS
# ═══════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs(["📈  Chart & Demo", "📋  Trade Log", "🔍  Backtest", "📟  Log"])

# ── TAB 1 : CHART & DEMO ─────────────────────────────────
with tab1:
    if df_s is None:
        st.markdown(
            '<div style="text-align:center;padding:70px 0;color:#7a9ab8;font-family:IBM Plex Mono;">'
            '<div style="font-size:2rem;margin-bottom:14px;">◫</div>'
            '<div style="font-size:0.9rem;letter-spacing:0.1em;">NO DATA LOADED</div>'
            '<div style="font-size:0.75rem;margin-top:8px;color:#9ab8d0;">'
            'Use sidebar → Load / Refresh Data</div></div>',
            unsafe_allow_html=True,
        )
    else:
        cursor = st.session_state.candle_cursor
        total  = len(df_s)

        # Controls
        cc1,cc2,cc3,cc4,cc5 = st.columns([1,1,1,1,4])
        with cc1:
            if st.button("▶ +1"):   step_sim(1);     st.rerun()
        with cc2:
            if st.button("▶▶ +5"):  step_sim(5);     st.rerun()
        with cc3:
            if st.button("⏩ All"):  step_sim(total); st.rerun()
        with cc4:
            if st.button("⏮ Reset"):
                _reset_engines(); st.rerun()
        with cc5:
            cur_t = df_s.iloc[min(cursor-1, total-1)]["datetime"].strftime("%d %b  %H:%M") if cursor > 0 else "—"
            st.markdown(
                f'<div style="font-family:IBM Plex Mono;font-size:0.7rem;color:#7a9ab8;padding-top:8px;">'
                f'Candle {cursor}/{total} &nbsp;·&nbsp; {cur_t} &nbsp;·&nbsp;'
                f' Active: {len(st.session_state.engine_spot.active_trades)}</div>',
                unsafe_allow_html=True,
            )

        inst = st.selectbox("Chart", ["SPOT", "ATM CE", "ATM PE"],
                            label_visibility="collapsed")
        chart_map = {
            "SPOT":   (df_s, f"NIFTY 50 SPOT — 15 MIN"),
            "ATM CE": (df_s if st.session_state.ce_df is None else st.session_state.ce_df,
                       f"NIFTY {st.session_state.atm_strike} CE — 15 MIN"),
            "ATM PE": (df_s if st.session_state.pe_df is None else st.session_state.pe_df,
                       f"NIFTY {st.session_state.atm_strike} PE — 15 MIN"),
        }
        c_df, c_title = chart_map[inst]

        fig = build_ohlc_chart(c_df, st.session_state.setups,
                               st.session_state.signals, c_title, cursor)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # Active trades
        active = st.session_state.engine_spot.active_trades
        if active:
            st.markdown('<div class="section-label">Active Positions</div>', unsafe_allow_html=True)
            curr = float(c_df.iloc[min(cursor-1, len(c_df)-1)]["close"])
            for t in active:
                unreal = (curr - t.entry_price) if t.signal.direction == "LONG" else (t.entry_price - curr)
                cc = "trade-card-win" if unreal >= 0 else "trade-card-loss"
                dir_badge = "long" if t.signal.direction == "LONG" else "short"
                st.markdown(
                    f'<div class="trade-card {cc}">'
                    f'<span style="color:#1a56db">{t.instrument}</span> &nbsp;'
                    f'<span style="background:{"#0d3320" if dir_badge=="long" else "#330d0d"};'
                    f'color:{"#3ddc84" if dir_badge=="long" else "#ff6b6b"};'
                    f'padding:2px 8px;border-radius:2px;font-size:0.7rem;">{t.signal.direction}</span> &nbsp;'
                    f'Entry <b>{t.entry_price:.2f}</b> &nbsp;'
                    f'SL <span style="color:#ff6b6b">{t.signal.stop_loss:.2f}</span> &nbsp;'
                    f'TGT <span style="color:#3ddc84">{t.signal.target:.2f}</span> &nbsp;'
                    f'LTP <b>{curr:.2f}</b> &nbsp;'
                    f'Unreal <b style="color:{"#3ddc84" if unreal>=0 else "#ff6b6b"}">{unreal:+.2f}</b>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

# ── TAB 2 : TRADE LOG ────────────────────────────────────
with tab2:
    engines = [("SPOT", st.session_state.engine_spot),
               ("CE",   st.session_state.engine_ce),
               ("PE",   st.session_state.engine_pe)]
    any_trades = False
    for inst_name, eng in engines:
        if not eng.closed_trades:
            continue
        any_trades = True
        st.markdown(f'<div class="section-label">{inst_name} — {len(eng.closed_trades)} trades</div>',
                    unsafe_allow_html=True)
        for t in reversed(eng.closed_trades):
            pnl = t.pnl_pts or 0
            cc  = "trade-card-win" if pnl >= 0 else "trade-card-loss"
            rc  = {"TARGET_HIT":"#3ddc84","SL_HIT":"#ff6b6b","TIME_EXIT":"#f0b840"}.get(t.exit_reason,"#7eb8f7")
            st.markdown(
                f'<div class="trade-card {cc}">'
                f'<span style="background:{"#0d3320" if t.signal.direction=="LONG" else "#330d0d"};'
                f'color:{"#3ddc84" if t.signal.direction=="LONG" else "#ff6b6b"};'
                f'padding:2px 8px;border-radius:2px;font-size:0.7rem;">{t.signal.direction}</span> &nbsp;'
                f'Entry <b>{t.entry_price:.2f}</b>'
                f' @ {t.entry_time.strftime("%H:%M") if t.entry_time else "—"} →'
                f' Exit <b>{t.exit_price:.2f}</b>'
                f' @ {t.exit_time.strftime("%H:%M") if t.exit_time else "—"} &nbsp;'
                f'<span style="color:{rc};font-size:0.68rem">{t.exit_reason}</span> &nbsp;'
                f'P&L <b style="color:{"#3ddc84" if pnl>=0 else "#ff6b6b"}">{pnl:+.2f} pts</b>'
                f'</div>',
                unsafe_allow_html=True,
            )
        pf = build_pnl_chart(eng.closed_trades)
        if pf:
            st.plotly_chart(pf, use_container_width=True, config={"displayModeBar": False})
        s = eng.summary()
        sc1,sc2,sc3,sc4 = st.columns(4)
        sc1.metric("Total",  s["total"])
        sc2.metric("Wins",   s["wins"])
        sc3.metric("Losses", s["losses"])
        sc4.metric("Net P&L",f"{s['net_pnl']:+.2f} pts")

    if not any_trades:
        st.markdown(
            '<div style="color:#3a5a7a;font-family:IBM Plex Mono;font-size:0.8rem;'
            'padding:30px 0;text-align:center;">'
            'No closed trades yet. Step through candles in the Chart tab.</div>',
            unsafe_allow_html=True,
        )

# ── TAB 3 : BACKTEST ─────────────────────────────────────
with tab3:
    bt = st.session_state.backtest_df
    if bt is None:
        st.markdown(
            '<div style="color:#3a5a7a;font-family:IBM Plex Mono;font-size:0.8rem;'
            'padding:30px 0;text-align:center;">'
            'Click "Run Full Backtest" in the sidebar.</div>',
            unsafe_allow_html=True,
        )
    elif bt.empty:
        st.info("No trades found in loaded data.")
    else:
        wins = bt[bt["pnl_pts"] > 0]
        net  = bt["pnl_pts"].sum()
        b1,b2,b3,b4,b5 = st.columns(5)
        b1.metric("Total",    len(bt))
        b2.metric("Wins",     len(wins))
        b3.metric("Losses",   len(bt)-len(wins))
        b4.metric("Win Rate", f"{len(wins)/len(bt)*100:.1f}%")
        b5.metric("Net P&L",  f"{net:+.2f} pts")

        pnls = bt["pnl_pts"].tolist()
        cum  = list(np.cumsum(pnls))
        clrs = ["#3ddc84" if p >= 0 else "#ff6b6b" for p in pnls]
        fig_bt = go.Figure()
        fig_bt.add_trace(go.Bar(x=list(range(len(pnls))), y=pnls, marker_color=clrs,
                                name="P&L", text=[f"{p:+.1f}" for p in pnls],
                                textposition="outside",
                                textfont=dict(size=9, family="IBM Plex Mono", color="#1a1a2e")))
        fig_bt.add_trace(go.Scatter(x=list(range(len(cum))), y=cum, mode="lines",
                                    name="Cumulative", line=dict(color="#1a56db", width=2)))
        fig_bt.update_layout(plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
                             font=dict(family="IBM Plex Mono", color="#5a7a9a", size=10),
                             height=270, margin=dict(l=10,r=10,t=10,b=30),
                             legend=dict(font=dict(size=9), bgcolor="#f5f7fa", bordercolor="#dde3ec"))
        fig_bt.update_xaxes(gridcolor="#e8edf5")
        fig_bt.update_yaxes(gridcolor="#e8edf5", ticksuffix=" pts")
        st.plotly_chart(fig_bt, use_container_width=True, config={"displayModeBar": False})

        dbt = bt.copy()
        dbt["entry_time"] = pd.to_datetime(dbt["entry_time"]).dt.strftime("%d/%m %H:%M")
        dbt["exit_time"]  = pd.to_datetime(dbt["exit_time"]).dt.strftime("%d/%m %H:%M")
        st.dataframe(
            dbt[["entry_time","exit_time","direction",
                 "entry_price","sl","target","exit_price","exit_reason","pnl_pts"]],
            use_container_width=True, height=320,
        )

# ── TAB 4 : LOG ──────────────────────────────────────────
with tab4:
    msgs = st.session_state.log_msgs
    if not msgs:
        st.markdown('<div style="color:#3a5a7a;font-family:IBM Plex Mono;font-size:0.8rem;'
                    'padding:20px 0;">Log is empty.</div>', unsafe_allow_html=True)
    else:
        lines = ""
        for m in msgs:
            clr = ("#ff6b6b" if "ERROR" in m else
                   "#1a56db" if "⚡" in m else
                   "#3ddc84" if "✅" in m else "#5a7a9a")
            lines += f'<div style="color:{clr}">{m}</div>'
        st.markdown(
            f'<div style="font-family:IBM Plex Mono;font-size:0.72rem;line-height:2;'
            f'background:#f5f7fa;padding:12px 16px;border-radius:4px;'
            f'border:1px solid #dde3ec;max-height:500px;overflow-y:auto;">{lines}</div>',
            unsafe_allow_html=True,
        )
    if st.button("Clear Log"):
        st.session_state.log_msgs = []
        st.rerun()
