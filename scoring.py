"""
World Cup 2026 Arena — Scoring Engine (admin-driven bonus edition).

ONE function: recalculate(supabase). It wipes every score and recomputes
everything from scratch, so the admin can fix a result 10 times and the totals
are always correct — points are NEVER double-counted.

Two clean sources:
  • MATCH POINTS  → from the admin-entered 90-minute score (exact / diff / outcome).
  • BONUS POINTS  → ONLY from what the admin has officially entered:
        group_official     (each group's real winner + runner-up)
        qualifiers         (the 32 teams that really reached the Round of 32)
        tournament_result  (real Gold / Silver / Bronze)
    The engine NEVER guesses the real standings from scores. Until the admin
    enters the official results, bonus stays 0.

Each user's *predicted* group table IS computed from their predicted scores,
using the exact FIFA tie-break method, then compared to the admin's official
result.

Call recalculate(sb) after the admin enters/edits any result or official outcome.
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

    Ranks teams by the exact FIFA group method:
      1) Points  2) Goal difference  3) Goals scored
      4) Head-to-head points  5) H2H goal difference  6) H2H goals scored
      7) stable first-seen order (Fair Play / drawing of lots aren't computable).
    Returns an ordered list of (team, stats)."""
    t = defaultdict(lambda: {'pts': 0, 'gf': 0, 'ga': 0})
    order = []                              # first-seen order -> stable fallback
    for home, away, hs, as_ in rows:
        for team in (home, away):
            if team not in t:
                order.append(team)
                _ = t[team]                 # materialise the entry
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

    idx = {team: i for i, team in enumerate(order)}

    def h2h(tied):
        """Mini-table among the tied teams, from the matches between them only."""
        s = set(tied)
        h = {tm: {'pts': 0, 'gf': 0, 'ga': 0} for tm in tied}
        for home, away, hs, as_ in rows:
            if home in s and away in s:
                h[home]['gf'] += hs; h[home]['ga'] += as_
                h[away]['gf'] += as_; h[away]['ga'] += hs
                if hs > as_:
                    h[home]['pts'] += 3
                elif hs < as_:
                    h[away]['pts'] += 3
                else:
                    h[home]['pts'] += 1; h[away]['pts'] += 1
        for v in h.values():
            v['gd'] = v['gf'] - v['ga']
        return h

    def rank(subset, use_h2h):
        """Order `subset` by FIFA criteria. With use_h2h=False use the overall
        table; ties are then broken by head-to-head among the tied teams, and if
        that still leaves a sub-group tied, head-to-head is RE-APPLIED to just
        that sub-group (recursive, exactly as FIFA does). Unbreakable ties fall
        to stable first-seen order."""
        if len(subset) <= 1:
            return list(subset)
        stats = t if not use_h2h else h2h(subset)
        ordered = sorted(subset,
                         key=lambda tm: (stats[tm]['pts'], stats[tm]['gd'],
                                         stats[tm]['gf'], -idx[tm]),
                         reverse=True)
        out, i = [], 0
        while i < len(ordered):
            j = i
            key_i = (stats[ordered[i]]['pts'], stats[ordered[i]]['gd'], stats[ordered[i]]['gf'])
            while (j + 1 < len(ordered) and
                   (stats[ordered[j + 1]]['pts'], stats[ordered[j + 1]]['gd'],
                    stats[ordered[j + 1]]['gf']) == key_i):
                j += 1
            block = ordered[i:j + 1]
            if len(block) == 1:
                out.append(block[0])
            elif not use_h2h:
                out.extend(rank(block, use_h2h=True))          # overall tie -> H2H
            elif len(block) < len(subset):
                out.extend(rank(block, use_h2h=True))          # refine the sub-group
            else:
                out.extend(block)                              # H2H can't separate -> first-seen
            i = j + 1
        return out

    return [(tm, t[tm]) for tm in rank(list(t.keys()), use_h2h=False)]


def _chunks(seq, n=400):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _table(sb, name):
    """Read a table, tolerating the case where it doesn't exist yet."""
    try:
        return sb.table(name).select('*').execute().data or []
    except Exception:
        return []


def recalculate(sb):
    """Full idempotent recompute. Returns a short summary string."""
    users   = sb.table('users').select('*').execute().data
    matches = sb.table('matches').select('*').execute().data
    preds   = sb.table('predictions').select('*').execute().data

    # ---- admin-entered OFFICIAL results (the only source of bonus) ----------
    group_official = {r['group_name']: r for r in _table(sb, 'group_official')}
    official_quals = {r['team_name'] for r in _table(sb, 'qualifiers')}
    tr_rows = _table(sb, 'tournament_result')
    medal = tr_rows[0] if tr_rows else {}

    finished = {m['id']: m for m in matches
                if m['status'] == 'finished'
                and m['home_score'] is not None and m['away_score'] is not None}

    # remember current ranks (same order as the leaderboard) for ↑/↓ arrows
    by_pts = sorted(users, key=lambda u: ((u.get('total_points') or 0),
                                          (u.get('exact_scores_count') or 0)), reverse=True)
    prev_rank = {u['id']: i + 1 for i, u in enumerate(by_pts)}

    pts    = {u['id']: 0 for u in users}   # match points
    bonus  = {u['id']: 0 for u in users}   # group + qualification + medals
    exact  = {u['id']: 0 for u in users}
    diffc  = {u['id']: 0 for u in users}
    outc   = {u['id']: 0 for u in users}
    wrongc = {u['id']: 0 for u in users}

    # ---- one active joker per (user, stage): the EARLIEST-submitted one wins -
    match_stage = {m['id']: m['stage'] for m in matches}
    chosen_joker = {}                       # (user_id, stage) -> True once taken
    active_joker = set()                    # prediction ids that actually get ×2
    # earliest created_at, then lowest id -> fully deterministic even on a tie
    for p in sorted(preds, key=lambda p: (p.get('created_at') or '', p.get('id') or 0)):
        if p.get('use_joker'):
            stg = match_stage.get(p['match_id'])
            if stg in JOKER_STAGES and (p['user_id'], stg) not in chosen_joker:
                chosen_joker[(p['user_id'], stg)] = True
                active_joker.add(p['id'])

    # ---- 1) MATCH POINTS -----------------------------------------------------
    pred_updates = []
    for p in preds:
        earned = 0
        m = finished.get(p['match_id'])
        if m:
            cat, bp = categorize(m['stage'], p['pred_home'], p['pred_away'],
                                 m['home_score'], m['away_score'])
            joker = p['id'] in active_joker          # at most one per stage
            earned = bp * (2 if joker else 1)
            if   cat == 'exact':   exact[p['user_id']] += 1
            elif cat == 'diff':    diffc[p['user_id']] += 1
            elif cat == 'outcome': outc[p['user_id']]  += 1
            else:                  wrongc[p['user_id']] += 1
        pts[p['user_id']] += earned
        if earned != (p.get('points_earned') or 0):
            pred_updates.append({
                'user_id': p['user_id'], 'match_id': p['match_id'],
                'pred_home': p['pred_home'], 'pred_away': p['pred_away'],
                'use_joker': p.get('use_joker', False), 'points_earned': earned})

    pred_by = {(p['user_id'], p['match_id']): p for p in preds}

    # group matches grouped by letter
    groups = defaultdict(list)
    for m in matches:
        if m['stage'] == 'group' and m['group_name']:
            groups[m['group_name']].append(m)

    # ---- 2) GROUP + QUALIFIER BONUS (admin official only) -------------------
    for u in users:
        uid = u['id']
        user_quals  = set()
        third_picks = []

        for g, gms in groups.items():
            # A group's bonus (winner/runner-up/qualifiers) is earned ONLY if the
            # user predicted ALL the group's games — a partial prediction can't
            # honestly claim the group's final order, so it earns nothing here.
            ups = [pred_by.get((uid, mm['id'])) for mm in gms]
            if len(gms) < 6 or any(u is None for u in ups):
                continue
            rows = [(mm['home_team'], mm['away_team'], up['pred_home'], up['pred_away'])
                    for mm, up in zip(gms, ups)]
            pst = _standings(rows)

            off = group_official.get(g)
            if off:
                if pst and pst[0][0] == off['winner_team']:
                    bonus[uid] += GROUP_WINNER_BONUS
                if len(pst) >= 2 and pst[1][0] == off['runnerup_team']:
                    bonus[uid] += GROUP_RUNNERUP_BONUS

            if len(pst) >= 1: user_quals.add(pst[0][0])
            if len(pst) >= 2: user_quals.add(pst[1][0])
            if len(pst) >= 3: third_picks.append((pst[2][0], pst[2][1]))

        # the user's predicted best-8 third-placed teams (by pts -> gd -> gf)
        if third_picks:
            best = sorted(third_picks, key=lambda x: (x[1]['pts'], x[1]['gd'], x[1]['gf']),
                          reverse=True)[:8]
            for team, _ in best:
                user_quals.add(team)

        # +1 per team the user predicted to qualify that REALLY qualified
        if official_quals:
            bonus[uid] += QUALIFY_BONUS * len(user_quals & official_quals)

    # ---- 3) MEDALS (admin official) -----------------------------------------
    def same(a, b):
        return a and b and a.strip().lower() == b.strip().lower()

    gold, silver, bronze = medal.get('gold'), medal.get('silver'), medal.get('bronze')
    for u in users:
        if same(u.get('champion_pick'), gold):   bonus[u['id']] += MEDAL_GOLD
        if same(u.get('runnerup_pick'), silver): bonus[u['id']] += MEDAL_SILVER
        if same(u.get('bronze_pick'),  bronze):  bonus[u['id']] += MEDAL_BRONZE

    # ---- 4) WRITE BACK -------------------------------------------------------
    for chunk in _chunks(pred_updates):
        sb.table('predictions').upsert(chunk, on_conflict='user_id,match_id').execute()

    # Write back ONLY the computed columns (+ the NOT NULL columns the upsert's
    # insert-path needs). We deliberately OMIT user-owned mutable columns
    # (champion_pick/runnerup_pick/bronze_pick, is_active, display_name): upsert
    # leaves columns it isn't given untouched, so a medal pick or an is_active
    # toggle made concurrently with a recalc can't be clobbered.
    user_rows = [{'id': u['id'],
                  'username': u['username'], 'email': u['email'],
                  'password_hash': u['password_hash'],
                  'total_points': pts[u['id']] + bonus[u['id']],
                  'bonus_points': bonus[u['id']],
                  'exact_scores_count': exact[u['id']],
                  'diff_count': diffc[u['id']],
                  'outcome_count': outc[u['id']],
                  'wrong_count': wrongc[u['id']],
                  'previous_rank': prev_rank[u['id']]} for u in users]
    for chunk in _chunks(user_rows):
        sb.table('users').upsert(chunk).execute()

    return (f"Recalculated: {len(finished)} finished matches, {len(users)} users, "
            f"{len(preds)} predictions, {len(group_official)} groups closed, "
            f"{len(official_quals)} qualifiers.")
