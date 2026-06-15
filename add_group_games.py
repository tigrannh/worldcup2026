"""Add the remaining World Cup 2026 group-stage games with correct Yerevan
kickoff times and lock_time = 1 hour before kickoff. Matches the official FIFA
schedule. Skips games already in the DB (updates their times if scheduled),
never duplicates, never touches finished games.

Dry-run by default (writes NOTHING). Apply with:  python add_group_games.py --apply
"""
import os, sys
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(override=True)
sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
APPLY = "--apply" in sys.argv
YER = pytz.timezone("Asia/Yerevan")

EN2HY = {
 "Mexico":"Մեքսիկա","South Africa":"Հարավային Աֆրիկա","South Korea":"Հարավային Կորեա","Czechia":"Չեխիա",
 "Canada":"Կանադա","Bosnia and Herzegovina":"Բոսնիա և Հերցեգովինա","Qatar":"Կատար","Switzerland":"Շվեյցարիա",
 "Brazil":"Բրազիլիա","Morocco":"Մարոկկո","Haiti":"Հաիթի","Scotland":"Շոտլանդիա",
 "USA":"ԱՄՆ","Paraguay":"Պարագվայ","Australia":"Ավստրալիա","Türkiye":"Թուրքիա",
 "Germany":"Գերմանիա","Curaçao":"Կյուրասաո","Ivory Coast":"Կոտ դ’Իվուար","Ecuador":"Էկվադոր",
 "Netherlands":"Նիդեռլանդներ","Japan":"Ճապոնիա","Sweden":"Շվեդիա","Tunisia":"Թունիս",
 "Belgium":"Բելգիա","Egypt":"Եգիպտոս","Iran":"Իրան","New Zealand":"Նոր Զելանդիա",
 "Spain":"Իսպանիա","Cabo Verde":"Կաբո Վերդե","Saudi Arabia":"Սաուդյան Արաբիա","Uruguay":"Ուրուգվայ",
 "France":"Ֆրանսիա","Senegal":"Սենեգալ","Iraq":"Իրաք","Norway":"Նորվեգիա",
 "Argentina":"Արգենտինա","Algeria":"Ալժիր","Austria":"Ավստրիա","Jordan":"Հորդանան",
 "Portugal":"Պորտուգալիա","DR Congo":"Կոնգո ԴՀ","Uzbekistan":"Ուզբեկստան","Colombia":"Կոլումբիա",
 "England":"Անգլիա","Croatia":"Խորվաթիա","Ghana":"Գանա","Panama":"Պանամա",
}

# (day, hour, minute, group, home_en, away_en)  — June 2026, Yerevan time
SCHED = [
 (16,2,0,"H","Saudi Arabia","Uruguay"),(16,5,0,"G","Iran","New Zealand"),(16,23,0,"I","France","Senegal"),
 (17,2,0,"I","Iraq","Norway"),(17,5,0,"J","Argentina","Algeria"),(17,8,0,"J","Austria","Jordan"),(17,21,0,"K","Portugal","DR Congo"),
 (18,0,0,"L","England","Croatia"),(18,3,0,"L","Ghana","Panama"),(18,6,0,"K","Uzbekistan","Colombia"),(18,20,0,"A","Czechia","South Africa"),(18,23,0,"B","Switzerland","Bosnia and Herzegovina"),
 (19,2,0,"B","Canada","Qatar"),(19,5,0,"A","Mexico","South Korea"),(19,23,0,"D","USA","Australia"),
 (20,2,0,"C","Scotland","Morocco"),(20,4,30,"C","Brazil","Haiti"),(20,7,0,"D","Türkiye","Paraguay"),(20,21,0,"F","Netherlands","Sweden"),
 (21,0,0,"E","Germany","Ivory Coast"),(21,4,0,"E","Ecuador","Curaçao"),(21,8,0,"F","Tunisia","Japan"),(21,20,0,"H","Spain","Saudi Arabia"),(21,23,0,"G","Belgium","Iran"),
 (22,2,0,"H","Uruguay","Cabo Verde"),(22,5,0,"G","New Zealand","Egypt"),(22,21,0,"J","Argentina","Austria"),
 (23,1,0,"I","France","Iraq"),(23,4,0,"I","Norway","Senegal"),(23,7,0,"J","Jordan","Algeria"),(23,21,0,"K","Portugal","Uzbekistan"),
 (24,0,0,"L","England","Ghana"),(24,3,0,"L","Panama","Croatia"),(24,6,0,"K","Colombia","DR Congo"),(24,23,0,"B","Switzerland","Canada"),(24,23,0,"B","Bosnia and Herzegovina","Qatar"),
 (25,2,0,"C","Morocco","Haiti"),(25,2,0,"C","Scotland","Brazil"),(25,5,0,"A","South Africa","South Korea"),(25,5,0,"A","Czechia","Mexico"),
 (26,0,0,"E","Curaçao","Ivory Coast"),(26,0,0,"E","Ecuador","Germany"),(26,3,0,"F","Tunisia","Netherlands"),(26,3,0,"F","Japan","Sweden"),(26,6,0,"D","Türkiye","USA"),(26,6,0,"D","Paraguay","Australia"),(26,23,0,"I","Norway","France"),(26,23,0,"I","Senegal","Iraq"),
 (27,4,0,"H","Cabo Verde","Saudi Arabia"),(27,4,0,"H","Uruguay","Spain"),(27,7,0,"G","New Zealand","Belgium"),(27,7,0,"G","Egypt","Iran"),
 (28,1,0,"L","Panama","England"),(28,1,0,"L","Croatia","Ghana"),(28,3,30,"K","Colombia","Portugal"),(28,3,30,"K","DR Congo","Uzbekistan"),(28,6,0,"J","Algeria","Austria"),(28,6,0,"J","Jordan","Argentina"),
]

# sanity: every team name maps
missing = {t for *_, h, a in SCHED for t in (h, a)} - set(EN2HY)
assert not missing, f"unmapped teams: {missing}"
print(f"Schedule games: {len(SCHED)}")

existing = sb.table("matches").select("*").execute().data or []
idx = {}
for m in existing:
    if m['stage'] == 'group' and m.get('group_name'):
        idx[(m['group_name'], frozenset((m['home_team'], m['away_team'])))] = m

to_insert, to_update, skip_fin, ok = [], [], [], 0
for (d, hh, mm, g, he, ae) in SCHED:
    h, a = EN2HY[he], EN2HY[ae]
    ko = YER.localize(datetime(2026, 6, d, hh, mm)).astimezone(pytz.UTC)
    lock = ko - timedelta(hours=1)
    ko_iso, lock_iso = ko.isoformat(), lock.isoformat()
    cur = idx.get((g, frozenset((h, a))))
    if cur is None:
        to_insert.append({"home_team": h, "away_team": a, "stage": "group", "group_name": g,
                          "kickoff_time": ko_iso, "lock_time": lock_iso, "status": "scheduled"})
    elif cur['status'] == 'finished':
        skip_fin.append(cur)
    elif cur.get('kickoff_time') != ko_iso or cur.get('lock_time') != lock_iso:
        to_update.append((cur['id'], h, a, g, ko_iso, lock_iso))
    else:
        ok += 1

def hy(iso):
    return datetime.fromisoformat(iso).astimezone(YER).strftime('%a %d %b %H:%M')

print(f"\nALREADY CORRECT: {ok} | FINISHED (left alone): {len(skip_fin)}")
print(f"\n== TO INSERT ({len(to_insert)}) ==")
for r in to_insert:
    print(f"  + [{r['group_name']}] {r['home_team']} vs {r['away_team']}  KO {hy(r['kickoff_time'])}  lock {hy(r['lock_time'])}")
print(f"\n== TO UPDATE times ({len(to_update)}) ==")
for (mid, h, a, g, ko_iso, lk_iso) in to_update:
    print(f"  ~ [{g}] {h} vs {a}  ->  KO {hy(ko_iso)}  lock {hy(lk_iso)}")

if not APPLY:
    print("\nDRY-RUN — nothing written. Re-run with --apply to write.")
else:
    for r in to_insert:
        sb.table("matches").insert(r).execute()
    for (mid, h, a, g, ko_iso, lk_iso) in to_update:
        sb.table("matches").update({"kickoff_time": ko_iso, "lock_time": lk_iso}).eq("id", mid).execute()
    print(f"\nAPPLIED: inserted {len(to_insert)}, updated {len(to_update)}.")
