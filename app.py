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
API_KEY = os.getenv('YOUTUBE_API_KEY')

# EXACT GOOGLE FREE LIMITS
GOOGLE_FREE_QUOTA = 10000  # Queries per day (Google Cloud)
SEARCHES_PER_QUERY = 100   # Each search uses ~100 quota
FREE_SEARCHES_DAY = GOOGLE_FREE_QUOTA // SEARCHES_PER_QUERY  # = 100 searches

PRO_PRICE = "$5/month"

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

class YouTubeTool:
    def __init__(self, api_key):
        self.youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)
    
    def extract_video_id(self, url):
        match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', url)
        return match.group(1) if match else None
    
    def get_channel_id(self, video_id):
        try:
            res = self.youtube.videos().list(part='snippet', id=video_id).execute()
            return res['items'][0]['snippet']['channelId'] if res['items'] else None
        except:
            return None
    
    def search_videos(self, channel_id, keyword):
        try:
            res = self.youtube.search().list(
                part='snippet,id', channelId=channel_id, 
                q=keyword, type='video', maxResults=20
            ).execute()
            return res.get('items', [])
        except:
            return []

tool = YouTubeTool(API_KEY)

@app.route('/', methods=['GET', 'POST'])
def index():
    ip = request.remote_addr
    usage = get_usage(ip)
    remaining = max(0, FREE_SEARCHES_DAY - usage)
    quota_percent = (usage / FREE_SEARCHES_DAY) * 100
    
    if request.method == 'POST':
        if usage >= FREE_SEARCHES_DAY:
            return render_template_string(PAYWALL_HTML, 
                usage=usage, limit=FREE_SEARCHES_DAY, 
                pro_price=PRO_PRICE, quota_percent=quota_percent)
        
        url = request.form['url']
        keyword = request.form['keyword']
        
        video_id = tool.extract_video_id(url)
        if not video_id:
            return '<h2 style="color:red;">❌ Invalid YouTube URL</h2>'
        
        channel_id = tool.get_channel_id(video_id)
        if not channel_id:
            return '<h2 style="color:red;">❌ Cannot find channel</h2>'
        
        videos = tool.search_videos(channel_id, keyword)
        record_usage(ip)
        
        return render_template_string(RESULTS_HTML, 
            videos=videos, keyword=keyword, count=len(videos),
            usage=usage+1, limit=FREE_SEARCHES_DAY, 
            remaining=remaining-1, quota_percent=quota_percent+1)
    
    return render_template_string(INDEX_HTML, 
        usage=usage, limit=FREE_SEARCHES_DAY, 
        remaining=remaining, quota_percent=quota_percent)

INDEX_HTML = '''
<!DOCTYPE html>
<html><head><title>YouTube Keyword Tool</title>
<style>*{margin:0;padding:0;box-sizing:border-box;}body{font-family:'Segoe UI',sans-serif;max-width:900px;margin:0 auto;padding:30px;background:#f8f9fa;}
.header{text-align:center;margin-bottom:40px;}.header h1{color:#e50914;font-size:2.8em;margin-bottom:10px;}
.quota{background:linear-gradient(90deg,#e50914 0%,#ff6b6b {{ quota_percent }}%,#e0e0e0 {{ quota_percent }}%);height:25px;border-radius:15px;margin:20px 0;padding:5px;}
.quota-info{display:flex;justify-content:space-between;font-weight:500;color:#333;}
form{background:white;padding:40px;border-radius:20px;box-shadow:0 15px 35px rgba(0,0,0,0.1);margin:20px 0;}
input{width:100%;padding:18px;margin:15px 0;border:2px solid #e0e0e0;border-radius:12px;font-size:16px;}
input:focus{border-color:#e50914;outline:none;}
.btn-search{width:100%;padding:20px;background:#e50914;color:white;border:none;border-radius:12px;font-size:18px;font-weight:500;cursor:pointer;transition:all 0.3s;}
.btn-search:hover{background:#c40000;transform:translateY(-2px);}
.limit-warning{background:#fff3cd;border:1px solid #ffeaa7;color:#856404;padding:20px;border-radius:12px;margin:20px 0;}</style>
</head><body>
<div class="header">
    <h1>🔍 YouTube Keyword Finder</h1>
    <p>Powered by <strong>YouTube Data API v3</strong> | <small>Free Tier</small></p>
</div>

<div class="quota-info">
    <span>📊 Free Searches Used: {{ usage }} / {{ limit }}</span>
    <span>{{ remaining }} remaining today</span>
</div>
<div class="quota"></div>

{% if remaining <= 10 %}
<div class="limit-warning">
    ⚠️ <strong>{{ remaining }} free searches left today!</strong> 
    Upgrade for unlimited access.
</div>
{% endif %}

<form method="POST">
    <input type="url" name="url" placeholder="https://youtube.com/watch?v=..." required>
    <input type="text" name="keyword" placeholder="Song name, artist, or keyword" required>
    <button class="btn-search" type="submit">🔎 Search Channel ({{ remaining }} free left)</button>
</form>

<div style="text-align:center;color:#666;margin-top:40px;">
    <p><strong>Google Free Quota:</strong> {{ limit }} searches = 10,000 API queries/day</p>
    <p>Quota usage: {{ "%.1f"|format(quota_percent) }}% | Resets daily</p>
</div>
</body></html>
'''

RESULTS_HTML = '''
<!DOCTYPE html>
<html><head><title>Results - {{ count }} Videos</title>
<style>*{margin:0;padding:0;box-sizing:border-box;}body{font-family:'Segoe UI',sans-serif;max-width:1000px;margin:0 auto;padding:30px;background:#f8f9fa;}
.header{text-align:center;margin-bottom:30px;}.header h1{color:#4CAF50;font-size:2.8em;}
.quota-info{background:#e8f5e8;padding:15px;border-radius:10px;margin-bottom:20px;text-align:center;}
.video-list{background:white;padding:30px;border-radius:20px;box-shadow:0 15px 35px rgba(0,0,0,0.1);margin:20px 0;}
.video{padding:20px 0;border-bottom:1px solid #eee;}
.video:last-child{border-bottom:none;}
.video h3{margin:10px 0;font-size:1.3em;}
.video a{color:#e50914;text-decoration:none;font-weight:500;}
.video a:hover{text-decoration:underline;}
.btn-back{background:#e50914;color:white;padding:15px 30px;border:none;border-radius:10px;font-size:16px;cursor:pointer;display:block;margin:40px auto;}</style>
</head><body>
<div class="header">
    <h1>✅ {{ count }} Videos Found!</h1>
    <p>Keyword: "<strong>{{ keyword }}</strong>"</p>
</div>

<div class="quota-info">
    <strong>Usage:</strong> {{ usage }} / {{ limit }} searches 
    ({{ remaining }} free left) | {{ "%.1f"|format(quota_percent) }}% quota used
</div>

<div class="video-list">
    {% for video in videos %}
    <div class="video">
        <h3>
            <a href="https://youtube.com/watch?v={{ video.id.videoId }}" target="_blank">
                {{ video.snippet.title[:120] }}{% if video.snippet.title|length > 120 %}...{% endif %}
            </a>
        </h3>
        <small>{{ video.snippet.channelTitle }} • {{ video.snippet.publishedAt[:10] }}</small>
    </div>
    {% endfor %}
</div>

<button class="btn-back" onclick="history.back()">🔙 New Search</button>
</body></html>
'''

PAYWALL_HTML = '''
<!DOCTYPE html>
<html><head><title>Upgrade Required</title>
<style>*{margin:0;padding:0;box-sizing:border-box;}body{font-family:'Segoe UI',sans-serif;height:100vh;background:linear-gradient(135deg,#e50914,#ff6b6b);display:flex;align-items:center;justify-content:center;}
.card{max-width:500px;background:white;border-radius:25px;padding:60px;box-shadow:0 25px 70px rgba(0,0,0,0.3);text-align:center;}
.card h1{font-size:3em;color:#333;margin-bottom:20px;}
.usage{font-size:1.4em;color:#666;margin-bottom:40px;background:#f8f9fa;padding:20px;border-radius:15px;}
.upgrade-btn{background:linear-gradient(45deg,#4CAF50,#45a049);color:white;padding:25px 50px;border:none;border-radius:20px;font-size:1.6em;cursor:pointer;margin:30px 0;box-shadow:0 15px 40px rgba(76,175,80,0.4);transition:all 0.3s;}
.upgrade-btn:hover{transform:translateY(-3px);box-shadow:0 20px 50px rgba(76,175,80,0.6);}
.features{list-style:none;color:#555;font-size:1.1em;}
.features li{padding:12px 0;position:relative;}
.features li:before{content:"✅";position:absolute;left:-30px;font-size:1.2em;}
.wait-info{background:#fff3cd;border:1px solid #ffeaa7;color:#856404;padding:20px;border-radius:15px;margin-top:30px;}</style>
</head><body>
<div class="card">
    <h1>⚡ Free Limit Reached</h1>
    <div class="usage">
        <strong>You've used all {{ usage }} / {{ limit }} free searches</strong><br>
        <small>Google Cloud Free Tier: 10,000 API queries/day</small>
    </div>
    
    <button class="upgrade-btn" onclick="upgradePro()">
        💎 Upgrade Pro {{ pro_price }}
    </button>
    
    <ul class="features">
        <li>✅ Unlimited searches (no daily limits)</li>
        <li>✅ Priority API access</li>
        <li>✅ 50x more results per search</li>
        <li>✅ Remove all watermarks</li>
    </ul>
    
    <div class="wait-info">
        ⏰ Free limit resets tomorrow (midnight)<br>
        Or upgrade now for instant unlimited access!
    </div>
</div>
<script>
function upgradePro() {
    if(confirm('Ready to upgrade to Pro? ($5/month unlimited searches)')) {
        alert('🚀 Stripe checkout coming soon!\\n\\nDemo: You now have unlimited access!');
        localStorage.setItem('pro_user', 'true');
        location.reload();
    }
}
</script>
</body></html>
'''

if __name__ == '__main__':
    print(f"✅ YouTube Tool LIVE!")
    print(f"📊 Google Free: {GOOGLE_FREE_QUOTA:,} queries = {FREE_SEARCHES_DAY} searches/day")
    app.run(debug=True, port=5000)