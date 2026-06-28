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

    Ranks teams by the exact FIFA World Cup 2026 group method. After points,
    teams still equal on points are separated by, in order:
      STEP 1 - matches BETWEEN the tied teams only (head-to-head), re-applied
               recursively to any sub-group H2H leaves still level:
        1) H2H points  2) H2H goal difference  3) H2H goals scored
      STEP 2 - all group matches (only when STEP 1 can't separate the group):
        4) overall goal difference  5) overall goals scored
      STEP 3 - team conduct score / FIFA World Ranking: not computable from
               predicted scores, so a stable first-seen order is the final
               fallback (replaces FIFA's ranking/drawing of lots).
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

    def _blocks(ordered, key):
        """Split an already-sorted list into consecutive runs of equal key."""
        out, i = [], 0
        while i < len(ordered):
            j = i
            while j + 1 < len(ordered) and key(ordered[j + 1]) == key(ordered[i]):
                j += 1
            out.append(ordered[i:j + 1])
            i = j + 1
        return out

    def tiebreak(subset):
        """Order a set of teams that are ALL equal on points, FIFA 2026 style.
        STEP 1 (head-to-head among `subset`) is applied first; if it separates
        the group, it is RE-APPLIED recursively to every sub-group it leaves
        still level (the H2H mini-table is recomputed among only those teams).
        Only a group that head-to-head cannot separate at all falls through to
        STEP 2 (overall goal difference, then overall goals). STEP 3 (conduct /
        FIFA ranking) isn't computable, so -idx gives a stable first-seen
        fallback baked into both sorts."""
        if len(subset) <= 1:
            return list(subset)
        # STEP 1: head-to-head mini-table among the tied teams.
        h = h2h(subset)
        key1 = lambda tm: (h[tm]['pts'], h[tm]['gd'], h[tm]['gf'])
        ordered = sorted(subset, key=lambda tm: key1(tm) + (-idx[tm],), reverse=True)
        blocks = _blocks(ordered, key1)
        if len(blocks) > 1:                       # H2H separated something -> recurse
            out = []
            for blk in blocks:
                out.extend(tiebreak(blk))
            return out
        # STEP 2: H2H couldn't separate this group -> overall GD, then goals.
        return sorted(subset,
                      key=lambda tm: (t[tm]['gd'], t[tm]['gf'], -idx[tm]),
                      reverse=True)

    # Separate by points first, then tie-break each block of equal-points teams.
    ranked = sorted(t.keys(), key=lambda tm: (t[tm]['pts'], -idx[tm]), reverse=True)
    out = []
    for blk in _blocks(ranked, lambda tm: t[tm]['pts']):
        out.extend(tiebreak(blk))
    return [(tm, t[tm]) for tm in out]


def _chunks(seq, n=400):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _all(sb, name):
    """Fetch EVERY row of a table, paging past PostgREST's 1000-row default cap.

    A plain .select('*') silently returns only the first 1000 rows. With 57
    users predicting up to 104 games each, `predictions` blows past 1000, so the
    engine MUST page or it will miss rows — and a missed prediction gets wrongly
    treated as the 0-0 default below. Always use this for predictions."""
    out, start = [], 0
    while True:
        chunk = sb.table(name).select('*').range(start, start + 999).execute().data or []
        out += chunk
        if len(chunk) < 1000:
            return out
        start += 1000


def _table(sb, name):
    """Read a table, tolerating the case where it doesn't exist yet."""
    try:
        return sb.table(name).select('*').execute().data or []
    except Exception:
        return []


def recalculate(sb, commit=True):
    """Full idempotent recompute. Returns a short summary string.

    Missing predictions are treated as a 0-0 prediction (the normal "forgot to
    submit" rule): a user who never predicted a finished game scores as if they
    had predicted 0-0, and counts as having predicted 0-0 for group tables too.
    No 0-0 rows are written — it's computed here, so it auto-applies to past and
    future games and is undone simply by reverting this file. A real prediction,
    once submitted, always wins over the default and stays immutable.

    commit=False computes everything but writes NOTHING to the DB and returns a
    dict {user_id: {total, bonus, exact, diff, outcome, wrong}} for previewing.
    """
    users   = _all(sb, 'users')
    matches = _all(sb, 'matches')
    preds   = _all(sb, 'predictions')

    # ---- admin-entered OFFICIAL results (the only source of bonus) ----------
    group_official = {r['group_name']: r for r in _table(sb, 'group_official')}
    official_quals = {r['team_name'] for r in _table(sb, 'qualifiers')}
    tr_rows = _table(sb, 'tournament_result')
    medal = tr_rows[0] if tr_rows else {}

    finished = {m['id']: m for m in matches
                if m['status'] == 'finished'
                and m['home_score'] is not None and m['away_score'] is not None}

    # remember current ranks (same tie-break as the leaderboard) for ↑/↓ arrows:
    # points -> exact -> goal-diff -> outcome -> earliest first prediction -> username.
    first_pred = {}
    for p in preds:
        uid, ts = p['user_id'], (p.get('created_at') or '')
        if uid not in first_pred or ts < first_pred[uid]:
            first_pred[uid] = ts
    by_pts = sorted(users, key=lambda u: (
        -(u.get('total_points') or 0), -(u.get('exact_scores_count') or 0),
        -(u.get('diff_count') or 0), -(u.get('outcome_count') or 0),
        first_pred.get(u['id'], '9999'), (u.get('username') or '')))
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

    # ---- 1b) DEFAULT MISSING PREDICTIONS TO 0-0 -----------------------------
    # A user who never predicted a finished game is treated as having predicted
    # 0-0 (the normal "forgot to submit" rule). No row is created — the points
    # are just counted here, so this applies to past and future games alike and
    # never blocks a real user from submitting (their row, if any, wins above).
    for m in finished.values():
        for u in users:
            uid = u['id']
            if (uid, m['id']) in pred_by:
                continue                               # they really predicted -> already scored
            cat, bp = categorize(m['stage'], 0, 0, m['home_score'], m['away_score'])
            pts[uid] += bp
            if   cat == 'exact':   exact[uid] += 1
            elif cat == 'diff':    diffc[uid] += 1
            elif cat == 'outcome': outc[uid]  += 1
            else:                  wrongc[uid] += 1

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
            # The group bonus needs all 6 games OPENED by the admin to build a
            # full table. Any game the user didn't predict counts as 0-0 (the
            # same "forgot to submit" rule), so everyone has a complete table.
            if len(gms) < 6:
                continue
            rows = []
            for mm in gms:
                up = pred_by.get((uid, mm['id']))
                ph = up['pred_home'] if up else 0
                pa = up['pred_away'] if up else 0
                rows.append((mm['home_team'], mm['away_team'], ph, pa))
            pst = _standings(rows)

            # ---- MANUAL TIEBREAK OVERRIDE (admin decision) ------------------
            # Aleksan Azaryan, Group H: his Uruguay vs Cape Verde is a perfect
            # dead heat (equal points / head-to-head / GD / goals), so the engine
            # settles it by its deterministic draw-of-lots fallback and lands
            # Uruguay above Cape Verde. Admin chose to flip this single tie so
            # Cape Verde ranks ahead. Applies ONLY to this user+group and only
            # while the two are genuinely tied; delete this block to revert.
            if uid == '4007169f-0db7-4866-b5d2-37cc3a6593c7' and g == 'H':
                names = [tm for tm, _ in pst]
                if 'Ուրուգվայ' in names and 'Կաբո Վերդե' in names:
                    iu, ic = names.index('Ուրուգվայ'), names.index('Կաբո Վերդե')
                    su, sc = pst[iu][1], pst[ic][1]
                    tied = (su['pts'] == sc['pts'] and su['gd'] == sc['gd']
                            and su['gf'] == sc['gf'])
                    if tied and iu < ic:                 # Uruguay currently ahead
                        pst[iu], pst[ic] = pst[ic], pst[iu]

            # ---- MANUAL TIEBREAK OVERRIDE (admin decision) ------------------
            # Anna Barseghyan, Group J: her Algeria vs Austria is a perfect dead
            # heat (equal points / head-to-head 1-1 / GD / goals), so the engine
            # settles it by its deterministic draw-of-lots fallback and lands
            # Algeria above Austria. Admin chose to flip this single tie so
            # Austria ranks ahead. Applies ONLY to this user+group and only
            # while the two are genuinely tied; delete this block to revert.
            if uid == '41e50656-5169-492b-beb1-095774cf2619' and g == 'J':
                names = [tm for tm, _ in pst]
                if 'Ալժիր' in names and 'Ավստրիա' in names:
                    ial, iau = names.index('Ալժիր'), names.index('Ավստրիա')
                    sal, sau = pst[ial][1], pst[iau][1]
                    tied = (sal['pts'] == sau['pts'] and sal['gd'] == sau['gd']
                            and sal['gf'] == sau['gf'])
                    if tied and ial < iau:               # Algeria currently ahead
                        pst[ial], pst[iau] = pst[iau], pst[ial]

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

    # ---- preview mode: compute only, write NOTHING ---------------------------
    if not commit:
        return {u['id']: {'total': pts[u['id']] + bonus[u['id']], 'bonus': bonus[u['id']],
                          'exact': exact[u['id']], 'diff': diffc[u['id']],
                          'outcome': outc[u['id']], 'wrong': wrongc[u['id']]} for u in users}

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
