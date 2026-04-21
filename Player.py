import streamlit as st
import json
import os
import base64
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
from datetime import datetime
from Script import process_youtube_video

# --- 設定 ---
APP_NAME = "LingoLoop AI"
DRIVE_FOLDER_ID = '1S1c7T0qe1e84xDvEZsZBQuFRbLREph1C' 
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

st.set_page_config(page_title=APP_NAME, layout="wide")

# --- Google 連携関数 ---
def get_google_service(service_name, version):
    token_info = st.secrets["google_drive_token"]
    creds = Credentials.from_authorized_user_info(token_info, SCOPES)
    return build(service_name, version, credentials=creds)

def list_saved_videos():
    service = get_google_service('drive', 'v3')
    results = service.files().list(
        q=f"'{DRIVE_FOLDER_ID}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        fields="files(id, name)"
    ).execute()
    return results.get('files', [])

def get_files_in_folder(folder_id):
    service = get_google_service('drive', 'v3')
    results = service.files().list(
        q=f"'{folder_id}' in parents",
        fields="files(id, name, mimeType)"
    ).execute()
    return results.get('files', [])

def download_file(file_id):
    service = get_google_service('drive', 'v3')
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    return fh.getvalue()

def save_to_spreadsheet(en, jp, video_name, memo):
    try:
        service = get_google_service('sheets', 'v4')
        spreadsheet_id = st.secrets["SPREADSHEET_ID"]
        range_name = 'シート1!A2'
        values = [[en, jp, video_name, memo, datetime.now().strftime("%Y-%m-%d %H:%M")]]
        body = {'values': values}
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id, range=range_name,
            valueInputOption='USER_ENTERED', insertDataOption='INSERT_ROWS', body=body
        ).execute()
        return True
    except Exception as e:
        st.error(f"スプレッドシート保存エラー: {e}")
        return False

# --- サイドバー UI ---
with st.sidebar:
    st.header("LingoLoop AI")
    
    st.subheader("新規動画を追加")
    new_url = st.text_input("YouTube URL")
    new_folder_name = st.text_input("保存名 (空なら動画ID)")
    if st.button("解析開始"):
        if new_url:
            with st.spinner("解析中... 数分かかります"):
                try:
                    process_youtube_video(new_url, new_folder_name)
                    st.success("解析完了！")
                    st.rerun()
                except Exception as e:
                    st.error(f"解析エラー: {e}")

    st.divider()
    st.subheader("学習ライブラリ")
    videos = list_saved_videos()
    selected_video = st.selectbox("動画を選択", videos, format_func=lambda x: x['name'])
    
    st.divider()
    st.subheader("📓 単語帳に保存")
    with st.form("word_form", clear_on_submit=True):
        new_en = st.text_input("英語表現")
        new_jp = st.text_input("日本語訳")
        new_memo = st.text_area("メモ (任意)", height=60)
        submit = st.form_submit_button("保存")
        if submit:
            if new_en and new_jp:
                v_name = selected_video['name'] if selected_video else "Unknown"
                if save_to_spreadsheet(new_en, new_jp, v_name, new_memo):
                    st.success("保存しました！")

# --- メインエリア ---
if selected_video:
    with st.spinner("データを読み込んでいます..."):
        folder_id = selected_video['id']
        files = get_files_in_folder(folder_id)
        video_id = next(f['id'] for f in files if 'video' in f['mimeType'])
        json_id = next(f['id'] for f in files if 'json' in f['mimeType'])
        video_data = download_file(video_id)
        json_data = download_file(json_id)
        video_base64 = base64.b64encode(video_data).decode()
        subtitles = json.loads(json_data.decode('utf-8'))

    sub_data_js = []
    for i, s in enumerate(subtitles):
        prefix = "⚠️ " if s.get('is_hard') else ""
        sub_data_js.append({
            "id": i, "start": s['start'], "end": s['end'],
            "text": prefix + s['text'], "translation": s['translation'],
            "note": s.get('note', '')
        })

    # ここが html_code。if selected_video: のブロック内(半角4スペース)に正確に配置
    html_code = f"""
    <div id="app-wrapper" class="hide-en hide-jp">
        <div id="video-header">
            <video id="v" controls playsinline webkit-playsinline>
                <source src="data:video/mp4;base64,{video_base64}" type="video/mp4">
            </video>
            <div class="learning-controls">
                <button class="ctrl-btn" id="btn-prev">⏮</button>
                <button class="ctrl-btn" id="btn-repeat">🔁 <span id="r-status">OFF</span></button>
                <button class="ctrl-btn" id="btn-next">⏭</button>
            </div>
            <div class="visibility-controls">
                <button class="vis-btn" id="toggle-en-btn">英</button>
                <button class="vis-btn" id="toggle-jp-btn">日</button>
                <span class="vis-label">表示切替</span>
            </div>
        </div>
        <div id="transcript-scroll-area">
            <div id="sl" style="position: relative; padding: 0; margin: 0;"></div>
            <div style="height: 100vh;"></div>
        </div>
    </div>
    <style>
        body, html {{ margin: 0; padding: 0; height: 100vh; width: 100vw; overflow: hidden; font-family: sans-serif; background: #fff; }}
        #app-wrapper {{ display: flex; flex-direction: column; height: 100vh; width: 100vw; }}
        #video-header {{ flex-shrink: 0; background: #000; z-index: 1000; box-shadow: 0 2px 5px rgba(0,0,0,0.2); }}
        video {{ width: 100%; aspect-ratio: 16/9; display: block; }}
        .learning-controls {{ display: flex; gap: 2px; padding: 4px; background: #333; }}
        .ctrl-btn {{ flex: 1; padding: 15px; border: none; border-radius: 4px; background: #555; color: white; font-weight: bold; font-size: 1.2em; }}
        .ctrl-btn.active {{ background: #f44336; }}
        .visibility-controls {{ display: flex; gap: 8px; padding: 6px 12px; background: #222; align-items: center; border-bottom: 1px solid #444; }}
        .vis-btn {{ padding: 6px 16px; border: 1px solid #666; border-radius: 20px; background: #444; color: #aaa; font-weight: bold; cursor: pointer; transition: 0.2s; }}
        .vis-btn.active {{ background: #2196f3; color: white; border-color: #2196f3; }}
        #transcript-scroll-area {{ flex-grow: 1; overflow-y: scroll; background: #fff; -webkit-overflow-scrolling: touch; padding: 0 !important; margin: 0 !important; scroll-behavior: auto; }}
        .item {{ position: relative; padding: 12px 60px 12px 15px; border-bottom: 1px solid #f0f0f0; cursor: pointer; box-sizing: border-box; opacity: 0.2; transition: opacity 0.3s; user-select: text; -webkit-user-select: text; }}
        .item.active {{ background: #fff9c4 !important; border-left: 8px solid #2196f3; opacity: 1; }}
        .item.near {{ opacity: 0.8; }}
        .copy-group {{ position: absolute; right: 5px; top: 8px; display: flex; flex-direction: column; gap: 4px; z-index: 200; }}
        .mini-copy-btn {{ background: #eee; border: 1px solid #ccc; border-radius: 4px; padding: 4px 6px; font-size: 0.8em; font-weight: bold; cursor: pointer; }}
        .en {{ font-weight: bold; font-size: 1.2em; line-height: 1.4; color: #000; pointer-events: none; }}
        .jp {{ font-size: 0.85em; color: #555; margin-top: 4px; pointer-events: none; }}
        .note {{ font-size: 0.7em; color: #d32f2f; margin-top: 3px; pointer-events: none; }}
        .star-text {{ display: none; color: #888; letter-spacing: 1px; }}
        #app-wrapper.hide-en .real-text {{ display: none; }}
        #app-wrapper.hide-en .star-text {{ display: inline; }}
        #app-wrapper.hide-en .mini-copy-btn:first-child {{ display: none; }}
        #app-wrapper.hide-jp .jp {{ display: none; }}
        #app-wrapper.hide-jp .mini-copy-btn:last-child {{ display: none; }}
        @media (min-width: 600px) {{ #app-wrapper {{ flex-direction: row; }} #video-header {{ width: 70%; height: 100vh; }} #transcript-scroll-area {{ width: 30%; height: 100vh; }} }}
    </style>
    <script>
        const data = {json.dumps(sub_data_js)};
        const v = document.getElementById('v');
        const sl = document.getElementById('sl');
        const ts = document.getElementById('transcript-scroll-area');
        const wrapper = document.getElementById('app-wrapper');
        let currentIdx = -1; 
        let repeatMode = 0; 
        let isWaiting = false;

        function copyText(txt) {{ navigator.clipboard.writeText(txt); }}

        const btnEn = document.getElementById('toggle-en-btn');
        const btnJp = document.getElementById('toggle-jp-btn');
        btnEn.onclick = () => {{ wrapper.classList.toggle('hide-en') ? btnEn.classList.remove('active') : btnEn.classList.add('active'); }};
        btnJp.onclick = () => {{ wrapper.classList.toggle('hide-jp') ? btnJp.classList.remove('active') : btnJp.classList.add('active'); }};

        data.forEach((s, i) => {{
            const div = document.createElement('div');
            div.id = 's-'+i; 
            div.className = 'item';
            const stars = s.text.replace(/[^\\s]/g, '*');
            div.innerHTML = `
                <div class="copy-group">
                    <button class="mini-copy-btn" onclick="event.stopPropagation(); copyText('${{s.text.replace(/'/g, "\\'")}}')">EN</button>
                    <button class="mini-copy-btn" onclick="event.stopPropagation(); copyText('${{s.translation.replace(/'/g, "\\'")}}')">日</button>
                </div>
                <div class="en">
                    <span class="real-text">${{s.text}}</span>
                    <span class="star-text">${{stars}}</span>
                </div>
                <div class="jp">${{s.translation}}</div>
                ${{s.note ? `<div class="note">💡 ${{s.note}}</div>` : ''}}
            `;
            div.onclick = () => jumpTo(i);
            sl.appendChild(div);
        }});

        function updateDisplay(idx) {{
            if (idx < 0) return;
            const items = document.querySelectorAll('.item');
            items.forEach((item, i) => {{
                item.classList.remove('active', 'near');
                if (i === idx) item.classList.add('active');
                else if (i === idx - 1 || i === idx + 1 || i === idx + 2) item.classList.add('near');
            }});
            if (idx === 0) {{ ts.scrollTop = 0; }} 
            else {{ const prevEl = document.getElementById('s-'+(idx-1)); if (prevEl) ts.scrollTop = prevEl.offsetTop; }}
        }}

        function jumpTo(idx) {{
            if(idx < 0 || idx >= data.length) return;
            isWaiting = false;
            currentIdx = idx;
            v.currentTime = data[idx].start;
            v.play();
            updateDisplay(idx);
        }}

        document.getElementById('btn-prev').onclick = () => jumpTo(currentIdx - 1);
        document.getElementById('btn-next').onclick = () => jumpTo(currentIdx + 1);
        const rBtn = document.getElementById('btn-repeat');
        rBtn.onclick = () => {{
            repeatMode = (repeatMode + 1) % 3;
            rBtn.classList.toggle('active', repeatMode > 0);
            const labels = ["OFF", "1s (聴)", "3s (練)"];
            document.getElementById('r-status').innerText = labels[repeatMode];
        }};

        v.addEventListener('timeupdate', () => {{
            const now = v.currentTime;
            if (repeatMode > 0 && currentIdx !== -1 && !isWaiting) {{
                const s = data[currentIdx];
                if (now >= s.end - 0.05) {{
                    isWaiting = true;
                    v.pause();
                    const waitTime = (repeatMode === 1) ? 1000 : 3000;
                    setTimeout(() => {{
                        if (repeatMode > 0 && isWaiting) {{ v.currentTime = s.start; v.play(); }}
                        isWaiting = false;
                    }}, waitTime);
                    return;
                }}
            }}
            if (!isWaiting) {{
                for (let i = 0; i < data.length; i++) {{
                    if (now >= data[i].start && now < data[i].end) {{
                        if (currentIdx !== i) {{ currentIdx = i; updateDisplay(i); }}
                        break;
                    }}
                }}
            }}
        }});
        updateDisplay(0);
    </script>
    """
    st.iframe(html_code, height=1200)