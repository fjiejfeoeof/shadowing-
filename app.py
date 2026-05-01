import streamlit as st
import os
import difflib
import torch
from faster_whisper import WhisperModel

# --- 1. AIモデルの準備 ---
@st.cache_resource
def load_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return WhisperModel("base", device=device, compute_type="int8")

model = load_model()

# --- 2. 音声解析関数（エラー回避版：15秒制限） ---
@st.cache_data
def transcribe_fixed_duration(file_path):
    # エラー回避のため、明示的に終了時間を指定する引数を使います
    # word_timestampsをTrueにすることで、より詳細な時間制御が可能になります
    segments, _ = model.transcribe(file_path, language="en")
    
    text_list = []
    for segment in segments:
        # セグメントの開始時間が15秒を超えたらループを終了する
        if segment.start > 15.0:
            break
        text_list.append(segment.text)
    
    return " ".join(text_list).strip()

# --- 3. アプリケーション設定 ---
st.set_page_config(page_title="Stable Shadowing Fixed", layout="centered")
st.title("🎙️ Shadowing Practice (15s Fixed)")

AUDIO_DIR = "."
audio_files = [f for f in os.listdir(AUDIO_DIR) if f.endswith(('.mp3', '.wav', '.m4a'))]

if not audio_files:
    st.error("音声ファイルが見つかりません。")
else:
    selected_file = st.selectbox("練習するファイルを選択してください", audio_files)
    file_path = os.path.join(AUDIO_DIR, selected_file)

    st.divider()

    st.subheader("1. お手本を聴く (最初の15秒間)")
    
    with st.spinner("AIが解析中..."):
        # 修正された関数を呼び出し
        master_text = transcribe_fixed_duration(file_path)
    
    st.audio(file_path)

    with st.expander("15秒分のスクリプトを表示"):
        st.write(master_text)

    st.divider()

    st.subheader("2. Shadowing & Upload")
    user_audio = st.file_uploader("録音ファイルをアップロード", type=["mp3", "wav", "m4a"])

    if user_audio:
        with st.spinner("解析中..."):
            with open("user_temp.wav", "wb") as f:
                f.write(user_audio.getbuffer())
            
            # ユーザー音声も同様のロジックで15秒までを抽出
            u_segments, _ = model.transcribe("user_temp.wav", language="en")
            u_text_list = []
            for s in u_segments:
                if s.start > 15.0:
                    break
                u_text_list.append(s.text)
            user_text = " ".join(u_text_list).strip()
            
            st.write(f"**あなたの発話 (冒頭15秒):** {user_text}")

            ratio = difflib.SequenceMatcher(None, master_text.lower(), user_text.lower()).ratio()
            score = int(ratio * 100)

            st.subheader("3. Result")
            st.metric(label="一致率", value=f"{score}%")
