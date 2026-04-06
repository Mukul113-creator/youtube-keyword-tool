from flask import Flask, request, render_template_string
import googleapiclient.discovery
import re
import os
from dotenv import load_dotenv
import sqlite3
from datetime import datetime

# FIX for pkg_resources error

load_dotenv()
app = Flask(__name__)
app.secret_key = 'your-secret-2024'

API_KEY = os.getenv('YOUTUBE_API_KEY')

# LIMITS
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
    c.execute("INSERT INTO usage (ip, date) VALUES (?, ?)", (ip, today))
    conn.commit()
    conn.close()

# ---------------- YOUTUBE TOOL ----------------
class YouTubeTool:
    def __init__(self, api_key):
        self.youtube = googleapiclient.discovery.build(
            "youtube", "v3", developerKey=api_key
        )

    # ✅ Extract video ID
    def extract_video_id(self, url):
        match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11})', url)
        return match.group(1) if match else None

    # ✅ Extract channel ID from URL
    def extract_channel_id(self, url):
        if "youtube.com/channel/" in url:
            return url.split("channel/")[1].split("/")[0]

        # if user directly pastes channel ID
        if url.startswith("UC"):
            return url

        return None

    # ✅ Get channel ID from video
    def get_channel_from_video(self, video_id):
        try:
            res = self.youtube.videos().list(
                part="snippet", id=video_id
            ).execute()
            return res['items'][0]['snippet']['channelId']
        except:
            return None

    # ✅ Search videos + FILTER
    def search_videos(self, channel_id, keyword):
        try:
            res = self.youtube.search().list(
                part="snippet,id",
                channelId=channel_id,
                q=keyword,
                type="video",
                maxResults=50
            ).execute()

            items = res.get('items', [])
            filtered = []

            keyword_lower = keyword.lower()
            pattern = r'\b' + re.escape(keyword_lower) + r'\b'

            for video in items:
                title = video['snippet']['title'].lower()
                desc = video['snippet']['description'].lower()

                if re.search(pattern, title) or re.search(pattern, desc):
                    filtered.append(video)

            return filtered

        except Exception as e:
            print("ERROR:", e)
            return []

tool = YouTubeTool(API_KEY)

# ---------------- ROUTES ----------------
@app.route('/', methods=['GET', 'POST'])
def index():
    ip = request.remote_addr
    usage = get_usage(ip)
    remaining = max(0, FREE_SEARCHES_DAY - usage)

    if request.method == 'POST':

        url = request.form['url']
        keyword = request.form['keyword']

        # ✅ Try channel first
        channel_id = tool.extract_channel_id(url)

        # ✅ If not channel → try video
        if not channel_id:
            video_id = tool.extract_video_id(url)
            if video_id:
                channel_id = tool.get_channel_from_video(video_id)

        if not channel_id:
            return '<h2 style="color:red;">❌ Invalid YouTube URL</h2>'

        videos = tool.search_videos(channel_id, keyword)
        record_usage(ip)

        return render_template_string(RESULTS_HTML,
            videos=videos,
            keyword=keyword,
            count=len(videos)
        )

    return render_template_string(INDEX_HTML,
        usage=usage,
        remaining=remaining
    )

# ---------------- HTML ----------------
INDEX_HTML = '''
<h1>YouTube Keyword Finder</h1>
<form method="POST">
<input name="url" placeholder="Channel or Video URL" required><br><br>
<input name="keyword" placeholder="Keyword" required><br><br>
<button type="submit">Search</button>
</form>
'''

RESULTS_HTML = '''
<h2>✅ {{ count }} Videos Found</h2>
<p>Keyword: <b>{{ keyword }}</b></p>

{% for video in videos %}
<div style="margin-bottom:20px;">
<a href="https://youtube.com/watch?v={{ video.id.videoId }}" target="_blank">
{{ video.snippet.title }}
</a>
</div>
{% endfor %}

<br><a href="/">🔙 Back</a>
'''

# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)