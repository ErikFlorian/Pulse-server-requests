from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
import tempfile
import threading
import time

app = Flask(__name__)

# Složka pro dočasné soubory
DOWNLOAD_DIR = tempfile.mkdtemp()

# Cesta k cookies souboru (musí být v root složce repozitáře)
COOKIES_FILE = os.path.join(os.path.dirname(__file__), 'cookies.txt')

def cleanup_old_files():
    """Maže soubory starší než 10 minut"""
    while True:
        time.sleep(300)
        now = time.time()
        for f in os.listdir(DOWNLOAD_DIR):
            path = os.path.join(DOWNLOAD_DIR, f)
            if os.path.isfile(path) and now - os.path.getmtime(path) > 600:
                os.remove(path)

# Spusť cleanup thread
threading.Thread(target=cleanup_old_files, daemon=True).start()

def get_ydl_opts_base():
    """Základní options společné pro info i download"""
    opts = {
        'quiet': True,
        'no_warnings': False,
    }
    if os.path.exists(COOKIES_FILE):
        opts['cookiefile'] = COOKIES_FILE
    return opts

@app.route('/health')
def health():
    cookies_ok = os.path.exists(COOKIES_FILE)
    return jsonify({'status': 'ok', 'cookies': cookies_ok})

@app.route('/info', methods=['POST'])
def get_info():
    """Vrátí info o videu (název, délka, thumbnail)"""
    data = request.get_json()
    url = data.get('url', '')
    if not url:
        return jsonify({'error': 'Missing url'}), 400

    try:
        opts = get_ydl_opts_base()
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'uploader': info.get('uploader', '')
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download():
    """Stáhne audio a vrátí MP3 soubor"""
    data = request.get_json()
    url = data.get('url', '')
    if not url:
        return jsonify({'error': 'Missing url'}), 400

    try:
        output_path = os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s')

        opts = get_ydl_opts_base()
        opts.update({
            'format': 'bestaudio/best',
            'outtmpl': output_path,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'audio')
            safe_title = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')
            mp3_path = os.path.splitext(safe_title)[0] + '.mp3'

        if os.path.exists(mp3_path):
            return send_file(
                mp3_path,
                mimetype='audio/mpeg',
                as_attachment=True,
                download_name=f"{title}.mp3"
            )
        else:
            return jsonify({'error': 'Download failed'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
