import os
import openai
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage ,ImageMessage, AudioMessage
from google.cloud import storage
from google.oauth2 import service_account

app = Flask(__name__)
from dotenv import load_dotenv
load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
openai.api_key = OPENAI_API_KEY
# Google Cloud Storageの設
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")

# GOOGLE_APPLICATION_CREDENTIALS環境変数からJSONファイルのパスを取得
json_path = "./credentials.json"

# JSONファイルから認証情報を読み込む
credentials = service_account.Credentials.from_service_account_file(json_path)

# Google Cloud Storageクライアントを初期化
storage_client = storage.Client(credentials=credentials, project=credentials.project_id)
bucket = storage_client.bucket(GCS_BUCKET_NAME)

@app.route("/")
def hello_world():
    return "Hello, World!"

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

@app.route("/test-gcs")
def test_gcs_connection():
    test_file_name = "test/gcs_test.txt"
    test_data = "これはテストデータです。"

    try:
        # テストファイルをバケットに書き込み
        blob = bucket.blob(test_file_name)
        blob.upload_from_string(test_data)
        app.logger.info(f"ファイル '{test_file_name}' をバケット '{GCS_BUCKET_NAME}' に書き込みました。")

        # テストファイルをバケットから読み込み
        blob = bucket.blob(test_file_name)
        data = blob.download_as_text()
        app.logger.info(f"ファイル '{test_file_name}' から読み込んだデータ: {data}")

        if data == test_data:
            return f"バケット '{GCS_BUCKET_NAME}' への書き込みおよび読み込みテストに成功しました。"
        else:
            return f"バケット '{GCS_BUCKET_NAME}' のデータ整合性エラー。", 500

    except Exception as e:
        app.logger.error(f"バケット '{GCS_BUCKET_NAME}' への接続に失敗しました: {e}")
        return f"バケットへの接続に失敗しました: {e}", 500

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text  # ユーザーからのメッセージを取得
    user_id = event.source.user_id  # ユーザーのIDを取得

    # OpenAI APIを使用してレスポンスを生成
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # モデルの指定
        messages=[{"role": "system", "content": "You are an assistant skilled in programming, general knowledge, and tool usage advice. You provide helpful information for tasks in Line.And You must return messages in japanese."},  # システムメッセージの設定
                  {"role": "user", "content": user_message}],  # ユーザーメッセー
        max_tokens=250          # 生成するトークンの最大数
    )
    res = f"あなたのユーザーIDは{user_id}です。\n"
    res += response.choices[0].message['content'].strip()
    # ユーザーのIDとメッセージをGoogle Cloud Storageに保存
    blob = bucket.blob(f"{user_id}/{user_message}.txt")
    blob.upload_from_string(res)
    # LINEユーザーにレスポンスを返信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=res)  # 正しいレスポンスの取得方法
    )

@handler.add(MessageEvent, message=AudioMessage)
def handle_audio(event):
    user_id = event.source.user_id  # ユーザーのIDを取得
    message_id = event.message.id  # メッセージのIDを取得

    # LINEから音声コンテンツを取得
    message_content = line_bot_api.get_message_content(message_id)
    audio_bytes = b''
    for chunk in message_content.iter_content():
        audio_bytes += chunk

    # 音声ファイルをGCSに保存
    file_path = f"{user_id}/{message_id}.m4a"  # 一意のファイル名
    blob = bucket.blob(file_path)
    blob.upload_from_string(audio_bytes, content_type='audio/m4a')

    # 音声ファイルをOpenAI APIに送信してテキストに変換
    with open("audio.m4a", "wb") as f:
        f.write(audio_bytes)

    audio_file = open("audio.m4a", "rb")
    transcript = openai.Audio.transcribe("whisper-1", audio_file)

    # 変換されたテキストを使用してレスポンスを生成
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # モデルの指定
        messages=[
            {"role": "system", "content": "You are an assistant skilled in programming, general knowledge, and tool usage advice. You provide helpful information for tasks in Line. And You must return messages in japanese."},  # システムメッセージの設定
            {"role": "user", "content": transcript["text"]},  # 変換されたテキストをユーザーメッセージとして使用
        ],
        max_tokens=250  # 生成するトークンの最大数
    )

    res = f"あなたのユーザーIDは{user_id}です。\n"
    res += response.choices[0].message['content'].strip()

    # ユーザーのIDとメッセージをGoogle Cloud Storageに保存
    blob = bucket.blob(f"{user_id}/{message_id}.txt")
    blob.upload_from_string(res)

    # LINEユーザーにレスポンスを返信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=res)
    )

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id  # ユーザーのIDを取得
    message_id = event.message.id  # メッセージのIDを取得

    # LINEから画像コンテンツを取得
    message_content = line_bot_api.get_message_content(message_id)
    image_bytes = b''
    for chunk in message_content.iter_content():
        image_bytes += chunk

    # 画像をGCSに保存
    file_path = f"{user_id}/{message_id}.jpg"  # 一意のファイル名
    blob = bucket.blob(file_path)
    blob.upload_from_string(image_bytes, content_type='image/jpeg')

    # ユーザーに保存完了のメッセージを送信
    response_message = f"画像が保存されました: {file_path}"
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response_message)
    )

if __name__ == "__main__":
    app.run()