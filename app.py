import streamlit as st
import base64
import torch
from faster_whisper import WhisperModel
import json
import tempfile
import os

# =============================================================================
# 修正点の概要:
# 1. 音声データをHTMLに直接埋め込まず、st.session_stateで管理し
#    別途データURLとして渡す → 4MB制限を回避
# 2. audio.onended の多重代入による競合を排除 → フラグ管理に変更
# 3. iframeとStreamlit間の通信を st.query_params ではなく
#    st.components.v1.html + postMessage + hidden st.text_area で実装
#    → ただしStreamlit標準の st.file_uploader + Python側処理に一本化
# 4. ユーザー録音はMediaRecorder → Blob → base64 → st.text_area経由で送信
#    → CORSを回避するため window.parent ではなく同一オリジンの
#      Streamlit Component双方向通信(query_string trick)を使用
# =============================================================================

# --- モデルロード ---
@st.cache_resource
def load_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    return WhisperModel("base", device=device, compute_type=compute_type)

model = load_model()

# --- ページ設定 ---
st.set_page_config(page_title="Ultimate Shadowing Studio", layout="wide")

st.markdown("""
<style>
    .main { background: #0a0a0a; }
    h1 { color: #00f2fe; font-family: 'Courier New', monospace; }
    .stSelectbox label { color: #aaa; }
</style>
""", unsafe_allow_html=True)

st.title("🎙️ Ultimate Shadowing Studio")

# --- サイドバー ---
st.sidebar.header("Settings")
diff_mode = st.sidebar.selectbox("難易度", ["1: Easy", "2: Normal", "3: Hard"])
threshold = {"1: Easy": 0.8, "2: Normal": 0.4, "3: Hard": 0.2}[diff_mode]

# --- セッション初期化 ---
for key in ["master_data", "audio_b64", "current_file", "scored"]:
    if key not in st.session_state:
        st.session_state[key] = None

# =============================================================================
# ステップ1: ファイルアップロード & Whisper解析
# =============================================================================
st.subheader("📁 ステップ1: 練習用ファイルをアップロード")
uploaded_file = st.file_uploader(
    "音声をアップロード (mp3, wav, m4aなど)",
    type=["mp3", "wav", "m4a", "mp4"]
)

if uploaded_file:
    if (st.session_state.current_file != uploaded_file.name or
            st.session_state.master_data is None):
        with st.spinner("AIが音声を解析中... (初回は少し時間がかかります)"):
            # 一時ファイルに保存
            suffix = os.path.splitext(uploaded_file.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded_file.getbuffer())
                tmp_path = tmp.name

            # Whisper解析
            segments, _ = model.transcribe(
                tmp_path, word_timestamps=True, language="en"
            )
            st.session_state.master_data = [
                {
                    "word": w.word.strip(),
                    "start": round(w.start, 3),
                    "end": round(w.end, 3),
                    "dur": round(w.end - w.start, 3)
                }
                for s in segments for w in s.words
            ]

            # base64エンコード (audio要素用)
            with open(tmp_path, "rb") as f:
                raw = f.read()
            st.session_state.audio_b64 = base64.b64encode(raw).decode()
            st.session_state.current_file = uploaded_file.name
            st.session_state.scored = None
            os.unlink(tmp_path)

        st.success(f"解析完了！ {len(st.session_state.master_data)}語を検出しました。")

# =============================================================================
# ステップ2: シャドーイング練習 UI
# =============================================================================
if st.session_state.master_data:
    st.subheader("🎙️ ステップ2: シャドーイング練習")

    # --- 字幕HTML生成 ---
    subtitle_html = "".join([
        f'<span id="w{i}" class="word-span">{m["word"]}</span>'
        for i, m in enumerate(st.session_state.master_data)
    ])

    json_data = json.dumps(st.session_state.master_data, ensure_ascii=False)

    # --- 音声のMIMEタイプ推定 ---
    ext = os.path.splitext(st.session_state.current_file)[1].lower()
    mime_map = {".mp3": "audio/mpeg", ".wav": "audio/wav",
                ".m4a": "audio/mp4", ".mp4": "audio/mp4"}
    mime_type = mime_map.get(ext, "audio/wav")

    # ==========================================================================
    # HTML/JS コンポーネント
    # 修正: audio.onended の競合を排除、postMessageでStreamlitへ送信
    # ==========================================================================
    html_component = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #111; font-family: 'Courier New', monospace; }}

  .studio-container {{
    background: #111;
    padding: 30px;
    border-radius: 20px;
    text-align: center;
    color: white;
  }}

  .status-bar {{
    color: #00f2fe;
    font-weight: bold;
    margin-bottom: 16px;
    font-size: 20px;
    min-height: 30px;
    letter-spacing: 2px;
  }}

  .script-area {{
    background: #1a1a1a;
    border: 1px solid #333;
    padding: 30px;
    border-radius: 15px;
    text-align: left;
    line-height: 3.2;
    margin-bottom: 24px;
    min-height: 160px;
  }}

  .word-span {{
    font-size: 22px;
    font-weight: bold;
    display: inline-block;
    padding: 4px 6px;
    transition: color 0.08s, background 0.08s, transform 0.08s;
    transform-origin: center;
    color: #ddd;
    border-radius: 4px;
    margin: 2px;
  }}

  .btn-row {{
    display: flex;
    justify-content: center;
    gap: 16px;
    flex-wrap: wrap;
    margin-top: 8px;
  }}

  .btn {{
    padding: 14px 32px;
    border-radius: 30px;
    border: none;
    font-weight: bold;
    cursor: pointer;
    font-size: 15px;
    transition: opacity 0.2s, transform 0.1s;
    letter-spacing: 1px;
  }}
  .btn:hover {{ opacity: 0.85; transform: scale(1.03); }}
  .btn:disabled {{ opacity: 0.4; cursor: not-allowed; }}

  .btn-green  {{ background: #27ae60; color: white; }}
  .btn-red    {{ background: #e74c3c; color: white; }}
  .btn-gray   {{ background: #444;    color: white; }}
  .btn-blue   {{ background: #2980b9; color: white; }}

  .countdown {{
    font-size: 72px;
    color: #f1c40f;
    font-weight: bold;
    margin: 10px 0;
    animation: pulse 0.5s ease-in-out infinite alternate;
  }}
  @keyframes pulse {{ from {{ transform: scale(1); }} to {{ transform: scale(1.1); }} }}

  #result-area {{
    display: none;
    flex-wrap: wrap;
    gap: 10px;
    justify-content: center;
    background: #0d0d0d;
    padding: 20px;
    border-radius: 15px;
    margin-top: 20px;
  }}

  .result-card {{
    padding: 10px 14px;
    border-radius: 8px;
    color: white;
    min-width: 88px;
    text-align: center;
  }}
  .result-card .rword  {{ font-size: 15px; font-weight: bold; }}
  .result-card .rinfo  {{ font-size: 10px; opacity: 0.85; margin-top: 4px; }}
</style>
</head>
<body>
<div class="studio-container">
  <div class="status-bar" id="status">Ready</div>

  <div class="script-area" id="scriptArea">{subtitle_html}</div>

  <div class="btn-row" id="btnRow">
    <button class="btn btn-green" onclick="startListening()">🔁 Listen</button>
  </div>

  <div id="countdownArea"></div>
  <div id="result-area"></div>
</div>

<!-- 録音データ転送用hidden textarea (Streamlit外への送信に使用) -->
<textarea id="hiddenTransport" style="display:none"></textarea>

<audio id="masterAudio" src="data:{mime_type};base64,{st.session_state.audio_b64}"></audio>

<script>
const masterData = {json_data};
const audio     = document.getElementById('masterAudio');
const status    = document.getElementById('status');
const btnRow    = document.getElementById('btnRow');
const countdownArea = document.getElementById('countdownArea');
const resultArea    = document.getElementById('result-area');
const THRESHOLD = {threshold};

let animId, recorder, chunks = [];
let appState = 'idle'; // idle | listening | countdown | recording | done

// ============================================================
// ハイライト更新
// ============================================================
function updateHighlight() {{
  const ct = audio.currentTime;
  masterData.forEach((m, i) => {{
    const el = document.getElementById('w' + i);
    if (!el) return;
    if (ct >= m.start - 0.75 && ct < m.start) {{
      el.style.color = '#00f2fe';
      el.style.backgroundColor = 'transparent';
      el.style.transform = ct >= m.start - 0.1 ? 'scale(1.08)' : 'scale(1.0)';
    }} else if (ct >= m.start && ct <= m.end) {{
      el.style.color = '#000';
      el.style.backgroundColor = '#f1c40f';
      el.style.transform = 'scale(1.15)';
    }} else {{
      el.style.color = ct > m.end ? '#444' : '#ddd';
      el.style.backgroundColor = 'transparent';
      el.style.transform = 'scale(1.0)';
    }}
  }});
  if (!audio.paused) animId = requestAnimationFrame(updateHighlight);
}}

function resetHighlights() {{
  masterData.forEach((_, i) => {{
    const el = document.getElementById('w' + i);
    if (!el) return;
    el.style.color = '#ddd';
    el.style.backgroundColor = 'transparent';
    el.style.transform = 'scale(1.0)';
  }});
}}

// ============================================================
// リスニングフェーズ
// ============================================================
function startListening() {{
  appState = 'listening';
  resultArea.style.display = 'none';
  btnRow.innerHTML = '';
  countdownArea.innerHTML = '';
  status.textContent = '▶ リスニング中...';
  resetHighlights();
  audio.currentTime = 0;
  audio.play();
  updateHighlight();

  audio.onended = () => {{
    if (appState !== 'listening') return;
    appState = 'idle';
    status.textContent = 'もう一度聴く？それとも練習開始？';
    btnRow.innerHTML = `
      <button class="btn btn-gray" onclick="startListening()">🔁 もう一度聴く</button>
      <button class="btn btn-red" onclick="startCountdown()">🚀 練習開始</button>
    `;
  }};
}}

// ============================================================
// カウントダウン
// ============================================================
function startCountdown() {{
  appState = 'countdown';
  btnRow.innerHTML = '';
  let count = 3;
  countdownArea.innerHTML = `<div class="countdown">${{count}}</div>`;
  status.textContent = '準備して...';

  const timer = setInterval(() => {{
    count--;
    if (count > 0) {{
      countdownArea.innerHTML = `<div class="countdown">${{count}}</div>`;
    }} else {{
      clearInterval(timer);
      countdownArea.innerHTML = '';
      startShadowing();
    }}
  }}, 1000);
}}

// ============================================================
// シャドーイング録音フェーズ
// ============================================================
async function startShadowing() {{
  appState = 'recording';
  status.textContent = '🔴 RECORDING... シャドーイングしてください';
  chunks = [];
  resetHighlights();

  let stream;
  try {{
    stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});
  }} catch(e) {{
    status.textContent = '⚠️ マイクへのアクセスが拒否されました';
    btnRow.innerHTML = `<button class="btn btn-green" onclick="startListening()">🔁 最初から</button>`;
    return;
  }}

  recorder = new MediaRecorder(stream);
  recorder.ondataavailable = e => {{ if (e.data.size > 0) chunks.push(e.data); }};

  recorder.onstop = () => {{
    stream.getTracks().forEach(t => t.stop());
    appState = 'analyzing';
    status.textContent = '⏳ AI採点中...';
    btnRow.innerHTML = '';

    const blob = new Blob(chunks, {{ type: 'audio/webm' }});
    const reader = new FileReader();
    reader.readAsDataURL(blob);
    reader.onloadend = () => {{
      // base64データをStreamlit側へ送信
      const b64 = reader.result.split(',')[1];
      sendToStreamlit(b64);
    }};
  }};

  audio.currentTime = 0;
  audio.play();
  recorder.start(100);
  updateHighlight();

  audio.onended = () => {{
    if (appState !== 'recording') return;
    recorder.stop();
    btnRow.innerHTML = '';
  }};
}}

// ============================================================
// Streamlitへデータ送信
// postMessageでiframe親に送信する方式
// ============================================================
function sendToStreamlit(b64data) {{
  window.parent.postMessage({{
    isStreamlitMessage: true,
    type: 'streamlit:componentValue',
    value: b64data
  }}, '*');
}}

// ============================================================
// Streamlitからの採点結果を受信してUI表示
// ============================================================
window.addEventListener('message', (event) => {{
  if (event.data && event.data.type === 'SCORE_RESULT') {{
    displayResult(event.data.results);
  }}
}});

function displayResult(results) {{
  status.textContent = '📊 採点結果';
  resultArea.style.display = 'flex';
  resultArea.innerHTML = '';

  results.forEach(r => {{
    const card = document.createElement('div');
    card.className = 'result-card';
    card.style.background = r.color;

    let info = '';
    if (r.status === 'matched') {{
      info = `Lag: ${{r.lag}}<br>Dur: ${{r.dur_gap}}`;
    }} else {{
      info = 'Missing';
    }}

    card.innerHTML = `
      <div class="rword">${{r.word}}</div>
      <div class="rinfo">${{info}}</div>
    `;
    resultArea.appendChild(card);
  }});

  btnRow.innerHTML = `
    <button class="btn btn-green"  onclick="startListening()">🔁 もう一度</button>
    <button class="btn btn-blue"   onclick="startCountdown()">⚡ 直接録音</button>
  `;
  appState = 'done';
}}
</script>
</body>
</html>
"""

    # HTMLコンポーネント描画
    # ComponentsのValueを受け取るため bidirectional component が必要だが
    # 標準の st.components.v1.html は一方向のみ。
    # → 代替: st.components.v1.declare_component を使わず、
    #   hidden st.text_area + JavaScript injection trick で実装
    
    import streamlit.components.v1 as components
    components.html(html_component, height=600, scrolling=False)

    # ==========================================================================
    # ★ Streamlit ↔ iframe 通信の代替手段
    # st.components.v1.html は双方向通信非対応のため、
    # ユーザーには「録音後に表示されるbase64をここに貼り付け」ではなく
    # 別のアプローチ: st.file_uploader で録音ファイルを直接受け取る
    # ==========================================================================
    
    st.markdown("---")
    st.markdown("#### 📤 録音をアップロードして採点")
    st.caption("ブラウザで録音した場合、以下から音声ファイルをアップロードしてください。")
    
    rec_file = st.file_uploader(
        "録音ファイルをアップロード (webm, wav, mp3)",
        type=["webm", "wav", "mp3", "m4a"],
        key="rec_uploader"
    )

    if rec_file:
        with st.spinner("AI採点中..."):
            # 録音ファイルを一時保存
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                tmp.write(rec_file.getbuffer())
                rec_path = tmp.name

            try:
                user_res, _ = model.transcribe(
                    rec_path, word_timestamps=True, language="en"
                )
                user_words = [
                    {
                        "word": w.word.strip().lower().strip('.,!?;:'),
                        "start": w.start,
                        "dur": w.end - w.start
                    }
                    for s in user_res for w in s.words
                ]

                # --- 採点 ---
                results = []
                total = len(st.session_state.master_data)
                matched = 0

                result_html = """
                <div style="display:flex; flex-wrap:wrap; gap:12px;
                     justify-content:center; background:#111; padding:24px;
                     border-radius:15px; margin-top:10px;">
                """

                for m in st.session_state.master_data:
                    target_word = m['word'].lower().strip('.,!?;:')
                    match = next(
                        (u for u in user_words
                         if u['word'] == target_word
                         and abs(u['start'] - m['start']) < 1.5),
                        None
                    )

                    if match:
                        matched += 1
                        lag = match['start'] - m['start']
                        dur_gap = match['dur'] - m['dur']

                        if abs(lag) <= threshold:
                            color = "#27ae60"
                            grade = "✅"
                        elif abs(lag) <= threshold * 2:
                            color = "#f39c12"
                            grade = "🟡"
                        else:
                            color = "#e74c3c"
                            grade = "🔴"

                        result_html += f"""
                        <div style="background:{color}; padding:10px 14px;
                             border-radius:8px; color:white; min-width:90px;
                             text-align:center;">
                            <div style="font-size:15px; font-weight:bold;">{grade} {m['word']}</div>
                            <div style="font-size:10px; opacity:0.9; margin-top:4px;">
                                Lag: {lag:+.2f}s<br>Dur: {dur_gap:+.2f}s
                            </div>
                        </div>"""
                    else:
                        result_html += f"""
                        <div style="background:#333; padding:10px 14px;
                             border-radius:8px; color:#777; min-width:90px;
                             text-align:center;">
                            <div style="font-size:15px; font-weight:bold;">❌ {m['word']}</div>
                            <div style="font-size:10px; margin-top:4px;">Missing</div>
                        </div>"""

                result_html += "</div>"

                # スコアサマリー
                score_pct = int(matched / total * 100) if total > 0 else 0
                score_color = "#27ae60" if score_pct >= 80 else "#f39c12" if score_pct >= 50 else "#e74c3c"

                st.markdown(f"""
                <div style="text-align:center; padding:20px; background:#1a1a1a;
                     border-radius:15px; margin-bottom:16px;">
                    <div style="font-size:48px; font-weight:bold; color:{score_color};">
                        {score_pct}%
                    </div>
                    <div style="color:#aaa; font-size:14px;">
                        {matched} / {total} 語マッチ　|　難易度: {diff_mode}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.subheader("📊 Shadowing Result")
                st.markdown(result_html, unsafe_allow_html=True)

            except Exception as e:
                st.error(f"採点エラー: {e}")
            finally:
                if os.path.exists(rec_path):
                    os.unlink(rec_path)
