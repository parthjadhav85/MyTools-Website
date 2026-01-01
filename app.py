import os
import subprocess
import uuid
import tempfile
from flask import Flask, request, jsonify, send_file, after_this_request
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

# 1. SETUP & PATHS
node_path = r"C:\Program Files\nodejs"
# Add Node and Current Folder (for FFmpeg) to Path
os.environ["PATH"] = node_path + os.pathsep + os.getcwd() + os.pathsep + os.environ["PATH"]

# USE SYSTEM TEMP FOLDER
TEMP_DIR = tempfile.gettempdir()

def get_opts(filename_id, quality, is_audio_only=False):
    # Save to System Temp Folder
    out_path = os.path.join(TEMP_DIR, f"{filename_id}.%(ext)s")
    
    opts = {
        'outtmpl': out_path,
        'quiet': False,
        'noplaylist': True,
        'writethumbnail': False,
        'ffmpeg_location': os.getcwd() 
    }

    if is_audio_only:
        opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else:
        # VIDEO MODE: FORCE COMPATIBILITY (H.264 / AVC)
        # We add [vcodec^=avc] to tell YouTube "Don't give me AV1/VP9"
        if quality == "1080":
            opts['format'] = 'bestvideo[height<=1080][ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        elif quality == "720":
             opts['format'] = 'bestvideo[height<=720][ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best'
        elif quality == "480":
             opts['format'] = 'bestvideo[height<=480][ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best'
        else:
             # Default: Safest MP4 available
             opts['format'] = 'best[ext=mp4][vcodec^=avc]/best[ext=mp4]/best'
    return opts

@app.route('/get-video-info', methods=['POST'])
def get_video_info():
    data = request.json
    url = data.get('url')
    print(f"🔎 Searching: {url}")
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                'title': info.get('title'),
                'thumbnail': info.get('thumbnail'),
                'duration': info.get('duration_string')
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download-video', methods=['POST'])
def download_video():
    data = request.json
    url = data.get('url')
    quality = data.get('quality', 'best')
    mode = data.get('mode', 'video')
    
    file_id = str(uuid.uuid4())
    print(f"⬇️ Downloading {mode} ({quality}) to Temp...")

    try:
        is_audio = (mode == 'audio')
        opts = get_opts(file_id, quality, is_audio)
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            if is_audio:
                filename = f"{file_id}.mp3"
            else:
                filename = f"{file_id}.mp4"
                # If YouTube forced a different container (like mkv), catch it
                if 'ext' in info and info['ext'] != 'mp4':
                     filename = f"{file_id}.{info['ext']}"

        file_path = os.path.join(TEMP_DIR, filename)
        
        # Clean User Filename
        user_filename = f"{info['title']}.{'mp3' if is_audio else 'mp4'}"
        user_filename = "".join([c for c in user_filename if c.isalnum() or c in (' ', '.', '-', '_')]).strip()

        print("✅ Ready! Sending to browser.")

        @after_this_request
        def remove_file(response):
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as error:
                print(f"Error removing file: {error}")
            return response

        return send_file(file_path, as_attachment=True, download_name=user_filename)

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🐍 Server Ready")
    app.run(debug=True, port=5000)