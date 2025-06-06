import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.exceptions import InvalidSignatureError


# 載入 .env
load_dotenv()

# 讀取環境變數（Render 也會從環境變數注入）
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=OPENAI_API_KEY) 

# 初始化套件
app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 載入固定回覆內容
with open('static_replies.json', encoding='utf-8') as f:
    static_replies = json.load(f)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text.strip()

    # 如果符合固定關鍵字，就自動回覆
    for keyword, reply in static_replies.items():
        if keyword in user_message:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

    # 其他情況交由 GPT 回答
    prompt = user_message

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            top_p=1,
            timeout=20
        )
        reply_text = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[GPT ERROR] {e}")
        reply_text = "目前伺服器有點慢，我暫時無法即時回覆😥，您可以稍後再試一次～"
    
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

@app.route("/", methods=["GET"])
def index():
    return "LINE Chatbot is running!", 200
    
# Render 會從這裡啟動
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
