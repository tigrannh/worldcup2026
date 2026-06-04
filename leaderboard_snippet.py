# PAGE: ARENA LEADERBOARD
if page == "ARENA LEADERBOARD":
    st.title("🏆 THE ARENA STANDINGS")
    
    # Fetch Leaderboard Data
    res = supabase.table("users").select("username, total_points, exact_scores_count").order("total_points", desc=True).execute()
    df = pd.DataFrame(res.data)
    
    if not df.empty:
        # --- THE PODIUM (TOP 3) ---
        p1, p2, p3 = st.columns(3)
        with p2:
            st.markdown(f'''<div class="glass-card" style="border: 2px solid gold; text-align:center;">
                <h2 style="color:gold !important;">🥇 1ST PLACE</h2>
                <h1 style="font-size:2.5rem;">{df.iloc[0]["username"].upper()}</h1>
                <h2 style="color:gold !important;">{df.iloc[0]["total_points"]} PTS</h2>
            </div>''', unsafe_allow_html=True)
        with p1:
            name = df.iloc[1]['username'].upper() if len(df) > 1 else "---"
            pts = df.iloc[1]['total_points'] if len(df) > 1 else 0
            st.markdown(f'''<div class="glass-card" style="border: 2px solid silver; text-align:center;">
                <h2 style="color:silver !important;">🥈 2ND PLACE</h2>
                <h1 style="font-size:2rem;">{name}</h1>
                <h2 style="color:silver !important;">{pts} PTS</h2>
            </div>''', unsafe_allow_html=True)
        with p3:
            name = df.iloc[2]['username'].upper() if len(df) > 2 else "---"
            pts = df.iloc[2]['total_points'] if len(df) > 2 else 0
            st.markdown(f'''<div class="glass-card" style="border: 2px solid #cd7f32; text-align:center;">
                <h2 style="color:#cd7f32 !important;">🥉 3RD PLACE</h2>
                <h1 style="font-size:2rem;">{name}</h1>
                <h2 style="color:#cd7f32 !important;">{pts} PTS</h2>
            </div>''', unsafe_allow_html=True)

    st.markdown("<br><h2 style='text-align:center;'>THE FULL ROSTER</h2>", unsafe_allow_html=True)
    
    # --- CUSTOM HTML LIST (NO SCROLLING) ---
    for index, row in df.iterrows():
        rank = index + 1
        name = row['username'].upper()
        pts = row['total_points']
        exacts = row['exact_scores_count']
        
        # Determine Status and Colors
        bg_color = "rgba(0, 255, 136, 0.1)" # Normal
        border_color = "rgba(255, 255, 255, 0.1)"
        status_msg = "Steady..."
        
        if rank == 1:
            bg_color = "rgba(255, 215, 0, 0.2)"
            status_msg = "👑 THE UNTOUCHABLE KING"
        elif rank <= 5:
            status_msg = "🔥 ON FIRE"
        elif rank >= len(df) - 2:
            bg_color = "rgba(255, 0, 0, 0.2)"
            border_color = "red"
            status_msg = "🤡 COMPLETE DISASTER"
        elif rank == len(df):
            bg_color = "rgba(139, 69, 19, 0.4)" # Brownish for Wooden Spoon
            status_msg = "🥄 THE WOODEN SPOON WINNER"

        st.markdown(f'''
            <div class="glass-card" style="display: flex; justify-content: space-between; align-items: center; background:{bg_color}; border: 1px solid {border_color}; margin-bottom: 10px;">
                <div style="display: flex; align-items: center;">
                    <h1 style="margin: 0 20px 0 0; width: 50px; text-align: center;">{rank}</h1>
                    <div>
                        <h3 style="margin:0; font-size:1.5rem;">{name}</h3>
                        <span style="font-size:0.8rem; color:#aaa;">{status_msg}</span>
                    </div>
                </div>
                <div style="text-align: right;">
                    <h2 style="margin:0;">{pts} PTS</h2>
                    <span style="font-size:0.8rem; color:#aaa;">Exact Scores: {exacts}</span>
                </div>
            </div>
        ''', unsafe_allow_html=True)
