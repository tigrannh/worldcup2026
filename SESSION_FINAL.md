# 🏆 Ameriabank World Cup 2026 Prediction Arena — Full End-to-End Documentation

*The complete, accurate description of the app as actually built. Single source of truth.*

---

## 1. What this is
A web app where **~57 Ameriabank colleagues** predict the scores of all **104 matches** of the FIFA World Cup 2026. Points are awarded automatically, a live leaderboard ranks everyone, and the **admin (Tigran)** runs the tournament from a private admin panel. Entire UI is in **Armenian**, neon/glassmorphism dark theme.

---

## 2. Architecture (decoupled, manual-admin)
```
ADMIN (Tigran)                         57 USERS
  opens games + enters scores            predict scores (one-time)
        │                                      │
        ▼                                      ▼
   ┌──────────────────────────────────────────────┐
   │        SUPABASE (cloud PostgreSQL)             │  ← single source of truth
   │   users · matches · predictions  + RLS lock    │
   └──────────────────────────────────────────────┘
        ▲                                      ▲
        │   server-side service key             │
   ┌──────────────────────────────────────────────┐
   │   STREAMLIT app (app.py) — only a viewer       │  ← hosted on Streamlit Cloud
   └──────────────────────────────────────────────┘
```
- **No external football API** (the free API-Football plan blocks 2026 data). The admin enters results manually. The Python scoring engine recomputes everything instantly on each entry.
- **Admin is the source of truth for all outcomes.** Match points come from the admin-entered 90-minute score; **bonus points come ONLY from official results the admin enters** (group winners/runners-up, the 32 qualifiers, the medals). The engine never guesses the real standings from scores — until the admin enters an outcome, that bonus stays 0.
- Streamlit runs server-side, so the Supabase key never reaches the browser.

---

## 3. Tech stack & files
| File | Purpose |
|---|---|
| `app.py` | The whole Streamlit app (all pages + admin). |
| `scoring.py` | The scoring engine — `recalculate(sb)` recomputes all points idempotently. |
| `database_setup.sql` | Creates the 3 core tables + RLS. Run once in Supabase SQL Editor. |
| `add_admin_results.sql` | Adds the admin official-result tables (`group_official`, `qualifiers`, `tournament_result`, `settings`) + `matches.winner_team`. Run once after `database_setup.sql`. Safe to re-run. |
| `seed_database.py` | Seeds the 57 users from `ameria_credentials.csv` (bcrypt-hashed). |
| `set_armenian_names.py` | Sets Armenian `display_name` for all 57 users. |
| `seed_groups.py` | (Optional) bulk-loads all 72 group games from the official draw. *Currently NOT used — admin adds games manually.* |
| `ameria_credentials.csv` | 57 names, emails, plaintext passwords. **Local only, git-ignored.** |
| `users_backup.json` | Local snapshot of users. Git-ignored. |
| `.env` | Secret keys (Supabase URL/keys, API key). **Git-ignored.** |
| `.streamlit/config.toml` | Dark theme config. |
| `requirements.txt` | streamlit, supabase, bcrypt, pandas, pytz, python-dotenv, requests. |
| `test_e2e.py` | End-to-end self-cleaning test of the scoring flow. |

---

## 4. Database schema
**users** (~57 rows) — `id` (uuid), `username`, `email` (login), `password_hash` (bcrypt), `display_name` (Armenian), `total_points`, `bonus_points`, `exact_scores_count`, `diff_count`, `outcome_count`, `wrong_count`, `champion_pick`, `runnerup_pick`, `bronze_pick`, `previous_rank`, `is_active`, `created_at`.

**matches** — `id`, `home_team`, `away_team`, `stage` (group/r32/r16/qf/sf/third/final), `group_name` (A–L for group games), `kickoff_time`, `lock_time`, `home_score`, `away_score`, `winner_team` (admin-entered: who advanced in a knockout, after ET/penalties), `status` (scheduled/finished), `created_at`.

**predictions** — `id`, `user_id`→users, `match_id`→matches, `pred_home`, `pred_away`, `use_joker`, `points_earned`, `created_at`, **UNIQUE(user_id, match_id)** ← guarantees one immutable prediction per game.

**Admin official-result tables** (the only source of bonus points, all RLS-locked — see `add_admin_results.sql`):
- **group_official** — `group_name` (PK), `winner_team`, `runnerup_team`. One row per group, filled when it closes.
- **qualifiers** — `team_name` (PK). The 32 teams that really reached the Round of 32.
- **tournament_result** — single row: `gold`, `silver`, `bronze`. The real medals.
- **settings** — single row: `medal_deadline`. The admin-set deadline for medal picks.

**Security:** RLS is ON with **no public policies** → the anon/public key can do nothing. The app uses the **service-role key server-side** (bypasses RLS, never exposed to browsers).

---

## 5. Authentication & users
- Login = email + password, verified with **bcrypt**.
- **Admin** = whoever's email equals `ADMIN_EMAIL` (default `tigran.hakobyan@ameriabank.am`). Only the admin sees the ⚡ admin panel.
- **`is_active`** flag: admin can deactivate a user (e.g., didn't pay) → they vanish from the leaderboard **and** can't log in. Reversible.
- Names display in **Armenian** (`display_name`), email stays the stable login ID.

---

## 6. Tournament format (104 games, 7 stages)
| Stage | Games |
|---|---|
| Group (12 groups × 4 teams) | 72 |
| Round of 32 | 16 |
| Round of 16 | 8 |
| Quarter-finals | 4 |
| Semi-finals | 2 |
| Third-place | 1 |
| Final | 1 |

The 48 qualified teams and the full group draw (A–L, with hosts Mexico→A, Canada→B, USA→D) are known and stored as the 48-country list used by the dropdowns.

---

## 7. SCORING RULES (the heart)

### 7a. Match points — best single tier (NOT summed), escalating by round
| Stage | Exact score | Goal difference | Correct outcome |
|---|---|---|---|
| Group | **6** | 4 | 2 |
| Round of 32 | **9** | 6 | 3 |
| Round of 16 | **12** | 8 | 4 |
| Quarter-final | **18** | 12 | 6 |
| Semi-final | **24** | 16 | 8 |
| Third-place | **15** | 10 | 5 |
| **Final** | **36** | **24** | **12** |

You get the **best** matching tier only (exact = just the exact value, not exact+diff+outcome).

**Draw nuance:** any drawn prediction (e.g. 9-9) on a real draw (e.g. 1-1) matches the **goal difference** (0 = 0) → goal-difference tier (e.g. 4 in group). Only the exact draw score (1-1) gets the exact tier (6).

**Time basis:** score = result after **90 minutes + referee's added/stoppage time** (a 90+3' goal counts). **Extra time (2×15) and penalties do NOT count** for predictions — they only decide who advances.

### 7b. Jokers (3 total) — double one match
- One usable in **Group stage**, one in **Round of 32**, one in **Round of 16** only (never QF or later).
- A joker **×2** the match's points. Use-it-or-lose-it per stage.
- **One per stage**, hard-enforced **in the scoring engine** (not just the UI): if more than one joker exists for a stage, only the **earliest-submitted** one counts; the rest are ignored. The UI also re-checks the DB at submit, so two tabs/devices can't both spend the same-stage joker.

### 7c. Group bonus (admin-entered winner/runner-up)
- The **real** group winner & runner-up are **entered by the admin** (`group_official`), never derived from scores.
- The **user's predicted** group table is ranked by the **exact FIFA World Cup 2026 method**: Points → **Head-to-head among the tied teams first** (H2H points → H2H goal difference → H2H goals, re-applied recursively to any sub-group it leaves level) → then overall **goal difference** → overall **goals scored** → stable first-seen order (conduct score / FIFA ranking aren't computable). Head-to-head is applied **before** overall GD, per the 2026 regulations.
- **Eligibility: the user must have predicted ALL 6 games of the group.** A partial prediction (even 5 of 6) earns **no** group bonus and contributes **no** qualifiers from that group — match points for the individual predicted games are unaffected.
- Correct group **Winner** → **+6**, correct **Runner-up** → **+4**, per group (×12). Awarded only after the admin enters that group's official result.

### 7d. Qualification bonus (admin-entered qualifiers)
- The **real** 32 qualifiers are **entered by the admin** (`qualifiers` table; includes the 8 best third-placed teams).
- **+1** per team the user correctly predicted to reach the Round of 32 (max **+32**) — i.e. the user's predicted top-2 of each **fully-predicted** group plus their predicted best-8 thirds, intersected with the official 32.
- Awarded once the admin has saved the qualifier list.

### 7e. Medals (pre-tournament, ONE-TIME locked)
- Each user picks **Champion (🥇 +30)**, **Runner-up (🥈 +18)**, **Bronze (🥉 +12)** from the 48-country dropdown. The three **must be different teams** (already-picked teams are hidden from the other dropdowns).
- **One-time:** once saved (all three), it's locked forever; also locks at the **admin-set medal deadline** (`settings.medal_deadline`).
- Scored when the **admin enters the official Gold/Silver/Bronze** (`tournament_result`) — never derived from the final score (a final decided on penalties is a 90-min draw, so the admin records the real winner). Gold = +30, Silver = +18, Bronze = +12.

### 7f. Bonus points are tracked separately
`total_points = match points + bonus_points`, where **`bonus_points` = group bonus + qualification + medals**. The leaderboard shows a **🎁 Բոնուս** column so everyone sees their bonus distinct from match points.

---

## 8. Prediction rules (fairness)
- **One-time & immutable:** once a user clicks "ՀԱՍՏԱՏԵԼ", the prediction is locked forever — can't change even if time remains (enforced by DB `UNIQUE` + INSERT-only).
- **Locks at the game's `lock_time`** (= kickoff). Re-checked **server-side at submit**, so you can't sneak in after kickoff. A finished game also can't be predicted.
- Nobody ever sees anyone else's predictions — only the leaderboard / aggregate stats are shared.

---

## 9. The scoring engine (`scoring.py`)
- `recalculate(sb)` runs **every time** the admin enters/edits a result **or an official outcome** (group result, qualifiers, medals).
- It **wipes and recomputes from scratch** (idempotent) → fixing a wrong score 10× always gives the correct total, never double-counts.
- Steps: match points from the 90-min score (× one joker per stage) → group bonus (vs admin `group_official`) → qualification (vs admin `qualifiers`) → medals (vs admin `tournament_result`) → ranks (`previous_rank`, same order as the leaderboard) → write back.
- **Bonus is 0 until the admin enters the matching official result** — nothing is guessed from scores.
- Reads the admin tables defensively, so it won't crash if they don't exist yet.

---

## 10. Pages
1. **Landing** — Waka Waka GIF + 🚀 enter button.
2. **📜 ԿԱՆՈՆՆԵՐ (Rules)** — full Armenian rules: format, points table, jokers, bonuses, FIFA group-ranking method, important one-time/lock rules.
3. **🏆 ԱՂՅՈՒՍԱԿ (Leaderboard)** — top-3 podium (with GIFs) → last-place "loser" card (spoon GIF + friendly message) → search → ranked list (rank ↑/↓ arrows, 🎁/🎯/➕/✅/❌ breakdown, no GIFs) → full comparison table.
4. **🎯 ԿԱՆԽԱՏԵՍՈՒՄՆԵՐ (Predictions)** — all stages shown; group stage split into per-group bordered blocks (📦 Խումբ A…); each game = date/time + two team boxes + score inputs + joker; unopened games shown as empty ❔ placeholder boxes.
5. **🥇 ՄԵԴԱԼՆԵՐ (Medals)** — 3 country dropdowns, one-time locked.
6. **📊 ԻՄ ԱՐԴՅՈՒՆՔՆԵՐԸ (My Results)** — my medal picks + my live predicted group tables (FIFA-ranked, fill in once all 6 of a group are predicted) + my prediction history with per-pick category + points.
7. **⚡ ԱԴՄԻՆ (admin only)** — 5 tabs:
   - **➕ Open games** — pick home/away from the 48-country dropdown (no typos) + stage + group + Yerevan date/time.
   - **📝 Enter result** — pick an open game, enter the **90-minute score**; for knockouts also pick **who advanced** (after ET/penalties) → scoring auto-runs.
   - **✏️ Fix** — edit date/time, score, status; teams are **dropdowns** and are **locked once a game has predictions** (changing them would scramble existing predictions). To correct teams on a game nobody predicted yet, just edit; otherwise delete & reopen.
   - **🏁 Official results** — set the **medal deadline**; per group enter the **Winner + Runner-up**; tick the **32 qualifiers**; enter the official **Gold/Silver/Bronze**. Each save triggers a recalc and is what awards bonus points.
   - **👥 Manage users** — activate/deactivate a participant.

---

## 11. Setup from scratch (if ever rebuilding)
1. Create a Supabase project → copy URL + anon (publishable) + service_role keys.
2. Put them in `.env` (`SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `ADMIN_EMAIL`).
3. Supabase SQL Editor → paste & run `database_setup.sql`, then `add_admin_results.sql`.
4. `python seed_database.py` → 57 users (from `ameria_credentials.csv`).
5. `python set_armenian_names.py` → Armenian display names.
6. `streamlit run app.py` locally to test.

---

## 12. Deployment (live)
- Code: **private GitHub repo** `tigrannh/worldcup2026` (secrets git-ignored — `.env`, credentials, backup never pushed).
- Host: **Streamlit Community Cloud** (free), main file `app.py`, branch `main`.
- Secrets pasted in Streamlit Cloud → Settings → **Secrets** (TOML): SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY, ADMIN_EMAIL.
- App **sharing set to Public** so anyone with the link reaches the login page.
- The bottom "Hosted with Streamlit" badge → links to streamlit.io (Streamlit branding); on the free tier it's rendered outside the app and **can't be removed** — it exposes nothing about the repo/data.
- Future code changes: `git push` → Streamlit auto-redeploys.

---

## 13. Security & data safety
- GitHub repo **private**; database **locked by RLS** (public key powerless); keys **server-side only**.
- App login gates all data; nobody sees others' predictions.
- Capacity: ~6,400 tiny rows total → ~1% of the free 500 MB / 5 GB limits. Free tier is plenty for 60 users.
- **Only real risk = Supabase free-tier 7-day idle pause.** During the cup, daily use keeps it awake. Before/after, open it once a week (or add a keep-alive). Local backups (`ameria_credentials.csv`, `users_backup.json`) make users recoverable.

---

## 14. Open / optional items
- 🛡️ Optional **keep-alive** (ping every few days so it never pauses) + a `backup.py` snapshot tool — not yet added.
- Admin must **open the games** (via the admin panel) before colleagues can predict each round.

---

*End of document.*
