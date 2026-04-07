from flask import Flask, request, render_template_string
import googleapiclient.discovery
import re
import os
from dotenv import load_dotenv
import sqlite3
from datetime import datetime

load_dotenv()
app = Flask(__name__)
app.secret_key = 'your-secret-2024'

# ✅ YOUR NEW FRESH API KEY
API_KEY = "AIzaSyA5LctWsGE8f2bhACTrYLLazFvEoO_l00k"

# Quota limits
GOOGLE_FREE_QUOTA = 10000
SEARCHES_PER_QUERY = 100
FREE_SEARCHES_DAY = GOOGLE_FREE_QUOTA // SEARCHES_PER_QUERY

# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect('usage.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usage 
                 (ip TEXT, date TEXT, count INTEGER DEFAULT 1)''')
    conn.commit()
    conn.close()

init_db()

def get_usage(ip):
    conn = sqlite3.connect('usage.db')
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT SUM(count) FROM usage WHERE ip=? AND date=?", (ip, today))
    usage = c.fetchone()[0] or 0
    conn.close()
    return int(usage)

def record_usage(ip):
    conn = sqlite3.connect('usage.db')
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT count FROM usage WHERE ip=? AND date=?", (ip, today))
    row = c.fetchone()
    if row:
        c.execute("UPDATE usage SET count=count+1 WHERE ip=? AND date=?", (ip, today))
    else:
        c.execute("INSERT INTO usage (ip, date, count) VALUES (?, ?, 1)", (ip, today))
    conn.commit()
    conn.close()

# ---------------- YOUTUBE TOOL (YOUR ORIGINAL) ----------------
class YouTubeTool:
    def __init__(self, api_key):
        self.youtube = googleapiclient.discovery.build(
            "youtube", "v3", developerKey=api_key, cache_discovery=False
        )

    def extract_video_id(self, url):
        match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11})', url)
        return match.group(1) if match else None

    def get_channel_from_video(self, video_id):
        try:
            res = self.youtube.videos().list(part="snippet", id=video_id).execute()
            return res['items'][0]['snippet']['channelId']
        except:
            return None

    # 🔥 UNIVERSAL CHANNEL RESOLVER (YOUR CODE)
    def resolve_channel(self, input_text):
        input_text = input_text.strip()
        if "youtube.com/channel/" in input_text:
            return input_text.split("channel/")[1].split("/")[0]

        video_id = self.extract_video_id(input_text)
        if video_id:
            return self.get_channel_from_video(video_id)

        try:
            res = self.youtube.search().list(
                part="snippet",
                q=input_text,
                type="channel",
                maxResults=1
            ).execute()
            if res.get('items'):
                return res['items'][0]['snippet']['channelId']
            return None
        except:
            return None

    # CHANNEL-SPECIFIC SEARCH (YOUR IMPROVED VERSION)
    def search_videos(self, channel_id, keyword):
        try:
            videos = []
            next_page_token = None
            pattern = re.compile(re.escape(keyword.lower()))
            
            while True:
                res = self.youtube.search().list(
                    part="snippet",
                    channelId=channel_id,
                    q=keyword,
                    type="video",
                    maxResults=50,
                    pageToken=next_page_token
                ).execute()

                for video in res.get('items', []):
                    title = video['snippet']['title'].lower()
                    desc = video['snippet']['description'].lower()

                    if re.search(pattern, title) or re.search(pattern, desc):
                        videos.append({
                            "videoId": video["id"]["videoId"],
                            "title": video["snippet"]["title"],
                            "channelTitle": video["snippet"]["channelTitle"]
                        })

                next_page_token = res.get('nextPageToken')
                if not next_page_token or len(videos) >= 200:
                    break
            return videos
        except Exception as e:
            print("ERROR:", e)
            return []

    # GLOBAL SEARCH (YOUR WORKING VERSION)
    def search_videos_global(self, keyword):
        try:
            videos = []
            next_page_token = None

            while True:
                res = self.youtube.search().list(
                    part="snippet",
                    q=keyword,
                    type="video",
                    maxResults=50,
                    pageToken=next_page_token,
                    order="relevance"
                ).execute()

                for item in res.get("items", []):
                    videos.append({
                        "videoId": item["id"]["videoId"],
                        "title": item["snippet"]["title"],
                        "channelTitle": item["snippet"]["channelTitle"]
                    })

                next_page_token = res.get("nextPageToken")
                if not next_page_token or len(videos) >= 100:
                    break

            return videos
        except Exception as e:
            print("ERROR:", e)
            return []

tool = YouTubeTool(API_KEY)

# ---------------- ROUTES (YOUR ORIGINAL LOGIC) ----------------
@app.route('/', methods=['GET', 'POST'])
def index():
    ip = request.remote_addr
    usage = get_usage(ip)
    remaining = max(0, FREE_SEARCHES_DAY - usage)

    if request.method == 'POST':
        url = request.form.get('url', '').strip()
        keyword = request.form.get('keyword', '').strip()

        if not keyword:
            return "<h2 style='color:red;'>❌ Enter keyword</h2>"

        # ✅ GLOBAL SEARCH if no URL (YOUR LOGIC)
        if url == "":
            videos = tool.search_videos_global(keyword)
            record_usage(ip)
            return render_template_string(GLOBAL_RESULTS_HTML,
                videos=videos,
                keyword=keyword,
                count=len(videos)
            )

        # ✅ CHANNEL SEARCH (YOUR LOGIC)
        channel_id = tool.resolve_channel(url)
        if not channel_id:
            return '<h2 style="color:red;">❌ Invalid Input</h2>'

        videos = tool.search_videos(channel_id, keyword)
        record_usage(ip)
        return render_template_string(RESULTS_HTML,
            videos=videos,
            keyword=keyword,
            count=len(videos)
        )

    return render_template_string(INDEX_HTML, usage=usage, remaining=remaining)

# ---------------- YOUR ORIGINAL HTML ----------------
INDEX_HTML = '''
<h1>YouTube Keyword Tool</h1>

<form method="POST">
<input name="url" placeholder="Channel URL / @handle (optional)"><br><br>
<input name="keyword" placeholder="Keyword" required><br><br>
<button type="submit">Search</button>
</form>

<p>Usage: {{ usage }} | Remaining: {{ remaining }}</p>
'''

RESULTS_HTML = '''
<h2>{{ count }} Videos Found (Channel)</h2>
<p>Keyword: <b>{{ keyword }}</b></p>

{% for v in videos %}
<div style="margin-bottom:20px;padding:15px;border:1px solid #ddd;border-radius:10px;">
<a href="https://youtube.com/watch?v={{ v.videoId }}" target="_blank" style="font-size:18px;font-weight:bold;color:#d00;">
{{ v.title }}
</a>
<p style="color:#666;margin-top:5px;">📺 {{ v.channelTitle }}</p>
</div>
{% endfor %}

<br><a href="/" style="background:#0066cc;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;">🔙 New Search</a>
'''

GLOBAL_RESULTS_HTML = '''
<h2>🔍 {{ count }} Videos Found (Global Search)</h2>
<p>Keyword: <b>{{ keyword }}</b></p>

{% if count == 0 %}
<div style="background:#ffebee;padding:30px;border-radius:15px;text-align:center;color:#c53030;">
<h3>😔 No results</h3>
<p>Try: "{{ keyword }} video" or "{{ keyword }} official"</p>
</div>
{% endif %}

{% for v in videos %}
<div style="margin-bottom:20px;padding:15px;border:1px solid #ddd;border-radius:10px;">
<a href="https://youtube.com/watch?v={{ v.videoId }}" target="_blank" style="font-size:18px;font-weight:bold;color:#d00;">
{{ v.title }}
</a>
<p style="color:#666;margin-top:5px;">📺 {{ v.channelTitle }}</p>
</div>
{% endfor %}

<br><a href="/" style="background:#0066cc;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;">🔙 New Search</a>
'''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)