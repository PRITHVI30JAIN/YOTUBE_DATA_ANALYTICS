"""
YouTube Analytics Dashboard (Streamlit)

How to use:
1. Install dependencies:
   pip install streamlit pandas plotly google-api-python-client

2. Run:
   streamlit run youtube_analytics_streamlit.py

3. In the app: paste your YouTube Data API v3 key (kept hidden), enter the Channel ID
   (starts with "UC...") and click "Fetch data". You can then download CSV and view charts.

Files created by this single-file app: it provides a downloadable `youtube_data.csv` when you fetch.

Requirements:
- Python 3.8+
- streamlit
- pandas
- plotly
- google-api-python-client

Note: This is a beginner-friendly, one-file app made so you can quickly run it and claim the project
on your resume. Customize the UI text (your name/logo) before publishing to GitHub or Streamlit Cloud.

"""

import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
import plotly.express as px
from datetime import datetime
import math

st.set_page_config(page_title="YouTube Analytics Dashboard", layout="wide")

st.sidebar.title("Quick Setup")
st.sidebar.markdown("Paste your **YouTube Data API v3** key and the **Channel ID**, then press Fetch.")
api_key = st.sidebar.text_input("YouTube API Key", type="password")
channel_id = st.sidebar.text_input("Channel ID (starts with 'UC')")
max_videos = st.sidebar.slider("Max videos to fetch", 5, 50, 20)
fetch_button = st.sidebar.button("Fetch data")

st.title("📺 YouTube Analytics Dashboard")
st.write("A lightweight Streamlit dashboard that pulls live channel + video stats using YouTube Data API v3.")

st.markdown("---")

# Small helper
def parse_published(published_at):
    try:
        # Example format: '2020-01-01T12:34:56Z'
        return datetime.fromisoformat(published_at.replace('Z', '+00:00'))
    except Exception:
        return None

# Function to fetch data
@st.cache_data(show_spinner=False)
def fetch_channel_and_videos(api_key, channel_id, max_videos=20):
    youtube = build("youtube", "v3", developerKey=api_key)

    # Channel details
    ch_req = youtube.channels().list(part="statistics,contentDetails,snippet", id=channel_id)
    ch_res = ch_req.execute()
    if not ch_res.get("items"):
        raise ValueError("Channel not found. Check Channel ID.")

    ch_item = ch_res["items"][0]
    stats = ch_item.get("statistics", {})
    snippet = ch_item.get("snippet", {})
    uploads_playlist = ch_item["contentDetails"]["relatedPlaylists"]["uploads"]

    # Fetch playlist items (video IDs)
    video_ids = []
    nextPageToken = None
    while len(video_ids) < max_videos:
        pl_req = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist,
            maxResults=min(50, max_videos - len(video_ids)),
            pageToken=nextPageToken,
        )
        pl_res = pl_req.execute()
        for item in pl_res.get("items", []):
            res_id = item["snippet"]["resourceId"].get("videoId")
            if res_id:
                video_ids.append(res_id)
        nextPageToken = pl_res.get("nextPageToken")
        if not nextPageToken:
            break

    # Fetch video statistics in batches of 50
    data = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        v_req = youtube.videos().list(part="snippet,statistics", id=",".join(batch))
        v_res = v_req.execute()
        for v in v_res.get("items", []):
            snip = v.get("snippet", {})
            stts = v.get("statistics", {})
            pub = parse_published(snip.get("publishedAt", ""))
            data.append(
                {
                    "videoId": v.get("id"),
                    "title": snip.get("title"),
                    "publishedAt": pub,
                    "views": int(stts.get("viewCount", 0)),
                    "likes": int(stts.get("likeCount", 0)) if stts.get("likeCount") else 0,
                    "comments": int(stts.get("commentCount", 0)) if stts.get("commentCount") else 0,
                    "description": snip.get("description", ""),
                }
            )

    df = pd.DataFrame(data)
    if not df.empty:
        df.sort_values(by="publishedAt", inplace=True)
        df.reset_index(drop=True, inplace=True)

    channel_info = {
        "title": snippet.get("title", ""),
        "description": snippet.get("description", ""),
        "subscriberCount": int(stats.get("subscriberCount", 0)) if stats.get("subscriberCount") else 0,
        "viewCount": int(stats.get("viewCount", 0)) if stats.get("viewCount") else 0,
        "videoCount": int(stats.get("videoCount", 0)) if stats.get("videoCount") else 0,
    }

    return channel_info, df

# Main interaction
if fetch_button:
    if not api_key or not channel_id:
        st.sidebar.error("Please provide both API Key and Channel ID.")
    else:
        with st.spinner("Fetching channel info and videos..."):
            try:
                channel_info, df = fetch_channel_and_videos(api_key, channel_id, max_videos)

                # Header / KPIs
                st.header(f"{channel_info.get('title', '')}")
                cols = st.columns(3)
                cols[0].metric("Subscribers", f"{channel_info.get('subscriberCount'):,}")
                cols[1].metric("Total views", f"{channel_info.get('viewCount'):,}")
                cols[2].metric("Total videos", f"{channel_info.get('videoCount'):,}")

                st.markdown("---")

                if df.empty:
                    st.info("No videos fetched for this channel.")
                else:
                    # Show table (top-level columns)
                    display_df = df.copy()
                    display_df["publishedAt"] = display_df["publishedAt"].dt.strftime("%Y-%m-%d")
                    st.subheader("Fetched video data")
                    st.dataframe(display_df[["title", "publishedAt", "views", "likes", "comments"]])

                    # Controls for charts
                    col_a, col_b = st.columns([2, 1])
                    with col_b:
                        top_n = st.slider("Top N videos for charts", 3, min(20, max(3, len(df))), 5)

                    with st.container():
                        st.subheader("Top videos by views")
                        fig = px.bar(df.nlargest(top_n, "views").sort_values("views"), x="views", y="title", orientation="h", title=f"Top {top_n} videos by views")
                        st.plotly_chart(fig, use_container_width=True)

                    st.subheader("Views over publish date")
                    fig2 = px.line(df, x="publishedAt", y="views", markers=True, title="Views by published date")
                    st.plotly_chart(fig2, use_container_width=True)

                    # Download CSV
                    csv = df.to_csv(index=False)
                    st.download_button(label="Download fetched data as CSV", data=csv, file_name="youtube_data.csv", mime="text/csv")

                st.success("Done — data fetched successfully.")
            except Exception as e:
                st.error(f"Failed to fetch data: {e}")

else:
    st.info("Enter your API Key and Channel ID on the left sidebar, adjust Max videos, then click 'Fetch data'.")

# Footer / Help
st.markdown("---")
st.caption("Tip: To find Channel ID, open YouTube Studio -> Settings -> Channel -> Advanced settings, or use the channel's URL. If you get a quota error, reduce the number of videos fetched.")


# End of file
