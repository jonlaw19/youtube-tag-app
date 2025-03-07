import os
import re
import time
import random
from functools import lru_cache
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify
import openai
from youtube_transcript_api import YouTubeTranscriptApi

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "replace-this-with-a-secret-key")  


def extract_video_id(url):
    """
    Extracts the YouTube video ID from various URL formats.
    """
    pattern = r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'
    match = re.search(pattern, url)
    return match.group(1) if match else None


@lru_cache(maxsize=100)
def get_transcript_text_cached(video_id):
    """
    Retrieves and caches the transcript for the given video ID.
    Implements exponential backoff for retries.
    """
    max_retries = 3
    retry_delay = 2 
    
    for attempt in range(max_retries):
        try:
       
            time.sleep(0.5 + random.random())
            
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
            transcript_text = " ".join(segment['text'] for segment in transcript_list)
            print(f"Successfully retrieved transcript for {video_id}")
            return transcript_text
        except Exception as e:
            print(f"Attempt {attempt+1}/{max_retries}: Error fetching transcript for {video_id}: {e}")
            if "Too Many Requests" in str(e):
        
                sleep_time = retry_delay * (4 ** attempt) + random.random() * 2
                print(f"Rate limit hit. Retrying in {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
            elif attempt < max_retries - 1:
    
                sleep_time = retry_delay * (2 ** attempt) + random.random()
                print(f"Retrying in {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
            else:
                print(f"All retry attempts failed for {video_id}")
                return None

def get_transcript_text(video_id):
    """
    Wrapper for the cached transcript function.
    """
    return get_transcript_text_cached(video_id)

def clean_tags(tag_string):
    """
    Clean and normalize tags by removing numbering and ensuring consistent format.
    """
    cleaned = re.sub(r'\d+[\.\)]\s*|\d+\.\s*', '', tag_string)
    
    parts = re.split(r',\s*|\s+(?=\w)', cleaned)
    
    return ', '.join(part.strip() for part in parts if part.strip())

def generate_tags(transcript):
    """
    Uses OpenAI's GPT-3.5 Turbo to generate tags from the transcript.
    """
    max_transcript_length = 4000
    if len(transcript) > max_transcript_length:
        transcript = transcript[:max_transcript_length] + "..."
    
    prompt = (
        "Extract 3-5 concise keywords that best describe the main topics of the following YouTube video transcript.\n"
        "Return the keywords as a comma-separated list (e.g., tag1, tag2, tag3):\n\n"
        f"\"\"\"\n{transcript}\n\"\"\"\n\nKeywords:"
    )
    
    try:
        time.sleep(0.5)
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are an assistant that extracts concise keywords from a YouTube video transcript."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=50,
            temperature=0.3
        )
        raw_tags = response.choices[0].message.content.strip()
        tags = clean_tags(raw_tags)
        return tags
    except Exception as e:
        print(f"Error generating tags: {e}")
        return None

# --- Flask Routes ---
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        video_url = request.form.get("video_url")
        if not video_url:
            flash("Please enter a YouTube video URL.")
            return redirect(url_for("index"))
        
        video_id = extract_video_id(video_url)
        if not video_id:
            flash("Could not extract video ID from the URL. Please try again.")
            return redirect(url_for("index"))
        
        transcript = get_transcript_text(video_id)
        if not transcript:
            flash("Failed to retrieve transcript. The video may not have captions or we're experiencing rate limits from YouTube. Please try again later.")
            return redirect(url_for("index"))
        
        tags = generate_tags(transcript)
        if not tags:
            flash("Failed to generate tags.")
            return redirect(url_for("index"))
        
        return render_template("result.html", video_url=video_url, transcript=transcript, tags=tags)
    
    return render_template("index.html")

@app.route("/debug/<video_id>")
def debug_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        return jsonify({
            "status": "success", 
            "length": len(transcript_list), 
            "sample": transcript_list[:5]
        })
    except Exception as e:
        return jsonify({
            "status": "error", 
            "error": str(e), 
            "type": str(type(e).__name__)
        })

@app.route("/health")
def health_check():
    """
    Simple health check endpoint to verify the app is running.
    """
    return jsonify({
        "status": "ok",
        "timestamp": time.time()
    })

if __name__ == "__main__":
    openai.api_key = os.getenv("OPENAI_API_KEY") 
    app.run(debug=True)
