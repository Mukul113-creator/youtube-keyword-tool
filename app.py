from flask import Flask, request, render_template_string
import googleapiclient.discovery
import re
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)

# ✅ YOUR BRAND NEW API KEY (10,000 quota!)
API_KEY = "AIzaSyA5LctWsGE8f2bhACTrYLLazFvEoO_l00k"

# Initialize YouTube API
youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=API_KEY)

# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect('usage.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usage 
                 (ip TEXT PRIMARY KEY, date TEXT, count INTEGER DEFAULT 1)''')
    conn.commit()
    conn.close()

init_db()

def get_usage(ip):
    conn = sqlite3.connect('usage.db')
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT count FROM usage WHERE ip=? AND date=?", (ip, today))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def update_usage(ip):
    conn = sqlite3.connect('usage.db')
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT count FROM usage WHERE ip=? AND date=?", (ip, today))
    result = c.fetchone()
    if result:
        c.execute("UPDATE usage SET count=? WHERE ip=? AND date=?", (result[0]+1, ip, today))
    else:
        c.execute("INSERT INTO usage (ip, date, count) VALUES (?, ?, 1)", (ip, today))
    conn.commit()
    conn.close()

# ---------------- YOUTUBE FUNCTIONS ----------------
def extract_channel_id(input_str):
    """Extract channel ID from URL, @handle, or video"""
    input_str = input_str.strip()
    
    # @handle
    if input_str.startswith('@'):
        try:
            res = youtube.channels().list(part="id", forHandle=input_str[1:]).execute()
            return res['items'][0]['id'] if res.get('items') else None
        except:
            return None
    
    # Channel URL
    if '/channel/' in input_str:
        return input_str.split('/channel/')[1].split('?')[0].split('&')[0]
    
    # Video URL → get channel
    video_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11})', input_str)
    if video_match:
        try:
            vid_id = video_match.group(1)
            res = youtube.videos().list(part="snippet", id=vid_id).execute()
            return res['items'][0]['snippet']['channelId'] if res.get('items') else None
        except:
            return None
    
    return None

def search_channel_videos(channel_id, keyword):
    """Search videos in specific channel"""
    try:
        res = youtube.search().list(
            part="snippet",
            channelId=channel_id,
            q=keyword,
            type="video",
            maxResults=30,
            order="relevance"
        ).execute()
        
        videos = []
        for item in res.get('items', []):
            videos.append({
                'id': item['id']['videoId'],
                'title': item['snippet']['title'][:80] + '...' if len(item['snippet']['title']) > 80 else item['snippet']['title'],
                'channel': item['snippet']['channelTitle'],
                'type': 'channel'
            })
        return videos
    except:
        return []

def search_global_videos(keyword):
    """🔥 GLOBAL SEARCH - Multiple queries for best results"""
    queries = [
        keyword,
        f'"{keyword}"',
        keyword + ' official',
        keyword + ' video',
        keyword + ' 2024'
    ]
    
    all_videos = []
    for q in queries:
        try:
            res = youtube.search().list(
                part="snippet",
                q=q,
                type="video",
                maxResults=15,
                order="relevance"
            ).execute()
            
            for item in res.get('items', []):
                vid = {
                    'id': item['id']['videoId'],
                    'title': item['snippet']['title'][:80] + '...' if len(item['snippet']['title']) > 80 else item['snippet']['title'],
                    'channel': item['snippet']['channelTitle'],
                    'type': 'global'
                }
                if vid['id'] not in [v['id'] for v in all_videos]:
                    all_videos.append(vid)
                    
            if len(all_videos) >= 30:
                break
                
        except:
            continue
    
    return all_videos[:30]

# ---------------- ROUTES ----------------
@app.route('/', methods=['GET', 'POST'])
def index():
    ip = request.remote_addr or '127.0.0.1'
    usage = get_usage(ip)
    
    if request.method == 'POST':
        url = request.form.get('url', '').strip()
        keyword = request.form.get('keyword', '').strip()
        
        if not keyword:
            return render_template_string(ERROR_HTML, message="❌ Please enter a keyword!")
        
        update_usage(ip)
        
        if not url:  # 🌍 GLOBAL SEARCH
            videos = search_global_videos(keyword)
            return render_template_string(GLOBAL_RESULTS, 
                videos=videos, keyword=keyword, count=len(videos), usage=usage)
        else:  # Channel search
            channel_id = extract_channel_id(url)
            if not channel_id:
                return render_template_string(ERROR_HTML, 
                    message="❌ Invalid URL or @handle!<br><br><small>✅ Examples:<br>&nbsp;&nbsp;@MrBeast<br>&nbsp;&nbsp;youtube.com/channel/UCX6OQ3DkcsbYNE6H8uQQuVA<br>&nbsp;&nbsp;youtube.com/watch?v=dQw4w9WgXcQ</small>")
            
            videos = search_channel_videos(channel_id, keyword)
            return render_template_string(CHANNEL_RESULTS,
                videos=videos, keyword=keyword, channel_id=channel_id, count=len(videos), usage=usage)
    
    return render_template_string(INDEX_HTML, usage=usage)

# ---------------- HTML TEMPLATES ----------------
INDEX_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>🎵 YouTube Keyword Tool</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {margin:0;padding:0;box-sizing:border-box;}
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh; padding: 20px;
        }
        .container { max-width: 800px; margin: 0 auto; }
        .card { 
            background: rgba(255,255,255,0.95); 
            backdrop-filter: blur(20px);
            border-radius: 25px; padding: 40px; box-shadow: 0 25px 50px rgba(0,0,0,0.15);
            border: 1px solid rgba(255,255,255,0.2);
        }
        h1 { 
            font-size: 2.8em; text-align: center; 
            background: linear-gradient(45deg, #ff6b6b, #feca57, #48bb78, #4299e1);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            background-clip: text; margin-bottom: 10px;
        }
        .subtitle { text-align: center; color: #666; font-size: 1.2em; margin-bottom: 30px; }
        input { 
            width: 100%; padding: 20px; font-size: 18px; border: 2px solid #e2e8f0; 
            border-radius: 15px; margin: 15px 0; transition: all 0.3s;
        }
        input:focus { border-color: #ff6b6b; outline: none; box-shadow: 0 0 0 4px rgba(255,107,107,0.1); }
        button { 
            width: 100%; padding: 20px; font-size: 20px; font-weight: 600;
            background: linear-gradient(45deg, #ff6b6b, #ff8e8e); color: white; 
            border: none; border-radius: 15px; cursor: pointer; transition: all 0.3s;
        }
        button:hover { transform: translateY(-2px); box-shadow: 0 15px 35px rgba(255,107,107,0.4); }
        .stats { 
            background: linear-gradient(45deg, #a8edea, #fed6e3); padding: 20px; 
            border-radius: 15px; text-align: center; margin: 25px 0; font-weight: 600;
            font-size: 1.1em;
        }
        .tip { 
            background: rgba(255,243,205,0.9); padding: 25px; border-radius: 15px; 
            margin: 25px 0; text-align: center; border-left: 5px solid #f6ad55;
        }
        .examples { font-size: 0.95em; color: #666; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>🔍 YouTube Keyword Tool</h1>
            <p class="subtitle">Find videos by keyword across YouTube!</p>
            
            <div class="tip">
                🎯 <strong>Leave URL empty</strong> = <span style="color:#ff6b6b;font-weight:600;">GLOBAL search</span><br>
                📺 Enter <code>@MrBeast</code> / channel URL / video URL = <span style="color:#48bb78;font-weight:600;">Channel search</span>
                <div class="examples">
                    💡 Try: <code>music</code> • <code>@pewdiepie gaming</code> • <code>tutorial python</code>
                </div>
            </div>
            
            <form method="POST">
                <input name="url" placeholder="@handle / Channel URL / Video URL (optional)">
                <input name="keyword" placeholder="music, gaming, tutorial..." required>
                <button>🚀 Search YouTube Now</button>
            </form>
            
            <div class="stats">
                📊 Your usage today: <strong style="color:#2d3748;">{{ usage }}</strong> searches
            </div>
        </div>
    </div>
</body>
</html>
'''

GLOBAL_RESULTS = '''
<!DOCTYPE html>
<html>
<head>
    <title>{{ count }} Videos • {{ keyword }}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {margin:0;padding:0;box-sizing:border-box;}
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: linear-gradient(135deg, #48bb78 0%, #38a169 100%); min-height: 100vh; padding: 20px;
        }
        .container { max-width: 1000px; margin: 0 auto; }
        .card { 
            background: rgba(255,255,255,0.95); border-radius: 25px; padding: 40px; 
            box-shadow: 0 25px 50px rgba(0,0,0,0.15); border: 1px solid rgba(255,255,255,0.2);
        }
        h2 { 
            font-size: 2.5em; text-align: center; 
            background: linear-gradient(45deg, #ffffff, #f7fafc); -webkit-background-clip: text; 
            -webkit-text-fill-color: transparent; margin-bottom: 15px;
        }
        .query { text-align: center; font-size: 1.3em; color: #2d3748; margin-bottom: 30px; }
        .video { 
            background: rgba(255,255,255,0.8); border-radius: 20px; padding: 25px; margin: 20px 0;
            border-left: 6px solid #38a169; box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            transition: all 0.3s;
        }
        .video:hover { transform: translateY(-5px); box-shadow: 0 20px 40px rgba(0,0,0,0.15); }
        .title { font-size: 20px; font-weight: 600; margin-bottom: 10px; }
        .title a { color: #2f855a; text-decoration: none; }
        .title a:hover { color: #22543d; }
        .channel { color: #718096; font-size: 16px; margin-top: 5px; }
        .back { 
            display: block; width: 250px; margin: 30px auto 0; padding: 18px 30px; 
            background: linear-gradient(45deg, #ed8936, #dd6b20); color: white; text-decoration: none; 
            border-radius: 15px; font-weight: 600; text-align: center; font-size: 18px;
        }
        .no-results { 
            text-align: center; padding: 60px 40px; background: rgba(255,243,205,0.9); 
            border-radius: 20px; margin: 40px 0; border-left: 6px solid #f6ad55;
        }
        .usage { text-align: center; padding: 20px; background: rgba(255,255,255,0.7); border-radius: 15px; margin-top: 30px; color: #4a5568; }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h2>🌍 {{ count }} Videos Found!</h2>
            <div class="query">🔍 <strong>"{{ keyword }}"</strong> - Global Search</div>
            
            {% if count > 0 %}
                {% for video in videos %}
                <div class="video">
                    <div class="title">
                        <a href="https://youtube.com/watch?v={{ video.id }}" target="_blank">
                            ▶ {{ video.title }}
                        </a>
                    </div>
                    <div class="channel">📺 {{ video.channel }}</div>
                </div>
                {% endfor %}
            {% else %}
                <div class="no-results">
                    <h3 style="color:#744210;font-size:1.8em;margin-bottom:15px;">😔 No videos found</h3>
                    <p style="font-size:1.2em;color:#965a1f;">
                        Try these instead:<br>
                        <code>"{{ keyword }} video"</code> • <code>"{{ keyword }} official"</code> • <code>"{{ keyword }} 2024"</code>
                    </p>
                </div>
            {% endif %}
            
            <div class="usage">📊 Usage today: {{ usage }} searches</div>
            <a href="/" class="back">🔍 New Search</a>
        </div>
    </div>
</body>
</html>
'''

CHANNEL_RESULTS = GLOBAL_RESULTS.replace('🌍', '🎯').replace('Global Search', 'Channel Search')

ERROR_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Error</title>
    <style>
        body { 
            font-family: 'Segoe UI', sans-serif; 
            background: linear-gradient(135deg, #fed7d7, #feb2b2); 
            min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px;
        }
        .error-card { 
            background: white; border-radius: 20px; padding: 50px; text-align: center; 
            box-shadow: 0 20px 40px rgba(254,178,178,0.3); max-width: 500px; 
            border: 1px solid rgba(255,255,255,0.5);
        }
        h1 { color: #c53030; font-size: 2.5em; margin-bottom: 20px; }
        .message { font-size: 1.3em; color: #742a2a; margin-bottom: 30px; line-height: 1.5; }
        .back { 
            display: inline-block; padding: 15px 40px; background: #48bb78; color: white; 
            text-decoration: none; border-radius: 12px; font-weight: 600; font-size: 18px;
        }
    </style>
</head>
<body>
    <div class="error-card">
        <h1>❌ Error</h1>
        <div class="message">{{ message }}</div>
        <a href="/" class="back">🔍 Back to Search</a>
    </div>
</body>
</html>
'''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 YouTube Keyword Tool running on port {port}")
    print("✅ API Key loaded - 10,000 quota available!")
    app.run(host='0.0.0.0', port=port, debug=False)