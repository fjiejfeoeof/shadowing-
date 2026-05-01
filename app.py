import streamlit as st
import streamlit.components.v1 as components
import base64
import torch
from faster_whisper import WhisperModel
import json
import tempfile
import os
import math

@st.cache_resource
def load_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    return WhisperModel("base", device=device, compute_type=compute_type)

model = load_model()

st.set_page_config(page_title="Ultimate Shadowing Studio", layout="wide")
st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:#0d0d0d}
[data-testid="stSidebar"]{background:#161616}
h1,h2,h3{color:#e0e0e0}
</style>
""", unsafe_allow_html=True)

st.title("🎙️ Ultimate Shadowing Studio")

st.sidebar.header("⚙️ Settings")
diff_mode = st.sidebar.selectbox("難易度", ["1: Easy", "2: Normal", "3: Hard"])
threshold = {"1: Easy": 0.8, "2: Normal": 0.4, "3: Hard": 0.2}[diff_mode]
st.sidebar.markdown("---")
st.sidebar.markdown("""
**使い方**
1. 練習音声をアップロード
2. **Listen** で音声確認
3. **練習開始** でシャドーイング
4. 録音が自動ダウンロード
5. Step 3 にアップロードして採点
""")

for key in ["master_data", "audio_b64", "current_file", "mime_type"]:
    if key not in st.session_state:
        st.session_state[key] = None

# ── STEP 1 ─────────────────────────────────────────────────
st.markdown("### 📁 Step 1 : 練習音声をアップロード")
uploaded_file = st.file_uploader("音声ファイル (mp3 / wav / m4a / mp4)", type=["mp3","wav","m4a","mp4"])

if uploaded_file:
    if st.session_state.current_file != uploaded_file.name or st.session_state.master_data is None:
        with st.spinner("🔍 AIが音声を解析中..."):
            ext = os.path.splitext(uploaded_file.name)[1].lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(uploaded_file.getbuffer())
                tmp_path = tmp.name

            segments, _ = model.transcribe(tmp_path, word_timestamps=True, language="en")
            st.session_state.master_data = [
                {"word": w.word.strip(), "start": round(w.start,3),
                 "end": round(w.end,3), "dur": round(w.end-w.start,3)}
                for s in segments for w in s.words
            ]
            with open(tmp_path,"rb") as f:
                st.session_state.audio_b64 = base64.b64encode(f.read()).decode()
            st.session_state.mime_type = {
                ".mp3":"audio/mpeg",".wav":"audio/wav",
                ".m4a":"audio/mp4",".mp4":"audio/mp4"
            }.get(ext,"audio/wav")
            st.session_state.current_file = uploaded_file.name
            os.unlink(tmp_path)
        st.success(f"✅ 解析完了！ {len(st.session_state.master_data)} 語を検出しました。")

# ── STEP 2 ─────────────────────────────────────────────────
if st.session_state.master_data:
    st.markdown("### 🎙️ Step 2 : シャドーイング練習")

    master_data = st.session_state.master_data
    audio_b64   = st.session_state.audio_b64
    mime_type   = st.session_state.mime_type
    json_data   = json.dumps(master_data, ensure_ascii=False)
    word_count  = len(master_data)

    # height 動的計算: 1行8語、1行55px + 固定余白280px
    lines = math.ceil(word_count / 8)
    script_h = max(160, lines * 55)
    iframe_h = script_h + 280

    subtitle_html = " ".join(
        f'<span id="w{i}" class="ws">{m["word"]}</span>'
        for i, m in enumerate(master_data)
    )

    html = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#111;font-family:'Courier New',monospace;padding:20px}}
#status{{color:#00f2fe;font-weight:bold;font-size:20px;letter-spacing:2px;
  min-height:32px;margin-bottom:14px;text-align:center}}
#script{{background:#1a1a1a;border:1px solid #2a2a2a;border-radius:12px;
  padding:24px;line-height:3.0;margin-bottom:20px;min-height:{script_h}px}}
.ws{{font-size:20px;font-weight:bold;display:inline-block;padding:3px 5px;
  margin:2px;border-radius:4px;color:#ccc;
  transition:color .08s,background .08s,transform .08s;transform-origin:center}}
#btnRow{{display:flex;justify-content:center;gap:14px;flex-wrap:wrap;
  min-height:52px;margin-bottom:10px}}
.btn{{padding:12px 28px;border-radius:28px;border:none;font-weight:bold;
  font-size:14px;cursor:pointer;letter-spacing:.5px;
  transition:opacity .2s,transform .1s}}
.btn:hover{{opacity:.82;transform:scale(1.04)}}
.g{{background:#27ae60;color:#fff}}.r{{background:#e74c3c;color:#fff}}
.k{{background:#444;color:#fff}}.b{{background:#2980b9;color:#fff}}
#cd{{text-align:center;font-size:64px;font-weight:bold;color:#f1c40f;
  min-height:80px;display:none;
  animation:pulse .5s ease-in-out infinite alternate}}
@keyframes pulse{{from{{transform:scale(1)}}to{{transform:scale(1.1)}}}}
#dlMsg{{display:none;color:#00f2fe;text-align:center;font-size:13px;margin-top:12px;
  background:#0a2a3a;border-radius:8px;padding:10px}}
</style></head><body>
<div id="status">Ready</div>
<div id="script">{subtitle_html}</div>
<div id="btnRow"><button class="btn g" onclick="doListen()">🔁 Listen</button></div>
<div id="cd"></div>
<div id="dlMsg">⬇️ 録音ファイルが自動ダウンロードされました。<br>下の <b>Step 3</b> にアップロードして採点してください。</div>
<audio id="audio" src="data:{mime_type};base64,{audio_b64}"></audio>
<script>
const MD={json_data};
const audio=document.getElementById('audio');
const status=document.getElementById('status');
const btnRow=document.getElementById('btnRow');
const cd=document.getElementById('cd');
const dlMsg=document.getElementById('dlMsg');
const THR={threshold};
let state='idle',animId,recorder,chunks=[];

function hl(){{
  const ct=audio.currentTime;
  MD.forEach((m,i)=>{{
    const el=document.getElementById('w'+i);if(!el)return;
    if(ct>=m.start-.75&&ct<m.start){{
      el.style.color='#00f2fe';el.style.background='transparent';
      el.style.transform=ct>=m.start-.1?'scale(1.08)':'scale(1)';
    }}else if(ct>=m.start&&ct<=m.end){{
      el.style.color='#000';el.style.background='#f1c40f';el.style.transform='scale(1.15)';
    }}else{{
      el.style.color=ct>m.end?'#444':'#ccc';
      el.style.background='transparent';el.style.transform='scale(1)';
    }}
  }});
  if(!audio.paused)animId=requestAnimationFrame(hl);
}}
function resetHL(){{
  MD.forEach((_,i)=>{{
    const el=document.getElementById('w'+i);if(!el)return;
    el.style.color='#ccc';el.style.background='transparent';el.style.transform='scale(1)';
  }});
}}
function setBtns(h){{btnRow.innerHTML=h;}}

function doListen(){{
  if(state==='recording')return;
  state='listening';dlMsg.style.display='none';
  setBtns('');status.textContent='▶ リスニング中...';
  resetHL();audio.currentTime=0;audio.play();hl();
  audio.onended=()=>{{
    if(state!=='listening')return;
    state='idle';status.textContent='確認できましたか？';
    setBtns(`<button class="btn k" onclick="doListen()">🔁 もう一度聴く</button>
             <button class="btn r" onclick="doCountdown()">🚀 練習開始</button>`);
  }};
}}

function doCountdown(){{
  state='countdown';setBtns('');
  let n=3;cd.textContent=n;cd.style.display='block';
  status.textContent='準備して...';
  const t=setInterval(()=>{{
    n--;
    if(n>0){{cd.textContent=n;}}
    else{{clearInterval(t);cd.style.display='none';doRecord();}}
  }},1000);
}}

async function doRecord(){{
  state='recording';chunks=[];
  status.textContent='🔴 RECORDING...  シャドーイングしてください';setBtns('');
  let stream;
  try{{stream=await navigator.mediaDevices.getUserMedia({{audio:true}});}}
  catch(e){{
    status.textContent='⚠️ マイクへのアクセスが拒否されました';
    setBtns('<button class="btn g" onclick="doListen()">🔁 最初から</button>');
    state='idle';return;
  }}
  const mime=MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
    ?'audio/webm;codecs=opus'
    :MediaRecorder.isTypeSupported('audio/webm')?'audio/webm':'audio/ogg';
  recorder=new MediaRecorder(stream,{{mimeType:mime}});
  recorder.ondataavailable=e=>{{if(e.data.size>0)chunks.push(e.data);}};
  recorder.onstop=()=>{{
    stream.getTracks().forEach(t=>t.stop());
    state='done';
    const blob=new Blob(chunks,{{type:mime}});
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');
    a.href=url;a.download='shadowing_recording.webm';
    document.body.appendChild(a);a.click();
    setTimeout(()=>{{URL.revokeObjectURL(url);a.remove();}},1000);
    setBtns(`<button class="btn g" onclick="doListen()">🔁 もう一度</button>
             <button class="btn b" onclick="doCountdown()">⚡ 直接録音</button>`);
    dlMsg.style.display='block';
    status.textContent='✅ 録音完了 → Step 3 にアップロードしてください';
  }};
  resetHL();audio.currentTime=0;audio.play();recorder.start(100);hl();
  audio.onended=()=>{{if(state==='recording')recorder.stop();}};
}}
</script></body></html>"""

    components.html(html, height=iframe_h, scrolling=False)

    # ── STEP 3 ─────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📊 Step 3 : 採点")
    st.caption("録音が自動ダウンロードされたら、そのファイルをここにアップロードしてください。")

    rec_file = st.file_uploader(
        "録音ファイルをアップロード (webm / wav / mp3 / ogg)",
        type=["webm","wav","mp3","m4a","ogg"],
        key="rec_uploader"
    )

    if rec_file:
        with st.spinner("🧠 AI採点中..."):
            ext = os.path.splitext(rec_file.name)[1] or ".webm"
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(rec_file.getbuffer())
                rec_path = tmp.name
            try:
                user_res, _ = model.transcribe(rec_path, word_timestamps=True, language="en")
                user_words = [
                    {"word": w.word.strip().lower().strip('.,!?;:\'"'),
                     "start": w.start, "dur": w.end-w.start}
                    for s in user_res for w in s.words
                ]
                total = len(master_data)
                matched = 0
                cards = []
                for m in master_data:
                    tgt = m["word"].lower().strip('.,!?;:\'"')
                    hit = next((u for u in user_words
                                if u["word"]==tgt and abs(u["start"]-m["start"])<1.5), None)
                    if hit:
                        matched += 1
                        lag = hit["start"]-m["start"]
                        dg  = hit["dur"]-m["dur"]
                        if abs(lag)<=threshold:       c,ic="#27ae60","✅"
                        elif abs(lag)<=threshold*2:   c,ic="#f39c12","🟡"
                        else:                          c,ic="#e74c3c","🔴"
                        cards.append(
                            f'<div style="background:{c};padding:10px 14px;border-radius:8px;'
                            f'color:#fff;min-width:88px;text-align:center;">'
                            f'<div style="font-size:14px;font-weight:bold;">{ic} {m["word"]}</div>'
                            f'<div style="font-size:10px;opacity:.9;margin-top:3px;">'
                            f'Lag:{lag:+.2f}s<br>Dur:{dg:+.2f}s</div></div>'
                        )
                    else:
                        cards.append(
                            f'<div style="background:#333;padding:10px 14px;border-radius:8px;'
                            f'color:#888;min-width:88px;text-align:center;">'
                            f'<div style="font-size:14px;font-weight:bold;">❌ {m["word"]}</div>'
                            f'<div style="font-size:10px;margin-top:3px;">Missing</div></div>'
                        )
                pct = int(matched/total*100) if total else 0
                sc  = "#27ae60" if pct>=80 else "#f39c12" if pct>=50 else "#e74c3c"
                st.markdown(
                    f'<div style="text-align:center;padding:24px;background:#1a1a1a;'
                    f'border-radius:14px;margin-bottom:16px;">'
                    f'<div style="font-size:56px;font-weight:bold;color:{sc};">{pct}%</div>'
                    f'<div style="color:#999;font-size:14px;margin-top:6px;">'
                    f'{matched}/{total}語マッチ &nbsp;|&nbsp; 難易度:{diff_mode}</div></div>',
                    unsafe_allow_html=True
                )
                st.markdown(
                    '<div style="display:flex;flex-wrap:wrap;gap:10px;'
                    'justify-content:center;padding:10px;">'
                    + "".join(cards) + "</div>",
                    unsafe_allow_html=True
                )
            except Exception as e:
                st.error(f"採点エラー: {e}")
            finally:
                if os.path.exists(rec_path):
                    os.unlink(rec_path)
