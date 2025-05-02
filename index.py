def analyze_with_openai(transcript, post_id):
    """
    Analyze transcript with OpenAI to get a relevance score for tracked topics
    Returns a continuous score from 1-100 and reasoning
    """
    try:
        logger.info(f"Analyzing transcript for post {post_id} with OpenAI...")
        
        # Prepare the prompt for OpenAI
        prompt = f"""
        I need to analyze if this transcript from a TikTok video is relevant to the following topics: {', '.join(TOPICS)}
        
        Transcript: 
        {transcript}
        
        Please analyze the relevance of this content to the specified topics.
        Rate the relevance on a continuous scale from 1-100, where:
        - 1-20: Completely unrelated or extremely minimal relation
        - 21-40: Slightly related (mentions topics briefly or tangentially)
        - 41-60: Moderately related (discusses topics but not as main focus)
        - 61-80: Highly related (topics are a major focus)
        - 81-100: Directly focused on the topics
        
        Choose a specific number within these ranges based on the exact relevance level.
        
        Provide your response in JSON format like this:
        {{
            "score": [specific number between 1-100],
            "reasoning": "[brief explanation for the score]"
        }}
        """
        
        # Call OpenAI API
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Use appropriate model
            messages=[
                {"role": "system", "content": "You are an AI that analyzes content relevance to specific topics. Respond with a precise numerical score between 1-100 in JSON format only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,  # Lower temperature for more consistent results
            max_tokens=300
        )
        
        # Extract the response
        result_text = response.choices[0].message.content.strip()
        
        # Parse the JSON response
        try:
            result = json.loads(result_text)
            
            # Ensure score is within 1-100 range
            score = result.get('score', 1)
            if score < 1:
                score = 1
            elif score > 100:
                score = 100
                
            result['score'] = score
            
            logger.info(f"OpenAI analysis complete for post {post_id}. Score: {score}")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing OpenAI response as JSON: {str(e)}")
            logger.error(f"Raw response: {result_text}")
            return {
                "score": 1,
                "reasoning": f"Error parsing OpenAI response: {str(e)}"
            }
    
    except Exception as e:
        logger.error(f"Error with OpenAI analysis: {str(e)}")
        return {
            "score": 1,
            "reasoning": f"Error with OpenAI analysis: {str(e)}"
        }

"""
Tiktok Monitor Script - Ensemble API Integration

This script monitors a specific Tiktok handle over a defined date range
for specified topics, then makes an API call to Ensemble to fetch data.
It also extracts video URLs and generates transcripts for videos in posts.
The transcripts are then analyzed using OpenAI to determine relevance to tracked topics.

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
import openai
from dotenv import load_dotenv

load_dotenv()

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
Tiktok_HANDLE = "giucomia"
TOPICS = ["base batches", "ETF", "XRP", "CRYPTO"]

# Date range: April 30, 2025 to May 2, 2025
# Convert to Unix timestamps
START_DATE = int(datetime(2025, 4, 30, 0, 0, 0).timestamp())
END_DATE = int(datetime(2025, 5, 2, 23, 59, 59).timestamp())

# Ensemble API details
API_BASE_URL = "https://ensembledata.com/apis/tt/user/posts"
API_TOKEN = "tDzaIB4HfO3tiZJd" # Replace with your actual token



# Get OpenAI API key from environment variable
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY


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
    
    data_array = data.get('data', [])
    posts = [data_array[3]]
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

def analyze_topics(data, transcripts=None):
    """
    Analyze the response data and transcripts for the specified topics
    Now includes both keyword matching and OpenAI analysis when available
    """
    if not data or 'data' not in data:
        logger.warning("No data to analyze for topics")
        return {}
    
    data_array = data.get('data', [])
    posts = [data_array[3]]
    logger.info(f"Analyzing {len(posts)} posts for topics: {', '.join(TOPICS)}")
    
    results = {}
    for post in posts:
        post_id = post.get('group_id', 'unknown')
        post_text = post.get('caption', '')
        
        # Initialize result for this post
        post_result = {
            "post_id": post_id,
            "keyword_matches": [],
            "openai_analysis": None,
            "combined_score": 0
        }
        
        # 1. Perform keyword matching
        for topic in TOPICS:
            if topic.lower() in post_text.lower():
                post_result["keyword_matches"].append(topic)
                logger.info(f"Topic match found: '{topic}' in post caption: {post_id}")
        
        # Calculate keyword score (simple percentage of matched topics)
        keyword_score = len(post_result["keyword_matches"]) / len(TOPICS) * 100 if TOPICS else 0
        post_result["keyword_score"] = keyword_score
        
        # 2. Check if we have a transcript for this post
        if transcripts and post_id in transcripts:
            transcript = transcripts[post_id]
            
            # Look for keyword matches in transcript
            for topic in TOPICS:
                if topic.lower() in transcript.lower() and topic not in post_result["keyword_matches"]:
                    post_result["keyword_matches"].append(topic)
                    logger.info(f"Topic match found: '{topic}' in post transcript: {post_id}")
            
            # Update keyword score with transcript matches
            keyword_score = len(post_result["keyword_matches"]) / len(TOPICS) * 100 if TOPICS else 0
            post_result["keyword_score"] = keyword_score
            
            # 3. Perform OpenAI analysis if we have a transcript and API key
            if OPENAI_API_KEY and OPENAI_API_KEY != "YOUR_OPENAI_API_KEY_HERE":
                try:
                    openai_result = analyze_with_openai(transcript, post_id)
                    post_result["openai_analysis"] = openai_result
                    
                    # Calculate combined score (average of keyword and OpenAI scores)
                    openai_score = openai_result.get("score", 0)
                    post_result["combined_score"] = (keyword_score + openai_score) / 2
                    
                    logger.info(f"Combined analysis for post {post_id}: " +
                               f"Keyword Score: {keyword_score}, OpenAI Score: {openai_score}, " +
                               f"Combined: {post_result['combined_score']}")
                except Exception as e:
                    logger.error(f"Error in OpenAI analysis for post {post_id}: {str(e)}")
                    # Fall back to keyword score
                    post_result["combined_score"] = keyword_score
            else:
                # If no OpenAI API key, just use keyword score
                post_result["combined_score"] = keyword_score
        else:
            # No transcript, just use keyword score
            post_result["combined_score"] = keyword_score
        
        results[post_id] = post_result
    
    return results

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Tiktok Monitor Script - Starting execution")
    
    # Fetch data from Ensemble API
    response_data = fetch_Tiktok_data()
    
    if response_data:
        # Extract video URLs from the response data
        video_urls = extract_video_urls(response_data)
        
        transcripts = {}
        if video_urls:
            # Process videos and generate transcripts
            logger.info("Starting video processing and transcription...")
            transcripts = process_videos_and_transcribe(video_urls)
            
            # Save all transcripts to a single file
            with open("all_transcripts.json", "w", encoding="utf-8") as f:
                json.dump(transcripts, f, indent=4, ensure_ascii=False)
            logger.info("All transcripts saved to: all_transcripts.json")
        else:
            logger.warning("No videos found in the response data")
        
        # Analyze posts and transcripts
        logger.info("Analyzing posts and transcripts...")
        analysis_results = analyze_topics(response_data, transcripts)
        
        # Save analysis results
        with open("analysis_results.json", "w", encoding="utf-8") as f:
            json.dump(analysis_results, f, indent=4, ensure_ascii=False)
        logger.info("Analysis results saved to: analysis_results.json")
        
        # Output summary
        logger.info("-" * 50)
        logger.info("ANALYSIS SUMMARY")
        logger.info("-" * 50)
        
        # Sort by combined score
        sorted_results = sorted(
            analysis_results.items(), 
            key=lambda x: x[1].get('combined_score', 0), 
            reverse=True
        )
        
        for post_id, result in sorted_results:
            logger.info(f"Post ID: {post_id}")
            logger.info(f"  Combined Score: {result.get('combined_score', 0):.1f}/100")
            logger.info(f"  Keyword Score: {result.get('keyword_score', 0):.1f}/100")
            
            if result.get('openai_analysis'):
                logger.info(f"  OpenAI Score: {result['openai_analysis'].get('score', 0):.1f}/100")
                logger.info(f"  Reasoning: {result['openai_analysis'].get('reasoning', 'N/A')}")
            
            logger.info(f"  Keyword Matches: {', '.join(result.get('keyword_matches', []))}")
            logger.info("-" * 30)
        
        logger.info("Script executed successfully")
    else:
        logger.error("Script execution failed")
    
    logger.info("Tiktok Monitor Script - Execution complete")
    logger.info("=" * 50)