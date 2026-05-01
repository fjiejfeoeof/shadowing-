import streamlit as st
import os
import difflib
import torch
from faster_whisper import WhisperModel

# --- 1. AIモデルの準備（キャッシュして高速化） ---
@st.cache_resource
def load_model():
    # CUDAが使えれば使用、なければCPU（Streamlit Cloudは通常CPU）
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # CPU環境ではint8が高速で省メモリ
    return WhisperModel("base", device=device, compute_type="int8")

model = load_model()

# --- 2. 音声解析関数（お手本テキスト生成） ---
@st.cache_data
def transcribe_audio(file_path):
    segments, info = model.transcribe(file_path, language="en")
    text = " ".join([segment.text for segment in segments])
    return text.strip()

# --- 3. アプリケーション設定 ---
st.set_page_config(page_title="Standard Shadowing App", layout="centered")
st.title("🎙️ Shadowing Practice (Stable Edition)")

# 音声ファイルが置いてあるディレクトリ（今回はルート）
AUDIO_DIR = "."
audio_files = [f for f in os.listdir(AUDIO_DIR) if f.endswith(('.mp3', '.wav', '.m4a'))]

if not audio_files:
    st.error("音声ファイルが見つかりません。リポジトリに .mp3 等をアップロードしてください。")
else:
    # 1. お手本の選択
    selected_file = st.selectbox("練習するファイルを選択してください", audio_files)
    file_path = os.path.join(AUDIO_DIR, selected_file)

    # 2. お手本再生
    st.subheader("1. お手本を聴く")
    st.audio(file_path)

    # 3. AIによるお手本テキストの自動生成と表示
    with st.spinner("AIがテキストを解析中..."):
        master_text = transcribe_audio(file_path)
    
    with st.expander("お手本テキストを確認する"):
        st.write(master_text)

    st.divider()

    # 4. ユーザーの録音アップロード
    st.subheader("2. 自分の声をアップロード")
    st.info("スマホのボイスメモ等で録音したファイルをアップロードしてください。")
    user_audio = st.file_uploader("録音ファイルをドロップ", type=["mp3", "wav", "m4a"])

    # 5. 採点処理
    if user_audio:
        with st.spinner("あなたの声を解析中..."):
            # 一時ファイルとして保存
            with open("user_temp.wav", "wb") as f:
                f.write(user_audio.getbuffer())
            
            # ユーザー音声の文字起こし
            user_segments, _ = model.transcribe("user_temp.wav", language="en")
            user_text = " ".join([s.text for s in user_segments]).strip()
            
            st.write("---")
            st.write(f"**あなたの発話:** {user_text}")

            # difflibで比較（大文字小文字を無視）
            ratio = difflib.SequenceMatcher(None, master_text.lower(), user_text.lower()).ratio()
            score = int(ratio * 100)

            # 6. 結果表示
            st.subheader("3. 採点結果")
            st.metric(label="一致率（スコア）", value=f"{score}%")

            if score >= 80:
                st.success("素晴らしい！完璧に近いシャドーイングです。")
            elif score >= 50:
                st.warning("良い調子です。もう少し正確に発音してみましょう。")
            else:
                st.error("もう少し練習が必要です。お手本を繰り返し聴いてみましょう。")
