import os
import time
import json
import yt_dlp
from google import genai
from google.genai import types
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
import streamlit as st

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

# --- 設定項目 ---
DRIVE_FOLDER_ID = '1S1c7T0qe1e84xDvEZsZBQuFRbLREph1C' 
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    token_info = st.secrets["google_drive_token"]
    creds = Credentials.from_authorized_user_info(token_info, SCOPES)
    return build('drive', 'v3', credentials=creds)

def upload_to_drive(local_path, drive_folder_id, mime_type):
    service = get_drive_service()
    file_metadata = {'name': os.path.basename(local_path), 'parents': [drive_folder_id]}
    media = MediaFileUpload(local_path, mimetype=mime_type, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')

def create_drive_folder(folder_name, parent_id):
    service = get_drive_service()
    file_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]}
    file = service.files().create(body=file_metadata, fields='id').execute()
    return file.get('id')

def convert_to_seconds(time_str):
    try:
        time_str = str(time_str).strip()
        parts = time_str.split(':')
        if len(parts) == 2:
            return round(int(parts[0]) * 60 + float(parts[1]), 1)
        elif len(parts) == 3:
            return round(int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2]), 1)
        else:
            return float(time_str)
    except (ValueError, IndexError):
        return 0.0

def process_youtube_video(url, custom_folder_name=None):
    local_video = "temp_video.mp4"
    local_json = "temp_subtitles.json"

    ydl_opts = {
        'format': 'mp4[height<=480]',
        'outtmpl': local_video,
        'nocheckcertificate': True,
        'overwrites': True,
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        v_id = info['id']
        folder_display_name = custom_folder_name if custom_folder_name else v_id

    print(f"--- Uploading {v_id} to Gemini ---")
    video_file = client.files.upload(file=local_video)
    while video_file.state == "PROCESSING":
        time.sleep(2)
        video_file = client.files.get(name=video_file.name)

    print("--- Analyzing with Gemini (Natural Sound Spelling Mode) ---")
    prompt = """
    動画の英語音声を書き起こし、JSON形式のリストを出力してください。
    『実際に聞こえる音』を読みやすくアルファベットで綴った「Sound Spelling」を作成することが最重要ミッションです。
    
    [出力項目]
    - 'start', 'end', 'text', 'translation'
    - 'phonetic': 実際の音の流れを表現したもの（※全セグメントで必須）
    
    [Sound Spelling（phonetic）の厳守ルール]
    1. 原則として、単語の間には半角スペースを入れ、視認性を高めること。
    2. 音が完全に連結（リエゾン）して1語のように聞こえる部分のみ、単語を繋げて書くこと。
       - Check it out -> Chekeraut
       - What are you -> Waraya / Watcha
       - Get it -> Gerit
    3. 音の脱落（リダクション）を綴りに反映すること。
       - going to -> gonna
       - for you -> foya
       - want to -> wanna
    4. フラッピング（Tがラ行化）を反映すること（water -> warer）。
    5. 各語の頭文字を大文字にしたり、句読点（, . ?）を使うことでリズムを表現すること。
       例: "Oh, ekselent. Evryon wuz so-so nice."
    """
    
    # --- リトライロジックの追加 ---
    max_retries = 3
    response = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite-preview",
                contents=[video_file, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                )
            )
            break
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"!!! API Error: {e}. Retrying in 5s... ({attempt+2}/{max_retries}) ---")
                time.sleep(5)
                continue
            else:
                raise e
    
    raw_data = json.loads(response.text)
    refined_subtitles = []
    for item in raw_data:
        item['start'] = convert_to_seconds(item['start'])
        item['end'] = convert_to_seconds(item['end'])
        refined_subtitles.append(item)
    
    with open(local_json, "w", encoding="utf-8") as f:
        json.dump(refined_subtitles, f, ensure_ascii=False, indent=2)

    try:
        v_folder_id = create_drive_folder(folder_display_name, DRIVE_FOLDER_ID)
        upload_to_drive(local_video, v_folder_id, 'video/mp4')
        upload_to_drive(local_json, v_folder_id, 'application/json')
    except Exception as e:
        print(f"Drive Upload Error: {e}")

    os.remove(local_video)
    os.remove(local_json)
    client.files.delete(name=video_file.name)
    print(f"--- ALL DONE for {folder_display_name} ---")

if __name__ == "__main__":
    test_url = "https://www.youtube.com/watch?v=E6LpBIwGyA4"
    process_youtube_video(test_url)