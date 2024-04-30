import os
import openai
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = Flask(__name__)
from dotenv import load_dotenv
load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
openai.api_key = OPENAI_API_KEY

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

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text  # ユーザーからのメッセージを取得

    # OpenAI APIを使用してレスポンスを生成
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # モデルの指定
        messages=[{"role": "system", "content": "You are an assistant skilled in programming, general knowledge, and tool usage advice. You provide helpful information for tasks in Line.And You must return messages in japanese."},  # システムメッセージの設定
                  {"role": "user", "content": user_message}],  # ユーザーメッセー
        max_tokens=250          # 生成するトークンの最大数
    )

    # LINEユーザーにレスポンスを返信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response.choices[0].message['content'].strip())  # 正しいレスポンスの取得方法
    )



if __name__ == "__main__":
    app.run()