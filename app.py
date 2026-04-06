from flask import Flask, request, render_template_string
import googleapiclient.discovery
import re
import os
from dotenv import load_dotenv
import sqlite3
from datetime import datetime

# FIX for pkg_resources error
import pkg_resources  

load_dotenv()

app = Flask(__name__)
app.secret_key = 'your-secret-2024'
API_KEY = os.getenv('YOUTUBE_API_KEY')

# ========================
# LIMIT SYSTEM
# ========================
GOOGLE_FREE_QUOTA = 10000
SEARCHES_PER_QUERY = 100
FREE_SEARCHES_DAY = GOOGLE_FREE_QUOTA // SEARCHES_PER_QUERY

# ========================
# DATABASE
# ========================
def init_db():
    conn = sqlite3.connect('usage.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS usage 
        (ip TEXT, date TEXT, count INTEGER DEFAULT 1)
    ''')
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

# ========================
# YOUTUBE TOOL
# ========================
class YouTubeTool:
    def __init__(self, api_key):
        self.youtube = googleapiclient.discovery.build(
            "youtube", "v3", developerKey=api_key
        )

    def get_channel_from_video(self, video_id):
        try:
            res = self.youtube.videos().list(
                part='snippet', id=video_id
            ).execute()
            return res['items'][0]['snippet']['channelId'] if res['items'] else None
        except:
            return None

    def extract_channel_id(self, url):
        # CHANNEL URL
        match = re.search(r'youtube\.com/channel/([A-Za-z0-9_-]+)', url)
        if match:
            return match.group(1)

        # VIDEO URL
        video_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11})', url)
        if video_match:
            video_id = video_match.group(1)
            return self.get_channel_from_video(video_id)

        return None

    def search_videos(self, channel_id, keyword):
        try:
            res = self.youtube.search().list(
                part='snippet,id',
                channelId=channel_id,
                q=keyword,
                type='video',
                maxResults=20
            ).execute()
            return res.get('items', [])
        except:
            return []

tool = YouTubeTool(API_KEY)

# ========================
# ROUTES
# ========================
@app.route('/', methods=['GET', 'POST'])
def index():
    ip = request.remote_addr
    usage = get_usage(ip)
    remaining = max(0, FREE_SEARCHES_DAY - usage)
    quota_percent = (usage / FREE_SEARCHES_DAY) * 100

    if request.method == 'POST':

        if usage >= FREE_SEARCHES_DAY:
            return f"<h2>❌ Limit reached ({FREE_SEARCHES_DAY})</h2>"

        url = request.form['url']
        keyword = request.form['keyword']

        channel_id = tool.extract_channel_id(url)

        if not channel_id:
            return '<h2 style="color:red;">❌ Invalid URL or Channel not found</h2>'

        videos = tool.search_videos(channel_id, keyword)
        record_usage(ip)

        html = f"""
        <h2>✅ Found {len(videos)} videos for keyword: {keyword}</h2>
        <p>Usage: {usage+1}/{FREE_SEARCHES_DAY}</p>
        <hr>
        """

        for v in videos:
            vid = v['id'].get('videoId')
            title = v['snippet']['title']
            html += f'<p><a href="https://youtube.com/watch?v={vid}" target="_blank">{title}</a></p>'

        html += '<br><a href="/">🔙 Back</a>'
        return html

    return f"""
    <h1>🔍 YouTube Keyword Finder</h1>
    <p>Free searches: {remaining}</p>
    <form method="POST">
        <input name="url" placeholder="YouTube Video or Channel URL" required><br><br>
        <input name="keyword" placeholder="Keyword" required><br><br>
        <button type="submit">Search</button>
    </form>
    """

# ========================
# RUN
# ========================
if __name__ == '__main__':
    app.run(debug=True)