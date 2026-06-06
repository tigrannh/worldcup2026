-- ============================================================================
--  WORLD CUP 2026 ARENA — ADMIN-DRIVEN RESULTS (run ONCE in Supabase SQL Editor)
--  Safe to re-run. Adds the tables/columns that make the ADMIN the source of
--  truth for all bonus points. Nothing here is auto-guessed from scores.
-- ============================================================================

-- 1) Knockout advancement: who actually went through (after ET / penalties).
--    The 90-minute score (home_score/away_score) still drives match points;
--    winner_team is only used for advancement + medals.
alter table matches add column if not exists winner_team text;

-- 2) Official group result — you fill ONE row per group when it closes.
create table if not exists group_official (
    group_name    text primary key,
    winner_team   text not null,
    runnerup_team text not null,
    closed_at     timestamptz default now()
);

-- 3) Official teams that reached the Round of 32 (the 32 qualifiers).
create table if not exists qualifiers (
    team_name text primary key
);

-- 4) Official medals — single row. Filling it triggers the medal bonus.
create table if not exists tournament_result (
    id     int  primary key default 1 check (id = 1),
    gold   text,
    silver text,
    bronze text
);

-- 5) App settings — single row. Holds the medal-pick deadline you set.
create table if not exists settings (
    id             int primary key default 1 check (id = 1),
    medal_deadline timestamptz
);

-- lock the public out (same model as the other tables: RLS on, no policies,
-- the app uses the service-role key server-side).
alter table group_official    enable row level security;
alter table qualifiers        enable row level security;
alter table tournament_result enable row level security;
alter table settings          enable row level security;

-- Done. ✅
