import yt_dlp
import sys
import os

# Get video URL from command line arguments
if len(sys.argv) < 2:
    print("Usage: python download_video.py <video_url>")
    sys.exit(1)

video_url = sys.argv[1]
output_template = 'temp_video.mp4'

ydl_opts = {
    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    'outtmpl': output_template,
    'merge_output_format': 'mp4',
    'noplaylist': True, # Ensure only the single video is downloaded
    'progress_hooks': [lambda d: print(d['status'])], # Optional: print download progress
}

try:
    print(f"Attempting to download: {video_url}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])
    print(f"Successfully downloaded {video_url} to {output_template}")
except Exception as e:
    print(f"Error downloading video: {e}")
    sys.exit(1)