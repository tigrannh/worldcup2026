-- ============================================================================
--  WORLD CUP 2026 ARENA  —  FULL DATABASE SETUP (fresh / empty project)
--  Run this ONCE in Supabase  →  SQL Editor  →  paste  →  Run.
--  This creates ALL THREE tables from scratch. After running it, re-seed the
--  57 users (seed_database.py) — the users table will be empty until then.
-- ============================================================================

-- clean slate (safe to re-run) ----------------------------------------------
drop table if exists predictions cascade;
drop table if exists matches     cascade;
drop table if exists users       cascade;

-- 1) USERS — the 57 colleagues ----------------------------------------------
create table users (
    id                 uuid primary key default gen_random_uuid(),
    username           text not null,
    email              text not null unique,
    password_hash      text not null,
    display_name       text,                       -- Armenian name to show
    total_points       int  default 0,
    bonus_points       int  default 0,             -- 🎁 group + qualification + medals
    exact_scores_count int  default 0,             -- 🎯 correct exact scores
    diff_count         int  default 0,             -- ➕ correct goal-difference
    outcome_count      int  default 0,             -- ✅ correct winner only
    wrong_count        int  default 0,             -- ❌ predicted wrong
    jokers_remaining   int  default 3,
    champion_pick      text,                        -- 🥇 medal pick
    runnerup_pick      text,                        -- 🥈
    bronze_pick        text,                        -- 🥉
    previous_rank      int,                         -- for ↑/↓ arrows
    status_message     text,
    is_active          boolean default true,        -- admin can turn a user OFF
    created_at         timestamptz default now()
);

-- 2) MATCHES — every game the admin opens -----------------------------------
create table matches (
    id            bigint generated always as identity primary key,
    home_team     text        not null,
    away_team     text        not null,
    stage         text        not null
                  check (stage in ('group','r32','r16','qf','sf','third','final')),
    group_name    text,                       -- 'A'..'L' for group games, else null
    kickoff_time  timestamptz not null,
    lock_time     timestamptz not null,       -- predictions refused at/after this
    home_score    int,
    away_score    int,
    status        text        not null default 'scheduled'
                  check (status in ('scheduled','finished')),
    created_at    timestamptz default now()
);
create index matches_stage_idx on matches (stage);
create index matches_group_idx on matches (group_name);

-- 3) PREDICTIONS — one-time, immutable, exactly one per user+match ----------
create table predictions (
    id            bigint generated always as identity primary key,
    user_id       uuid    not null references users(id)   on delete cascade,
    match_id      bigint  not null references matches(id)  on delete cascade,
    pred_home     int     not null check (pred_home >= 0),
    pred_away     int     not null check (pred_away >= 0),
    use_joker     boolean not null default false,
    points_earned int     not null default 0,
    created_at    timestamptz default now(),
    unique (user_id, match_id)   -- DB GUARANTEE: a 2nd prediction is impossible
);
create index predictions_match_idx on predictions (match_id);
create index predictions_user_idx  on predictions (user_id);

-- 4) SECURITY — lock the public out completely ------------------------------
--    The app connects ONLY from the server with the SERVICE ROLE key
--    (Streamlit never exposes it to browsers). RLS on + no policies =
--    the public/anon key can do nothing. service_role bypasses RLS.
alter table users       enable row level security;
alter table matches     enable row level security;
alter table predictions enable row level security;

-- Done. ✅  Next: re-seed the 57 users (seed_database.py).
