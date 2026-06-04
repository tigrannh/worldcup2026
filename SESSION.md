# 🏆 Automated World Cup 2026 Prediction Platform - Exhaustive Technical Manual

## 1. Executive Vision & Scope
The "Ameriabank Prediction Arena 2026" is an enterprise-grade, fully automated forecasting environment designed for 57 professional users. The system was architected to solve the "Excel Scalability Problem" where 104 matches for 50+ users creates massive manual calculation overhead and data integrity risks. This platform provides a zero-maintenance solution that scales linearly with match volume.

---

## 2. Technical Architecture: The Immutable Trinity
We implemented a **Decoupled Stateless Architecture** to ensure that peak traffic (simultaneous logins right before kickoff) never results in server crashes or data loss.

### A. The Viewer (Streamlit Frontend)
- **Engine:** Python 3.9+ with Streamlit.
- **Custom CSS Architecture:** We injected a custom "Neon Dark" theme using `unsafe_allow_html=True`. This theme uses:
  - **Glassmorphism:** Semi-transparent containers with `backdrop-filter: blur(15px)` to create depth.
  - **Animated Mesh Gradients:** A radial background that mimics the atmosphere of a professional stadium at night.
  - **Responsive Layout:** The app uses `st.columns` and `use_container_width=True` to ensure readability on both office desktops and mobile devices.
- **Stateless Navigation:** Page state is managed via `st.session_state['page']` using button-callback logic to provide a fast, non-dropdown vertical navigation experience.

### B. The Brain (Supabase / PostgreSQL)
- **Single Source of Truth:** We chose Supabase because it offers a hosted PostgreSQL instance with native support for Row-Level Security (RLS) and real-time triggers.
- **Normalization:** The database is split into four primary entities:
  1. `users`: Stores UUIDs, bcrypt-hashed passwords, and aggregated statistics.
  2. `matches`: Stores API fixture IDs, kickoff times, and real scores.
  3. `predictions`: The link between users and matches.
  4. `group_standings_cache`: (Planned) To optimize the "Point Bomb" reveal at the end of the group stage.
- **ACID Compliance:** PostgreSQL ensures that if 50 users click "Save" at the same microsecond, each transaction is queued and executed in isolation, preventing "Dirty Reads" or deadlocks.

### C. The Robot (GitHub Actions + API-Football)
- **Data Source:** `api-football` (League ID 1, Season 2026). This is a professional REST API.
- **Orchestration:** GitHub Actions runs a cron job every 20 minutes (`*/20 * * * *`).
- **Automation Logic:** The `updater.py` script performs an `UPSERT` operation on the match table. If the API provides a new score or team name (bracket progression), the database is updated immediately without manual intervention.

---

## 3. The Mathematical "Brain" (SQL Point Engine)
Instead of calculating points in Python (which is slow), we moved the entire "Logic" into a **PostgreSQL Trigger** (`calculate_match_points`).

### A. The Base Scoring Formula
When a match status changes from `scheduled/live` to `finished`, the trigger fires and applies this logic to all user rows:
1. **Exact Score (6 pts):** `IF pred_home = real_home AND pred_away = real_away`
2. **Goal Difference (4 pts):** `IF (pred_home - pred_away) = (real_home - real_away)`
3. **Correct Outcome (2 pts):** `IF SIGN(pred_home - pred_away) = SIGN(real_home - real_away)`

### B. Scalability & Multipliers
The system applies a `NEW.multiplier` based on the round:
- Group Stage: **1x**
- R32 / R16: **2x**
- Quarters / Semis: **3x**
- The Final: **5x**

### C. The Joker Strategic Multiplier
Users are given 5 `⚡ JOKERS`. When a user enables a Joker for a match, the database logic detects the `use_joker = TRUE` flag and **DOUBLES** the entire result (e.g., an Exact Score in the Final with a Joker would yield **60 points**).

---

## 4. UI/UX & Gamification Details
- **Waka Waka Entrance:** A high-energy landing page that uses `st.balloons()` and custom HTML headers to create emotional hype.
- **The "Wooden Spoon" Prize:** To keep the bottom of the leaderboard engaged, we added a special "Wooden Spoon" badge for the player in last place.
- **Transparency Receipts:** On the "My Performance" page, the app pulls the raw data from the `predictions` table and dynamically generates a receipt using `st.expander`, explaining the exact math of how points were earned.

---

## 5. Security Protocols
- **Authentication:** passwords are encrypted using `bcrypt` (Salted and Hashed). The plain-text passwords never touch the database.
- **Hard Deadline Locking:** We implemented a `timedelta(hours=2)` hard lock. The database physically rejects updates 120 minutes before a game, preventing "Insider Predictions".
- **Row-Level Security (RLS):** Policies are enforced at the database level:
  - `CREATE POLICY "Users can only see their own predictions"`
  - This ensures even if a user tries to access the raw API, they cannot see or modify their colleagues' data.

---

## 6. How to Deploy (Master Guide)
1. **GitHub:** Push `app.py`, `updater.py`, `requirements.txt`, and `.github/` to a private repo.
2. **Streamlit Cloud:** Connect the repo and deploy `app.py`.
3. **Secrets:** In Streamlit's Dashboard, add:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `API_FOOTBALL_KEY`
4. **Robot Activation:** In GitHub Settings -> Secrets -> Actions, add the same keys. The robot will start running automatically.

**The Ameriabank Prediction Arena 2026 is officially ready for the world stage.** 🏆🇦🇲🚀
