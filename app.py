import streamlit as st
import os
import difflib
import torch
from faster_whisper import WhisperModel

# --- 1. AIモデルの準備 ---
@st.cache_resource
def load_model():
    # Streamlit CloudなどのCPU環境を想定し、int8で最適化
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return WhisperModel("base", device=device, compute_type="int8")

model = load_model()

# --- 2. 音声解析関数（15秒固定） ---
@st.cache_data
def transcribe_fixed_duration(file_path):
    # duration=15.0 を指定することで、音声の冒頭15秒間だけを解析対象にします
    segments, _ = model.transcribe(file_path, language="en", duration=15.0)
    text = " ".join([segment.text for segment in segments])
    return text.strip()

# --- 3. アプリケーション設定 ---
st.set_page_config(page_title="Stable Shadowing 15s", layout="centered")
st.title("🎙️ Shadowing Practice (15s Fixed)")

# 音声ファイルの読み込み
AUDIO_DIR = "."
audio_files = [f for f in os.listdir(AUDIO_DIR) if f.endswith(('.mp3', '.wav', '.m4a'))]

if not audio_files:
    st.error("音声ファイルが見つかりません。リポジトリに音声を配置してください。")
else:
    # 1. お手本の選択
    selected_file = st.selectbox("練習するファイルを選択してください", audio_files)
    file_path = os.path.join(AUDIO_DIR, selected_file)

    st.divider()

    # 2. お手本の解析と再生
    st.subheader("1. お手本を聴く (最初の15秒間)")
    
    with st.spinner("AIが冒頭15秒を解析中..."):
        # AI解析（15秒間のみ）
        master_text = transcribe_fixed_duration(file_path)
    
    # 音声の再生
    # 注意: 再生自体はファイル全体が読み込まれますが、15秒で止めて練習してください
    st.audio(file_path)

    with st.expander("15秒分のスクリプトを表示"):
        st.write(master_text)

    st.divider()

    # 3. ユーザーの録音アップロード
    st.subheader("2. Shadowing & Upload")
    st.info("冒頭15秒を練習し、録音したファイルをアップロードしてください。")
    user_audio = st.file_uploader("録音ファイルをドロップ", type=["mp3", "wav", "m4a"])

    if user_audio:
        with st.spinner("あなたの声を解析中..."):
            with open("user_temp.wav", "wb") as f:
                f.write(user_audio.getbuffer())
            
            # ユーザーの録音も同様に解析（ユーザーが15秒以上録音しても15秒までを評価）
            user_segments, _ = model.transcribe("user_temp.wav", language="en", duration=15.0)
            user_text = " ".join([s.text for s in user_segments]).strip()
            
            st.write(f"**あなたの発話 (冒頭15秒):** {user_text}")

            # 採点
            ratio = difflib.SequenceMatcher(None, master_text.lower(), user_text.lower()).ratio()
            score = int(ratio * 100)

            st.subheader("3. Result")
            st.metric(label="一致率", value=f"{score}%")
