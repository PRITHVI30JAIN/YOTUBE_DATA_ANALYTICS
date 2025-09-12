import streamlit as st
import pandas as pd
import plotly.express as px
from googleapiclient.discovery import build

st.warning("🚀 NEW VERSION LOADED")

# ---------------------------
# CONFIG
# ---------------------------
API_KEY = "AIzaSyCxjHXpZKCFFTrhtPg_MELMd7ajnGb2yeA"  # your API key
CHANNEL_ID = "UCX6OQ3DkcsbYNE6H8uQQuVA"  # MrBeast channel ID

# ---------------------------
# FUNCTIONS
# ---------------------------

def get_channel_stats(api_key, channel_id):
    youtube = build("youtube", "v3", developerKey=api_key)
    request = youtube.channels().list(
        part="snippet,contentDetails,statistics",
        id=channel_id
    )
    response = request.execute()
    data = response["items"][0]

    channel_data = {
        "channelName": data["snippet"]["title"],
        "subscribers": int(data["statistics"]["subscriberCount"]),
        "views": int(data["statistics"]["viewCount"]),
        "totalVideos": int(data["statistics"]["videoCount"]),
        "playlistId": data["contentDetails"]["relatedPlaylists"]["uploads"]
    }
    return channel_data


def get_video_details(api_key, playlist_id):
    youtube = build("youtube", "v3", developerKey=api_key)
    videos = []
    next_page_token = None

    while True:
        pl_request = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page_token
        )
        pl_response = pl_request.execute()

        video_ids = [item["contentDetails"]["videoId"] for item in pl_response["items"]]

        vid_request = youtube.videos().list(
            part="snippet,statistics",
            id=",".join(video_ids)
        )
        vid_response = vid_request.execute()

        for item in vid_response["items"]:
            videos.append({
                "title": item["snippet"]["title"],
                "publishedAt": item["snippet"]["publishedAt"],
                "views": int(item["statistics"].get("viewCount", 0)),
                "likes": int(item["statistics"].get("likeCount", 0)),
                "comments": int(item["statistics"].get("commentCount", 0)),
            })

        next_page_token = pl_response.get("nextPageToken")
        if not next_page_token:
            break

    return pd.DataFrame(videos)


# ---------------------------
# STREAMLIT APP
# ---------------------------

st.set_page_config(
    page_title="YouTube Analytics Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title("📊 YouTube Analytics Dashboard")
st.write("Interactive dashboard to analyze a YouTube channel's performance.")

# Get data
channel_data = get_channel_stats(API_KEY, CHANNEL_ID)
st.sidebar.header("Channel Info")
st.sidebar.write(f"**Channel:** {channel_data['channelName']}")
st.sidebar.write(f"**Subscribers:** {channel_data['subscribers']:,}")
st.sidebar.write(f"**Total Views:** {channel_data['views']:,}")
st.sidebar.write(f"**Videos:** {channel_data['totalVideos']:,}")

df = get_video_details(API_KEY, channel_data["playlistId"])
df["publishedAt"] = pd.to_datetime(df["publishedAt"], errors="coerce")

# ---------------------------
# FILTER
# ---------------------------
st.sidebar.header("Filters")
date_range = st.sidebar.date_input("Select Date Range:", [])
if len(date_range) == 2:
    df_filtered = df[
        (df["publishedAt"] >= pd.to_datetime(date_range[0])) &
        (df["publishedAt"] <= pd.to_datetime(date_range[1]))
    ]
else:
    df_filtered = df.copy()

# ---------------------------
# TABS
# ---------------------------
tab1, tab2, tab3 = st.tabs(["Overview", "Top Videos", "Trends"])

# ---- OVERVIEW ----
with tab1:
    st.subheader("📌 Overview Metrics")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Views", f"{df_filtered['views'].sum():,}")
    col2.metric("Total Likes", f"{df_filtered['likes'].sum():,}")
    col3.metric("Total Comments", f"{df_filtered['comments'].sum():,}")

# ---- TOP VIDEOS ----
with tab2:
    st.subheader("🔥 Top 10 Videos by Views")
    top_videos = df_filtered.sort_values("views", ascending=False).head(10)

    fig = px.bar(
        top_videos,
        x="views",
        y="title",
        orientation="h",
        title="Top 10 Videos by Views",
        text="views",
        color="views",
        color_continuous_scale="viridis"
    )
    fig.update_layout(yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, use_container_width=True)

# ---- TRENDS ----
with tab3:
    st.subheader("📈 Growth Trends Over Time")

    # Ensure publishedAt is datetime
    df_filtered["publishedAt"] = pd.to_datetime(df_filtered["publishedAt"], errors="coerce")

    # Explicitly pick numeric columns
    numeric_cols = ["views", "likes", "comments"]

    # Convert them to numeric safely
    for col in numeric_cols:
        df_filtered[col] = pd.to_numeric(df_filtered[col], errors="coerce")

    # Group by month and sum numeric only
    df_trend = (
        df_filtered
        .groupby(df_filtered["publishedAt"].dt.to_period("M"))[numeric_cols]
        .sum(min_count=1)
    )
    df_trend.index = df_trend.index.to_timestamp()

    # Dropdown to choose metric
    metric = st.selectbox("Choose metric to visualize:", numeric_cols, index=0)

    fig_line = px.line(
        df_trend,
        x=df_trend.index,
        y=metric,
        markers=True,
        title=f"{metric.title()} Over Time",
        color_discrete_sequence=["#FF4B4B"]
    )
    st.plotly_chart(fig_line, use_container_width=True)
