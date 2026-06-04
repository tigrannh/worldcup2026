"""Load all 72 World Cup 2026 group-stage games (real draw) into `matches`.

Each group of 4 teams -> 6 games (round-robin). All open for prediction now,
all locking at ONE deadline (default: tournament start, edit LOCK_YEREVAN below).
You set real per-game times / enter scores later in the admin panel.

Run once:  python seed_groups.py
"""
import os
from datetime import datetime
import pytz
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(override=True)
sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])

YEREVAN = pytz.timezone('Asia/Yerevan')
# >>> deadline to predict the whole group stage (Yerevan time). Edit if needed.
LOCK_YEREVAN = datetime(2026, 6, 11, 18, 0)
LOCK_ISO = YEREVAN.localize(LOCK_YEREVAN).astimezone(pytz.UTC).isoformat()

# Official draw — seeded order 1..4 per group (Armenian names)
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
# 6 round-robin pairings for a 4-team group
PAIRS = [(0, 1), (2, 3), (0, 2), (1, 3), (0, 3), (1, 2)]

rows = []
for g, teams in GROUPS.items():
    for i, j in PAIRS:
        rows.append({
            "home_team": teams[i], "away_team": teams[j], "stage": "group",
            "group_name": g, "kickoff_time": LOCK_ISO, "lock_time": LOCK_ISO,
            "status": "scheduled",
        })

# guard: don't double-seed
existing = sb.table("matches").select("id", count="exact").eq("stage", "group").execute().count
if existing:
    print(f"⚠️  {existing} group matches already exist — delete them first if you want a clean reseed.")
else:
    sb.table("matches").insert(rows).execute()
    print(f"✅ Seeded {len(rows)} group games (12 groups × 6). "
          f"Deadline: {LOCK_YEREVAN.strftime('%d.%m.%Y %H:%M')} (Երևան).")
