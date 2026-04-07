from flask import Flask, request, render_template_string
import googleapiclient.discovery
import re
import os
from dotenv import load_dotenv
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'super-secret-2024'

# ✅ YOUR API KEY (CHANGE THIS LATER!)
API_KEY = "AIzaSyC7BRFy3rMbOI3H8Iokf6i--COcSu-XOaU"

# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect('usage.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usage (ip TEXT, date TEXT, count INTEGER DEFAULT 1)''')
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

# ---------------- YOUTUBE TOOL ----------------
youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=API_KEY)

class YouTubeSearch:
    @staticmethod
    def search_global(keyword):
        """🔥 FIXED - Works for "music" NOW"""
        videos = []
        try:
            # Multiple search variations for better results
            queries = [keyword, f'"{keyword}"', keyword + " video"]
            
            for q in queries:
                res = youtube.search().list(
                    part="snippet",
                    q=q,
                    type="video",
                    maxResults=25,
                    order="relevance"
                ).execute()
                
                for item in res.get('items', [])[:10]:
                    vid = item['id']['videoId']
                    videos.append({
                        'videoId': vid,
                        'title': item['snippet']['title'][:80],
                        'channel': item['snippet']['channelTitle']
                    })
                
                if len(videos) >= 30:
                    break
                    
            return videos[:30]
        except:
            return []

    @staticmethod
    def search_channel(channel_id, keyword):
        res = youtube.search().list(
            part="snippet",
            channelId=channel_id,
            q=keyword,
            type="video",
            maxResults=30
        ).execute()
        
        videos = []
        for item in res.get('items', []):
            vid = item['id']['videoId']
            videos.append({
                'videoId': vid,
                'title': item['snippet']['title'][:80],
                'channel': item['snippet']['channelTitle']
            })
        return videos

    @staticmethod
    def get_channel_id(url):
        if "channel/" in url:
            return url.split("channel/")[1].split("?")[0]
        if url.startswith('@'):
            try:
                res = youtube.channels().list(part="id", forHandle=url[1:]).execute()
                return res['items'][0]['id'] if res.get('items') else None
            except:
                return None
        return None

# ---------------- ROUTES ----------------
@app.route('/', methods=['GET', 'POST'])
def index():
    ip = request.remote_addr or '127.0.0.1'
    usage = get_usage(ip)
    
    if request.method == 'POST':
        keyword = request.form.get('keyword', '').strip()
        url = request.form.get('url', '').strip()

        if not keyword:
            return '<h2 style="color:red;">❌ Enter keyword!</h2><a href="/">Back</a>'

        record_usage(ip)
        
        if not url:  # 🌍 GLOBAL SEARCH
            videos = YouTubeSearch.search_global(keyword)
            return render_template_string(GLOBAL_HTML, videos=videos, keyword=keyword, count=len(videos))
        else:  # Channel search
            channel_id = YouTubeSearch.get_channel_id(url)
            if not channel_id:
                return '<h2 style="color:red;">❌ Invalid URL/@handle</h2><a href="/">Back</a>'
            videos = YouTubeSearch.search_channel(channel_id, keyword)
            return render_template_string(CHANNEL_HTML, videos=videos, keyword=keyword, count=len(videos))

    return render_template_string(INDEX_HTML, usage=usage)

# ---------------- HTML ----------------
INDEX_HTML = '''
<!DOCTYPE html>
<html><head><title>🎵 YouTube Search</title>
<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:900px;margin:50px auto;padding:20px;background:#f8f9fa;}
input[type=text]{width:100%;padding:15px;margin:10px 0;font-size:16px;border:2px solid #ddd;border-radius:10px;box-sizing:border-box;}
button{background:linear-gradient(45deg,#ff0000,#cc0000);color:white;padding:15px 30px;border:none;font-size:16px;border-radius:10px;cursor:pointer;font-weight:600;}
button:hover{transform:translateY(-2px);box-shadow:0 5px 15px rgba(255,0,0,0.3);}
.stats{background:#e3f2fd;padding:15px;border-radius:10px;margin:20px 0;}
.tip{background:#fff3e0;padding:15px;border-radius:10px;margin:20px 0;}
h1{font-size:2.5em;background:linear-gradient(45deg,#ff0000,#ff4444); -webkit-background-clip:text; -webkit-text-fill-color:transparent; margin-bottom:10px;}
</style></head><body>
<h1>🔍 YouTube Keyword Tool</h1>

<div class="tip">🎯 <strong>Leave URL empty</strong> = Global search (works for "music")<br>📺 Enter <code>@MrBeast</code> or <code>youtube.com/channel/...</code> = Channel search</div>

<form method="POST">
<input name="url" placeholder="@handle or Channel URL (optional)">
<input name="keyword" placeholder="music, songs, gaming..." required>
<button type="submit">🚀 SEARCH YOUTUBE</button>
</form>

<div class="stats">📊 Today: {{ usage }} searches</div>
</body></html>
'''

GLOBAL_HTML = '''
<!DOCTYPE html>
<html><head><title>{{ count }} Videos</title>
<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:1000px;margin:20px auto;padding:20px;}
.video{background:white;border-radius:15px;padding:20px;margin:15px 0;box-shadow:0 4px 12px rgba(0,0,0,0.1);border-left:5px solid #ff4444;}
.title{font-size:20px;font-weight:600;margin:0 0 8px 0;}
.title a{color:#ff0000;text-decoration:none;}
.title a:hover{text-decoration:underline;}
.channel{color:#666;font-size:15px;margin:5px 0;}
.back{background:#0066cc;color:white;padding:12px 25px;text-decoration:none;border-radius:10px;font-weight:600;display:inline-block;margin:20px 0;}
h2{font-size:2em;color:#333;text-align:center;background:linear-gradient(45deg,#ff4444,#ff6666);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.stats{padding:15px;background:#e8f5e8;border-radius:10px;margin:20px 0;}
</style></head><body>
<h2>🌍 {{ count }} Videos Found!</h2>
<div class="stats"><strong>🔍 "{{ keyword }}"</strong> - Global YouTube Search</div>

{% if videos %}
{% for v in videos %}
<div class="video">
<div class="title"><a href="https://youtube.com/watch?v={{ v.videoId }}" target="_blank">▶ {{ v.title }}</a></div>
<div class="channel">📺 {{ v.channel }}</div>
</div>
{% endfor %}
{% else %}
<div style="text-align:center;padding:40px;background:#fff3cd;border-radius:15px;">
<h3>😔 No videos found</h3>
<p>Try "music video", "latest music", or more specific keywords</p>
</div>
{% endif %}

<a href="/" class="back">🔍 New Search</a>
</body></html>
'''

CHANNEL_HTML = GLOBAL_HTML.replace('🌍', '🎯 Channel').replace('Global YouTube Search', 'Channel Search')

if __name__ == '__main__':
    print("🚀 Server starting... Test 'music' NOW!")
    app.run(debug=True, host='0.0.0.0', port=5000)