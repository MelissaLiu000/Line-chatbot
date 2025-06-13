import os
import json
from openai import OpenAI
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.exceptions import InvalidSignatureError



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

user_sessions = {}  # 儲存每個使用者的對話歷史

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text.strip()
    
    # 如果符合固定關鍵字，就自動回覆
    for keyword, reply in static_replies.items():
        if keyword in user_message:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

    # 其他情況交由 GPT 回答
    # 初始化對話歷史（每位用戶獨立）
    if user_id not in user_sessions:
        user_sessions[user_id] = []

    # 加入本次提問
    user_sessions[user_id].append({"role": "user", "content": user_message})

    # 呼叫 GPT 回答
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=user_sessions[user_id],
            temperature=0.7,
            top_p=1,
            timeout=20
        )
        reply_text = response.choices[0].message.content.strip()

        # 加入 GPT 回覆進歷史
        user_sessions[user_id].append({"role": "assistant", "content": reply_text})

        # 限制歷史長度（避免過長）
        user_sessions[user_id] = user_sessions[user_id][-50:]

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
