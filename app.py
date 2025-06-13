import os
import json
from openai import OpenAI
from flask import Flask, request, abort
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient, TextMessage, ReplyMessageRequest
from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError

# 讀取環境變數
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=OPENAI_API_KEY)

# 初始化 LINE Messaging API v3
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

app = Flask(__name__)

# 載入固定回覆內容
with open('static_replies.json', encoding='utf-8') as f:
    static_replies = json.load(f)

# 使用者對話紀錄
user_sessions = {}

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text.strip()

    # 關鍵字自動回覆
    for keyword, reply in static_replies.items():
        if keyword in user_message:
            reply_text = reply
            break
    else:
        # 若無匹配關鍵字，呼叫 GPT
        if user_id not in user_sessions:
            user_sessions[user_id] = [
                {"role": "system", "content": "請用繁體中文回答使用者的問題。"}
            ]

        user_sessions[user_id].append({"role": "user", "content": user_message})

        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=user_sessions[user_id],
                temperature=0.7,
                top_p=1,
                timeout=30
            )
            reply_text = response.choices[0].message.content.strip()
            user_sessions[user_id].append({"role": "assistant", "content": reply_text})
            user_sessions[user_id] = user_sessions[user_id][-50:]

        except Exception as e:
            print(f"[GPT ERROR] {e}")
            reply_text = "目前伺服器有點慢，我暫時無法即時回覆😥，您可以稍後再試一次～"

    # 發送回覆訊息
    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

@app.route("/", methods=["GET"])
def index():
    return "LINE Chatbot is running!", 200

# Render 啟動用
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
