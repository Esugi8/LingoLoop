import os
import time
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

# 1. 環境設定
load_dotenv("API.env")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# 解析したい動画ファイルのパス
VIDEO_PATH = "sample_video.mp4" 

def main():
    # 2. アップロード
    print(f"Uploading {VIDEO_PATH}...")
    video_file = client.files.upload(file=VIDEO_PATH)

    # 3. 処理完了待機
    while video_file.state == "PROCESSING":
        print(".", end="", flush=True)
        time.sleep(2)
        video_file = client.files.get(name=video_file.name)
    
    print("\nProcessing complete. Generating JSON...")

    # 4. Gemini 3.1 Flash Lite での解析
    # response_mime_type を指定することで、確実にパース可能なJSONが返ります
    prompt = """
    Transcribe English audio to JSON: list of objects with 'start', 'end', 'text', and 'translation'.
    Important: 'start' and 'end' must be numbers representing total seconds (e.g., 3.5, NOT "0:03").
    Segments should be 1-2 sentences.
    """
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-preview",
        contents=[video_file, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        )
    )

    # 5. 結果の保存
    # response.text に JSON 文字列が入っているので、それを辞書に変換して保存
    output_data = json.loads(response.text)
    
    with open("subtitles.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    # 6. 後片付け（サーバー上のファイルを削除）
    client.files.delete(name=video_file.name)
    
    print("Success! Result saved to subtitles.json")
    print(f"Total segments: {len(output_data)}")

if __name__ == "__main__":
    main()