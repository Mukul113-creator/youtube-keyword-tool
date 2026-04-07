from flask import Flask, request, render_template_string
import googleapiclient.discovery
import googleapiclient.errors
import re
import os
from dotenv import load_dotenv
import sqlite3
from datetime import datetime
import logging

# Enable logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
app = Flask(__name__)
app.secret_key = os.urandom(24)

API_KEY = os.getenv('YOUTUBE_API_KEY')

# ✅ CHECK API KEY
if not API_KEY:
    raise ValueError("❌ YOUTUBE_API_KEY is missing! Add it in .env file")

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

# ---------------- YOUTUBE TOOL ----------------
class YouTubeTool:
    def __init__(self, api_key):
        self.api_key = api_key
        self.youtube = googleapiclient.discovery.build(
            "youtube",
            "v3",
            developerKey=api_key,
            cache_discovery=False
        )

    def extract_video_id(self, url):
        """Extract video ID from various YouTube URL formats"""
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11})',
            r'\/embed\/([0-9A-Za-z_-]{11})',
            r'\/shorts\/([0-9A-Za-z_-]{11})',
            r'([0-9A-Za-z_-]{11})$'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def get_channel_from_video(self, video_id):
        """Get channel ID from video ID"""
        try:
            res = self.youtube.videos().list(
                part="snippet",
                id=video_id
            ).execute()
            
            if res.get('items'):
                return res['items'][0]['snippet']['channelId']
            return None
        except googleapiclient.errors.HttpError as e:
            logger.error(f"HTTP Error getting channel from video {video_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting channel from video {video_id}: {e}")
            return None

    def resolve_channel(self, input_text):
        """Resolve channel from URL, video, or handle"""
        input_text = input_text.strip()
        
        # Direct channel URL
        if "youtube.com/channel/" in input_text:
            return input_text.split("channel/")[1].split("?")[0].split("&")[0]
        
        # @handle
        if input_text.startswith('@'):
            return self.search_channel_by_handle(input_text[1:])
        
        # Video URL
        video_id = self.extract_video_id(input_text)
        if video_id:
            return self.get_channel_from_video(video_id)
        
        # Channel name search
        return self.search_channel_by_name(input_text)

    def search_channel_by_handle(self, handle):
        """Search channel by @handle"""
        try:
            res = self.youtube.channels().list(
                part="id,snippet",
                forHandle=handle,
                maxResults=1
            ).execute()
            if res.get('items'):
                return res['items'][0]['id']
            return None
        except Exception as e:
            logger.error(f"Error searching handle {handle}: {e}")
            return None

    def search_channel_by_name(self, name):
        """Search channel by name"""
        try:
            res = self.youtube.search().list(
                part="snippet",
                q=name,
                type="channel",
                maxResults=1
            ).execute()
            if res.get('items'):
                return res['items'][0]['snippet']['channelId']
            return None
        except Exception as e:
            logger.error(f"Error searching channel name {name}: {e}")
            return None

    def search_videos(self, channel_id, keyword):
        """Search videos in specific channel"""
        try:
            videos = []
            next_page_token = None
            
            while len(videos) < 200:
                res = self.youtube.search().list(
                    part="snippet",
                    channelId=channel_id,
                    q=keyword,
                    type="video",
                    maxResults=50,
                    pageToken=next_page_token,
                    order="relevance"
                ).execute()

                logger.info(f"Channel search returned {len(res.get('items', []))} items")

                for video in res.get('items', []):
                    video_id = video["id"].get("videoId")
                    if video_id:
                        videos.append({
                            "videoId": video_id,
                            "title": video["snippet"]["title"],
                            "channelTitle": video["snippet"]["channelTitle"],
                            "publishedAt": video["snippet"].get("publishedAt", "")
                        })

                next_page_token = res.get('nextPageToken')
                if not next_page_token:
                    break
                    
            logger.info(f"Total channel videos found: {len(videos)}")
            return videos[:200]
            
        except googleapiclient.errors.HttpError as e:
            logger.error(f"HTTP Error searching channel {channel_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error searching channel {channel_id}: {e}")
            return []

    def search_videos_global(self, keyword):
        """🔥 FIXED GLOBAL SEARCH - Main issue resolved"""
        try:
            videos = []
            next_page_token = None
            
            logger.info(f"🔍 Global search for: '{keyword}'")
            
            while len(videos) < 100:
                search_request = self.youtube.search().list(
                    part="snippet",
                    q=keyword,
                    type="video",
                    maxResults=50,
                    pageToken=next_page_token,
                    order="relevance",
                    # ✅ FIXED: Removed regionCode and safeSearch that were causing issues
                )
                
                res = search_request.execute()
                logger.info(f"Global search page returned {len(res.get('items', []))} items")

                if not res.get('items'):
                    logger.info("No more items found")
                    break

                for item in res.get('items', []):
                    video_id = item["id"].get("videoId")
                    if video_id:
                        videos.append({
                            "videoId": video_id,
                            "title": item["snippet"]["title"][:100] + "..." if len(item["snippet"]["title"]) > 100 else item["snippet"]["title"],
                            "channelTitle": item["snippet"]["channelTitle"],
                            "publishedAt": item["snippet"].get("publishedAt", "")
                        })

                next_page_token = res.get('nextPageToken')
                if not next_page_token:
                    break
                    
            logger.info(f"✅ Total global videos found: {len(videos)}")
            return videos
            
        except googleapiclient.errors.HttpError as e:
            logger.error(f"HTTP Error in global search: {e}")
            if hasattr(e, 'response') and e.response.status == 403:
                return [{"error": "API quota exceeded or key invalid"}]
            return []
        except Exception as e:
            logger.error(f"Unexpected error in global search: {e}")
            return []

tool = YouTubeTool(API_KEY)

# ---------------- ROUTES ----------------
@app.route('/', methods=['GET', 'POST'])
def index():
    ip = request.remote_addr or '127.0.0.1'
    usage = get_usage(ip)
    remaining = max(0, FREE_SEARCHES_DAY - usage)

    if request.method == 'POST':
        url = request.form.get('url', '').strip()
        keyword = request.form.get('keyword', '').strip()

        if not keyword:
            return render_template_string(ERROR_HTML, message="❌ Enter a keyword to search!")

        logger.info(f"Search request: keyword='{keyword}', url='{url}', ip='{ip}'")

        # Global search if no URL provided
        if not url:
            logger.info("Performing global search")
            videos = tool.search_videos_global(keyword)
            record_usage(ip)
            
            if videos and "error" in videos[0]:
                return render_template_string(ERROR_HTML, 
                    message=f"❌ API Error: {videos[0]['error']}")
                
            return render_template_string(GLOBAL_RESULTS_HTML,
                videos=videos,
                keyword=keyword,
                count=len(videos)
            )

        # Channel-specific search
        logger.info(f"Resolving channel from: {url}")
        channel_id = tool.resolve_channel(url)
        
        if not channel_id:
            return render_template_string(ERROR_HTML, 
                message="❌ Invalid channel URL, @handle, or video URL!<br><br>"
                       f"<small>Examples:<br>"
                       f"• @MrBeast<br>"
                       f"• https://youtube.com/channel/UCX6OQ3DkcsbYNE6H8uQQuVA<br>"
                       f"• https://youtube.com/watch?v=VIDEO_ID</small>")

        logger.info(f"Channel resolved to: {channel_id}")
        videos = tool.search_videos(channel_id, keyword)
        record_usage(ip)
        
        return render_template_string(RESULTS_HTML,
            videos=videos,
            keyword=keyword,
            channel_id=channel_id,
            count=len(videos)
        )

    return render_template_string(INDEX_HTML,
        usage=usage,
        remaining=remaining
    )

# ---------------- HTML TEMPLATES ----------------
INDEX_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>YouTube Keyword Tool</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
        input { width: 100%; padding: 12px; margin: 10px 0; font-size: 16px; }
        button { background: #ff0000; color: white; padding: 12px 24px; border: none; font-size: 16px; cursor: pointer; }
        button:hover { background: #cc0000; }
        .stats { background: #f0f0f0; padding: 15px; border-radius: 8px; margin: 20px 0; }
        .tip { background: #e8f4f8; padding: 15px; border-radius: 8px; margin: 20px 0; }
    </style>
</head>
<body>
    <h1>🔍 YouTube Keyword Tool</h1>
    
    <div class="tip">
        <strong>💡 Tip:</strong> Leave URL empty for <strong>GLOBAL search</strong><br>
        Enter channel URL, @handle, or video URL for <strong>channel-specific search</strong>
    </div>
    
    <form method="POST">
        <input name="url" placeholder="@handle / Channel URL / Video URL (optional)">
        <input name="keyword" placeholder="Enter keyword to search" required>
        <button type="submit">🚀 Search YouTube</button>
    </form>
    
    <div class="stats">
        📊 Usage today: <strong>{{ usage }}</strong> | 
        Remaining: <strong style="color: {% if remaining > 0 %}green{% else %}red{% endif %}">{{ remaining }}</strong>
    </div>
</body>
</html>
'''

ERROR_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Error</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 600px; margin: 100px auto; padding: 20px; text-align: center; }
        .error { color: #d00; background: #fee; padding: 30px; border-radius: 10px; margin: 20px 0; }
        a { color: #0066cc; text-decoration: none; }
        button { background: #ff0000; color: white; padding: 12px 24px; border: none; font-size: 16px; cursor: pointer; margin: 10px; }
    </style>
</head>
<body>
    <div class="error">
        <h2>{{ message }}</h2>
        <br>
        <a href="/">← Back to Search</a>
    </div>
</body>
</html>
'''

RESULTS_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>{{ count }} Videos Found</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 900px; margin: 20px auto; padding: 20px; }
        .video { border: 1px solid #ddd; margin: 15px 0; padding: 20px; border-radius: 10px; background: #fafafa; }
        .title { font-size: 18px; margin: 0 0 10px 0; }
        .title a { color: #ff0000; text-decoration: none; font-weight: bold; }
        .title a:hover { text-decoration: underline; }
        .channel { color: #666; font-size: 14px; margin: 5px 0; }
        .back { background: #0066cc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin: 20px 0; display: inline-block; }
        h2 { color: #333; }
    </style>
</head>
<body>
    <h2>🎯 {{ count }} Videos Found (Channel)</h2>
    <p><strong>Keyword:</strong> "{{ keyword }}"</p>
    
    {% if videos %}
        {% for v in videos %}
        <div class="video">
            <div class="title">
                <a href="https://youtube.com/watch?v={{ v.videoId }}" target="_blank">
                    ▶️ {{ v.title }}
                </a>
            </div>
            <div class="channel">📺 {{ v.channelTitle }}</div>
        </div>
        {% endfor %}
    {% else %}
        <p>No videos found for this keyword in the channel.</p>
    {% endif %}
    
    <a href="/" class="back">🔍 New Search</a>
</body>
</html>
'''

GLOBAL_RESULTS_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>{{ count }} Videos Found</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 900px; margin: 20px auto; padding: 20px; }
        .video { border: 1px solid #ddd; margin: 15px 0; padding: 20px; border-radius: 10px; background: #fafafa; }
        .title { font-size: 18px; margin: 0 0 10px 0; }
        .title a { color: #ff0000; text-decoration: none; font-weight: bold; }
        .title a:hover { text-decoration: underline; }
        .channel { color: #666; font-size: 14px; margin: 5px 0; }
        .back { background: #0066cc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin: 20px 0; display: inline-block; }
        h2 { color: #333; }
    </style>
</head>
<body>
    <h2>🌍 {{ count }} Videos Found (Global Search)</h2>
    <p><strong>Keyword:</strong> "{{ keyword }}"</p>
    
    {% if videos and videos|length > 0 %}
        {% for v in videos %}
        <div class="video">
            <div class="title">
                <a href="https://youtube.com/watch?v={{ v.videoId }}" target="_blank">
                    ▶️ {{ v.title }}
                </a>
            </div>
            <div class="channel">📺 {{ v.channelTitle }}</div>
        </div>
        {% endfor %}
    {% else %}
        <div style="background: #ffebee; padding: 20px; border-radius: 10px; text-align: center;">
            <h3>😔 No videos found</h3>
            <p>Try a different keyword or check your API key quota.</p>
        </div>
    {% endif %}
    
    <a href="/" class="back">🔍 New Search</a>
</body>
</html>
'''

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)