import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import bcrypt
from datetime import datetime
import pytz

import scoring

# --- CONFIG & SECRETS --------------------------------------------------------
load_dotenv()

def _secret(key, default=None):
    """Read from Streamlit Cloud secrets first, then local .env / environment."""
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)

SUPABASE_URL = _secret("SUPABASE_URL")
# Use the SERVICE ROLE key: it stays on the Streamlit server, never reaches the
# browser, and bypasses RLS so the app works while the public stays locked out.
SUPABASE_SERVICE = _secret("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_KEY = SUPABASE_SERVICE or _secret("SUPABASE_KEY")
ADMIN_EMAIL  = (_secret("ADMIN_EMAIL") or "tigran.hakobyan@ameriabank.am").lower()

# Fail LOUD if the server isn't configured, instead of silently showing no data.
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("⚙️ Սերվերը կարգավորված չէ (SUPABASE_URL / SERVICE_ROLE_KEY բացակայում են)։")
    st.stop()
if not SUPABASE_SERVICE:
    st.warning("⚠️ Աշխատում է հանրային բանալիով — տվյալները չեն երևա։ Անհրաժեշտ է SERVICE_ROLE բանալին։")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

STAGES = {
    "group": "Խմբային փուլ",
    "r32":   "1/16 (32-ի փուլ)",
    "r16":   "1/8 (16-ի փուլ)",
    "qf":    "1/4 Քառորդ եզրափակիչ",
    "sf":    "1/2 Կիսաեզրափակիչ",
    "third": "3-րդ տեղի խաղ",
    "final": "ԵԶՐԱՓԱԿԻՉ",
}
STAGE_ORDER = ["group", "r32", "r16", "qf", "sf", "third", "final"]
JOKER_STAGES = ("group", "r32", "r16")

# All 48 WC 2026 teams (Armenian) — used for the Medals dropdown + admin reference
COUNTRIES = sorted([
    "Ալժիր", "Արգենտինա", "Ավստրալիա", "Ավստրիա", "Բելգիա", "Բոսնիա և Հերցեգովինա",
    "Բրազիլիա", "Կաբո Վերդե", "Կանադա", "Կոլումբիա", "Կոնգո ԴՀ", "Կոտ դ’Իվուար",
    "Խորվաթիա", "Կյուրասաո", "Չեխիա", "Էկվադոր", "Եգիպտոս", "Անգլիա", "Ֆրանսիա",
    "Գերմանիա", "Գանա", "Հաիթի", "Իրան", "Իրաք", "Ճապոնիա", "Հորդանան",
    "Հարավային Կորեա", "Մեքսիկա", "Մարոկկո", "Նիդեռլանդներ", "Նոր Զելանդիա",
    "Նորվեգիա", "Պանամա", "Պարագվայ", "Պորտուգալիա", "Կատար", "Սաուդյան Արաբիա",
    "Շոտլանդիա", "Սենեգալ", "Հարավային Աֆրիկա", "Իսպանիա", "Շվեդիա", "Շվեյցարիա",
    "Թունիս", "Թուրքիա", "ԱՄՆ", "Ուրուգվայ", "Ուզբեկստան",
])

# Flag emoji per country (display-only, predictions page). If a name is
# missing here the team name still shows with no flag — nothing breaks.
FLAGS = {
    "Ալժիր": "🇩🇿", "Արգենտինա": "🇦🇷", "Ավստրալիա": "🇦🇺", "Ավստրիա": "🇦🇹",
    "Բելգիա": "🇧🇪", "Բոսնիա և Հերցեգովինա": "🇧🇦", "Բրազիլիա": "🇧🇷",
    "Կաբո Վերդե": "🇨🇻", "Կանադա": "🇨🇦", "Կոլումբիա": "🇨🇴", "Կոնգո ԴՀ": "🇨🇩",
    "Կոտ դ’Իվուար": "🇨🇮", "Խորվաթիա": "🇭🇷", "Կյուրասաո": "🇨🇼", "Չեխիա": "🇨🇿",
    "Էկվադոր": "🇪🇨", "Եգիպտոս": "🇪🇬", "Անգլիա": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Ֆրանսիա": "🇫🇷",
    "Գերմանիա": "🇩🇪", "Գանա": "🇬🇭", "Հաիթի": "🇭🇹", "Իրան": "🇮🇷", "Իրաք": "🇮🇶",
    "Ճապոնիա": "🇯🇵", "Հորդանան": "🇯🇴", "Հարավային Կորեա": "🇰🇷", "Մեքսիկա": "🇲🇽",
    "Մարոկկո": "🇲🇦", "Նիդեռլանդներ": "🇳🇱", "Նոր Զելանդիա": "🇳🇿", "Նորվեգիա": "🇳🇴",
    "Պանամա": "🇵🇦", "Պարագվայ": "🇵🇾", "Պորտուգալիա": "🇵🇹", "Կատար": "🇶🇦",
    "Սաուդյան Արաբիա": "🇸🇦", "Շոտլանդիա": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "Սենեգալ": "🇸🇳",
    "Հարավային Աֆրիկա": "🇿🇦", "Իսպանիա": "🇪🇸", "Շվեդիա": "🇸🇪", "Շվեյցարիա": "🇨🇭",
    "Թունիս": "🇹🇳", "Թուրքիա": "🇹🇷", "ԱՄՆ": "🇺🇸", "Ուրուգվայ": "🇺🇾",
    "Ուզբեկստան": "🇺🇿",
}

def flag(name):
    f = FLAGS.get(name, "")
    return f + " " if f else ""

st.set_page_config(page_title="WC2026 Arena | Ameriabank", page_icon="🏆", layout="wide", initial_sidebar_state="expanded")

# --- CINEMATIC + READABLE CSS ------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Inter:wght@300;400;600;700&display=swap');

    .stApp {
        background: radial-gradient(circle at 50% 50%, #0f0c29 0%, #302b63 50%, #24243e 100%);
        background-attachment: fixed;
    }
    /* readable body text everywhere */
    .stApp, .stApp p, .stApp span, .stApp label, .stApp div { color: #F2F2F7; }

    .glass-card {
        background: rgba(255, 255, 255, 0.06);
        backdrop-filter: blur(15px);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 20px;
        padding: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.6);
        margin-bottom: 12px;
    }
    h1, h2, h3 {
        font-family: 'Orbitron', sans-serif !important;
        background: linear-gradient(to right, #00ff88, #00d4ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 900 !important;
    }
    .roster-row {
        display: flex; justify-content: space-between; align-items: center;
        padding: 12px 20px; border-radius: 12px; margin-bottom: 6px;
        border: 1px solid rgba(255,255,255,0.12); transition: 0.2s;
    }
    .roster-row:hover { background: rgba(255, 255, 255, 0.08); }
    /* brighter secondary text (was hard to read) */
    .muted { color: #D6D6E0 !important; font-weight: 600; }
    .team-box {
        background: rgba(0,212,255,0.08); border:1px solid rgba(0,212,255,0.35);
        border-radius:10px; padding:8px 6px; text-align:center;
        font-family:'Orbitron',sans-serif; font-weight:700; font-size:0.95rem;
        color:#FFFFFF; min-height:44px; display:flex; align-items:center; justify-content:center;
    }
    .rules-table { width:100%; border-collapse:collapse; }
    .rules-table th, .rules-table td {
        border:1px solid rgba(255,255,255,0.18); padding:10px 12px; text-align:center; color:#FFFFFF;
    }
    .rules-table th { background: rgba(0,255,136,0.15); font-family:'Orbitron'; }
    div.stButton > button {
        background: linear-gradient(45deg, #00ff88, #00d4ff) !important;
        color: #000000 !important;
        font-family: 'Orbitron', sans-serif !important; font-weight: 900 !important;
        border-radius: 50px !important; width: 100%; transition: 0.3s !important;
    }
    /* force the button LABEL itself black + bold (beats the dark theme) */
    div.stButton > button p,
    div.stButton > button div,
    div.stButton > button span {
        color: #000000 !important; font-weight: 900 !important;
    }
    /* dropdown (selectbox) menus — readable on the dark theme */
    div[data-baseweb="popover"] ul { background-color: #16213e !important; }
    div[data-baseweb="popover"] li,
    div[data-baseweb="popover"] li span,
    div[data-baseweb="popover"] li div { color: #FFFFFF !important; }
    div[data-baseweb="popover"] li:hover { background-color: rgba(0,212,255,0.30) !important; }
    /* the closed selectbox control + its selected value (was white-on-white) */
    div[data-baseweb="select"] > div {
        background-color: rgba(255,255,255,0.08) !important; color: #FFFFFF !important;
    }
    div[data-baseweb="select"] input { color: #FFFFFF !important; }
    /* hide Streamlit chrome so viewers can't reach GitHub / other apps */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    [data-testid="stToolbar"] { display: none !important; }
    [data-testid="stStatusWidget"] { display: none !important; }
    [class*="viewerBadge"] { display: none !important; }
    [data-testid="stAppViewerBadge"] { display: none !important; }
    a[href*="streamlit.io"] { display: none !important; }
    /* --- responsive: phones only (<=640px). Laptops/desktops unaffected. --- */
    @media (max-width: 640px) {
        html, body, [data-testid="stAppViewContainer"] { font-size: 14px !important; }
        .block-container { padding-left: 0.6rem !important; padding-right: 0.6rem !important; padding-top: 1rem !important; }
        div.stButton > button { font-size: 0.9rem !important; }
        h1 { font-size: 1.5rem !important; }
        h2 { font-size: 1.25rem !important; }
        h3 { font-size: 1.1rem !important; }
    }
    /* --- DESKTOP only (>=641px): lock sidebar open, remove collapse button --- */
    @media (min-width: 641px) {
        [data-testid="stSidebarCollapseButton"],
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"],
        [data-testid="stSidebar"] button[kind="header"],
        [data-testid="stSidebarHeader"] button {
            display: none !important;
        }
        [data-testid="stSidebar"],
        [data-testid="stSidebar"][aria-expanded="false"] {
            transform: none !important;
            visibility: visible !important;
            margin-left: 0 !important;
            min-width: 244px !important;
        }
        /* the phone page-picker is redundant on desktop -> hide it */
        .st-key-wc_topnav { display: none !important; }
    }
    /* on PHONES the sidebar stays collapsible (so the page gets full width);
       the top page-picker above guarantees navigation either way. */
</style>
""", unsafe_allow_html=True)


# --- HELPERS -----------------------------------------------------------------
YEREVAN = pytz.timezone('Asia/Yerevan')   # Armenia time (UTC+4)

def now_utc():
    return datetime.now(pytz.UTC)

def parse_dt(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00'))

def to_yerevan(dt):
    return dt.astimezone(YEREVAN)

def disp_name(u):
    return (u.get('display_name') or u.get('username') or "").strip()


# --- LANDING -----------------------------------------------------------------
def landing_page():
    st.markdown("""
        <style>
        /* Full-screen Waka Waka GIF background for the landing page only */
        .stApp {
            background:
                linear-gradient(rgba(15,12,41,0.72), rgba(36,36,62,0.88)),
                url('https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExMThzamU3emJkaGZyZmd5NDFsOGhkbjZ4bzgyNzJlM3pyc2luN3NjaSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/gLWTWCg96RA0btDUm0/giphy.gif')
                center center / cover no-repeat fixed !important;
        }
        </style>
        <div style="padding-top: 60px; padding-bottom: 40px; text-align:center;">
            <h1 style="font-size:5rem; margin-bottom:0; text-shadow:0 0 20px #FFD700;">Ցամինա Մինա Է Է!</h1>
            <h1 style="font-size:4rem; margin-top:0; color:#FFD700 !important; text-shadow:0 0 30px #FFD700;">Վակա Վակա Է Է!</h1>
            <p style="font-family:'Orbitron'; font-size:1.4rem; letter-spacing:4px; color:#00ff88; text-shadow:0 0 12px #000;">🇦🇲 ԱՄԵՐԻԱԲԱՆԿ ԿԱՆԽԱՏԵՍՈՒՄՆԵՐԻ ԱՐԵՆԱ 2026 🇦🇲</p>
            <br><br>
            <div style="max-width:700px; margin:0 auto; padding:30px; border:2px solid #00ff88;" class="glass-card">
                <h2 style="color:white !important;">ՊԱՏՐԱ՞ՍՏ ԵՔ ՀԱՂԹԱՆԱԿԻ</h2>
                <p style="font-size:1.15rem; color:#EDEDED;">Աշխարհի ամենաթեժ կանխատեսումների հարթակ։<br>Ո՞վ կլինի համար մեկը։</p>
            </div>
        </div>
    """, unsafe_allow_html=True)
    c = st.columns([2, 1, 2])
    with c[1]:
        if st.button("🚀 ՄՈՒՏՔ ԳՈՐԾԵԼ ԱՐԵՆԱ"):
            st.session_state['entered'] = True
            st.rerun()


def login_ui():
    st.markdown("<br>", unsafe_allow_html=True)
    cols = st.columns([1, 2, 1])
    with cols[1]:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.title("🛡️ ԷԼԻՏԱՐ ՄՈՒՏՔ")
        email = st.text_input("ԷԼ. ՓՈՍՏ", placeholder="name@ameriabank.am")
        password = st.text_input("ԳԱՂՏՆԱԲԱՌ", type="password")
        if st.button("ՄԻԱՆԱԼ ՀԱՄԱԿԱՐԳԻՆ"):
            # case-insensitive email match; escape LIKE metacharacters (_ and %)
            # so an address like "a_b@x.am" can't act as a wildcard pattern.
            safe_email = email.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            res = supabase.table("users").select("*").ilike("email", safe_email).execute()
            if res.data and bcrypt.checkpw(password.encode('utf-8'),
                                           res.data[0]['password_hash'].encode('utf-8')):
                if not res.data[0].get('is_active', True):
                    st.error("🚫 Ձեր հաշիվն անջատված է։ Դիմեք ադմինիստրատորին։")
                else:
                    st.session_state['logged_in'] = True
                    st.session_state['user'] = res.data[0]
                    st.rerun()
            else:
                st.error("ՄՈՒՏՔԸ ՄԵՐԺՎԱԾ Է։ Սխալ տվյալներ։")
        st.markdown('</div>', unsafe_allow_html=True)


# ===================  GATES  =================================================
if 'entered' not in st.session_state:
    landing_page(); st.stop()
if 'logged_in' not in st.session_state:
    login_ui(); st.stop()

# refresh the cached user row each run (so points/jokers stay current)
_fresh = supabase.table("users").select("*").eq("id", st.session_state['user']['id']).execute().data
if not _fresh:                       # account was removed mid-session -> log out cleanly
    for k in ('logged_in', 'user', 'page'):
        st.session_state.pop(k, None)
    st.warning("Ձեր հաշիվը այլևս հասանելի չէ։ Մուտք գործեք կրկին։")
    st.stop()
user_data = _fresh[0]
st.session_state['user'] = user_data
is_admin = (user_data.get('email', '').lower() == ADMIN_EMAIL)


# --- SIDEBAR / NAV -----------------------------------------------------------
st.sidebar.markdown(f"### 🎖️ {disp_name(user_data).upper()}")
st.sidebar.markdown(f"**ՄԻԱՎՈՐ՝** `{user_data.get('total_points', 0)}`")
st.sidebar.divider()

if 'page' not in st.session_state:
    st.session_state['page'] = "ԿԱՆՈՆՆԵՐ"

NAV = [("ԿԱՆՈՆՆԵՐ", "📜 ԿԱՆՈՆՆԵՐ"),
       ("ԱՂՅՈՒՍԱԿ", "🏆 ԱՂՅՈՒՍԱԿ"),
       ("ԿԱՆԽԱՏԵՍՈՒՄՆԵՐ", "🎯 ԿԱՆԽԱՏԵՍՈՒՄՆԵՐ"),
       ("ՄԵԴԱԼՆԵՐ", "🥇 ՄԵԴԱԼՆԵՐ"),
       ("ԱՐԴՅՈՒՆՔՆԵՐ", "📊 ԻՄ ԱՐԴՅՈՒՆՔՆԵՐԸ"),
       ("ՎԵՐԼՈՒԾՈՒԹՅՈՒՆ", "📈 ՎԵՐԼՈՒԾՈՒԹՅՈՒՆ")]
for key, label in NAV:
    if st.sidebar.button(label, use_container_width=True,
                         type="primary" if st.session_state['page'] == key else "secondary"):
        st.session_state['page'] = key; st.rerun()

if is_admin:
    st.sidebar.divider()
    st.sidebar.markdown("### ⚡ ԱԴՄԻՆ")
    if st.sidebar.button("🛠️ ՀԱՄԱԿԱՐԳԻ ԿԱՌԱՎԱՐՈՒՄ", use_container_width=True,
                         type="primary" if st.session_state['page'] == "ԱԴՄԻՆ" else "secondary"):
        st.session_state['page'] = "ԱԴՄԻՆ"; st.rerun()

st.sidebar.divider()
if st.sidebar.button("🔌 ԵԼՔ", use_container_width=True):
    for k in ('logged_in', 'user', 'page'):
        st.session_state.pop(k, None)
    st.rerun()

page = st.session_state['page']

# --- phone-only top page-picker (hidden on desktop via CSS) ------------------
# guarantees navigation even when the sidebar is collapsed on a small screen.
_nav_labels = {k: lbl for k, lbl in NAV}
if is_admin:
    _nav_labels["ԱԴՄԻՆ"] = "🛠️ ԱԴՄԻՆ"
_nav_keys = list(_nav_labels.keys())

# Keep the picker in sync with the current page so sidebar-button navigation is
# reflected here too. We DON'T pass index= and DON'T compare against page: the
# selectbox and the sidebar buttons both drive the same `page` state, and an
# index/compare approach makes the stale widget value hijack button navigation.
# Seeding the widget's session_state key before it renders is the supported way
# to set its value; genuine user picks are captured by the on_change callback
# (callbacks run before the rerun, so `page` is already updated above).
st.session_state['wc_pagesel'] = page if page in _nav_keys else _nav_keys[0]

def _on_pagesel():
    st.session_state['page'] = st.session_state['wc_pagesel']

with st.container(key="wc_topnav"):
    st.selectbox("📂 Էջ", _nav_keys, format_func=lambda k: _nav_labels[k],
                 key="wc_pagesel", on_change=_on_pagesel)


# ===================  PAGE: RULES  ===========================================
if page == "ԿԱՆՈՆՆԵՐ":
    st.title("📜 ԽԱՂԻ ԿԱՆՈՆՆԵՐ")
    st.markdown("""
    <div class="glass-card">
      <h3>🏟️ Մրցաշարի ձևաչափ — 104 խաղ, 7 փուլ</h3>
      <ul style="font-size:1.05rem; color:#FFFFFF;">
        <li><b>Խմբային փուլ</b> — 72 խաղ (12 խումբ × 4 թիմ)</li>
        <li><b>1/16 փուլ</b> — 16 խաղ &nbsp;|&nbsp; <b>1/8 փուլ</b> — 8 խաղ</li>
        <li><b>Քառորդ եզրափակիչ</b> — 4 խաղ &nbsp;|&nbsp; <b>Կիսաեզրափակիչ</b> — 2 խաղ</li>
        <li><b>3-րդ տեղի խաղ</b> — 1 &nbsp;|&nbsp; <b>Եզրափակիչ</b> — 1</li>
      </ul>
    </div>

    <div class="glass-card">
      <h3>⚽ Միավորներ յուրաքանչյուր խաղի համար</h3>
      <p class="muted">Ստանում ես միայն մեկ՝ ամենաբարձր կատեգորիան (ճիշտ հաշիվը չի գումարվում տարբերության հետ)։</p>
      <table class="rules-table">
        <tr><th>Փուլ</th><th>Ճիշտ հաշիվ</th><th>Գոլային տարբերություն</th><th>Ճիշտ ելք</th></tr>
        <tr><td>Խմբային</td><td>6</td><td>4</td><td>2</td></tr>
        <tr><td>1/16</td><td>9</td><td>6</td><td>3</td></tr>
        <tr><td>1/8</td><td>12</td><td>8</td><td>4</td></tr>
        <tr><td>Քառորդ եզր.</td><td>18</td><td>12</td><td>6</td></tr>
        <tr><td>Կիսաեզր.</td><td>24</td><td>16</td><td>8</td></tr>
        <tr><td>3-րդ տեղ</td><td>15</td><td>10</td><td>5</td></tr>
        <tr><td><b>Եզրափակիչ</b></td><td><b>36</b></td><td><b>24</b></td><td><b>12</b></td></tr>
      </table>
      <p class="muted" style="margin-top:10px;">⏱️ Հաշիվը հաշվարկվում է խաղի <b>90 րոպեի + խաղավարի ավելացրած (փոխհատուցման) րոպեների</b> արդյունքով (օր.՝ 90+3'-ին խփված գոլը հաշվի է առնվում)։ <b>Լրացուցիչ ժամանակը (2×15 րոպե) և պենալտիները հաշվի չեն առնվում</b> կանխատեսման համար — դրանք միայն որոշում են, թե ով է անցնում հաջորդ փուլ։</p>
    </div>

    <div class="glass-card">
      <h3>🃏 Ջոկերներ (3 հատ)</h3>
      <p style="color:#FFFFFF;">Ջոկերը <b>×2 կրկնապատկում</b> է տվյալ խաղի միավորները։ Ունես ընդամենը 3 ջոկեր՝ խիստ ֆիքսված փուլերով․</p>
      <ul style="color:#FFFFFF;">
        <li>🃏 1 — միայն <b>Խմբային փուլում</b></li>
        <li>🃏 2 — միայն <b>1/16 փուլում</b></li>
        <li>🃏 3 — միայն <b>1/8 փուլում</b> (Քառորդ եզրափակիչից սկսած ջոկեր ՉԿԱ)</li>
      </ul>
      <ul style="color:#FFFFFF;">
        <li>Յուրաքանչյուր փուլում <b>միայն 1 ջոկեր</b>։ Եթե փորձես երկրորդը՝ համակարգը <b>թույլ չի տա</b> (կպահվի առանց ջոկերի)։</li>
        <li>Եթե փուլում ջոկերը չես օգտագործում՝ այն <b>կորչում է</b> (չի փոխանցվում հաջորդ փուլ)։</li>
      </ul>
    </div>

    <div class="glass-card">
      <h3>🧠 Բոնուս միավորներ</h3>
      <p class="muted">Բոնուսները հաշվարկվում են այն ժամանակ, երբ ադմինը մուտքագրում է <b>պաշտոնական արդյունքը</b>։ Մինչ այդ՝ բոնուսը 0 է։</p>
      <ul style="color:#FFFFFF; font-size:1.05rem;">
        <li><b>📦 Խմբի աղյուսակ՝</b> ճիշտ <b>հաղթող +6</b>, ճիշտ <b>2-րդ տեղ +4</b> (յուրաքանչյուր խմբի համար)։
            <br><b style="color:#FFD700;">⚠️ Կարևոր՝</b> խմբի բոնուսը ստանում ես <b>միայն եթե կանխատեսել ես այդ խմբի բոլոր 6 խաղերը</b>։ Եթե թեկուզ 1 խաղ բաց ես թողել՝ այդ խմբից բոնուս չես ստանում (բայց առանձին խաղերի միավորները մնում են)։</li>
        <li><b>✅ Որակավորում՝ +1</b> միավոր յուրաքանչյուր թիմի համար, որը ճիշտ ես կանխատեսել, որ կանցնի 1/16 փուլ (առավելագույնը +32)։ Սա նույնպես պահանջում է խմբի <b>բոլոր 6 խաղերի</b> կանխատեսում։</li>
        <li><b>🥇 Մեդալներ՝</b> Ոսկի (չեմպիոն) <b>+30</b>, Արծաթ (ֆինալիստ) <b>+18</b>, Բրոնզ (3-րդ տեղ) <b>+12</b>։
            <br>Ընտրում ես <b>3 տարբեր թիմ</b> մինչև ադմինի սահմանած վերջնաժամկետը։ Ընտրությունը <b>մեկանգամյա է</b> և կողպվում է ընդմիշտ։</li>
      </ul>
    </div>

    <div class="glass-card">
      <h3>📊 Ինչպե՞ս է կազմվում խմբի աղյուսակը (պարզ բացատրություն)</h3>
      <p style="color:#FFFFFF;">Ամեն խումբ ունի <b>4 թիմ</b>։ Քո կանխատեսած հաշիվներով ծրագիրն <b>ինքնաշխատ</b> կազմում է աղյուսակը՝ ո՞վ է 1-ին, 2-րդ, 3-րդ, 4-րդ տեղում։ Թիմերը դասավորվում են այս հերթականությամբ․</p>
      <ol style="color:#FFFFFF; font-size:1.05rem;">
        <li><b>Միավորներ։</b> Ամեն հաղթանակ՝ <b>3 միավոր</b>, ոչ-ոքի՝ <b>1</b>, պարտություն՝ <b>0</b>։ Ով ավելի շատ միավոր ունի, ավելի վերև է։</li>
        <li>Եթե <b>միավորները հավասար են</b> → նայում ենք <b>գոլային տարբերությունը</b> (քանի գոլ է խփել՝ հանած քանի գոլ է բաց թողել)։</li>
        <li>Եթե դա էլ է հավասար → ով <b>ավելի շատ գոլ</b> է խփել։</li>
        <li>Եթե դեռ հավասար են → նայում ենք <b>իրար միջև խաղը</b> (ո՞վ ում հաղթեց)։</li>
      </ol>
      <p class="muted" style="margin-top:6px;">💡 Պարզ ասած՝ ավելի շատ հաղթանակ ու ավելի շատ գոլ = ավելի բարձր տեղ։</p>

      <div style="background:rgba(0,255,136,0.08); border:1px solid rgba(0,255,136,0.35); border-radius:12px; padding:12px; margin-top:12px;">
        <b style="color:#00ff88;">🏁 Ո՞վ է անցնում հաջորդ փուլ</b>
        <p style="color:#FFFFFF; margin:6px 0;">Ամեն խմբից <b>լավագույն 2 թիմն</b> անցնում է հաջորդ փուլ (1/16)։ Խմբերը 12-ն են, ուստի՝ <b>24 թիմ</b>։ Բացի դրանից՝ 3-րդ տեղ զբաղեցրած թիմերից <b>լավագույն 8-ն</b> էլ են անցնում։ Ընդամենը՝ <b>32 թիմ</b>։</p>
        <p class="muted" style="margin:6px 0 0 0;">🎁 Եթե ճիշտ ես գուշակում՝ այս 32 թիմից որո՞նք կանցնեն, ամեն ճիշտ թիմի համար ստանում ես <b>+1 միավոր</b>։</p>
      </div>
      <p class="muted" style="margin-top:10px;">Իրական արդյունքները (ով հաղթեց խումբը, ով անցավ հաջորդ փուլ) մուտքագրում է <b>կազմակերպիչը</b>, ապա ծրագիրը համեմատում է քո կանխատեսման հետ ու տալիս բոնուս միավորները։</p>
    </div>

    <div class="glass-card" style="border:2px solid #FFD700;">
      <h3 style="color:#FFD700 !important;">⚠️ Կարևոր կանոններ</h3>
      <ul style="color:#FFFFFF; font-size:1.05rem;">
        <li>Հաշիվը՝ խաղի <b>90 րոպեի + փոխհատուցման</b> արդյունքով։ <b>Լրացուցիչ ժամանակը և պենալտիները ՉԵՆ հաշվվում</b> միավորների համար։</li>
        <li>Յուրաքանչյուր խաղ ունի <b>ճշգրիտ փակման ժամ</b> (Երևանի ժամանակով)՝ նշված հենց խաղի վրա։ Կանխատեսում կարող ես անել <b>միայն մինչև այդ ժամը</b>։</li>
        <li>Կանխատեսումը <b>մեկանգամյա է</b>։ Երբ սեղմում ես «Հաստատել»՝ այն <b>կողպվում է ընդմիշտ</b> և այլևս հնարավոր չէ փոխել, <b>նույնիսկ եթե դեռ ժամանակ կա</b>։</li>
        <li>Փակման ժամը լրանալուց հետո խաղը <b>փակվում է</b>, և կանխատեսումն այլևս հնարավոր չէ։ Չկանխատեսված խաղը = <b>0 միավոր</b>։</li>
        <li>Առանձին խաղի միավորները ստանում ես ցանկացած դեպքում, բայց <b>խմբի բոնուսի համար պետք է կանխատեսես խմբի բոլոր 6 խաղերը</b>։</li>
        <li>Ոչ ոք չի տեսնում մյուսների կանխատեսումները։ Տեսանելի է միայն ընդհանուր աղյուսակը։</li>
      </ul>
    </div>
    """, unsafe_allow_html=True)


# ===================  PAGE: LEADERBOARD  =====================================
elif page == "ԱՂՅՈՒՍԱԿ":
    st.title("🏆 ԱՐԵՆԱՅԻ ԱՂՅՈՒՍԱԿ")
    res = supabase.table("users").select(
        "id, username, display_name, total_points, bonus_points, exact_scores_count, "
        "diff_count, outcome_count, wrong_count, previous_rank"
    ).eq("is_active", True).execute()
    df = pd.DataFrame(res.data)
    for c in ['exact_scores_count', 'diff_count', 'outcome_count', 'wrong_count',
              'total_points', 'bonus_points']:
        if c not in df.columns:
            df[c] = 0
        df[c] = df[c].fillna(0).astype(int)
    df['name'] = df.apply(lambda r: (r.get('display_name') or r.get('username') or ""), axis=1)
    # Tie-break for equal points: more exact scores (🎯) -> more goal-difference
    # hits (➕) -> more correct outcomes (✅) -> whoever submitted their FIRST
    # prediction earliest (accounts were bulk-seeded, so creation order is random;
    # first prediction is the meaningful "who got there first"). Deterministic.
    if not df.empty:
        first_pred = {}
        for p in (supabase.table("predictions").select("user_id, created_at").execute().data or []):
            uid, ts = p['user_id'], (p.get('created_at') or '')
            if uid not in first_pred or ts < first_pred[uid]:
                first_pred[uid] = ts
        df['_first'] = df['id'].map(lambda x: first_pred.get(x, '9999'))
        df = df.sort_values(
            by=['total_points', 'exact_scores_count', 'diff_count', 'outcome_count', '_first', 'username'],
            ascending=[False, False, False, False, True, True])
    df = df.reset_index(drop=True)
    df['rank'] = df.index + 1
    total = len(df)

    GIFS = {
        1: 'https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExcnhhajZpaXp2NTl2OGZoYmloc3FqcDFmeTdqajR3cGxheDB6Z3Z1NCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/IeX7IzEYkvrXri0fN3/giphy.gif',
        2: 'https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExcW00NTk1Y2gyZGFrZGVvbm5hdGhkMGFmNHNqcHp5ejNtejZhbTQ0biZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/pslhvBFfstOJiyBOrs/giphy.gif',
        3: 'https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExcjNrdHZvbWJkYjl5Y3M1eGY3M3ZvcGlnZmhqaDZ4OWQ4dDhieDY0YSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/5AwCyyscRqpSvh0V6Bq/giphy.gif',
    }
    SPOON_GIF = 'https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExZ2psODNjZm1zd2Uwd3F5ZDl6bXluZmF3MjZ3bnZpcmNkbTR2enptdCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/SCFB9A9pbzh04/giphy.gif'

    if not df.empty:
        st.markdown("### 🔝 ԼԱՎԱԳՈՒՅՆ ԵՌՅԱԿԸ")
        cols = st.columns(3)
        medals = {1: ("🥇 1-ԻՆ ՏԵՂ", "gold"), 2: ("🥈 2-ՐԴ ՏԵՂ", "silver"), 3: ("🥉 3-ՐԴ ՏԵՂ", "#cd7f32")}
        for col_i, rank in zip(range(3), [2, 1, 3]):   # silver, gold, bronze visual order
            label, color = medals[rank]
            with cols[col_i]:
                if len(df) >= rank:
                    nm = df.iloc[rank - 1]['name'].upper()
                    pt = df.iloc[rank - 1]['total_points']
                    gif = f'<img src="{GIFS[rank]}" style="width:100%; height:110px; object-fit:cover; border-radius:12px; margin-bottom:8px;">'
                else:
                    nm, pt, gif = "—", 0, ""
                st.markdown(
                    f'<div class="glass-card" style="border:2px solid {color}; text-align:center;">{gif}'
                    f'<h4 style="color:{color} !important;">{label}</h4>'
                    f'<h2 style="margin:0; color:#FFFFFF !important;">{nm}</h2>'
                    f'<h3>{pt} ՄԻԱՎՈՐ</h3></div>', unsafe_allow_html=True)

        if total > 3:
            st.markdown("<br>", unsafe_allow_html=True)
            last = df.iloc[-1]
            lc = st.columns([1, 2, 1])
            with lc[1]:
                st.markdown(
                    f'<div class="glass-card" style="border:2px solid saddlebrown; text-align:center;">'
                    f'<img src="{SPOON_GIF}" style="width:100%; height:130px; object-fit:cover; border-radius:12px; margin-bottom:8px;">'
                    f'<h2 style="margin:0; color:#FFFFFF !important;">{last["name"].upper()}</h2>'
                    f'<h3>{last["total_points"]} ՄԻԱՎՈՐ</h3>'
                    f'<small class="muted">😅 Ոչինչ, ինչ-որ մեկը պետք է վերջինը լինի... 🤣 Մի՛ հանձնվիր։</small></div>',
                    unsafe_allow_html=True)

    st.divider()
    search = st.text_input("🔍 Փնտրել գործընկերոջը...", placeholder="Անուն...")
    # regex=False so names with special characters (or a stray "(") can't crash search
    view = df[df['name'].str.contains(search, case=False, na=False, regex=False)] if search else df

    for _, row in view.iterrows():
        rank = int(row['rank'])
        nm, pts = row['name'].upper(), row['total_points']
        ex, di, ou, wr = row['exact_scores_count'], row['diff_count'], row['outcome_count'], row['wrong_count']
        bo = row.get('bonus_points', 0)
        prev = row.get('previous_rank')
        arrow = ("" if not prev or prev == rank else (" 🔼" if rank < prev else " 🔻"))

        color, msg = "rgba(255,255,255,0.04)", "Շարունակիր այսպես..."
        if rank == 1:
            color, msg = "rgba(255,215,0,0.18)", "👑 ԱՆՀԱՍԱՆԵԼԻ ԱՌԱՋԱՏԱՐ"
        elif rank == 2:
            color, msg = "rgba(192,192,192,0.15)", "🥈 ՀՐԱՇԱԼԻ ՄՐՑԱԿԻՑ"
        elif rank == 3:
            color, msg = "rgba(205,127,50,0.15)", "🥉 ԼԱՎԱԳՈՒՅՆ ԵՌՅԱԿՈՒՄ"
        elif pts > 0 and rank <= 6:
            msg = "🔥 ՇԱՏ ՏԱՔ Է"
        if total > 3 and rank == total:
            color, msg = "rgba(139,69,19,0.30)", "🥄 ՓԱՅՏԵ ԳԴԱԼԻ ՏԵՐԸ"

        st.markdown(
            f'<div class="roster-row" style="background:{color};">'
            f'<div style="display:flex; align-items:center;">'
            f'<span style="font-family:Orbitron; font-size:1.3rem; width:55px; color:#00ff88; font-weight:900;">{rank}{arrow}</span>'
            f'<span style="font-weight:900; font-size:1.2rem; color:#FFFFFF;">{nm}</span></div>'
            f'<div style="text-align:right;">'
            f'<span style="font-family:Orbitron; font-size:1.25rem; color:#00d4ff; font-weight:900;">{pts} ՄԻԱՎՈՐ</span><br>'
            f'<small class="muted">🎁{bo} 🎯{ex} ➕{di} ✅{ou} ❌{wr} | {msg}</small></div></div>',
            unsafe_allow_html=True)

    # --- full comparison table (everyone, all columns, no individual picks) ---
    st.divider()
    st.markdown("### 📊 ՄԱՆՐԱՄԱՍՆ ՀԱՄԵՄԱՏՈՒԹՅՈՒՆ")
    st.caption("🎯 Ճիշտ հաշիվ · ➕ Գոլային տարբերություն · ✅ Ճիշտ ելք · ❌ Սխալ")
    table = df.copy()
    table.insert(0, "Տեղ", range(1, len(table) + 1))
    table = table[["Տեղ", "name", "total_points", "bonus_points", "exact_scores_count",
                   "diff_count", "outcome_count", "wrong_count"]]
    table.columns = ["Տեղ", "Մասնակից", "Միավոր", "🎁 Բոնուս", "🎯 Ճիշտ հաշիվ",
                     "➕ Տարբերություն", "✅ Ճիշտ ելք", "❌ Սխալ"]
    st.dataframe(table, use_container_width=True, hide_index=True, height=min(600, 60 + 35 * len(table)))


# ===================  PAGE: PREDICTIONS  =====================================
elif page == "ԿԱՆԽԱՏԵՍՈՒՄՆԵՐ":
    st.title("🎯 ԿԱՆԽԱՏԵՍՈՒՄՆԵՐ")
    matches = supabase.table("matches").select("*").order("kickoff_time").execute().data or []
    my_preds = supabase.table("predictions").select("*").eq("user_id", user_data['id']).execute().data or []
    pred_by_match = {p['match_id']: p for p in my_preds}
    joker_used_stage = set()
    for p in my_preds:
        if p.get('use_joker'):
            m = next((mm for mm in matches if mm['id'] == p['match_id']), None)
            if m:
                joker_used_stage.add(m['stage'])

    if not matches:
        st.info("Այս պահին հասանելի խաղեր չկան։ Սպասեք ադմինի կողմից խաղերի բացմանը։")

    EXPECTED = {'group': 72, 'r32': 16, 'r16': 8, 'qf': 4, 'sf': 2, 'third': 1, 'final': 1}

    def render_card(m):
        stage = m['stage']
        lock = parse_dt(m['lock_time'])
        is_locked = now_utc() >= lock or m.get('status') == 'finished'
        existing = pred_by_match.get(m['id'])
        st.markdown('<div class="glass-card" style="padding:12px; margin-bottom:8px;">', unsafe_allow_html=True)
        grp_badge = (f"<span style='color:#FFD700; font-weight:900;'>📦 Խումբ {m['group_name']}</span> · "
                     if m.get('group_name') else "")
        st.markdown(
            f"<div style='text-align:center; color:#00d4ff; font-weight:700; font-size:0.85rem;'>"
            f"{grp_badge}🔒 Վերջնաժամկետ՝ {to_yerevan(lock).strftime('%d.%m  %H:%M')} (Երևան)</div>",
            unsafe_allow_html=True)
        c1, c2, c3 = st.columns([2, 1.3, 2])
        with c1: st.markdown(f"<div class='team-box'>{flag(m['home_team'])}{m['home_team']}</div>", unsafe_allow_html=True)
        with c3: st.markdown(f"<div class='team-box'>{flag(m['away_team'])}{m['away_team']}</div>", unsafe_allow_html=True)
        if existing:                       # immutable — already predicted
            with c2:
                jk = " 🃏" if existing.get('use_joker') else ""
                st.markdown(
                    f"<div style='text-align:center;'><div style='font-family:Orbitron; font-weight:900;"
                    f" font-size:1.4rem; color:#00ff88;'>{existing['pred_home']} : {existing['pred_away']}{jk}</div>"
                    f"<small class='muted'>✅ Հաստատված</small></div>", unsafe_allow_html=True)
        elif is_locked:
            with c2:
                st.markdown("<div style='text-align:center; font-size:1.6rem;'>🔒</div>", unsafe_allow_html=True)
        else:
            with c2:
                h = st.number_input(f"{flag(m['home_team'])}{m['home_team']}", min_value=0, step=1, key=f"h_{m['id']}")
                a = st.number_input(f"{flag(m['away_team'])}{m['away_team']}", min_value=0, step=1, key=f"a_{m['id']}")
                can_joker = stage in JOKER_STAGES and stage not in joker_used_stage
                use_jk = st.checkbox("🃏 ՋՈԿԵՐ (×2)", key=f"jk_{m['id']}", disabled=not can_joker)
                if st.button("ՀԱՍՏԱՏԵԼ", key=f"btn_{m['id']}"):
                    # re-read this match NOW (page may be stale): refuse if locked or finished
                    mnow = supabase.table("matches").select(
                        "status, lock_time").eq("id", m['id']).execute().data
                    if (not mnow) or mnow[0]['status'] == 'finished' or \
                       now_utc() >= parse_dt(mnow[0]['lock_time']):
                        st.error("🔒 Ուշացաք — խաղը փակվեց։")
                    else:
                        # re-read the DB right now so two tabs/devices can't both
                        # spend the same-stage joker, and can't double-predict.
                        fresh = supabase.table("predictions").select(
                            "match_id, use_joker").eq("user_id", user_data['id']).execute().data or []
                        if any(fp['match_id'] == m['id'] for fp in fresh):
                            st.error("Արդեն կանխատեսված է։")
                            st.rerun()
                        used_stage_now = set()
                        for fp in fresh:
                            if fp.get('use_joker'):
                                fm = next((mm for mm in matches if mm['id'] == fp['match_id']), None)
                                if fm:
                                    used_stage_now.add(fm['stage'])
                        joker_ok = bool(use_jk and can_joker and stage not in used_stage_now)
                        if use_jk and not joker_ok:
                            st.warning("🃏 Այս փուլի ջոկերն արդեն օգտագործված է — կպահվի առանց ջոկերի։")
                        try:
                            supabase.table("predictions").insert({
                                "user_id": user_data['id'], "match_id": m['id'],
                                "pred_home": int(h), "pred_away": int(a),
                                "use_joker": joker_ok}).execute()
                            st.toast("✅ Ընդունված է և կողպված։")
                            st.rerun()
                        except Exception:
                            st.error("Արդեն կանխատեսված է։")
        st.markdown('</div>', unsafe_allow_html=True)

    for stage in STAGE_ORDER:
        smatches = [m for m in matches if m['stage'] == stage]
        jk_note = ""
        if stage in JOKER_STAGES:
            left = 0 if stage in joker_used_stage else 1
            jk_note = (f" <span style='font-size:0.95rem; color:{'#888' if left == 0 else '#FFD700'};'>"
                       f"🃏 ՋՈԿԵՐ՝ {left}/1</span>")
        st.markdown(
            f"## {STAGES[stage]} "
            f"<span style='font-size:1rem; color:#00d4ff;'>({len(smatches)}/{EXPECTED[stage]})</span>{jk_note}",
            unsafe_allow_html=True)

        # All stages render as one flat list ordered by deadline (smatches is
        # already sorted by kickoff_time). For the group stage the group letter
        # is shown as a badge on each card instead of separate group blocks, so
        # the soonest-closing game is always nearest the top — no deadline hides
        # under a "later" group.
        for m in smatches:
            render_card(m)

        # empty placeholder boxes for games not yet added (all stages, no extra text)
        remaining = EXPECTED[stage] - len(smatches)
        if remaining > 0:
            pcols = st.columns(2)
            for i in range(remaining):
                with pcols[i % 2]:
                    st.markdown(
                        "<div class='glass-card' style='opacity:0.4; border-style:dashed; padding:10px;'>"
                        "<div style='display:flex; gap:8px;'>"
                        "<div class='team-box' style='flex:1; color:#888 !important;'>❔</div>"
                        "<div class='team-box' style='flex:1; color:#888 !important;'>❔</div></div></div>",
                        unsafe_allow_html=True)


# ===================  PAGE: MEDALS  ==========================================
elif page == "ՄԵԴԱԼՆԵՐ":
    st.title("🥇 ՄԵԴԱԼՆԵՐԻ ԿԱՆԽԱՏԵՍՈՒՄ")
    # deadline is the one the ADMIN sets (settings.medal_deadline)
    _settings = supabase.table("settings").select("medal_deadline").execute().data or []
    medal_deadline = _settings[0].get('medal_deadline') if _settings else None
    deadline_passed = bool(medal_deadline) and now_utc() >= parse_dt(medal_deadline)
    already_set = bool(user_data.get('champion_pick'))   # one-time: once saved -> locked
    locked = already_set or deadline_passed

    st.markdown('<div class="glass-card"><p style="color:#FFFFFF; font-size:1.05rem;">'
                'Ընտրիր մրցաշարի <b>Չեմպիոնին (Ոսկի +30)</b>, <b>Ֆինալիստին (Արծաթ +18)</b> և '
                '<b>Բրոնզե մեդալակիրին (+12)</b>։ <b>Երեքն էլ պետք է տարբեր թիմեր լինեն։</b> '
                '<b>Ուշադրություն՝ ընտրությունը մեկանգամյա է</b> — '
                'պահպանելուց հետո այլևս հնարավոր չէ փոխել։</p></div>', unsafe_allow_html=True)
    if medal_deadline and not locked:
        st.caption(f"⏱️ Վերջնաժամկետ՝ {to_yerevan(parse_dt(medal_deadline)).strftime('%d.%m %H:%M')} (Երևան)")

    if locked:
        if already_set:
            st.success("✅ Ձեր ընտրությունը գրանցված է և կողպված է (մեկանգամյա)։")
        else:
            st.warning("🔒 Ընտրությունը փակ է — վերջնաժամկետն անցել է։")
        st.markdown(f"🥇 **Ոսկի՝** {user_data.get('champion_pick') or '—'}")
        st.markdown(f"🥈 **Արծաթ՝** {user_data.get('runnerup_pick') or '—'}")
        st.markdown(f"🥉 **Բրոնզ՝** {user_data.get('bronze_pick') or '—'}")
    else:
        BLANK = "— ընտրիր —"
        # full list in all three (stable, never resets); duplicates are blocked below
        opts = [BLANK] + COUNTRIES
        gold = st.selectbox("🥇 Չեմպիոն (Ոսկի)", opts, key="medal_gold")
        silver = st.selectbox("🥈 Ֆինալիստ (Արծաթ)", opts, key="medal_silver")
        bronze = st.selectbox("🥉 Բրոնզ", opts, key="medal_bronze")
        chosen = [x for x in (gold, silver, bronze) if x in COUNTRIES]
        dup = len(chosen) != len(set(chosen))
        if dup:
            st.warning("⚠️ Երեք մեդալների համար ընտրիր ՏԱՐԲԵՐ թիմեր։")
        st.caption("⚠️ Պահպանելուց հետո ընտրությունը կկողպվի ընդմիշտ։")
        if st.button("💾 ՊԱՀՊԱՆԵԼ ԵՎ ԿՈՂՊԵԼ"):
            picks = [gold, silver, bronze]
            if not all(p in COUNTRIES for p in picks):
                st.error("Ընտրիր բոլոր երեքը (Ոսկի, Արծաթ, Բրոնզ)։")
            elif len(set(picks)) != 3:
                st.error("Երեքն էլ պետք է տարբեր թիմեր լինեն։")
            else:
                # re-read the deadline NOW: the page may have been open past it
                dl = supabase.table("settings").select("medal_deadline").execute().data
                dlv = dl[0].get('medal_deadline') if dl else None
                if dlv and now_utc() >= parse_dt(dlv):
                    st.error("🔒 Ուշացաք — մեդալների վերջնաժամկետն անցել է։")
                    st.rerun()
                # re-read the DB so a double-click / two tabs can't overwrite a saved pick
                fresh = supabase.table("users").select("champion_pick").eq(
                    "id", user_data['id']).execute().data
                if fresh and fresh[0].get('champion_pick'):
                    st.warning("Ձեր ընտրությունն արդեն պահպանված է։")
                    st.rerun()
                supabase.table("users").update({
                    "champion_pick": gold, "runnerup_pick": silver, "bronze_pick": bronze,
                }).eq("id", user_data['id']).execute()
                st.success("✅ Պահպանված և կողպված է։")
                st.rerun()


# ===================  PAGE: MY RESULTS  ======================================
elif page == "ԱՐԴՅՈՒՆՔՆԵՐ":
    st.title("📊 ԻՄ ԱՐԴՅՈՒՆՔՆԵՐԸ")

    # --- my medal picks ---
    st.markdown(
        f"<div class='glass-card' style='padding:12px;'><b style='color:#FFD700; font-family:Orbitron;'>"
        f"🏆 ԻՄ ՉԵՄՊԻՈՆՈՒԹՅԱՆ ԿԱՆԽԱՏԵՍՈՒՄ</b><br>"
        f"🥇 {user_data.get('champion_pick') or '—'} &nbsp;&nbsp; "
        f"🥈 {user_data.get('runnerup_pick') or '—'} &nbsp;&nbsp; "
        f"🥉 {user_data.get('bronze_pick') or '—'}</div>", unsafe_allow_html=True)

    # --- my predicted group tables (built live from my predictions) ---
    st.markdown("## 📋 ԻՄ ԽՄԲԱՅԻՆ ԱՂՅՈՒՍԱԿՆԵՐԸ")
    st.caption("Կազմվում է ըստ քո կանխատեսած հաշիվների. թարմացվում է ինքնաշխատ։")
    gmatches = supabase.table("matches").select(
        "id,home_team,away_team,group_name").eq("stage", "group").execute().data or []
    myp = {p['match_id']: p for p in supabase.table("predictions").select(
        "match_id,pred_home,pred_away").eq("user_id", user_data['id']).execute().data or []}
    bygroup = {}
    for mm in gmatches:
        if mm.get('group_name'):
            bygroup.setdefault(mm['group_name'], []).append(mm)
    if not bygroup:
        st.info("Խմբային խաղերը դեռ ավելացված չեն։")
    else:
        gcols = st.columns(3)
        for i, g in enumerate(sorted(bygroup)):
            gms = bygroup[g]
            preds = [myp.get(mm['id']) for mm in gms]
            with gcols[i % 3]:
                if all(preds):
                    standings = scoring._standings(
                        [(mm['home_team'], mm['away_team'], p['pred_home'], p['pred_away'])
                         for mm, p in zip(gms, preds)])
                    html = (f"<div class='glass-card' style='padding:12px;'>"
                            f"<b style='color:#FFD700; font-family:Orbitron;'>Խումբ {g}</b>")
                    for pos, (team, stt) in enumerate(standings, start=1):
                        c = '#00ff88' if pos == 1 else ('#c0c0c0' if pos == 2 else '#E0E0E0')
                        mk = '🥇' if pos == 1 else ('🥈' if pos == 2 else f'{pos}.')
                        html += (f"<div style='display:flex; justify-content:space-between; color:{c};'>"
                                 f"<span>{mk} {team}</span><span>{stt['pts']}մ</span></div>")
                    st.markdown(html + "</div>", unsafe_allow_html=True)
                else:
                    done = sum(1 for p in preds if p)
                    st.markdown(
                        f"<div class='glass-card' style='padding:12px; opacity:0.6;'>"
                        f"<b style='color:#FFD700; font-family:Orbitron;'>Խումբ {g}</b><br>"
                        f"<small class='muted'>Կանխատեսիր բոլոր 6 խաղերը ({done}/6)՝ "
                        f"աղյուսակը տեսնելու համար</small></div>", unsafe_allow_html=True)

    st.divider()
    st.markdown("## 🧾 ԻՄ ԿԱՆԽԱՏԵՍՈՒՄՆԵՐԻ ՊԱՏՄՈՒԹՅՈՒՆ")
    rows = supabase.table("predictions").select("*, matches(*)").eq(
        "user_id", user_data['id']).execute().data or []
    # Finished games the user never predicted are scored as an automatic 0-0
    # (the "forgot to submit" rule). No row exists in the DB — we just show the
    # 0-0 here so the user sees it, with the points the engine actually counted.
    predicted_ids = {r.get('match_id') for r in rows}
    for m in (supabase.table("matches").select("*").eq("status", "finished").execute().data or []):
        if m['id'] in predicted_ids or m.get('home_score') is None or m.get('away_score') is None:
            continue
        rows.append({'match_id': m['id'], 'pred_home': 0, 'pred_away': 0, 'use_joker': False,
                     'auto': True, 'matches': m,
                     'points_earned': scoring.base_points(m['stage'], 0, 0,
                                                           m['home_score'], m['away_score'])})
    if not rows:
        st.info("Դեռևս կանխատեսումներ չկան։ Երբ մրցաշարը սկսվի՝ քո պատմությունը կհայտնվի այստեղ։")
    else:
        rows.sort(key=lambda r: (r['matches'] or {}).get('kickoff_time', ''))
        for r in rows:
            m = r['matches'] or {}
            jk = " 🃏" if r.get('use_joker') else ""
            auto_tag = " <small class='muted'>(ինքնաշխատ 0-0)</small>" if r.get('auto') else ""
            CAT = {'exact': '🎯 Ճիշտ հաշիվ', 'diff': '➕ Գոլային տարբերություն',
                   'outcome': '✅ Ճիշտ ելք', 'wrong': '❌ Սխալ'}
            if m.get('status') == 'finished':
                real = f"{m['home_score']} : {m['away_score']}"
                pe = r.get('points_earned', 0)
                cat, _ = scoring.categorize(m['stage'], r['pred_home'], r['pred_away'],
                                            m['home_score'], m['away_score'])
                col = "#00ff88" if pe > 0 else "#ff6b6b"
                badge = (f"<span style='color:{col}; font-weight:900;'>{CAT[cat]}</span><br>"
                         f"<span style='color:{col}; font-weight:900;'>+{pe} ՄԻԱՎՈՐ</span>")
            else:
                real, badge = "—", "<span class='muted'>⏳ սպասում է</span>"
            st.markdown(
                f"<div class='glass-card' style='display:flex; justify-content:space-between; align-items:center;'>"
                f"<div><b>{m.get('home_team','?')} {r['pred_home']}:{r['pred_away']}{jk} {m.get('away_team','?')}</b>{auto_tag}"
                f"<br><small class='muted'>{STAGES.get(m.get('stage'),'')} · Իրական՝ {real}</small></div>"
                f"<div style='text-align:right;'>{badge}</div></div>", unsafe_allow_html=True)


# ===================  PAGE: ANALYTICS / WIN PROBABILITY  =====================
elif page == "ՎԵՐԼՈՒԾՈՒԹՅՈՒՆ":
    import random as _random
    import math as _math
    from collections import Counter as _Counter
    N_RUNS = 1200

    st.title("📈 ՎԵՐԼՈՒԾՈՒԹՅՈՒՆ")
    st.caption(f"Հաղթելու հավանականությունը՝ {N_RUNS:,}+ սիմուլյացիայի հիման վրա, "
               f"ըստ ձեր կանխատեսման ոճի։ Թարմացվում է ինքնաշխատ՝ ամեն նոր արդյունքից հետո։")

    @st.cache_data(ttl=900, show_spinner=False)
    def _win_probabilities(version, n_runs=N_RUNS):
        users = supabase.table("users").select(
            "id, username, display_name, total_points, champion_pick, runnerup_pick, bronze_pick"
        ).eq("is_active", True).execute().data or []
        if len(users) < 2:
            return None, None
        matches = supabase.table("matches").select("*").execute().data or []
        preds = supabase.table("predictions").select(
            "user_id, match_id, pred_home, pred_away, use_joker").execute().data or []
        try:
            tr = supabase.table("tournament_result").select("*").execute().data or []
        except Exception:
            tr = []
        medals_done = bool(tr and (tr[0].get('gold') or tr[0].get('silver') or tr[0].get('bronze')))

        pred_by = {(p['user_id'], p['match_id']): p for p in preds}
        finished_ids = {m['id'] for m in matches
                        if m['status'] == 'finished' and m['home_score'] is not None}

        # bonuses the admin already entered are in the baseline points -> don't re-sim
        try:
            group_official = {r['group_name'] for r in
                              (supabase.table("group_official").select("group_name").execute().data or [])}
        except Exception:
            group_official = set()
        try:
            official_quals = {r['team_name'] for r in
                              (supabase.table("qualifiers").select("team_name").execute().data or [])}
        except Exception:
            official_quals = set()

        # goal models: home/away calibrated to real games; neutral for knockouts
        fin = [(m['home_score'], m['away_score']) for m in matches if m['id'] in finished_ids]
        if fin:
            lamH = max(0.2, sum(h for h, _ in fin) / len(fin))
            lamA = max(0.2, sum(a for _, a in fin) / len(fin))
        else:
            lamH, lamA = 1.4, 1.1
        lamN = (lamH + lamA) / 2.0

        # scoreline distributions used to PROJECT a user's unmade picks (their own
        # style, smoothed toward the whole pool when they have few predictions)
        pool_lines = [(p['pred_home'], p['pred_away']) for p in preds]
        user_lines = {}
        for p in preds:
            user_lines.setdefault(p['user_id'], []).append((p['pred_home'], p['pred_away']))
        uids = [u['id'] for u in users]
        now_pts = {u['id']: (u.get('total_points') or 0) for u in users}
        nm = {u['id']: (u.get('display_name') or u.get('username') or u['id']) for u in users}

        # full 2026 draw (mirrors seed_groups.py) -> structure for ALL 72 group games
        GROUPS = {
            "A": ["Մեքսիկա", "Հարավային Աֆրիկա", "Հարավային Կորեա", "Չեխիա"],
            "B": ["Կանադա", "Բոսնիա և Հերցեգովինա", "Կատար", "Շվեյցարիա"],
            "C": ["Բրազիլիա", "Մարոկկո", "Հաիթի", "Շոտլանդիա"],
            "D": ["ԱՄՆ", "Պարագվայ", "Ավստրալիա", "Թուրքիա"],
            "E": ["Գերմանիա", "Կյուրասաո", "Կոտ դ’Իվուար", "Էկվադոր"],
            "F": ["Նիդեռլանդներ", "Ճապոնիա", "Շվեդիա", "Թունիս"],
            "G": ["Բելգիա", "Եգիպտոս", "Իրան", "Նոր Զելանդիա"],
            "H": ["Իսպանիա", "Կաբո Վերդե", "Սաուդյան Արաբիա", "Ուրուգվայ"],
            "I": ["Ֆրանսիա", "Սենեգալ", "Իրաք", "Նորվեգիա"],
            "J": ["Արգենտինա", "Ալժիր", "Ավստրիա", "Հորդանան"],
            "K": ["Պորտուգալիա", "Կոնգո ԴՀ", "Ուզբեկստան", "Կոլումբիա"],
            "L": ["Անգլիա", "Խորվաթիա", "Գանա", "Պանամա"],
        }
        PAIRS = [(0, 1), (2, 3), (0, 2), (1, 3), (0, 3), (1, 2)]
        KO_STAGES = [('r32', 16), ('r16', 8), ('qf', 4), ('sf', 2), ('third', 1), ('final', 1)]

        real_group = {}
        for m in matches:
            if m['stage'] == 'group' and m.get('group_name'):
                real_group[(m['group_name'], frozenset((m['home_team'], m['away_team'])))] = m
        # a locked game can no longer be predicted -> missing = 0-0 (the real rule)
        locked_real = set()
        for m in matches:
            try:
                lk = parse_dt(m['lock_time'])
            except Exception:
                lk = None
            if m['status'] != 'finished' and lk and now_utc() >= lk:
                locked_real.add(m['id'])
        real_ko = _Counter(m['stage'] for m in matches if m['stage'] in dict(KO_STAGES))

        rng = _random.Random(20260615)   # fixed seed -> numbers stable across reruns

        def poisson(lam):
            L = _math.exp(-lam); k = 0; pr = 1.0
            while True:
                k += 1; pr *= rng.random()
                if pr <= L:
                    return k - 1

        def proj_pick(uid):
            lines = user_lines.get(uid)
            if lines and rng.random() < len(lines) / (len(lines) + 5):
                return rng.choice(lines)          # their own style
            if pool_lines:
                return rng.choice(pool_lines)     # fall back to the room's style
            return (rng.randint(0, 3), rng.randint(0, 3))

        # medals drawn from teams people actually rated (popularity-weighted),
        # restricted to the teams that qualified in THAT run
        cont_w = (_Counter(u.get('champion_pick') for u in users if u.get('champion_pick'))
                  + _Counter(u.get('runnerup_pick') for u in users if u.get('runnerup_pick'))
                  + _Counter(u.get('bronze_pick') for u in users if u.get('bronze_pick')))

        def draw_medals(qualset):
            pool = [(t, w) for t, w in cont_w.items() if (not qualset or t in qualset)]
            if len(pool) < 3:
                pool = [(t, 1) for t in qualset] if qualset else [(t, 1) for t in cont_w]
            out = []
            for _ in range(3):
                if not pool:
                    break
                tot = sum(w for _, w in pool); r = rng.random() * tot; acc = 0
                for j, (it, w) in enumerate(pool):
                    acc += w
                    if r <= acc:
                        out.append(it); pool.pop(j); break
            while len(out) < 3:
                out.append(None)
            return out

        GW, GR, QB = scoring.GROUP_WINNER_BONUS, scoring.GROUP_RUNNERUP_BONUS, scoring.QUALIFY_BONUS
        _stand = scoring._standings
        cat = scoring.categorize
        win = {u: 0 for u in uids}
        top3 = {u: 0 for u in uids}
        totals = {u: [] for u in uids}

        for _ in range(n_runs):
            score = dict(now_pts)
            thirds_sim = []
            group_win = {}
            user_quals = {u: set() for u in uids}
            user_thirds = {u: [] for u in uids}
            # ---- GROUP STAGE: all 72 games + group/qualifier bonus ----
            for g, gteams in GROUPS.items():
                actual_rows = []
                user_rows = {u: [] for u in uids}
                for (i, j) in PAIRS:
                    h, a = gteams[i], gteams[j]
                    rm = real_group.get((g, frozenset((h, a))))
                    is_fin = bool(rm and rm['id'] in finished_ids)
                    if is_fin:
                        oh, oa, ah, aa = rm['home_team'], rm['away_team'], rm['home_score'], rm['away_score']
                    else:
                        oh, oa, ah, aa = h, a, poisson(lamH), poisson(lamA)
                    actual_rows.append((oh, oa, ah, aa))
                    for uid in uids:
                        if rm and pred_by.get((uid, rm['id'])):
                            p = pred_by[(uid, rm['id'])]
                            ho, ao, ph, pa = rm['home_team'], rm['away_team'], p['pred_home'], p['pred_away']
                        elif rm and rm['id'] in locked_real:
                            ho, ao, ph, pa = rm['home_team'], rm['away_team'], 0, 0
                        else:
                            ph, pa = proj_pick(uid); ho, ao = h, a
                        user_rows[uid].append((ho, ao, ph, pa))
                        if not is_fin:        # finished games already counted in baseline
                            rhh, raa = (ah, aa) if (ho, ao) == (oh, oa) else (aa, ah)
                            _, bp = cat('group', ph, pa, rhh, raa)
                            score[uid] += bp
                st_act = _stand(actual_rows)
                if g not in group_official and len(st_act) >= 2:
                    group_win[g] = (st_act[0][0], st_act[1][0])
                if len(st_act) >= 3:
                    thirds_sim.append((st_act[2][0], st_act[2][1]))
                for uid in uids:
                    pst = _stand(user_rows[uid])
                    if pst:
                        user_quals[uid].add(pst[0][0])
                    if len(pst) >= 2:
                        user_quals[uid].add(pst[1][0])
                    if len(pst) >= 3:
                        user_thirds[uid].append((pst[2][0], pst[2][1]))
                    if g in group_win:
                        w_, r_ = group_win[g]
                        if pst and pst[0][0] == w_: score[uid] += GW
                        if len(pst) >= 2 and pst[1][0] == r_: score[uid] += GR
            # ---- QUALIFIER bonus (best-8 thirds, like the engine) ----
            if official_quals:
                off_quals = official_quals
            else:
                best_thirds = sorted(thirds_sim, key=lambda x: (x[1]['pts'], x[1]['gd'], x[1]['gf']),
                                     reverse=True)[:8]
                off_quals = {t for wr in group_win.values() for t in wr} | {t for t, _ in best_thirds}
                for uid in uids:
                    ut = sorted(user_thirds[uid], key=lambda x: (x[1]['pts'], x[1]['gd'], x[1]['gf']),
                                reverse=True)[:8]
                    uq = user_quals[uid] | {t for t, _ in ut}
                    score[uid] += QB * len(uq & off_quals)
            # ---- KNOCKOUTS: real games + synthetic fillers (escalating tiers) ----
            for m in matches:
                if m['stage'] in ('r32', 'r16', 'qf', 'sf', 'third', 'final') and m['id'] not in finished_ids:
                    rh, ra = poisson(lamN), poisson(lamN)
                    for uid in uids:
                        p = pred_by.get((uid, m['id']))
                        if p:
                            ph, pa = p['pred_home'], p['pred_away']
                        elif m['id'] in locked_real:
                            ph, pa = 0, 0
                        else:
                            ph, pa = proj_pick(uid)
                        _, bp = cat(m['stage'], ph, pa, rh, ra)
                        score[uid] += bp
            for stg, cnt in KO_STAGES:
                for _g in range(max(0, cnt - real_ko.get(stg, 0))):
                    rh, ra = poisson(lamN), poisson(lamN)
                    for uid in uids:
                        ph, pa = proj_pick(uid)
                        _, bp = cat(stg, ph, pa, rh, ra)
                        score[uid] += bp
            # ---- MEDALS ----
            if not medals_done:
                gm, sm, bm = draw_medals(off_quals)
                for u in users:
                    uid = u['id']
                    if u.get('champion_pick') == gm: score[uid] += scoring.MEDAL_GOLD
                    if u.get('runnerup_pick') == sm: score[uid] += scoring.MEDAL_SILVER
                    if u.get('bronze_pick') == bm:   score[uid] += scoring.MEDAL_BRONZE
            ranked = sorted(uids, key=lambda u: score[u], reverse=True)
            win[ranked[0]] += 1
            for u in ranked[:3]:
                top3[u] += 1
            for u in uids:
                totals[u].append(score[u])

        rows = []
        for u in users:
            uid = u['id']; ts = sorted(totals[uid]); n = len(ts)
            rows.append({'name': nm[uid], 'now': now_pts[uid],
                         'win': 100.0 * win[uid] / n_runs, 'top3': 100.0 * top3[uid] / n_runs,
                         'proj': ts[n // 2], 'lo': ts[int(0.05 * n)], 'hi': ts[min(n - 1, int(0.95 * n))]})
        df = pd.DataFrame(rows).sort_values(['win', 'proj'], ascending=False).reset_index(drop=True)

        pat = {}
        for u in users:
            uid = u['id']; lines = user_lines.get(uid, [])
            if lines:
                n = len(lines)
                sig = _Counter(lines).most_common(1)[0][0]
                pat[uid] = {'name': nm[uid], 'n': n,
                            'avg': sum(h + a for h, a in lines) / n,
                            'draw': 100.0 * sum(1 for h, a in lines if h == a) / n,
                            'fav': 100.0 * sum(1 for h, a in lines if h > a) / n,
                            'sig': f"{sig[0]}-{sig[1]}"}
            else:
                pat[uid] = {'name': nm[uid], 'n': 0, 'avg': 0, 'draw': 0, 'fav': 0, 'sig': '—'}
        return df, pat

    _av = supabase.table("users").select("total_points").eq("is_active", True).execute().data or []
    _pc = supabase.table("predictions").select("id").execute().data or []
    version = f"{sum((u.get('total_points') or 0) for u in _av)}-{len(_pc)}"

    with st.spinner("Հաշվարկվում է հաղթելու հավանականությունը..."):
        df, pat = _win_probabilities(version)

    if df is None or df.empty:
        st.info("Դեռ բավարար տվյալներ չկան սիմուլյացիայի համար։")
    else:
        st.markdown("### 🎲 ՀԱՂԹԵԼՈՒ ՀԱՎԱՆԱԿԱՆՈՒԹՅՈՒՆ")
        st.caption("Ընթացիկ տեղը կարող է խաբուսիկ լինի. դեռ շատ միավորներ խաղում են (մեդալներ, "
                   "առաջիկա խաղեր)։ 🚀 = ցածր տեղ, բայց հաղթելու լուրջ շանս։")
        maxwin = max(df['win'].max(), 1e-9)
        topnow = max(df['now'].max(), 1)
        for i, r in df.iterrows():
            rank = i + 1
            w = r['win']
            barw = max(2, int(100 * w / maxwin))
            col = ("#00ff88" if rank == 1 else "#00d4ff" if rank <= 3
                   else "#FFD700" if w >= 5 else "#9aa")
            spark = " 🚀" if (rank > 3 and r['now'] < 0.7 * topnow and w >= 5) else ""
            st.markdown(
                f"<div class='glass-card' style='padding:10px 14px; margin-bottom:8px;'>"
                f"<div style='display:flex; justify-content:space-between; align-items:center;'>"
                f"<span style='font-weight:900; color:#fff; font-size:1.05rem;'>{rank}. {r['name'].upper()}{spark}</span>"
                f"<span style='font-family:Orbitron; color:{col}; font-weight:900; font-size:1.15rem;'>{w:.1f}%</span></div>"
                f"<div style='background:rgba(255,255,255,0.07); border-radius:6px; height:11px; margin:7px 0;'>"
                f"<div style='width:{barw}%; height:11px; border-radius:6px; "
                f"background:linear-gradient(90deg,#00d4ff,{col});'></div></div>"
                f"<small class='muted'>Հիմա՝ {int(r['now'])}մ · 🥉 Եռյակում՝ {r['top3']:.0f}% · "
                f"🔮 Կանխատեսվող՝ {int(r['proj'])}մ ({int(r['lo'])}–{int(r['hi'])})</small></div>",
                unsafe_allow_html=True)

        st.divider()
        st.markdown("### 🧬 ԿԱՆԽԱՏԵՍՄԱՆ ՈՃԵՐ")
        me = pat.get(user_data['id'])
        if me and me['n']:
            st.caption(f"Քո ստորագրությունը՝ հիմնված {me['n']} կանխատեսման վրա "
                       f"(ճշտվում է՝ որքան շատ կանխատեսես)։")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🎯 Միջ. գոլ/խաղ", f"{me['avg']:.1f}")
            c2.metric("🤝 Ոչ-ոքի", f"{me['draw']:.0f}%")
            c3.metric("🏠 Ֆավորիտ", f"{me['fav']:.0f}%")
            c4.metric("✍️ Ստորագրություն", me['sig'])
        else:
            st.info("Դեռ չունես կանխատեսումներ՝ ոճդ ցույց տալու համար։")

        st.markdown("#### Բոլորի ոճերը")
        pdf = pd.DataFrame([pat[u] for u in pat])
        pdf = pdf[pdf['n'] > 0].sort_values('n', ascending=False)
        if not pdf.empty:
            pdf = pdf[['name', 'n', 'avg', 'draw', 'fav', 'sig']].copy()
            pdf['avg'] = pdf['avg'].round(1)
            pdf['draw'] = pdf['draw'].round(0).astype(int).astype(str) + '%'
            pdf['fav'] = pdf['fav'].round(0).astype(int).astype(str) + '%'
            pdf.columns = ["Մասնակից", "Կանխ.", "Միջ. գոլ", "🤝 Ոչ-ոքի", "🏠 Ֆավորիտ", "✍️ Ստորագր."]
            st.dataframe(pdf, use_container_width=True, hide_index=True,
                         height=min(600, 60 + 35 * len(pdf)))

        st.caption("ℹ️ Սիմուլյացիան ներառում է ԲՈԼՈՐ մնացած խաղերը՝ խմբային փուլ (72 խաղ) + "
                   "խմբային ու որակավորման բոնուսներ + բոլոր փլեյ-օֆ փուլերը (աճող միավորներ՝ "
                   "մինչև եզրափակիչ 36) + մեդալներ։ Թիմերը՝ հավասար ուժի, արդյունքները՝ ըստ իրական "
                   "խաղերի միջինի, մեդալները՝ ըստ մասնակիցների ընտրած ֆավորիտների։ Ապագա խաղերի "
                   "կանխատեսումները գնահատվում են ձեր ոճով։")


# ===================  PAGE: ADMIN  ===========================================
elif page == "ԱԴՄԻՆ" and is_admin:
    st.title("⚡ ՀԱՄԱԿԱՐԳԻ ԿԱՌԱՎԱՐՈՒՄ")
    tab_open, tab_results, tab_fix, tab_official, tab_users, tab_stats = st.tabs(
        ["➕ ԲԱՑԵԼ ԽԱՂԵՐ", "📝 ՄՈՒՏՔԱԳՐԵԼ ԱՐԴՅՈՒՆՔ", "✏️ ՈՒՂՂԵԼ",
         "🏁 ՊԱՇՏՈՆԱԿԱՆ ԱՐԴՅՈՒՆՔ", "👥 ՄԱՍՆԱԿԻՑՆԵՐ", "📊 ՎԵՐԼՈՒԾՈՒԹՅՈՒՆ"])

    # ---- Tab 1: open new matches -------------------------------------------
    with tab_open:
        st.subheader("Բացել նոր խաղ")
        st.caption("Թիմերն ընտրիր ցանկից (նույն 48 անունները, ինչ մեդալներում)՝ "
                   "այսպես անունները միշտ ճիշտ կհամընկնեն, սխալ չի լինի։")
        with st.form("open_match", clear_on_submit=True):
            stage = st.selectbox("Փուլ", STAGE_ORDER, format_func=lambda s: STAGES[s])
            grp = st.text_input("Խումբ (միայն խմբային փուլի համար, օր. A)", max_chars=2)
            c1, c2 = st.columns(2)
            home = c1.selectbox("Տանտեր թիմ", ["—"] + COUNTRIES)
            away = c2.selectbox("Հյուր թիմ", ["—"] + COUNTRIES)
            d1, d2 = st.columns(2)
            kdate = d1.date_input("📅 Փակման ամսաթիվ (Երևան)")
            ktime = d2.time_input("🕓 Փակման ժամ (Երևան)")
            st.caption("⏱️ Ժամը՝ Երևանի ժամանակով։ Կանխատեսումները կփակվեն այս պահին։")
            if st.form_submit_button("✅ ԲԱՑԵԼ ԽԱՂԸ"):
                if home in COUNTRIES and away in COUNTRIES and home != away:
                    local = YEREVAN.localize(datetime.combine(kdate, ktime))
                    ko_iso = local.astimezone(pytz.UTC).isoformat()
                    supabase.table("matches").insert({
                        "home_team": home, "away_team": away, "stage": stage,
                        "group_name": (grp.strip().upper() or None) if stage == "group" else None,
                        "kickoff_time": ko_iso, "lock_time": ko_iso, "status": "scheduled"}).execute()
                    st.success(f"✅ Բացվեց՝ {home} – {away}  "
                               f"({local.strftime('%d.%m %H:%M')} Երևան)")
                elif home == away and home in COUNTRIES:
                    st.error("Տանտերն ու հյուրը պետք է տարբեր թիմեր լինեն։")
                else:
                    st.error("Ընտրիր երկու թիմերը ցանկից։")

    # ---- Tab 2: enter results ----------------------------------------------
    with tab_results:
        st.subheader("Մուտքագրել ավարտված խաղի հաշիվը")
        unfinished = supabase.table("matches").select("*").eq(
            "status", "scheduled").order("kickoff_time").execute().data or []
        if not unfinished:
            st.info("Բոլոր բացված խաղերը մուտքագրված են։")
        else:
            opts = {f"{m['home_team']} vs {m['away_team']} ({STAGES[m['stage']]})": m for m in unfinished}
            sel = st.selectbox("Ընտրիր խաղը", list(opts.keys()))
            m = opts[sel]
            st.caption("⏱️ Մուտքագրիր 90 րոպեի (+ փոխհատուցման) հաշիվը։ Այս հաշիվով են "
                       "հաշվարկվում կանխատեսման միավորները։")
            c1, c2 = st.columns(2)
            hs = c1.number_input(f"{m['home_team']}", min_value=0, step=1, key="rh")
            as_ = c2.number_input(f"{m['away_team']}", min_value=0, step=1, key="ra")
            knockout = m['stage'] != 'group'
            winner = "—"
            if knockout:
                st.caption("🏆 Նոկ-աութ խաղ․ նշիր ով անցավ հաջորդ փուլ "
                           "(լրաց. ժամանակ/պենալտիից հետո)։ Միավորների հաշվարկը մնում է 90 րոպեով։ "
                           "ℹ️ Սա տեղեկատվական է — մեդալները շնորհվում են «🏁 Պաշտոնական արդյունք» բաժնում։")
                winner = st.selectbox("Ով անցավ հաջորդ փուլ",
                                      ["—", m['home_team'], m['away_team']], key="rwin")
            if st.button("🔥 ՀԱՍՏԱՏԵԼ ԵՎ ՎԵՐԱՀԱՇՎԱՐԿԵԼ"):
                upd = {"home_score": int(hs), "away_score": int(as_), "status": "finished"}
                if knockout and winner in (m['home_team'], m['away_team']):
                    upd["winner_team"] = winner
                supabase.table("matches").update(upd).eq("id", m['id']).execute()
                with st.spinner("Վերահաշվարկ..."):
                    msg = scoring.recalculate(supabase)
                st.success(f"✅ {m['home_team']} {hs}:{as_} {m['away_team']} — {msg}")

    # ---- Tab 3: fix anything -----------------------------------------------
    with tab_fix:
        st.subheader("Ուղղել խաղ (թիմ, հաշիվ, ժամ, կարգավիճակ)")
        allm = supabase.table("matches").select("*").order("kickoff_time", desc=True).execute().data or []
        if allm:
            opts = {f"#{m['id']} {m['home_team']} vs {m['away_team']}": m for m in allm}
            sel = st.selectbox("Ընտրիր խաղը", list(opts.keys()), key="fixsel")
            m = opts[sel]
            # if anyone already predicted this game, the TEAMS are locked — changing
            # them would silently re-interpret every existing prediction.
            pred_cnt = supabase.table("predictions").select("id", count="exact").eq(
                "match_id", m['id']).execute().count or 0
            has_preds = pred_cnt > 0

            c1, c2 = st.columns(2)
            if has_preds:
                c1.markdown(f"**Տանտեր՝** {m['home_team']}")
                c2.markdown(f"**Հյուր՝** {m['away_team']}")
                home, away = m['home_team'], m['away_team']
                st.caption(f"🔒 Թիմերը կողպված են — այս խաղն ունի {pred_cnt} կանխատեսում։ "
                           "Թիմը փոխելը կխեղաթյուրեր մասնակիցների կանխատեսումները։ "
                           "Սխալ թիմերի դեպքում՝ ջնջիր ու նորից բացիր խաղը։")
            else:
                hi = COUNTRIES.index(m['home_team']) if m['home_team'] in COUNTRIES else 0
                ai = COUNTRIES.index(m['away_team']) if m['away_team'] in COUNTRIES else 0
                home = c1.selectbox("Տանտեր", COUNTRIES, index=hi, key="fixhome")
                away = c2.selectbox("Հյուր", COUNTRIES, index=ai, key="fixaway")

            cur_ko = to_yerevan(parse_dt(m['kickoff_time']))
            d1, d2 = st.columns(2)
            kdate = d1.date_input("📅 Փակման ամսաթիվ (Երևան)", value=cur_ko.date(), key="fixdate")
            ktime = d2.time_input("🕓 Փակման ժամ (Երևան)", value=cur_ko.time(), key="fixtime")
            c3, c4 = st.columns(2)
            hs = c3.number_input("Հաշիվ (տանտեր, 90 րոպե)", min_value=0, step=1, value=m.get('home_score') or 0)
            as_ = c4.number_input("Հաշիվ (հյուր, 90 րոպե)", min_value=0, step=1, value=m.get('away_score') or 0)
            status = st.selectbox("Կարգավիճակ", ["scheduled", "finished"],
                                  index=["scheduled", "finished"].index(m['status']))
            winner = "—"
            if m['stage'] != 'group':
                wopts = ["—", home, away]
                wcur = m.get('winner_team')
                widx = wopts.index(wcur) if wcur in wopts else 0
                winner = st.selectbox("🏆 Ով անցավ հաջորդ փուլ", wopts, index=widx, key="fixwin")
            if st.button("💾 ՊԱՀՊԱՆԵԼ ՈՒՂՂՈՒՄԸ"):
                if (not has_preds) and (home == away):
                    st.error("Տանտերն ու հյուրը պետք է տարբեր թիմեր լինեն։")
                else:
                    ko_iso = YEREVAN.localize(datetime.combine(kdate, ktime)).astimezone(pytz.UTC).isoformat()
                    upd = {"status": status, "kickoff_time": ko_iso, "lock_time": ko_iso}
                    if not has_preds:                      # teams only changeable pre-predictions
                        upd["home_team"], upd["away_team"] = home, away
                    if status == "finished":
                        upd["home_score"], upd["away_score"] = int(hs), int(as_)
                    if m['stage'] != 'group':
                        upd["winner_team"] = winner if winner in (home, away) else None
                    supabase.table("matches").update(upd).eq("id", m['id']).execute()
                    with st.spinner("Վերահաշվարկ..."):
                        msg = scoring.recalculate(supabase)
                    st.success(f"✅ Ուղղված է — {msg}")

    # ---- Tab 4: OFFICIAL results -> bonus points ---------------------------
    with tab_official:
        st.subheader("Պաշտոնական արդյունքներ → բոնուս միավորներ")
        st.caption("Բոնուսները հաշվարկվում են ՄԻԱՅՆ այստեղ մուտքագրածից։ "
                   "Քանի դեռ չես լրացրել՝ բոլորի բոնուսը 0 է։")

        # --- medal-pick deadline ---
        with st.expander("⏱️ Մեդալների ընտրության վերջնաժամկետ"):
            _s = supabase.table("settings").select("*").execute().data or []
            cur_dl = _s[0].get('medal_deadline') if _s else None
            if cur_dl:
                st.caption(f"Ընթացիկ՝ {to_yerevan(parse_dt(cur_dl)).strftime('%d.%m %H:%M')} (Երևան)")
            dd1, dd2 = st.columns(2)
            mdate = dd1.date_input("📅 Ամսաթիվ (Երևան)", key="mdldate")
            mtime = dd2.time_input("🕓 Ժամ (Երևան)", key="mdltime")
            if st.button("💾 Պահպանել վերջնաժամկետը"):
                iso = YEREVAN.localize(datetime.combine(mdate, mtime)).astimezone(pytz.UTC).isoformat()
                supabase.table("settings").upsert({"id": 1, "medal_deadline": iso}).execute()
                st.success("✅ Պահպանված է։")
                st.rerun()

        # --- per-group official winner / runner-up ---
        gmatches = supabase.table("matches").select(
            "home_team,away_team,group_name").eq("stage", "group").execute().data or []
        gteams = {}
        for mm in gmatches:
            if mm.get('group_name'):
                s = gteams.setdefault(mm['group_name'], set())
                s.add(mm['home_team']); s.add(mm['away_team'])
        official = {r['group_name']: r for r in
                    (supabase.table("group_official").select("*").execute().data or [])}

        st.markdown("### 📦 Խմբերի պաշտոնական արդյունք")
        if not gteams:
            st.info("Դեռ խմբային խաղեր չկան։")
        else:
            for g in sorted(gteams):
                teams = sorted(gteams[g])
                cur = official.get(g, {})
                with st.container(border=True):
                    st.markdown(f"**Խումբ {g}**" + (
                        f" — ✅ {cur.get('winner_team')} / {cur.get('runnerup_team')}" if cur else ""))
                    wc, rc = st.columns(2)
                    wi = teams.index(cur['winner_team']) + 1 if cur.get('winner_team') in teams else 0
                    ri = teams.index(cur['runnerup_team']) + 1 if cur.get('runnerup_team') in teams else 0
                    win = wc.selectbox("1-ին (հաղթող)", ["—"] + teams, index=wi, key=f"gw_{g}")
                    run = rc.selectbox("2-րդ", ["—"] + teams, index=ri, key=f"gr_{g}")
                    if st.button(f"💾 Պահպանել Խումբ {g}", key=f"gsave_{g}"):
                        if win in teams and run in teams and win != run:
                            supabase.table("group_official").upsert({
                                "group_name": g, "winner_team": win, "runnerup_team": run}).execute()
                            with st.spinner("Վերահաշվարկ..."):
                                msg = scoring.recalculate(supabase)
                            st.success(f"✅ Խումբ {g} — {msg}")
                            st.rerun()
                        else:
                            st.error("Ընտրիր երկու տարբեր թիմ։")

        # --- qualifiers (the 32 that reached the Round of 32) ---
        st.markdown("### ✅ Անցած թիմերը (1/16-ի փուլ)")
        all_teams = sorted({t for s in gteams.values() for t in s}) or COUNTRIES
        cur_quals = [r['team_name'] for r in
                     (supabase.table("qualifiers").select("team_name").execute().data or [])]
        picked = st.multiselect("Ընտրիր անցած թիմերը (մինչև 32)", all_teams,
                                default=[t for t in cur_quals if t in all_teams], key="qmulti")
        st.caption(f"Ընտրված՝ {len(picked)} թիմ")
        if st.button("💾 Պահպանել անցած թիմերը և վերահաշվարկել"):
            # Upsert the selected teams FIRST (so the list is never momentarily
            # empty), then drop only the ones no longer selected. No data-loss gap.
            if picked:
                supabase.table("qualifiers").upsert(
                    [{"team_name": t} for t in picked]).execute()
                supabase.table("qualifiers").delete().not_.in_("team_name", picked).execute()
            else:
                supabase.table("qualifiers").delete().neq("team_name", "").execute()
            with st.spinner("Վերահաշվարկ..."):
                msg = scoring.recalculate(supabase)
            st.success(f"✅ {len(picked)} թիմ պահպանված — {msg}")

        # --- official medals (Gold/Silver/Bronze) ---
        st.markdown("### 🥇 Պաշտոնական մեդալներ")
        st.caption("Մուտքագրելը գործարկում է մեդալների բոնուսը (Ոսկի +30, Արծաթ +18, Բրոնզ +12)։")
        tr = supabase.table("tournament_result").select("*").execute().data or []
        cur_m = tr[0] if tr else {}
        mo = ["—"] + COUNTRIES
        gi = mo.index(cur_m['gold']) if cur_m.get('gold') in COUNTRIES else 0
        si = mo.index(cur_m['silver']) if cur_m.get('silver') in COUNTRIES else 0
        bi = mo.index(cur_m['bronze']) if cur_m.get('bronze') in COUNTRIES else 0
        gold = st.selectbox("🥇 Ոսկի (չեմպիոն)", mo, index=gi, key="ogold")
        silver = st.selectbox("🥈 Արծաթ (ֆինալիստ)", mo, index=si, key="osilver")
        bronze = st.selectbox("🥉 Բրոնզ (3-րդ տեղ)", mo, index=bi, key="obronze")
        if st.button("💾 Պահպանել մեդալները և վերահաշվարկել"):
            picks = [p for p in (gold, silver, bronze) if p in COUNTRIES]
            if len(set(picks)) != len(picks):
                st.error("Մեդալների թիմերը պետք է տարբեր լինեն։")
            else:
                supabase.table("tournament_result").upsert({
                    "id": 1,
                    "gold":   gold   if gold   in COUNTRIES else None,
                    "silver": silver if silver in COUNTRIES else None,
                    "bronze": bronze if bronze in COUNTRIES else None}).execute()
                with st.spinner("Վերահաշվարկ..."):
                    msg = scoring.recalculate(supabase)
                st.success(f"✅ Մեդալները պահպանված — {msg}")

    # ---- Tab 5: activate / deactivate participants -------------------------
    with tab_users:
        st.subheader("Միացնել / Անջատել մասնակցին")
        st.caption("Անջատված մասնակիցը չի երևում աղյուսակում և չի կարող մուտք գործել։")
        allu = supabase.table("users").select(
            "id, username, display_name, email, is_active, total_points"
        ).order("username").execute().data or []
        if allu:
            def _lbl(u):
                nm = u.get('display_name') or u.get('username')
                flag = "✅ ԱԿՏԻՎ" if u.get('is_active', True) else "🚫 ԱՆՋԱՏՎԱԾ"
                return f"{nm} ({u['email']}) — {flag}"
            opts = {_lbl(u): u for u in allu}
            sel = st.selectbox("Ընտրիր մասնակցին", list(opts.keys()), key="usersel")
            u = opts[sel]
            active = u.get('is_active', True)
            st.markdown(f"**Կարգավիճակ՝** {'✅ Ակտիվ' if active else '🚫 Անջատված'} &nbsp;|&nbsp; "
                        f"**Միավոր՝** {u.get('total_points', 0)}")
            if st.button("🚫 ԱՆՋԱՏԵԼ ՄԱՍՆԱԿՑԻՆ" if active else "✅ ՄԻԱՑՆԵԼ ՄԱՍՆԱԿՑԻՆ"):
                supabase.table("users").update(
                    {"is_active": not active}).eq("id", u['id']).execute()
                st.success("✅ Թարմացված է։")
                st.rerun()
            inactive = [u for u in allu if not u.get('is_active', True)]
            if inactive:
                st.divider()
                st.markdown("**🚫 Անջատված մասնակիցներ՝**")
                for u in inactive:
                    st.markdown(f"- {u.get('display_name') or u['username']} ({u['email']})")

    # ---- Tab 6: participation analytics (read-only) ------------------------
    with tab_stats:
        st.subheader("📊 Մասնակցության վերլուծություն")
        st.caption("Ո՞վ է կանխատեսել առաջիկա խաղերը և ո՞վ՝ ոչ։ Միայն ընթերցում է — "
                   "ոչ մի միավոր/կանխատեսում չի փոխվում։")

        # active participants only (deactivated users can't predict anyway)
        a_users = supabase.table("users").select(
            "id, display_name, username, email").eq("is_active", True).execute().data or []
        total_active = len(a_users)
        name_of = {u['id']: (u.get('display_name') or u.get('username') or u['email']) for u in a_users}
        email_of = {u['id']: u['email'] for u in a_users}
        active_ids = set(name_of.keys())

        all_preds = supabase.table("predictions").select("user_id, match_id").execute().data or []

        # upcoming = open (scheduled) AND not yet locked → still predictable
        allm = supabase.table("matches").select("*").order("kickoff_time").execute().data or []
        upcoming = [m for m in allm
                    if m.get('status') != 'finished' and now_utc() < parse_dt(m['lock_time'])]

        # --- overall picture ---
        users_with_any = {p['user_id'] for p in all_preds} & active_ids
        st.markdown(f"**Ակտիվ մասնակից՝** {total_active} &nbsp;|&nbsp; "
                    f"**Գոնե մեկ կանխատեսում արել է՝** {len(users_with_any)} &nbsp;|&nbsp; "
                    f"**Բացակա (0 կանխատեսում)՝** {total_active - len(users_with_any)}")
        st.divider()

        st.markdown(f"### ⏳ Առաջիկա խաղեր ({len(upcoming)})")
        if not upcoming:
            st.info("Այս պահին բաց, դեռ չփակված խաղ չկա։")
        for m in upcoming:
            predicted_ids = {p['user_id'] for p in all_preds
                             if p['match_id'] == m['id'] and p['user_id'] in active_ids}
            missing = [u for u in a_users if u['id'] not in predicted_ids]
            done = total_active - len(missing)
            grp = f"📦 {m['group_name']} · " if m.get('group_name') else ""
            dl = to_yerevan(parse_dt(m['lock_time'])).strftime('%d.%m %H:%M')
            with st.expander(
                    f"{flag(m['home_team'])}{m['home_team']} – {m['away_team']}{flag(m['away_team'])}  "
                    f"·  ✅ {done}/{total_active}  ·  ⏳ {len(missing)} բացակա  "
                    f"·  {grp}🔒 {dl}"):
                if not missing:
                    st.success("🎉 Բոլորը կանխատեսել են այս խաղը։")
                else:
                    st.caption("Չեն կանխատեսել (հիշեցնելու համար)՝")
                    for u in sorted(missing, key=lambda x: name_of[x['id']]):
                        st.markdown(f"- {name_of[u['id']]} — `{email_of[u['id']]}`")
                    emails = "; ".join(email_of[u['id']] for u in missing)
                    st.text_area("✉️ Email-եր (պատճենիր)", emails, height=68, key=f"em_{m['id']}")

        # --- who hasn't predicted ANY upcoming game ---
        if upcoming:
            up_ids = {m['id'] for m in upcoming}
            predicted_any_up = {p['user_id'] for p in all_preds
                                if p['match_id'] in up_ids and p['user_id'] in active_ids}
            no_up = [u for u in a_users if u['id'] not in predicted_any_up]
            st.divider()
            st.markdown(f"### 🔕 Ոչ մի առաջիկա խաղ չեն կանխատեսել ({len(no_up)})")
            if not no_up:
                st.success("🎉 Բոլոր ակտիվ մասնակիցները կանխատեսել են գոնե մեկ առաջիկա խաղ։")
            else:
                for u in sorted(no_up, key=lambda x: name_of[x['id']]):
                    st.markdown(f"- {name_of[u['id']]} — `{email_of[u['id']]}`")
                st.text_area("✉️ Բոլոր բացակաների email-երը",
                             "; ".join(email_of[u['id']] for u in no_up),
                             height=80, key="em_none_up")
