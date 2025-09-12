import streamlit as st
import pandas as pd
import plotly.express as px
from googleapiclient.discovery import build

# ========== CONFIG ==========
st.set_page_config(page_title="YouTube Analytics Dashboard", page_icon="📊", layout="wide")

# 🔑 Your API Key and MrBeast's Channel ID
API_KEY = "AIzaSyCxjHXpZKCFFTrhtPg_MELMd7ajnGb2yeA"
CHANNEL_ID = "UCX6OQ3DkcsbYNE6H8uQQuVA"  # MrBeast's official channel ID

# ========== YOUTUBE API ==========
def get_channel_stats(api_key, channel_id):
    youtube = build("youtube", "v3", developerKey=api_key)
    request = youtube.channels().list(
        part="snippet,contentDetails,statistics",
        id=channel_id
    )
    response = request.execute()
    return response

def get_video_stats(api_key, playlist_id, max_results=20):
    youtube = build("youtube", "v3", developerKey=api_key)
    videos = []
    next_page_token = None

    while True:
        request = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=playlist_id,
            maxResults=max_results,
            pageToken=next_page_token
        )
        response = request.execute()

        video_ids = [item["contentDetails"]["videoId"] for item in response["items"]]

        stats_request = youtube.videos().list(
            part="snippet,statistics",
            id=",".join(video_ids)
        )
        stats_response = stats_request.execute()

        for item in stats_response["items"]:
            videos.append({
                "title": item["snippet"]["title"],
                "publishedAt": item["snippet"]["publishedAt"],
                "views": int(item["statistics"].get("viewCount", 0)),
                "likes": int(item["statistics"].get("likeCount", 0)),
                "comments": int(item["statistics"].get("commentCount", 0))
            })

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return pd.DataFrame(videos)

# ========== FETCH DATA ==========
channel_data = get_channel_stats(API_KEY, CHANNEL_ID)
playlist_id = channel_data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
df = get_video_stats(API_KEY, playlist_id)

df["publishedAt"] = pd.to_datetime(df["publishedAt"])
df = df.sort_values("publishedAt")

# ========== SIDEBAR ==========
st.sidebar.header("⚙️ Filters")
metric = st.sidebar.selectbox("Choose Metric", ["views", "likes", "comments"])
top_n = st.sidebar.slider("Top N Videos", min_value=5, max_value=20, value=10)

# Sidebar date filter (fix applied ✅)
date_range = st.sidebar.date_input(
    "Date Range",
    value=[df["publishedAt"].min().date(), df["publishedAt"].max().date()]
)

# Ensure it's always a range (start, end)
if isinstance(date_range, tuple) or isinstance(date_range, list):
    start_date, end_date = date_range
else:
    start_date = end_date = date_range

# Filter dataframe
df_filtered = df[(df["publishedAt"].dt.date >= start_date) &
                 (df["publishedAt"].dt.date <= end_date)]

# ========== TABS ==========
tab1, tab2, tab3 = st.tabs(["📊 Overview", "🎥 Top Videos", "📈 Trends"])

# ---- OVERVIEW ----
with tab1:
    st.subheader("📊 Channel Overview")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("👀 Total Views", f"{df['views'].sum():,}")
    with col2:
        st.metric("👍 Total Likes", f"{df['likes'].sum():,}")
    with col3:
        st.metric("💬 Total Comments", f"{df['comments'].sum():,}")
    with col4:
        st.metric("🎥 Total Videos", f"{len(df):,}")

# ---- TOP VIDEOS ----
with tab2:
    st.subheader(f"🎥 Top {top_n} Videos by {metric.title()}")
    top_videos = df_filtered.sort_values(metric, ascending=False).head(top_n)

    fig_bar = px.bar(top_videos, x="title", y=metric, text=metric,
                     title=f"Top {top_n} Videos by {metric.title()}",
                     color=metric, color_continuous_scale="viridis")
    fig_bar.update_layout(xaxis_tickangle=-45, height=600)
    st.plotly_chart(fig_bar, use_container_width=True)

    fig_pie = px.pie(top_videos, values=metric, names="title",
                     title=f"Contribution of Top {top_n} Videos by {metric.title()}",
                     hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
    st.plotly_chart(fig_pie, use_container_width=True)

# ---- TRENDS ----
with tab3:
    st.subheader("📈 Growth Trends Over Time")

    # Group by month and aggregate only numeric columns ✅
    df_trend = df_filtered.groupby(df_filtered["publishedAt"].dt.to_period("M"))[
        ["views", "likes", "comments"]
    ].sum()
    df_trend.index = df_trend.index.to_timestamp()

    fig_line = px.line(
        df_trend,
        x=df_trend.index,
        y=metric,
        markers=True,
        title=f"{metric.title()} Over Time",
        color_discrete_sequence=["#FF4B4B"]
    )
    st.plotly_chart(fig_line, use_container_width=True)

# ========== EXPORT ==========
st.sidebar.download_button(
    "📥 Download Data as CSV",
    data=df_filtered.to_csv(index=False).encode("utf-8"),
    file_name="youtube_data.csv",
    mime="text/csv"
)
