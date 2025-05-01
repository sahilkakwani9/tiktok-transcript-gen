#!/usr/bin/env python3
"""
Tiktok Monitor Script - Ensemble API Integration

This script monitors a specific Tiktok handle over a defined date range
for specified topics, then makes an API call to Ensemble to fetch data.
It also extracts video URLs and generates transcripts for videos in posts.

Static information:
- Tiktok handle: mjaguilar_official
- Date range: April 30, 2025 to May 2, 2025
- Topics to track: base batches, ETF, XRP
"""

import requests
import time
import json
import logging
import os
import tempfile
"""
Tiktok Monitor Script - Ensemble API Integration

This script monitors a specific Tiktok handle over a defined date range
for specified topics, then makes an API call to Ensemble to fetch data.
It also extracts video URLs and generates transcripts for videos in posts.

Static information:
- Tiktok handle: mjaguilar_official
- Date range: April 30, 2025 to May 2, 2025
- Topics to track: base batches
"""

import requests
import time
import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime
import concurrent.futures

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ensemble_monitor.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger()

# Static information
Tiktok_HANDLE = "mjaguilar_official"
TOPICS = ["base batches", "ETF", "XRP"]

# Date range: April 30, 2025 to May 2, 2025
# Convert to Unix timestamps
START_DATE = int(datetime(2025, 4, 30, 0, 0, 0).timestamp())
END_DATE = int(datetime(2025, 5, 2, 23, 59, 59).timestamp())

# Ensemble API details
API_BASE_URL = "https://ensembledata.com/apis/tt/user/posts"
API_TOKEN = "tDzaIB4HfO3tiZJd"

def fetch_Tiktok_data():
    """
    Fetch Tiktok data for the specified handle within the date range
    """
    # Log the start of the operation
    logger.info(f"Starting to fetch data for handle: {Tiktok_HANDLE}")
    logger.info(f"Date range: {datetime.fromtimestamp(START_DATE).strftime('%Y-%m-%d')} to {datetime.fromtimestamp(END_DATE).strftime('%Y-%m-%d')}")
    logger.info(f"Topics to track: {', '.join(TOPICS)}")
    
    # Construct the API URL
    params = {
        "username": Tiktok_HANDLE,
        "depth": 1,
        "start_cursor": 0,
        "oldest_createtime": START_DATE,
        "alternative_method": False,
        "token": API_TOKEN
    }
    
    try:
        # Make the API call
        response = requests.get(API_BASE_URL, params=params)
        
        # Check if the request was successful
        if response.status_code == 200:
            data = response.json()
            
            # Log the successful response
            logger.info("API call successful")
            logger.info(f"Received {len(data.get('data', [])) if 'data' in data else 0} records")
            
            # Log the full response to a JSON file for detailed analysis
            with open(f"ensemble_data_{Tiktok_HANDLE}_{int(time.time())}.json", "w") as f:
                json.dump(data, f, indent=4)
            
            # Log simplified response summary
            logger.info("Response summary: " + json.dumps(data)[:500] + "...")
            
            # Process and analyze topics
            analyze_topics(data)
            
            return data
        else:
            # Log error response
            logger.error(f"API call failed with status code: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return None
    
    except Exception as e:
        logger.error(f"An error occurred during API call: {str(e)}")
        return None

def extract_video_urls(data):
    """
    Extract video URLs from the response data
    Returns a dictionary mapping post IDs to video URLs
    """
    video_urls = {}
    
    if not data or 'data' not in data:
        logger.warning("No data to extract video URLs from")
        return video_urls
    
    posts = data.get('data', [])
    logger.info(f"Extracting video URLs from {len(posts)} posts")
    
    for post in posts:
        post_id = post.get('group_id', 'unknown')
        
        # Navigate through the data structure to find video URL
        if 'video' in post and isinstance(post['video'], dict):
            video_obj = post['video']
            
            if 'play_addr' in video_obj and isinstance(video_obj['play_addr'], dict):
                play_addr = video_obj['play_addr']
                
                if 'url_list' in play_addr and isinstance(play_addr['url_list'], list) and len(play_addr['url_list']) > 0:
                    video_url = play_addr['url_list'][0]
                    video_urls[post_id] = video_url
                    logger.info(f"Found video URL for post ID {post_id}: {video_url}")
    
    logger.info(f"Total videos found: {len(video_urls)}")
    return video_urls

def download_video(video_url, output_path):
    """
    Download a video from a URL using requests
    """
    try:
        logger.info(f"Downloading video from: {video_url}")
        response = requests.get(video_url, stream=True)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Video downloaded to: {output_path}")
        return True
    except Exception as e:
        logger.error(f"Error downloading video: {str(e)}")
        return False

def generate_transcript(video_path):
    """
    Generate transcript from video using Whisper
    
    This function uses OpenAI's Whisper model via Python package (not CLI)
    for speech recognition and transcription
    """
    try:
        logger.info(f"Generating transcript for: {video_path}")
        
        # We'll use the whisper package directly rather than the CLI
        # First, check if whisper module is available
        try:
            import whisper
            logger.info("Whisper package found, using it for transcription")
            
            # Load the model (smaller models are faster but less accurate)
            model = whisper.load_model("base")
            logger.info("Whisper model loaded")
            
            # Generate transcript
            result = model.transcribe(video_path)
            transcript = result["text"]
            
            logger.info(f"Transcript generated successfully ({len(transcript)} characters)")
            return transcript
            
        except ImportError:
            logger.warning("Whisper package not installed, trying ffmpeg + basic transcription")
            
            # Extract audio using ffmpeg (more reliable than other methods)
            audio_path = os.path.splitext(video_path)[0] + ".wav"
            ffmpeg_command = [
                "ffmpeg", "-i", video_path, 
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                audio_path
            ]
            
            try:
                subprocess.run(ffmpeg_command, check=True, capture_output=True)
                logger.info(f"Audio extracted to: {audio_path}")
                
                # Now try to use speech_recognition if available
                try:
                    import speech_recognition as sr
                    recognizer = sr.Recognizer()
                    
                    with sr.AudioFile(audio_path) as source:
                        audio_data = recognizer.record(source)
                        transcript = recognizer.recognize_google(audio_data)
                        
                    logger.info(f"Transcript generated with Google Speech API ({len(transcript)} characters)")
                    return transcript
                    
                except ImportError:
                    return "Please install either 'openai-whisper' or 'SpeechRecognition' packages for transcription"
                    
            except Exception as e:
                logger.error(f"Error extracting audio with ffmpeg: {str(e)}")
                return f"Error extracting audio: {str(e)}"
    
    except Exception as e:
        logger.error(f"Error generating transcript: {str(e)}")
        return f"Error generating transcript: {str(e)}"

def process_videos_and_transcribe(video_urls):
    """
    Process videos from URLs and generate transcripts
    Returns a dictionary mapping post IDs to transcripts
    """
    transcripts = {}
    temp_dir = tempfile.mkdtemp()
    logger.info(f"Created temporary directory for videos: {temp_dir}")
    
    # Process videos concurrently for better performance
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_to_post = {}
        
        # Start video downloads
        for post_id, video_url in video_urls.items():
            video_path = os.path.join(temp_dir, f"video_{post_id}.mp4")
            future = executor.submit(download_video, video_url, video_path)
            future_to_post[future] = (post_id, video_path)
        
        # Process downloaded videos and generate transcripts
        for future in concurrent.futures.as_completed(future_to_post):
            post_id, video_path = future_to_post[future]
            try:
                if future.result():  # If download was successful
                    transcript = generate_transcript(video_path)
                    transcripts[post_id] = transcript
                    
                    # Save transcript to file
                    transcript_path = f"transcript_{post_id}.txt"
                    with open(transcript_path, 'w', encoding='utf-8') as f:
                        f.write(transcript)
                    logger.info(f"Saved transcript to: {transcript_path}")
            except Exception as e:
                logger.error(f"Error processing video {post_id}: {str(e)}")
    
    logger.info(f"Generated {len(transcripts)} transcripts")
    return transcripts

def analyze_topics(data):
    """
    Analyze the response data for the specified topics
    """
    if not data or 'data' not in data:
        logger.warning("No data to analyze for topics")
        return
    
    posts = data.get('data', [])
    logger.info(f"Analyzing {len(posts)} posts for topics: {', '.join(TOPICS)}")
    
    topic_matches = 0
    for post in posts:
        post_text = post.get('caption', '').lower()
        
        for topic in TOPICS:
            if topic.lower() in post_text:
                topic_matches += 1
                logger.info(f"Topic match found: '{topic}' in post ID: {post.get('id', 'unknown')}")
    
    logger.info(f"Total posts matching tracked topics: {topic_matches}")

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Tiktok Monitor Script - Starting execution")
    
    # Fetch data from Ensemble API
    response_data = fetch_Tiktok_data()
    
    if response_data:
        # Extract video URLs from the response data
        video_urls = extract_video_urls(response_data)
        
        if video_urls:
            # Process videos and generate transcripts
            logger.info("Starting video processing and transcription...")
            transcripts = process_videos_and_transcribe(video_urls)
            
            # Save all transcripts to a single file
            with open("all_transcripts.json", "w", encoding="utf-8") as f:
                json.dump(transcripts, f, indent=4, ensure_ascii=False)
            logger.info("All transcripts saved to: all_transcripts.json")
            
            # Analyze transcripts for topics
            logger.info("Analyzing transcripts for topics...")
            for post_id, transcript in transcripts.items():
                transcript_lower = transcript.lower()
                for topic in TOPICS:
                    if topic.lower() in transcript_lower:
                        logger.info(f"Topic '{topic}' found in transcript for post ID: {post_id}")
        else:
            logger.warning("No videos found in the response data")
        
        logger.info("Script executed successfully")
    else:
        logger.error("Script execution failed")
    
    logger.info("Tiktok Monitor Script - Execution complete")
    logger.info("=" * 50)