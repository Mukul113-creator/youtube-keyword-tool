from flask import Flask, request, render_template_string
import googleapiclient.discovery
import googleapiclient.errors
import traceback
import sqlite3
from datetime import datetime

app = Flask(__name__)

# YOUR API KEY
API_KEY = "AIzaSyC7BRFy3rMbOI3H8Iokf6i--COcSu-XOaU"

# ---------------- SIMPLE DB ----------------
def init_db():
    conn = sqlite3.connect('usage.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usage (ip TEXT, date TEXT, count INTEGER)''')
    conn.commit()
    conn.close()
init_db()

# ---------------- YOUTUBE WITH FULL DEBUG ----------------
def search_youtube_debug(query):
    """🔍 FULL DEBUG - Shows EXACT ERROR"""
    youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=API_KEY)
    
    try:
        print(f"🔍 DEBUG: Searching '{query}'...")
        res = youtube.search().list(
            part="snippet",
            q=query,
            type="video",
            maxResults=5
        ).execute()
        
        print(f"✅ SUCCESS: Found {len(res.get('items', []))} videos")
        videos = []
        for item in res.get('items', []):
            videos.append({
                'videoId': item['id']['videoId'],
                'title': item['snippet']['title'],
                'channel': item['snippet']['channelTitle']
            })
        return videos
        
    except googleapiclient.errors.HttpError as e:
        error_content = e.content.decode('utf-8')
        print(f"❌ HTTP ERROR {e.resp.status}: {error_content}")
        return [{'error': f"HTTP {e.resp.status}", 'details': error_content}]
    except Exception as e:
        print(f"💥 FULL ERROR: {str(e)}")
        print(f"TRACEBACK: {traceback.format_exc()}")
        return [{'error': f"ERROR: {str(e)}"}]

# ---------------- ROUTES ----------------
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        keyword = request.form.get('keyword', 'music').strip()
        
        # 🔥 SEARCH WITH DEBUG
        videos = search_youtube_debug(keyword)
        
        if videos and 'error' in videos[0]:
            return f"""
            <h1>🔍 DEBUG RESULTS</h1>
            <h2 style="color:red;">❌ ERROR:</h2>
            <pre style="background:#fee;padding:20px;border-radius:10px;">{videos[0]['details']}</pre>
            <p><a href="/">← Back</a></p>
            """
        
        # SUCCESS - Show videos
        html = '<h1>✅ ' + str(len(videos)) + ' Videos Found!</h1>'
        for v in videos:
            html += f'''
            <div style="border:1px solid #ddd;padding:15px;margin:10px 0;border-radius:10px;">
                <a href="https://youtube.com/watch?v={v['videoId']}" target="_blank" style="font-size:18px;color:#d00;font-weight:bold;">
                    ▶ {v['title']}
                </a><br>
                <span style="color:#666;">📺 {v['channel']}</span>
            </div>
            '''
        html += '<p><a href="/">New Search</a></p>'
        return html
    
    return '''
    <h1>🎵 YouTube Test</h1>
    <form method="POST">
        <input name="keyword" placeholder="music" style="width:400px;padding:15px;font-size:16px;">
        <br><button style="padding:15px 30px;font-size:16px;background:#ff4444;color:white;border:none;border-radius:10px;cursor:pointer;">TEST API</button>
    </form>
    <p><strong>Expected:</strong> Taylor Swift, Drake music videos</p>
    '''

@app.route('/logs')
def logs():
    """🔍 SHOW SERVER LOGS"""
    import subprocess
    try:
        result = subprocess.run(['tail', '-n', '50', '/tmp/render.log'], capture_output=True, text=True)
        return f'<pre style="background:black;color:lime;padding:20px;">{result.stdout}</pre>'
    except:
        return "No logs found"

if __name__ == '__main__':
    print("🚀 DEBUG SERVER - Check console for errors!")
    app.run(debug=True)