from flask import Flask, request, jsonify, send_from_directory
import google.generativeai as genai
import os
import json
import yt_dlp
import os
import threading

app = Flask(__name__)

# Global variable to store download progress
download_progress = 0

# Progress hook function for yt-dlp
def progress_hook(d):
    global download_progress
    print(f"Progress hook received: {d['status']}")
    if d['status'] == 'downloading':
        if '_percent_str' in d:
            progress_str = d['_percent_str'].strip()
            print(f"_percent_str: '{progress_str}'")
            import re
            match = re.search(r'(\d+\.?\d*)%', progress_str)
            if match:
                try:
                    download_progress = float(match.group(1))
                    print(f"Extracted progress: {download_progress}")
                except ValueError:
                    print(f"Could not convert extracted percentage to float: {match.group(1)}")
            else:
                print(f"Could not find percentage in _percent_str: {progress_str}")
        elif 'downloaded_bytes' in d and 'total_bytes' in d and d['total_bytes'] is not None:
             download_progress = (d['downloaded_bytes'] / d['total_bytes']) * 100
             print(f"Calculated progress from bytes: {download_progress}")
        elif 'downloaded_bytes' in d and 'total_bytes_estimate' in d and d['total_bytes_estimate'] is not None:
             download_progress = (d['downloaded_bytes'] / d['total_bytes_estimate']) * 100
             print(f"Calculated progress from bytes estimate: {download_progress}")


    if d['status'] == 'finished':
        download_progress = 100.0
        print("Download finished. Progress set to 100.")
    if d['status'] == 'error':
        download_progress = -1.0
        print("Download error. Progress set to -1.")



# Configure Gemini API key
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    API_KEY = "AIzaSyASUzj4TwSEZTCd3QEycwgfBQgjfHykaBE"

genai.configure(api_key=API_KEY)
print(f"Using API Key (first 5 chars): {API_KEY[:5]}...")

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

@app.route('/convert', methods=['POST'])
def convert_youtube_link():
    print("Received request to /convert")
    data = request.get_json()
    print(f"Received data: {data}")
    youtube_link = data.get('youtube_link')
    print(f"Extracted youtube_link: {youtube_link}")

    if not youtube_link:
        print("No YouTube link provided in request")
        return jsonify({"error": "No YouTube link provided"}), 400

    try:
        print("Crafting prompt for Gemini API")
        prompt = f"""
        Analyze the content of the YouTube video at the following link: {youtube_link}

        Identify five distinct, independent segments within the video that would make engaging YouTube Shorts.
        For each segment, provide the start and end timestamps in seconds.
        Return ONLY a json containing the timestamps in a JSON array format.No info no intro no context image i am copying the response without looking and using it. Each object in the array should have 'start_time' and 'end_time' keys.
        Ensure the segments are independent and do not overlap significantly.

        Example JSON format:
        [
          {{ "start_time": integer in secs, "end_time": integeer in secs }},
          {{ "start_time": integer in secs, "end_time": integer in secs }}
        ]
        """

        print("Calling Gemini API")
        model = genai.GenerativeModel('gemini-2.0-flash')
        try:
            response = model.generate_content(prompt)
            print("Received response from Gemini API")
            print(f"Gemini API raw response: {response}")
            print(f"Gemini API response text: {response.text}")
        except Exception as gemini_e:
            print(f"Error calling Gemini API: {gemini_e}")
            return jsonify({"error": f"Error calling Gemini API: {gemini_e}"}), 500


        print("Attempting to parse Gemini API response as JSON")
        try:
            import re
            json_string_match = re.search(r'\[.*?\]', response.text, re.DOTALL)
            if json_string_match:
                json_string = json_string_match.group(0)
                print(f"Attempting to parse JSON string: {json_string}")
                try:
                    timestamps = json.loads(json_string)
                    print(f"Parsed timestamps: {timestamps}")
                    if isinstance(timestamps, list) and all(isinstance(item, dict) and 'start_time' in item and 'end_time' in item for item in timestamps):
                         print("JSON format validated. Attempting to download video.")

                         output_template = 'temp_video.mp4'
                         ydl_opts = {
                             'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                             'outtmpl': output_template,
                             'merge_output_format': 'mp4',
                             'noplaylist': True,
                             'progress_hooks': [progress_hook],
                         }

                         global download_progress
                         download_progress = 0

                         try:
                             print(f"Attempting to download: {youtube_link}")
                             with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                 ydl.download([youtube_link])
                             print(f"Successfully downloaded {youtube_link} to {output_template}")
                             print("Video downloaded. Cutting segments based on timestamps.")
                             cut_segments = []
                             for i, timestamp in enumerate(timestamps):
                                 start = timestamp['start_time']
                                 end = timestamp['end_time']
                                 output_filename = f'segment_{i+1}.mp4'
                                 command = [
                                     './ffmpeg-7.0.2-amd64-static/ffmpeg',
                                     '-i', output_template,
                                     '-ss', str(start),
                                     '-to', str(end),
                                     '-c', 'copy',
                                     output_filename
                                 ]
                                 print(f"Executing ffmpeg command: {' '.join(command)}")
                                 try:
                                     import subprocess
                                     subprocess.run(command, check=True, capture_output=True)
                                     print(f"Successfully cut segment {i+1} to {output_filename}")
                                     cut_segments.append(output_filename)
                                 except subprocess.CalledProcessError as ffmpeg_e:
                                     print(f"Error cutting video segment {i+1}: {ffmpeg_e.stderr.decode()}")
                                 except FileNotFoundError:
                                     print("ffmpeg command not found. Please ensure ffmpeg is installed and in your PATH.")
                                     return jsonify({"error": "ffmpeg not found. Please install ffmpeg."}), 500


                             try:
                                 os.remove(output_template)
                                 print(f"Removed temporary file: {output_template}")
                             except OSError as cleanup_e:
                                 print(f"Error removing temporary file {output_template}: {cleanup_e}")

                             return jsonify({"segments": cut_segments}), 200

                         except Exception as download_e:
                             error_message = str(download_e)
                             print(f"Error downloading video: {error_message}")
                             return jsonify({"error": f"Video download failed: {error_message}"}), 500
                    else:
                         print("Gemini API response did not match expected JSON format.")
                         return jsonify({"error": "Gemini API did not match expected JSON format"}), 500
                except json.JSONDecodeError as e:
                    print(f"JSONDecodeError: Failed to parse JSON response. Raw response: {response.text}, Extracted JSON string: {json_string}, Error: {str(e)}")
                    return jsonify({"error": "Failed to parse JSON response from Gemini API", "raw_response": response.text, "extracted_json": json_string, "error_message": str(e)}), 500
            else:
                print("No JSON string found in Gemini API response.")
                return jsonify({"error": "No JSON string found in Gemini API response", "raw_response": response.text}), 500
        except Exception as parse_e:
             print(f"An unexpected error occurred during JSON parsing: {parse_e}")
             return jsonify({"error": f"An unexpected error occurred during JSON parsing: {parse_e}", "raw_response": response.text}), 500


    except Exception as e:
        print(f"An unexpected exception occurred in /convert route: {e}")
        return jsonify({"error": f"An unexpected exception occurred in /convert route: {e}"}), 500

@app.route('/download_segment/<filename>')
def download_segment(filename):
   print(f"Received request to download segment: {filename}")
   try:
       if not (filename.startswith('segment_') or filename.startswith('processed_')) or not filename.endswith('.mp4'):
            return "Invalid filename", 400

       return send_from_directory('.', filename)
   except FileNotFoundError:
       return "File not found", 404
   except Exception as e:
       print(f"Error serving file {filename}: {e}")
       return "An error occurred", 500

@app.route('/delete_segment/<filename>', methods=['DELETE'])
def delete_segment(filename):
   print(f"Received request to delete segment: {filename}")
   try:
       if not (filename.startswith('segment_') or filename.startswith('processed_')) or not filename.endswith('.mp4'):
            return "Invalid filename", 400
            
       if os.path.exists(filename):
           os.remove(filename)
           return "File deleted", 200
       return "File not found", 404
   except Exception as e:
       print(f"Error deleting file {filename}: {e}")
       return "An error occurred", 500


@app.route('/progress', methods=['GET'])
def get_progress():
    global download_progress
    return jsonify({"progress": download_progress})


@app.route('/process_videos', methods=['POST'])
def process_videos():
    print("Received request to /process_videos")
    data = request.get_json()
    print(f"Received data: {data}")
    segment_filenames = data.get('segments')
    option = data.get('option')

    if not segment_filenames or not option:
        print("Missing segment filenames or option in request")
        return jsonify({"error": "Missing segment filenames or option"}), 400

    processed_segments = []
    for filename in segment_filenames:
        input_path = filename
        output_filename = f'processed_{filename}'
        output_path = output_filename

        ffmpeg_command = []

        if option == 'crop':
            print(f"Processing {filename}: Cropping to 9:16")
            ffmpeg_command = [
                'ffmpeg',
                '-i', input_path,
                '-vf', "crop='if(gte(ih,iw*16/9),iw,ih*9/16)':'if(gte(ih,iw*16/9),ih*16/9,ih)'",
                '-c:a', 'copy',
                output_path
            ]
        elif option == 'bars':
            print(f"Processing {filename}: Adding black bars to 9:16")
            ffmpeg_command = [
                'ffmpeg',
                '-i', input_path,
                '-vf', "scale=1080:-1,pad=1080:1920:0:(1920-ih)/2:black",
                '-c:a', 'copy',
                output_path
            ]
        else:
            print(f"Invalid option received: {option}")
            return jsonify({"error": f"Invalid processing option: {option}"}), 400

        print(f"Executing ffmpeg command: {' '.join(ffmpeg_command)}")
        try:
            import subprocess
            subprocess.run(ffmpeg_command, check=True, capture_output=True)
            print(f"Successfully processed {filename} to {output_filename}")
            processed_segments.append(output_filename)
            try:
                os.remove(input_path)
                print(f"Removed temporary segment file: {input_path}")
            except OSError as cleanup_e:
                print(f"Error removing temporary segment file {input_path}: {cleanup_e}")
        except subprocess.CalledProcessError as ffmpeg_e:
            print(f"Error processing video segment {filename}: {ffmpeg_e.stderr.decode()}")
        except FileNotFoundError:
            print("ffmpeg command not found. Please ensure ffmpeg is installed and in your PATH.")
            return jsonify({"error": "ffmpeg not found. Please install ffmpeg."}), 500
        except Exception as e:
            print(f"An unexpected error occurred during processing {filename}: {e}")
            return jsonify({"error": f"An unexpected error occurred during processing {filename}: {e}"}), 500


    return jsonify({"processed_segments": processed_segments}), 200


if __name__ == '__main__':
   app.run(debug=True)