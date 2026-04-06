from flask import Flask, request, render_template_string
import googleapiclient.discovery
import re
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = 'secret-key'

API_KEY = os.getenv("YOUTUBE_API_KEY")

youtube = googleapiclient.discovery.build(
    "youtube", "v3", developerKey=API_KEY
)

# ----------------------------
# 🔍 EXTRACT VIDEO ID
# ----------------------------
def extract_video_id(url):
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else None


# ----------------------------
# 🔍 GET CHANNEL ID FROM VIDEO
# ----------------------------
def get_channel_from_video(video_id):
    try:
        res = youtube.videos().list(
            part="snippet",
            id=video_id
        ).execute()

        return res["items"][0]["snippet"]["channelId"]
    except:
        return None


# ----------------------------
# 🔍 GET CHANNEL ID FROM ANY INPUT
# ----------------------------
def get_channel_id(url):
    # 1. Channel URL
    if "youtube.com/channel/" in url:
        return url.split("channel/")[1].split("/")[0]

    # 2. Video URL
    video_id = extract_video_id(url)
    if video_id:
        return get_channel_from_video(video_id)

    return None


# ----------------------------
# 📦 GET UPLOAD PLAYLIST
# ----------------------------
def get_uploads_playlist(channel_id):
    res = youtube.channels().list(
        part="contentDetails",
        id=channel_id
    ).execute()

    return res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]


# ----------------------------
# 🔥 REAL KEYWORD SEARCH
# ----------------------------
def search_keyword(channel_id, keyword):
    keyword = keyword.lower()
    matched_videos = []

    try:
        playlist_id = get_uploads_playlist(channel_id)

        next_page = None

        while True:
            playlist = youtube.playlistItems().list(
                part="snippet",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page
            ).execute()

            video_ids = [
                item["snippet"]["resourceId"]["videoId"]
                for item in playlist["items"]
            ]

            videos_data = youtube.videos().list(
                part="snippet",
                id=",".join(video_ids)
            ).execute()

            for video in videos_data["items"]:
                title = video["snippet"]["title"].lower()
                desc = video["snippet"]["description"].lower()

                if keyword in title or keyword in desc:
                    matched_videos.append(video)

            next_page = playlist.get("nextPageToken")

            if not next_page:
                break

        return matched_videos

    except Exception as e:
        print("ERROR:", e)
        return []


# ----------------------------
# 🌐 ROUTE
# ----------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":

        url = request.form["url"]
        keyword = request.form["keyword"]

        channel_id = get_channel_id(url)

        if not channel_id:
            return "<h2 style='color:red;'>❌ Invalid YouTube URL</h2>"

        videos = search_keyword(channel_id, keyword)

        return render_template_string(RESULT_HTML,
                                      videos=videos,
                                      keyword=keyword,
                                      count=len(videos))

    return render_template_string(INDEX_HTML)


# ----------------------------
# 🎨 UI
# ----------------------------
INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>YouTube Keyword Tool</title>
<style>
body{font-family:Arial;text-align:center;padding:50px;background:#f5f5f5;}
input{padding:15px;width:60%;margin:10px;border-radius:10px;border:1px solid #ccc;}
button{padding:15px 30px;background:red;color:white;border:none;border-radius:10px;}
</style>
</head>
<body>

<h1>🔍 YouTube Keyword Finder</h1>

<form method="POST">
<input type="text" name="url" placeholder="Channel or Video URL" required><br>
<input type="text" name="keyword" placeholder="Enter keyword" required><br>
<button type="submit">Search</button>
</form>

</body>
</html>
"""

RESULT_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Results</title>
<style>
body{font-family:Arial;padding:40px;background:#f5f5f5;}
.video{background:white;padding:20px;margin:15px;border-radius:10px;}
a{color:red;text-decoration:none;}
</style>
</head>
<body>

<h1>✅ {{ count }} Videos Found</h1>
<h3>Keyword: "{{ keyword }}"</h3>

{% for v in videos %}
<div class="video">
<h3>
<a href="https://youtube.com/watch?v={{ v.id }}" target="_blank">
{{ v.snippet.title }}
</a>
</h3>
<p>{{ v.snippet.channelTitle }}</p>
</div>
{% endfor %}

<br><a href="/">🔙 Back</a>

</body>
</html>
"""

# ----------------------------
# 🚀 RUN
# ----------------------------
if __name__ == "__main__":
    app.run(debug=True)