import os
import re
from flask import Flask, request, render_template, redirect, url_for, flash
import openai
from youtube_transcript_api import YouTubeTranscriptApi

app = Flask(__name__)
app.secret_key = 'replace-this-with-a-secret-key'  # needed for flash messages

# --- Helper Functions ---
def extract_video_id(url):
    """
    Extracts the YouTube video ID from various URL formats.
    """
    pattern = r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'
    match = re.search(pattern, url)
    return match.group(1) if match else None

def get_transcript_text(video_id):
    """
    Retrieves the transcript for the given video ID.
    """
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        transcript_text = " ".join(segment['text'] for segment in transcript_list)
        return transcript_text
    except Exception as e:
        print(f"Error fetching transcript for {video_id}: {e}")
        return None

def generate_tags(transcript):
    """
    Uses OpenAI's GPT-3.5 Turbo to generate tags from the transcript.
    """
    prompt = (
        "Extract 3-5 concise keywords that best describe the main topics of the following YouTube video transcript.\n"
        "Return the keywords as a comma-separated list (e.g., tag1, tag2, tag3):\n\n"
        f"\"\"\"\n{transcript}\n\"\"\"\n\nKeywords:"
    )
    try:
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
        tags = response.choices[0].message.content.strip()
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
            flash("Failed to retrieve transcript. The video may not have captions.")
            return redirect(url_for("index"))

        tags = generate_tags(transcript)
        if not tags:
            flash("Failed to generate tags.")
            return redirect(url_for("index"))

        return render_template("result.html", video_url=video_url, transcript=transcript, tags=tags)

    return render_template("index.html")

if __name__ == "__main__":
    # Set your OpenAI API key from an environment variable or directly here
    openai.api_key = os.getenv("OPENAI_API_KEY") or "YOUR-API-KEY"
    app.run(debug=True)
