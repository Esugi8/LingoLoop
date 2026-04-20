import streamlit as st
import json
import os
import base64
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
# --- Script.py から関数をインポート ---
from Script import process_youtube_video

# --- 設定 ---
APP_NAME = "LingoLoop AI"
TOKEN_FILE = 'token.json'
DRIVE_FOLDER_ID = '1S1c7T0qe1e84xDvEZsZBQuFRbLREph1C' # Script.pyと同じもの
SCOPES = ['https://www.googleapis.com/auth/drive']

st.set_page_config(page_title=APP_NAME, layout="wide")

# --- Google Drive 連携関数 ---
# def get_drive_service():
    # creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    # return build('drive', 'v3', credentials=creds)
    
def get_drive_service():
    # ファイルからではなく、Secretsの辞書から認証情報を生成
    token_info = st.secrets["google_drive_token"]
    creds = Credentials.from_authorized_user_info(token_info, SCOPES)
    return build('drive', 'v3', credentials=creds)

def list_saved_videos():
    service = get_drive_service()
    # 親フォルダ内のフォルダ（動画ID）一覧を取得 (ゴミ箱を除外)
    results = service.files().list(
        q=f"'{DRIVE_FOLDER_ID}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        fields="files(id, name)"
    ).execute()
    return results.get('files', [])

def get_files_in_folder(folder_id):
    service = get_drive_service()
    results = service.files().list(
        q=f"'{folder_id}' in parents",
        fields="files(id, name, mimeType)"
    ).execute()
    return results.get('files', [])

def download_file(file_id):
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    return fh.getvalue()

# --- メイン UI ---
# タイトル (st.title) は削除

# Streamlit自体の余白を消すための魔法のCSS
st.markdown("""
    <style>
        /* メインコンテンツのパディングをゼロにする */
        .block-container {
            padding-top: 0rem;
            padding-bottom: 0rem;
            padding-left: 0rem;
            padding-right: 0rem;
        }
        /* ヘッダー（右上のメニューなど）を隠す */
        header {visibility: hidden;}
        /* フッターを隠す */
        footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# サイドバーの設定
with st.sidebar:
    st.header("LingoLoop AI") # サイドバーに名前を移動
    # --- 新規動画の追加セクション ---
    st.header("新規動画を追加")
    new_url = st.text_input("YouTube URL")
    new_folder_name = st.text_input("保存名 (空なら動画ID)")
    
    if st.button("解析開始"):
        if new_url:
            with st.spinner("解析中... 数分かかります"):
                try:
                    process_youtube_video(new_url, new_folder_name)
                    st.success("解析完了！")
                    st.rerun() # リストを更新するために再起動
                except Exception as e:
                    st.error(f"解析エラー: {e}")
        else:
            st.warning("URLを入力してください")

    st.divider()

    # --- 学習ライブラリセクション ---
    st.header("学習ライブラリ")
    videos = list_saved_videos()
    if not videos:
        st.write("保存された動画がありません。")
    
    selected_video = st.selectbox("動画を選択", videos, format_func=lambda x: x['name'])

# 動画が選択されたらデータを読み込む
if selected_video:
    with st.spinner("データを読み込んでいます..."):
        folder_id = selected_video['id']
        files = get_files_in_folder(folder_id)
        
        # JSONと動画のIDを特定
        video_id = next(f['id'] for f in files if 'video' in f['mimeType'])
        json_id = next(f['id'] for f in files if 'json' in f['mimeType'])
        
        # ダウンロード（メモリ上に保持）
        video_data = download_file(video_id)
        json_data = download_file(json_id)
        
        video_base64 = base64.b64encode(video_data).decode()
        subtitles = json.loads(json_data.decode('utf-8'))

    # JavaScript用のデータ作成
    sub_data_js = []
    for i, s in enumerate(subtitles):
        # Geminiが判定した「難しい箇所」にアイコンをつける
        prefix = "⚠️ " if s.get('is_hard') else ""
        sub_data_js.append({
            "id": i, "start": s['start'], "end": s['end'],
            "text": prefix + s['text'], "translation": s['translation'],
            "note": s.get('note', '')
        })

# --- プレイヤー HTML (フォーカス表示・リピート時ジャンプ対応) ---
    html_code = f"""
    <div id="app-wrapper">
        <div id="video-fixed-container">
            <video id="v" controls playsinline webkit-playsinline>
                <source src="data:video/mp4;base64,{video_base64}" type="video/mp4">
            </video>
            <div class="learning-controls">
                <button class="ctrl-btn" id="btn-prev">⏮</button>
                <button class="ctrl-btn" id="btn-repeat">🔁 <span id="r-status">OFF</span></button>
                <button class="ctrl-btn" id="btn-next">⏭</button>
            </div>
            <div class="jp-toggle-bar">
                <label><input type="checkbox" id="toggle-jp" checked> 日本語訳を表示</label>
            </div>
        </div>
        
        <div id="transcript-scroll-area">
            <div id="sl"></div>
            <!-- 下部の余白は不要になったため削除（または小さく） -->
        </div>
    </div>

    <style>
        body, html {{ margin: 0; padding: 0; height: 100vh; overflow: hidden; font-family: sans-serif; background: #fff; }}
        #app-wrapper {{ display: flex; flex-direction: column; height: 100vh; width: 100vw; }}
        
        #video-fixed-container {{ flex-shrink: 0; background: #000; z-index: 1000; width: 100%; }}
        video {{ width: 100%; aspect-ratio: 16/9; display: block; }}
        
        .learning-controls {{ display: flex; gap: 2px; padding: 2px; background: #333; }}
        .ctrl-btn {{ flex: 1; padding: 15px; border: none; border-radius: 2px; background: #444; color: white; font-weight: bold; font-size: 1.1em; }}
        .ctrl-btn.active {{ background: #f44336; }}
        .jp-toggle-bar {{ padding: 6px 12px; font-size: 0.8em; color: #ccc; background: #222; border-bottom: 1px solid #444; }}

        #transcript-scroll-area {{
            flex-grow: 1;
            overflow-y: auto;
            background: #fff;
        }}

        .item {{ 
            padding: 10px 15px; 
            border-bottom: 1px solid #eee; 
            cursor: pointer;
            display: none; /* 基本は非表示 */
        }}
        /* 表示対象（前1文、今、後2文）だけを表示 */
        .item.show-context {{ 
            display: block; 
        }}
        .item.active {{ 
            background: #fff9c4; 
            border-left: 8px solid #2196f3; 
            display: block;
        }}
        .en {{ font-weight: bold; font-size: 0.9em; line-height: 1.4; color: #000; }}
        .jp {{ font-size: 0.8em; color: #555; margin-top: 4px; }}
        .note {{ font-size: 0.75em; color: #d32f2f; margin-top: 4px; }}
        .hidden {{ display: none !important; }}

        @media (min-width: 600px) {{
            #app-wrapper {{ flex-direction: row; }}
            #video-fixed-container {{ width: 70%; height: 100vh; }}
            #transcript-scroll-area {{ width: 30%; height: 100vh; }}
        }}
    </style>

    <script>
        const data = {json.dumps(sub_data_js)};
        const v = document.getElementById('v');
        const sl = document.getElementById('sl');
        const ts = document.getElementById('transcript-scroll-area');
        let currentIdx = 0; 
        let isRepeat = false;

        // 全字幕の生成（最初はcurrentIdx=0付近を表示）
        function buildSubtitles() {{
            sl.innerHTML = '';
            data.forEach((s, i) => {{
                const div = document.createElement('div');
                div.id = 's-'+i; 
                div.className = 'item';
                div.innerHTML = `<div class="en">${{s.text}}</div>
                                 <div class="jp">${{s.translation}}</div>
                                 ${{s.note ? `<div class="note">💡 ${{s.note}}</div>` : ''}}`;
                div.onclick = () => jumpTo(i);
                sl.appendChild(div);
            }});
            updateDisplay(0);
        }}

        // 表示の更新（前1文、今、後2文のみ表示）
        function updateDisplay(idx) {{
            const items = document.querySelectorAll('.item');
            items.forEach((item, i) => {{
                item.classList.remove('active', 'show-context');
                if (i === idx) {{
                    item.classList.add('active');
                }} else if (i === idx - 1 || i === idx + 1 || i === idx + 2) {{
                    item.classList.add('show-context');
                }}
            }});
            // 常に一番上へ
            ts.scrollTop = 0;
        }}

        function jumpTo(idx) {{
            if(idx < 0 || idx >= data.length) return;
            currentIdx = idx; // ここで即座にcurrentIdxを更新するのが重要
            updateDisplay(idx);
            v.currentTime = data[idx].start;
            v.play();
        }}

        document.getElementById('btn-prev').onclick = () => jumpTo(currentIdx - 1);
        document.getElementById('btn-next').onclick = () => jumpTo(currentIdx + 1);
        
        const rBtn = document.getElementById('btn-repeat');
        rBtn.onclick = () => {{
            isRepeat = !isRepeat;
            rBtn.classList.toggle('active', isRepeat);
            document.getElementById('r-status').innerText = isRepeat ? "ON" : "OFF";
        }};

        document.getElementById('toggle-jp').onchange = (e) => {{
            const jpStyle = document.createElement('style');
            jpStyle.id = "jp-hide-style";
            jpStyle.innerHTML = ".jp {{ display: none; }}";
            if (!e.target.checked) document.head.appendChild(jpStyle);
            else {{
                const s = document.getElementById("jp-hide-style");
                if(s) s.remove();
            }}
        }};

        v.addEventListener('timeupdate', () => {{
            const now = v.currentTime;
            const s = data[currentIdx];

            // リピート処理
            if (isRepeat) {{
                // 現在のセグメントを越えたら戻る
                if (now >= s.end - 0.05 || now < s.start - 0.1) {{
                    v.currentTime = s.start;
                    v.play();
                }}
                return;
            }}

            // 通常再生時の自動追従
            for (let i = 0; i < data.length; i++) {{
                if (now >= data[i].start && now < data[i].end) {{
                    if (currentIdx !== i) {{
                        currentIdx = i;
                        updateDisplay(i);
                    }}
                    break;
                }}
            }}
        }});

        buildSubtitles();
    </script>
    """
    st.iframe(html_code, height=1200)