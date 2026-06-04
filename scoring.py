"""
World Cup 2026 Arena — Scoring Engine.

ONE function: recalculate(supabase). It wipes every score and recomputes
everything from the raw matches + predictions. Because it always recomputes
from zero, the admin can fix a wrong score 10 times and the totals are always
correct — points are NEVER double-counted.

Call it after the admin enters/edits any result.
"""
from collections import defaultdict

# --- (exact score, goal-difference, correct-outcome) points per stage --------
POINTS = {
    'group': (6,  4,  2),
    'r32':   (9,  6,  3),
    'r16':   (12, 8,  4),
    'qf':    (18, 12, 6),
    'sf':    (24, 16, 8),
    'third': (15, 10, 5),
    'final': (36, 24, 12),
}
JOKER_STAGES = ('group', 'r32', 'r16')      # jokers only allowed here

GROUP_WINNER_BONUS   = 6
GROUP_RUNNERUP_BONUS = 4
QUALIFY_BONUS        = 1                      # per correctly predicted qualifier
MEDAL_GOLD, MEDAL_SILVER, MEDAL_BRONZE = 30, 18, 12


def categorize(stage, ph, pa, rh, ra):
    """Returns (category, points): 'exact' / 'diff' / 'outcome' / 'wrong'."""
    exact, diff, outcome = POINTS[stage]
    if ph == rh and pa == ra:
        return 'exact', exact
    if (ph - pa) == (rh - ra):
        return 'diff', diff
    if ((ph > pa) - (ph < pa)) == ((rh > ra) - (rh < ra)):
        return 'outcome', outcome
    return 'wrong', 0


def base_points(stage, ph, pa, rh, ra):
    """Best single tier (not summed). 0 if nothing matches."""
    return categorize(stage, ph, pa, rh, ra)[1]


def _standings(rows):
    """rows: list of (home_team, away_team, home_score, away_score).
    Returns ordered list of (team, stats) by Points -> GD -> GF (FIFA-style)."""
    t = defaultdict(lambda: {'pts': 0, 'gf': 0, 'ga': 0})
    for home, away, hs, as_ in rows:
        t[home]['gf'] += hs; t[home]['ga'] += as_
        t[away]['gf'] += as_; t[away]['ga'] += hs
        if hs > as_:
            t[home]['pts'] += 3
        elif hs < as_:
            t[away]['pts'] += 3
        else:
            t[home]['pts'] += 1; t[away]['pts'] += 1
    for s in t.values():
        s['gd'] = s['gf'] - s['ga']
    return sorted(t.items(), key=lambda kv: (kv[1]['pts'], kv[1]['gd'], kv[1]['gf']),
                  reverse=True)


def _chunks(seq, n=400):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def recalculate(sb):
    """Full idempotent recompute. Returns a short summary string."""
    users   = sb.table('users').select('*').execute().data
    matches = sb.table('matches').select('*').execute().data
    preds   = sb.table('predictions').select('*').execute().data

    finished = {m['id']: m for m in matches
                if m['status'] == 'finished'
                and m['home_score'] is not None and m['away_score'] is not None}

    # remember current ranks so the UI can show ↑/↓ movement
    by_pts = sorted(users, key=lambda u: u.get('total_points') or 0, reverse=True)
    prev_rank = {u['id']: i + 1 for i, u in enumerate(by_pts)}

    pts    = {u['id']: 0 for u in users}   # match points
    bonus  = {u['id']: 0 for u in users}   # group + qualification + medals
    exact  = {u['id']: 0 for u in users}
    diffc  = {u['id']: 0 for u in users}
    outc   = {u['id']: 0 for u in users}
    wrongc = {u['id']: 0 for u in users}

    # ---- 1) MATCH POINTS -----------------------------------------------------
    pred_updates = []
    for p in preds:
        earned = 0
        m = finished.get(p['match_id'])
        if m:
            cat, bp = categorize(m['stage'], p['pred_home'], p['pred_away'],
                                 m['home_score'], m['away_score'])
            joker = bool(p.get('use_joker')) and m['stage'] in JOKER_STAGES
            earned = bp * (2 if joker else 1)
            if   cat == 'exact':   exact[p['user_id']] += 1
            elif cat == 'diff':    diffc[p['user_id']] += 1
            elif cat == 'outcome': outc[p['user_id']]  += 1
            else:                  wrongc[p['user_id']] += 1
        pts[p['user_id']] += earned
        if earned != (p.get('points_earned') or 0):
            # minimal payload (no auto-generated id) — upsert matches on user+match
            pred_updates.append({
                'user_id': p['user_id'], 'match_id': p['match_id'],
                'pred_home': p['pred_home'], 'pred_away': p['pred_away'],
                'use_joker': p.get('use_joker', False), 'points_earned': earned})

    # index predictions for fast lookup
    pred_by = {(p['user_id'], p['match_id']): p for p in preds}

    # ---- 2) GROUP STANDINGS: real tables, qualifiers, best thirds -----------
    groups = defaultdict(list)
    for m in matches:
        if m['stage'] == 'group' and m['group_name']:
            groups[m['group_name']].append(m)

    real_table = {}            # group -> ordered standings (only if fully finished)
    real_quals = set()         # teams that really advanced
    real_thirds = []           # (group, team, stats) for best-third ranking
    for g, gms in groups.items():
        # a real group = 4 teams × 6 matches; only score it once ALL 6 are finished
        if len(gms) >= 6 and all(mm['id'] in finished for mm in gms):
            st = _standings([(mm['home_team'], mm['away_team'],
                              mm['home_score'], mm['away_score']) for mm in gms])
            real_table[g] = st
            for team, _ in st[:2]:
                real_quals.add(team)
            if len(st) >= 3:
                real_thirds.append((g, st[2][0], st[2][1]))

    all_groups_done = len(real_table) == 12   # qualification only after all 12 groups finish
    if all_groups_done and len(real_thirds) >= 8:
        best = sorted(real_thirds, key=lambda x: (x[2]['pts'], x[2]['gd'], x[2]['gf']),
                      reverse=True)[:8]
        for _, team, _ in best:
            real_quals.add(team)

    # ---- 3) per-user GROUP BONUS + QUALIFICATION BONUS ----------------------
    for u in users:
        uid = u['id']
        user_quals = set()
        third_picks = []                 # this user's predicted thirds (all groups)
        predicted_all_groups = True

        for g, gms in groups.items():
            ups = [pred_by.get((uid, mm['id'])) for mm in gms]
            if any(x is None for x in ups):   # didn't predict whole group -> skip it
                predicted_all_groups = False
                continue
            pst = _standings([(mm['home_team'], mm['away_team'],
                               up['pred_home'], up['pred_away'])
                              for mm, up in zip(gms, ups)])
            # group winner / runner-up bonus (only if the real group is decided)
            if g in real_table:
                rst = real_table[g]
                if pst and rst and pst[0][0] == rst[0][0]:
                    bonus[uid] += GROUP_WINNER_BONUS
                if len(pst) >= 2 and len(rst) >= 2 and pst[1][0] == rst[1][0]:
                    bonus[uid] += GROUP_RUNNERUP_BONUS
            for team, _ in pst[:2]:
                user_quals.add(team)
            if len(pst) >= 3:
                third_picks.append((pst[2][0], pst[2][1]))

        # predicted best-8 thirds count only if user predicted ALL groups
        if all_groups_done and predicted_all_groups and len(third_picks) >= 8:
            best = sorted(third_picks, key=lambda x: (x[1]['pts'], x[1]['gd'], x[1]['gf']),
                          reverse=True)[:8]
            for team, _ in best:
                user_quals.add(team)

        # qualification bonus: +1 per correctly predicted qualifier
        if real_quals:
            bonus[uid] += QUALIFY_BONUS * len(user_quals & real_quals)

    # ---- 4) MEDALS (pre-tournament picks) -----------------------------------
    gold = silver = bronze = None
    fin = next((m for m in matches if m['stage'] == 'final' and m['id'] in finished), None)
    if fin:
        if fin['home_score'] > fin['away_score']:
            gold, silver = fin['home_team'], fin['away_team']
        elif fin['away_score'] > fin['home_score']:
            gold, silver = fin['away_team'], fin['home_team']
    thr = next((m for m in matches if m['stage'] == 'third' and m['id'] in finished), None)
    if thr:
        if thr['home_score'] > thr['away_score']:
            bronze = thr['home_team']
        elif thr['away_score'] > thr['home_score']:
            bronze = thr['away_team']

    def same(a, b):
        return a and b and a.strip().lower() == b.strip().lower()

    for u in users:
        if same(u.get('champion_pick'), gold):
            bonus[u['id']] += MEDAL_GOLD
        if same(u.get('runnerup_pick'), silver):
            bonus[u['id']] += MEDAL_SILVER
        if same(u.get('bronze_pick'), bronze):
            bonus[u['id']] += MEDAL_BRONZE

    # ---- 5) WRITE BACK -------------------------------------------------------
    for chunk in _chunks(pred_updates):
        sb.table('predictions').upsert(chunk, on_conflict='user_id,match_id').execute()

    user_rows = [{**u,
                  'total_points': pts[u['id']] + bonus[u['id']],
                  'bonus_points': bonus[u['id']],
                  'exact_scores_count': exact[u['id']],
                  'diff_count': diffc[u['id']],
                  'outcome_count': outc[u['id']],
                  'wrong_count': wrongc[u['id']],
                  'previous_rank': prev_rank[u['id']]} for u in users]
    for chunk in _chunks(user_rows):
        sb.table('users').upsert(chunk).execute()

    return f"Recalculated: {len(finished)} finished matches, {len(users)} users, {len(preds)} predictions."
