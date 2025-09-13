import os
from dotenv import load_dotenv
from googleapiclient.discovery import build

# Load environment variables from .env
load_dotenv()

# Get API key from .env file
api_key = os.getenv("YOUTUBE_API_KEY")

if not api_key:
    raise ValueError("⚠️ No API key found! Please add YOUTUBE_API_KEY in your .env file.")

# Create YouTube API client
youtube = build("youtube", "v3", developerKey=api_key)

# Example: Get channel details
request = youtube.channels().list(
    part="snippet,contentDetails,statistics",
    forUsername="GoogleDevelopers"   # Change this to your target channel
)
response = request.execute()

print("Channel Details:")
print(response)
