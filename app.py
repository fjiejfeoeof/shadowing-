import streamlit as st
import time

# UIの設定
st.set_page_config(page_title="TED Shadowing Master", layout="wide")

# サイドバー設定
st.sidebar.title("🛠️ Settings")
difficulty = st.sidebar.selectbox("Difficulty Level", ["Easy", "Normal", "Hard"])
duration = st.sidebar.slider("Practice Duration (sec)", 5, 30, 15)

# 難易度別の判定しきい値
threshold = {"Easy": 0.8, "Normal": 0.4, "Hard": 0.2}[difficulty]

st.title("🎙️ TED Voice Shadowing Master")
st.write(f"Current Mode: **{difficulty}** (Target Sync: ±{threshold}s)")

# Step 1: Listening phase
st.divider()
st.subheader("Step 1: Listening & Rhythm Check")
st.info("Listen to the model voice and check the script below.")

# スクリプト表示（サンプル：マララさんのスピーチ）
sample_text = "When I was a child, I thought changing the world was simple."
st.markdown(f"### <div style='text-align: center; color: #4ecdc4; padding: 20px;'>\"{sample_text}\"</div>", unsafe_allow_html=True)

if st.button("Ready! Start Shadowing"):
    # Step 2: Shadowing phase
    st.subheader("Step 2: Shadowing...")
    
    # カウントダウン
    with st.empty():
        for i in range(3, 0, -1):
            st.markdown(f"<h1 style='text-align: center;'>🚀 {i}</h1>", unsafe_allow_html=True)
            time.sleep(1)
        st.markdown("<h1 style='text-align: center; color: #ff6b6b;'>🔥 GO!</h1>", unsafe_allow_html=True)

    # 進行状況バー
    progress_bar = st.progress(0)
    for p in range(100):
        time.sleep(duration / 100)
        progress_bar.progress(p + 1)
    
    st.success("Recording finished! Analyzing your sync...")

    # Step 3: Precision Analysis Report
    st.divider()
    st.subheader("Step 3: Precision Analysis Report")
    
    words = sample_text.split()
    cols = st.columns(len(words))
    
    for i, word in enumerate(words):
        # 判定デモ（実際はここをAI解析結果と連動させる）
        # 例：3番目の単語で少し遅れた想定
        lag = 0.04 if i != 2 else 0.45
        is_ok = abs(lag) < threshold
        bg_color = "#27ae60" if is_ok else "#e74c3c"
        
        with cols[i]:
            st.markdown(f"""
                <div style="background-color:{bg_color}; color:white; padding:10px; border-radius:8px; text-align:center; min-height:80px;">
                    <div style="font-weight:bold; font-size:16px;">{word}</div>
                    <div style="font-size:12px; margin-top:5px;">Lag: {lag:+.2f}s</div>
                </div>
            """, unsafe_allow_html=True)
