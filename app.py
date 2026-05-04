import streamlit as st
import os
import time
import difflib
import torch
from faster_whisper import WhisperModel
import io

# --- 1. AIモデルの準備 ---
@st.cache_resource
def load_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return WhisperModel("base", device=device, compute_type="int8")

model = load_model()

# --- 2. 解析ロジック（エラー根絶版） ---
@st.cache_data
def get_master_data(file_path):
    # 生のsegmentオブジェクトをリストとして保持する
    segments, _ = model.transcribe(file_path, language="en")
    
    # リスト化してキャッシュに安全に保存（15秒分）
    seg_list = []
    full_text_list = []
    for s in segments:
        if s.start > 15.0:
            break
        seg_list.append(s)
        full_text_list.append(s.text.strip())
    
    return seg_list, " ".join(full_text_list)

def get_diff_markdown(master, user):
    m_words = master.lower().replace('.', '').replace(',', '').split()
    u_words = user.lower().replace('.', '').replace(',', '').split()
    user_set = set(u_words)
    result = [word if word in user_set else f"~~:red[{word}]~~" for word in m_words]
    return " ".join(result)

# --- 3. メインUI ---
st.set_page_config(page_title="Shadowing Prompter Final", layout="centered")
st.title("🎙️ Shadowing Prompter (Stable Edition)")

AUDIO_DIR = "."
audio_files = [f for f in os.listdir(AUDIO_DIR) if f.endswith(('.mp3', '.wav', '.m4a'))]

if not audio_files:
    st.error("音声ファイルが見つかりません。")
else:
    selected_file = st.selectbox("練習するファイルを選択:", audio_files)
    file_path = os.path.join(AUDIO_DIR, selected_file)

    with st.spinner("AIがスクリプトを準備中..."):
        master_segments, master_full_text = get_master_data(file_path)

    st.divider()

    # --- プロンプター機能 ---
    st.subheader("1. プロンプター連動再生")
    prompt_area = st.empty()
    progress_bar = st.progress(0)
    
    st.audio(file_path)
    
    if st.button("プロンプターをスタート"):
        start_time = time.time()
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > 15.0: break
            
            now_text = ""
            next_text = ""
            
            for i, s in enumerate(master_segments):
                # .start と .end という「属性」を正しく参照
                if s.start - 0.5 <= elapsed <= s.end:
                    now_text = f"### NOW: :orange[{s.text}]"
                    if i + 1 < len(master_segments):
                        next_text = f"Next: {master_segments[i+1].text}"
                    break
            
            with prompt_area.container():
                st.markdown(now_text if now_text else "### (Ready...)")
                if next_text:
                    st.caption(next_text)
            
            progress_bar.progress(min(elapsed / 15.0, 1.0))
            time.sleep(0.05) # 更新頻度を上げてより滑らかに
        
        st.success("終了！")

    st.divider()

    # --- 録音・採点 ---
    st.subheader("2. Shadowing & Result")
    recorded_audio = st.audio_input("録音を開始")

    if recorded_audio:
        with st.spinner("採点中..."):
            u_segs, _ = model.transcribe(io.BytesIO(recorded_audio.read()), language="en")
            user_text = " ".join([s.text for s in u_segs if s.start <= 15.0]).strip()
            
            score = int(difflib.SequenceMatcher(None, master_full_text.lower(), user_text.lower()).ratio() * 100)
            
            st.metric("一致率", f"{score}%")
            st.markdown(f"**フィードバック:**\n> {get_diff_markdown(master_full_text, user_text)}")
            
            col1, col2 = st.columns(2)
            with col1: st.info(f"**[お手本]**\n{master_full_text}")
            with col2: st.success(f"**[あなた]**\n{user_text if user_text else '???'}")
