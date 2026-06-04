"""End-to-end test against the live DB. Creates test data, verifies scoring,
then CLEANS UP completely (deletes test rows, resets everyone to 0)."""
import os
from dotenv import load_dotenv
from supabase import create_client
import scoring

load_dotenv(override=True)
sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])

users = sb.table("users").select("id, display_name").order("username").limit(4).execute().data
U = [u['id'] for u in users]
N = {u['id']: u['display_name'] for u in users}
match_id = None
try:
    print("1) ADMIN opens a finished group game: Բրազիլիա 2 : 1 Սերբիա")
    match_id = sb.table("matches").insert({
        "home_team": "Բրազիլիա", "away_team": "Սերբիա", "stage": "group", "group_name": "A",
        "kickoff_time": "2026-06-11T18:00:00+00:00", "lock_time": "2026-06-11T18:00:00+00:00",
        "home_score": 2, "away_score": 1, "status": "finished",
    }).execute().data[0]['id']

    print("2) USERS predict:")
    plan = [(U[0], 2, 1, True, "exact + JOKER -> 6x2=12"),
            (U[1], 3, 2, False, "goal-diff (diff +1) -> 4"),
            (U[2], 3, 0, False, "winner only (home win) -> 2"),
            (U[3], 0, 2, False, "wrong -> 0")]
    for uid, h, a, jk, why in plan:
        sb.table("predictions").insert({"user_id": uid, "match_id": match_id,
                                        "pred_home": h, "pred_away": a, "use_joker": jk}).execute()
        print(f"   {N[uid]}: {h}:{a} {'🃏' if jk else '  '} ({why})")

    print("3) Immutability check: same user predicts the SAME game again...")
    try:
        sb.table("predictions").insert({"user_id": U[0], "match_id": match_id,
                                        "pred_home": 9, "pred_away": 9}).execute()
        print("   ❌ FAIL — a 2nd prediction was allowed!")
    except Exception:
        print("   ✅ BLOCKED by the database (unique rule) — immutable confirmed")

    print("4) ADMIN enters result -> scoring runs:")
    print("   ", scoring.recalculate(sb))

    print("5) LEADERBOARD result:")
    res = sb.table("users").select(
        "display_name,total_points,exact_scores_count,diff_count,outcome_count,wrong_count"
    ).in_("id", U).order("total_points", desc=True).execute().data
    for r in res:
        print(f"   {r['display_name']:25s} | {r['total_points']:3d} pts "
              f"| 🎯{r['exact_scores_count']} ➕{r['diff_count']} ✅{r['outcome_count']} ❌{r['wrong_count']}")

    expected = {N[U[0]]: 12, N[U[1]]: 4, N[U[2]]: 2, N[U[3]]: 0}  # pure match pts (group not complete)
    ok = all(next(r['total_points'] for r in res if r['display_name'] == nm) == pts
             for nm, pts in expected.items())
    print("   => SCORING", "✅ CORRECT" if ok else "❌ WRONG")
finally:
    print("6) CLEANUP: deleting test data and resetting everyone to 0...")
    if match_id:
        sb.table("predictions").delete().eq("match_id", match_id).execute()
        sb.table("matches").delete().eq("id", match_id).execute()
    scoring.recalculate(sb)
    chk = sb.table("users").select("total_points").execute().data
    print(f"   ✅ cleaned. all users total = {sum(x['total_points'] for x in chk)} (should be 0)")
