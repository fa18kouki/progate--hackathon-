from dotenv import load_dotenv
import os
import openai
import re
import sys
from pathlib import Path
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, request, abort, render_template
from flask_socketio import SocketIO, emit
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, ButtonsTemplate,  TemplateSendMessage, PostbackAction, TextSendMessage, ImageMessage, AudioMessage, FollowEvent, ImageSendMessage, PostbackEvent
from apscheduler.schedulers.background import BackgroundScheduler
from gcs_client import CloudStorageManager
# from . import MicrophoneStream
from datetime import datetime
from ocr import ocr

load_dotenv()
db = SQLAlchemy()
socketio = SocketIO()


class User(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(255), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    residence = db.Column(db.String(255), nullable=False)
    grade = db.Column(db.String(255), nullable=False)
    desired_jobs = db.Column(db.PickleType, nullable=False)
    brief_biography = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(
        db.DateTime, default=datetime.now, onupdate=datetime.now)


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    socketio.init_app(app)  # 既存の socketio インスタンスに app を関連付ける
    migrate = Migrate(app, db)
    return app


app = create_app()

if __name__ == "__main__":
    socketio.run(app, debug=True)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
openai.api_key = OPENAI_API_KEY
gcs_user_manager = CloudStorageManager("user-backets")
system_prompts = "You are an assistant skilled in programming, general knowledge, and tool usage advice. You provide helpful information for tasks in Line. And You must return messages in japanese."
user_status = "INITIAL"

# リアルタイム音声認識


@socketio.on('connect', namespace='/transcribe')
def test_connect():
    emit('response', {'data': 'Connected'})


@socketio.on('start_rec', namespace='/transcribe')
def start_recording():
    # ここでspeech2text.pyの音声認識を開始
    pass


@socketio.on('stop_rec', namespace='/transcribe')
def stop_recording():
    # ここで音声認識を停止
    pass


def listen_print_loop(responses):
    """Iterates through server responses and prints them.

    The responses passed is a generator that will block until a response
    is provided by the server.

    Each response may contain multiple results, and each result may contain
    multiple alternatives; for details, see https://goo.gl/tjCPAU.  Here we
    print only the transcription for the top alternative of the top result.

    In this case, responses are provided for interim results as well. If the
    response is an interim one, print a line feed at the end of it, to allow
    the next result to overwrite it, until the response is a final one. For the
    final one, print a newline to preserve the finalized transcription.
    """
    num_chars_printed = 0
    for response in responses:
        if not response.results:
            continue

        # The `results` list is consecutive. For streaming, we only care about
        # the first result being considered, since once it's `is_final`, it
        # moves on to considering the next utterance.
        result = response.results[0]
        if not result.alternatives:
            continue

        # Display the transcription of the top alternative.
        transcript = result.alternatives[0].transcript

        # Display interim results, but with a carriage return at the end of the
        # line, so subsequent lines will overwrite them.
        #
        # If the previous result was longer than this one, we need to print
        # some extra spaces to overwrite the previous result
        overwrite_chars = " " * (num_chars_printed - len(transcript))

        if not result.is_final:
            sys.stdout.write(transcript + overwrite_chars + "\r")
            sys.stdout.flush()

            num_chars_printed = len(transcript)

        else:
            print(transcript + overwrite_chars)

            # Exit recognition if any of the transcribed phrases could be
            # one of our keywords.
            if re.search(r"\b(exit|quit)\b", transcript, re.I):
                print("Exiting..")
                break

            num_chars_printed = 0


def chatGPTResponse(prompts, model, user_id, system_prompts=system_prompts, temperature=0.5):
    '''response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # モデルの指定
        messages=[
            {"role": "system", "content": "You are an assistant skilled in programming, general knowledge, and tool usage advice. You provide helpful information for tasks in Line. And You must return messages in japanese."},  # システムメッセージの設定
            {"role": "user", "content": transcript["text"]},  # 変換されたテキストをユーザーメッセージとして使用
        ],
        max_tokens=250  # 生成するトークンの最大数
    )'''
    cloud_storage_manager = CloudStorageManager(bucket_name="user-backets")
    user_history = cloud_storage_manager.readChatHistory(user_id)
    response = openai.ChatCompletion.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompts},  # システムメッセージの設定
            {"role": "system", "content": user_history},
            {"role": "user", "content": prompts},  # 変換されたテキストをユーザーメッセージとして使用
        ],
        temperature=temperature
    )
    return response.choices[0].message['content'].strip()


def chatGPTResponseFromImages(prompt):
    response = openai.ChatCompletions.create(
        model="gpt-3.5-turbo-16k-0613",
        messages=[
            {"role": "system", "content": "あなたは就活生をサポートする優秀な教師です"},
            {"role": "system", "content": "あなたは送られてきた文章の文法的な間違いや、論理構造の欠陥を指摘して修正します"},
            {"role": "system", "content": "さらに、文章の内容を補完して、より魅力的な文章に仕上げます"},
            {"role": "system",
                "content": "与えられた文章で、定量的でない発言や、抽象的意見がある場合は、具体性や数字を使った説明をしてください"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3)
    text = response.choices[0].message['content'].strip()
    return text


def send_encouragement_message():
    user_id = "YOUR_USER_ID"  # ユーザーIDを設定
    message = "おはようございます！新しい一日がんばりましょう！"  # 送るメッセージ
    line_bot_api.push_message(user_id, TextSendMessage(text=message))


def send_encouragement_message():
    user_id = "YOUR_USER_ID"  # ユーザーIDを設定
    message = "おはようございます！新しい一日がんばりましょう！"  # 送るメッセージ
    line_bot_api.push_message(user_id, TextSendMessage(text=message))


scheduler = BackgroundScheduler()
scheduler.add_job(send_encouragement_message, 'cron',
                  hour=9, minute=0)  # 毎日9時0分に実行
scheduler.start()


@app.route("/")
# マイページ的なもの
def hello_world():
    return render_template("index.html")


@app.route("/transcribe")
# リアルタイム音声認譞
def transcribe():
    return render_template("transcribe.html")


@app.route("/line/login", methods=["GET"])
def line_login():
    request_code = request.args["code"]
    # 認可コードを取得する処理をここに追加


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
    return gcs_user_manager.test_connection()


@handler.add(FollowEvent)
def handle_follow(event):
    user_id = event.source.user_id  # ユーザーのIDを取得
    gcs_user_manager.initialize_user_storage(user_id)  # ユーザーストレージを初期化
    display_name = line_bot_api.get_profile(user_id).display_name
    app.logger.info(f"ユーザーの表示名: {display_name}")
    # ユーザーのデータベースに新しいユーザーを追加
    new_user = User(
        user_id=user_id,
        nickname="未設定",
        age=0,
        residence="未設定",
        grade="未設定",
        desired_jobs=[],
        brief_biography=""
    )
    db.session.add(new_user)
    db.session.commit()
    # ユーザーIDをログに記録
    app.logger.info(f"新しいユーザーが追加されました: {new_user.id}")
    # ユーザーに歓迎メッセージを送信
    welcome_message = "ようこそ！私たちのサービスへ。まずは以下のフォーマットに従って自己紹介をお願いします。\n自己紹介: \n ニックネーム：\n年齢：\n居住地：\n学年：\n希望職種：\n簡単な経歴：\n"
    line_bot_api.push_message(user_id, TextSendMessage(text=welcome_message))

    # ユーザーにサービスの説明を送信
    service_description = "こちらで写真や音声の保存が可能です。また、質問に答えることでより良いサービスを提供します。"
    line_bot_api.push_message(
        user_id, TextSendMessage(text=service_description))


@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id  # ユーザーのIDを取得
    data = event.postback.data  # ポストバックデータを取得

    # ポストバックデータを解析
    action, info = data.split(':')
    if action == "update":
        field, value = info.split(',')
        # ユーザー情報を更新
        user = User.query.filter_by(user_id=user_id).first()
        if user:
            setattr(user, field, value)
            db.session.commit()
            response_message = f"{field}を更新しました。新しい値: {value}"
        else:
            response_message = "ユーザー情報が見つかりません。"
    else:
        response_message = "不明なアクションです。"

    # ユーザーに応答メッセージを送信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response_message)
    )


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    # ユーザーからのポストバックアクションを処理する
    if event.message.text == "ボタン":
        buttons_template = ButtonsTemplate(
            title='あなたの選択', text='以下から選んでください', actions=[
                PostbackAction(label='選択肢 1', data='action1'),
                PostbackAction(label='選択肢 2', data='action2')
            ]
        )
        template_message = TemplateSendMessage(
            alt_text='Buttons alt text', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    model = "gpt-3.5-turbo"
    if event.message.text == "GPT-4を使用する":
        model = "gpt-4-turbo"
    user_message = event.message.text  # ユーザーからのメッセージを取得
    user_id = event.source.user_id  # ユーザーのIDを取得
    display_name = line_bot_api.get_profile(
        user_id).display_name  # ユーザーの表示名を取得
    gcs_client = CloudStorageManager("user-backets")
    gcs_client.ensure_user_storage(user_id)
    gcs_client.writeChatHistory(user_id, "user", user_message)
    # ユーザーのメッセージを使用してレスポンスを生成
    response = chatGPTResponse(user_message, model, user_id)
    res = f"あなたのユーザーIDは{user_id}です。\n"
    res = f"{display_name}さん、こんにちは！\n"
    res += response
    gcs_client.writeChatHistory(user_id, "system", response)
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
    gcs_user_manager.upload_file(
        file_path, audio_bytes, content_type='audio/m4a')

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
            # 変換されたテキストをユーザーメッセージとして使用
            {"role": "user", "content": transcript["text"]},
        ],
        max_tokens=250  # 生成するトークンの最大数
    )

    res = f"あなたのユーザーIDは{user_id}です。\n"
    res += response.choices[0].message['content'].strip()

    # ユーザーのIDとメッセージをGoogle Cloud Storageに保存
    gcs_user_manager.upload_file(f"{user_id}/{message_id}.txt", res)

    # LINEユーザーにレスポンスを返信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=res)
    )


@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id  # ユーザーのIDを取得
    message_id = event.message.id  # メッセージのIDを取得

    # メッセージIDを元に画像ファイルを取得
    message_content = line_bot_api.get_message_content(message_id)
    image = message_content.content
    # ユーザーに画像の受信完了を通知
    line_bot_api.push_message(user_id, TextSendMessage(text="画像の受信が完了しました。"))
    
    #画像からテキストを抽出
    ocr_text = ocr(image)
    #GPTに渡してテキストを修正
    chatGPTResponseFromImages(ocr_text)
    #GPTに回答させる。

    # 画像ファイルをバケットに書き込み
    image_file_name = f"images/{user_id}.jpg"
    gcs_user_manager.upload_file(image_file_name, image)
    app.logger.info(f"画像ファイル '{image_file_name}' をバケットに書き込みました。")

    # 画像ファイルをGoogle Cloud Vision APIに送信して解析
    vision_api_response = "この画像の特徴は次の通りです:\n"
    line_bot_api.push_message(
        user_id, TextSendMessage(text=vision_api_response))