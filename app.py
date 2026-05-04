import streamlit as st
import os
import difflib
import torch
from faster_whisper import WhisperModel
import io

# --- 1. AIモデルの準備 ---
@st.cache_resource
def load_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # CPU環境でも軽量に動くようint8量子化を使用
    return WhisperModel("base", device=device, compute_type="int8")

model = load_model()

# --- 2. 解析・比較ロジック ---
@st.cache_data
def transcribe_fixed_15s(audio_data):
    """
    音声データを解析し、冒頭15秒分のテキストを返す
    audio_data: ファイルパスまたはバイトデータ
    """
    segments, _ = model.transcribe(audio_data, language="en")
    
    text_list = []
    for segment in segments:
        if segment.start > 15.0:
            break
        text_list.append(segment.text.strip())
    
    return " ".join(text_list).strip()

def get_visual_diff(master, user):
    """
    お手本とユーザーの発話を比較し、マークダウン形式のハイライトを生成する
    """
    master_words = master.lower().replace('.', '').replace(',', '').split()
    user_words = user.lower().replace('.', '').replace(',', '').split()
    
    # お手本をベースに、ユーザーが言えなかった単語を赤色にする
    result_md = []
    user_set = set(user_words)
    
    for word in master_words:
        # 簡易的な一致確認（より厳密にする場合はSequenceMatcherを使用）
        if word in user_set:
            result_md.append(word)
        else:
            # ユーザーが発話できなかった単語を赤色＋太字
            result_md.append(f"**:red[{word}]**")
            
    return " ".join(result_md)

# --- 3. UI設定 ---
st.set_page_config(page_title="Shadowing Studio Pro", layout="centered")
st.title("🎙️ Shadowing Studio (Visual Feedback)")

# 音声ファイル読み込み（GitHubリポジトリ内のファイルを想定）
AUDIO_DIR = "."
audio_files = [f for f in os.listdir(AUDIO_DIR) if f.endswith(('.mp3', '.wav', '.m4a'))]

if not audio_files:
    st.error("音声ファイルが見つかりません。sample1.mp3 などを配置してください。")
else:
    # 1. お手本の選択
    selected_name = st.selectbox("練習するファイルを選択:", audio_files)
    file_path = os.path.join(AUDIO_DIR, selected_name)

    st.divider()

    # 2. お手本の解析と再生
    st.subheader("1. お手本を聴く (15秒)")
    with st.spinner("AIが解析中..."):
        master_text = transcribe_fixed_15s(file_path)
    
    st.audio(file_path)
    with st.expander("お手本の全スクリプトを確認"):
        st.write(master_text)

    st.divider()

    # 3. ブラウザ直接録音 (st.audio_input)
    st.subheader("2. あなたのシャドーイング")
    st.info("下のマイクボタンを押して録音を開始してください（最大15秒）")
    recorded_audio = st.audio_input("録音を開始")

    # 4. 解析と視覚的フィードバック
    if recorded_audio:
        with st.spinner("あなたの声をAIが分析中..."):
            # st.audio_input からのバイトデータを直接 Whisper に渡す
            # 一旦 io.BytesIO でメモリ上に保持
            user_text = transcribe_fixed_15s(io.BytesIO(recorded_audio.read()))
            
            # --- 採点 ---
            ratio = difflib.SequenceMatcher(None, master_text.lower(), user_text.lower()).ratio()
            score = int(ratio * 100)
            
            # --- フィードバック表示 ---
            st.subheader("3. 採点結果")
            st.metric(label="一致率", value=f"{score}%")
            
            # 比較表示
            st.write("### 視覚的フィードバック")
            st.caption("赤文字：聞き取れなかった、または発音ミスがあった箇所")
            
            diff_display = get_visual_diff(master_text, user_text)
            st.markdown(f"> {diff_display}")
            
            # 上下比較
            st.write("---")
            col1, col2 = st.columns(2)
            with col1:
                st.write("**[1. お手本テキスト]**")
                st.info(master_text)
            with col2:
                st.write("**[2. あなたの発話]**")
                st.success(user_text if user_text else "(音声が聞き取れませんでした)")

            if score >= 80:
                st.balloons()
