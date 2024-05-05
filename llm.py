import openai
from dotenv import load_dotenv
import os
import requests
from google.generativeai import *
from gcs_client import CloudStorageManager
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY
system_prompts = "あなたは就活生を支援するLineのアシスタントです。以下のメッセージはすべて就活生からのメッセージです。"


def chatGPTResponse(prompts, model, user_id, system_prompts=system_prompts, temperature=0.5):
    cloud_storage_manager = CloudStorageManager(bucket_name="user-backets")
    user_history = cloud_storage_manager.readChatHistory(user_id)
    model
    if model != "gpt-3.5-turbo":
        model = "gpt-4"
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

def geminiResponse(prompt):
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    configure(api_key=API_KEY)
    model = GenerativeModel("gemini-pro")
    response = model.predict(prompt, max_tokens=100, temperature=0.5)

def responseLLM(prompt, model):
    response = None
    if model == "gemini-1.5":
        response = requests.post(
            "https://api.gemini.com/v1/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {os.getenv('GEMINI_API_KEY')}"
            },
            json={
                "prompt": prompt,
                "max_tokens": 100,
                "temperature": 0.5
            }
        )
        response = response.json()
    else:
        responcse = chatGPTResponse(prompt, model)
    if not response:
        return "エラーが発生しました"
    

def formatTextFromInfo(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-16k-0613",
        messages=[
            {"role": "system", "content": "あなたは文字修正Botです。" +
             "要件を守らなければ罰が与えられます。" +
             "Userが送ったメッセージの中からの指定した要素の情報を取得して,指定したフォーマットで必ず返してください。" +
             "わかりました、などの余計な内容は入りません、。" +
             "必要な情報のみを返してください."},
            {"role": "system", "content": "##要件##" +
             "分かりましたなどの指定していない内容は送信するな" +
             "必ず指定したフォーマット通りで返せ},"},
            {"role": "system", "content": "さらに、文章の内容を補完して、より魅力的な文章に仕上げます"},
            {"role": "system",
                "content": "##フォーマット##" +
             "年齢：" +
             "居住地：" +
             "文系：" +
             "情報："
             },
            {"role": "system",
                "content":
                    "##要素##"+
             "年齢はユーザーの年齢です。わからなければ空白にしてください。" +
             "居住地はユーザーの住んでいる県です。" +
             "args=文系は文系かどうかです。文系ならTrue、理系ならFalseにしてください。" +
             "情報はユーザーの情報です。簡単にユーザーの情報を簡潔に短めにまとめてください。"
             },
            {"role": "user", "content": prompt}
        ],
        temperature=0.1)
    text = response.choices[0].message['content'].strip()
    return text


def formatTextFromImage(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-16k-0613",
        messages=[
            {"role": "system", "content": "あなたは熟練の校閲官です"},
            {"role": "system",
                "content": "あなたは送られてきた文章の助詞や接続詞を例とする文法的な間違いや、論理構造の欠陥を指摘して修正します"},
            {"role": "system", "content": "さらに、文章の内容を補完して、より魅力的な文章に仕上げます"},
            {"role": "system",
                "content": "与えられた文章で、定量的でない発言や、抽象的意見がある場合は、具体性や数字を使った説明をしてください"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1)
    text = response.choices[0].message['content'].strip()
    return text


def ESAdviceGPT(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-16k-0613",
        messages=[
            {"role": "system", "content": "あなたは凄腕の教師です"},
            {"role": "system", "content": "あなたは送られてきた文章の欠点を見つけて指摘してください"},
            {"role": "system", "content":
                "欠点: 能力や性格について書かれていない, なぜその企業を選んだか書かれていない, 伝えたいポイントが多岐に渡り多岐に渡り一つ一つのエピソードの内容が薄い, 一つの文章が長い"},
            {"role": "system", "content":
                "欠点: 結論→理由→具体例→結論の構成になっていない, 文章同士の関係が明白でない, 主語が明確でない, 主述の対応が誤っている, 表現に社会人らしさがない, 具体的な数値による説明がない"},
            {"role": "system",
                "content": ""},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3)
    text = response.choices[0].message['content'].strip()
    return text


def EmailAdviceGPT(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-16k-0613",
        messages=[
            {"role": "system", "content": "あなたは凄腕の教師です"},
            {"role": "system", "content": "あなたは送られてきた文章の欠点を見つけて指摘してください"},
            {"role": "system", "content":
                "欠点: 能力や性格について書かれていない, なぜその企業を選んだか書かれていない, 伝えたいポイントが多岐に渡り多岐に渡り一つ一つのエピソードの内容が薄い, 一つの文章が長い"},
            {"role": "system", "content":
                "欠点: 結論→理由→具体例→結論の構成になっていない, 文章同士の関係が明白でない, 主語が明確でない, 主述の対応が誤っている, 表現に社会人らしさがない, 具体的な数値による説明がない"},
            {"role": "system",
                "content": ""},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3)
    text = response.choices[0].message['content'].strip()
    return text
