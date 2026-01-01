import os
import subprocess
import uuid
import tempfile
import shutil
from pathlib import Path
from flask import Flask, request, jsonify, send_file, after_this_request
from flask_cors import CORS
from werkzeug.utils import secure_filename
import yt_dlp

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ---
node_path = r"C:\Program Files\nodejs"
os.environ["PATH"] = node_path + os.pathsep + os.getcwd() + os.pathsep + os.environ["PATH"]

# Use System Temp Folder for all operations
TEMP_DIR = tempfile.gettempdir()
UPLOAD_FOLDER = os.path.join(TEMP_DIR, "mytools_uploads")

# Create upload folder if not exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- YOUTUBE DOWNLOADER LOGIC (Previous Tool) ---
def get_opts(filename_id, quality, is_audio_only=False):
    out_path = os.path.join(TEMP_DIR, f"{filename_id}.%(ext)s")
    opts = {
        'outtmpl': out_path, 'quiet': False, 'noplaylist': True, 
        'writethumbnail': False, 'ffmpeg_location': os.getcwd() 
    }
    if is_audio_only:
        opts.update({'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}]})
    else:
        # Force H.264 (AVC)
        if quality == "1080": opts['format'] = 'bestvideo[height<=1080][ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        elif quality == "720": opts['format'] = 'bestvideo[height<=720][ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best'
        elif quality == "480": opts['format'] = 'bestvideo[height<=480][ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best'
        else: opts['format'] = 'best[ext=mp4][vcodec^=avc]/best[ext=mp4]/best'
    return opts

@app.route('/get-video-info', methods=['POST'])
def get_video_info():
    try:
        url = request.json.get('url')
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({'title': info.get('title'), 'thumbnail': info.get('thumbnail'), 'duration': info.get('duration_string')})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/download-video', methods=['POST'])
def download_video():
    try:
        data = request.json
        file_id = str(uuid.uuid4())
        mode = data.get('mode', 'video')
        opts = get_opts(file_id, data.get('quality', 'best'), mode == 'audio')
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(data.get('url'), download=True)
            ext = 'mp3' if mode == 'audio' else 'mp4'
            # Catch odd extensions
            if 'ext' in info and info['ext'] != 'mp4' and mode != 'audio': ext = info['ext']
            
        file_path = os.path.join(TEMP_DIR, f"{file_id}.{ext}")
        user_filename = f"{info['title']}.{ext}"
        user_filename = "".join([c for c in user_filename if c.isalnum() or c in (' ', '.', '-', '_')]).strip()

        @after_this_request
        def remove_file(response):
            try: os.remove(file_path)
            except: pass
            return response

        return send_file(file_path, as_attachment=True, download_name=user_filename)
    except Exception as e: return jsonify({'error': str(e)}), 500


# --- NEW TOOL: UNIVERSAL MEDIA CONVERTER ---

@app.route('/convert-media', methods=['POST'])
def convert_media():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    target_format = request.form.get('format', 'mp4') # mp4, mp3, gif, wav
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # 1. Save uploaded file
    file_id = str(uuid.uuid4())
    original_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'tmp'
    input_filename = f"{file_id}_input.{original_ext}"
    input_path = os.path.join(UPLOAD_FOLDER, input_filename)
    file.save(input_path)

    # 2. Define Output Path
    output_filename = f"{file_id}_output.{target_format}"
    output_path = os.path.join(UPLOAD_FOLDER, output_filename)

    print(f"🔄 Converting {input_filename} to {target_format}...")

    try:
        # 3. Construct FFmpeg Command
        command = ['ffmpeg', '-i', input_path]

        if target_format == 'mp4':
            # Force H.264 Video + AAC Audio (Standard MP4)
            command.extend(['-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart'])
        
        elif target_format == 'mp3':
            # Extract Audio Only
            command.extend(['-vn', '-acodec', 'libmp3lame', '-ab', '192k'])
        
        elif target_format == 'wav':
            # High Quality Audio
            command.extend(['-vn', '-acodec', 'pcm_s16le'])
            
        elif target_format == 'gif':
            # Create optimized GIF (15fps, width 480px)
            command.extend(['-vf', 'fps=15,scale=480:-1:flags=lanczos', '-c:v', 'gif'])

        # Overwrite output if exists
        command.append(output_path)
        command.append('-y') 

        # 4. RUN FFmpeg
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("✅ Conversion Success!")

        # 5. Send file back to user
        @after_this_request
        def cleanup(response):
            try:
                os.remove(input_path) # Delete original
                os.remove(output_path) # Delete converted
                print("🧹 Cleaned up conversion files.")
            except Exception as e:
                print(f"Cleanup Error: {e}")
            return response

        # Use original name but with new extension
        download_name = Path(file.filename).stem + "." + target_format
        return send_file(output_path, as_attachment=True, download_name=download_name)

    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg Error: {e.stderr.decode()}")
        return jsonify({'error': 'Conversion failed. File might be corrupted.'}), 500
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'error': str(e)}), 500

# --- 4. PDF MERGER TOOL ---
from pypdf import PdfWriter

@app.route('/merge-pdfs', methods=['POST'])
def merge_pdfs():
    if 'files' not in request.files: return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('files')
    if not files or files[0].filename == '': return jsonify({'error': 'No files selected'}), 400

    merge_id = str(uuid.uuid4())
    output_filename = f"merged_{merge_id}.pdf"
    output_path = os.path.join(UPLOAD_FOLDER, output_filename)

    print(f"📄 Merging {len(files)} PDFs...")

    try:
        merger = PdfWriter()
        temp_paths = []

        # Save and append each file
        for i, file in enumerate(files):
            # Save temporarily
            temp_name = f"{merge_id}_{i}.pdf"
            temp_path = os.path.join(UPLOAD_FOLDER, temp_name)
            file.save(temp_path)
            temp_paths.append(temp_path)
            # Append to merger
            merger.append(temp_path)

        # Write final file
        merger.write(output_path)
        merger.close()
        
        print("✅ Merge Complete!")

        # Cleanup inputs + Schedule output deletion
        for path in temp_paths:
            try: os.remove(path)
            except: pass

        @after_this_request
        def cleanup(response):
            try: os.remove(output_path)
            except: pass
            return response

        return send_file(output_path, as_attachment=True, download_name="merged_document.pdf")

    except Exception as e:
        print(f"❌ PDF Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🐍 MyTools Server Running (Port 5000)")
    app.run(debug=True, port=5000)