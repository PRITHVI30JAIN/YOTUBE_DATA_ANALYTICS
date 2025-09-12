# youtube_analytics_streamlit.py
import streamlit as st
import pandas as pd
import plotly.express as px
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import traceback

# Visible marker so you can confirm the updated file is actually running
st.set_page_config(page_title="YouTube Analytics Dashboard", page_icon="📊", layout="wide")
st.warning("🚀 NEW VERSION LOADED — REPLACE COMPLETE FILE, COMMIT & RERUN (clear cache)")

# ---------------------------
# CONFIG (paste your key / channel here)
# ---------------------------
API_KEY = "AIzaSyCxjHXpZKCFFTrhtPg_MELMd7ajnGb2yeA"   # <- YOUR API KEY (you provided this)
CHANNEL_ID = "UCX6OQ3DkcsbYNE6H8uQQuVA"               # <- MrBeast channel ID

# ---------------------------
# UTIL / API FUNCTIONS
# ---------------------------

def safe_build_youtube(api_key):
    try:
        return build("youtube", "v3", developerKey=api_key)
    except Exception as e:
        st.error("Could not initialize YouTube API client.")
        st.error(str(e))
        raise

def get_channel_stats(api_key, channel_id):
    youtube = safe_build_youtube(api_key)
    try:
        req = youtube.channels().list(part="snippet,contentDetails,statistics", id=channel_id)
        res = req.execute()
        if not res.get("items"):
            raise ValueError("Channel not found or no items returned.")
        item = res["items"][0]
        return {
            "channelName": item["snippet"].get("title", "Unknown"),
            "subscribers": int(item["statistics"].get("subscriberCount", 0)),
            "views": int(item["statistics"].get("viewCount", 0)),
            "totalVideos": int(item["statistics"].get("videoCount", 0)),
            "playlistId": item["contentDetails"]["relatedPlaylists"]["uploads"]
        }
    except HttpError as he:
        st.error("YouTube API returned an HTTP error. Check API key / quota.")
        st.error(str(he))
        raise
    except Exception as e:
        st.error("Failed to fetch channel stats.")
        st.error(str(e))
        raise

def get_video_details(api_key, playlist_id, max_fetch_per_call=50, max_videos=None):
    youtube = safe_build_youtube(api_key)
    videos = []
    token = None
    fetched = 0
    try:
        while True:
            # Respect max_videos if provided
            to_fetch = max_fetch_per_call
            if max_videos is not None:
                remaining = max_videos - fetched
                if remaining <= 0:
                    break
                to_fetch = min(to_fetch, remaining)

            req = youtube.playlistItems().list(
                part="contentDetails",
                playlistId=playlist_id,
                maxResults=to_fetch,
                pageToken=token
            )
            res = req.execute()
            ids = [i["contentDetails"]["videoId"] for i in res.get("items", [])]
            if not ids:
                break

            # batch video details
            vid_req = youtube.videos().list(part="snippet,statistics", id=",".join(ids))
            vid_res = vid_req.execute()
            for it in vid_res.get("items", []):
                snip = it.get("snippet", {})
                stts = it.get("statistics", {})
                videos.append({
                    "title": snip.get("title", ""),
                    "publishedAt": snip.get("publishedAt", None),
                    "views": int(stts.get("viewCount", 0)) if stts.get("viewCount") else 0,
                    "likes": int(stts.get("likeCount", 0)) if stts.get("likeCount") else 0,
                    "comments": int(stts.get("commentCount", 0)) if stts.get("commentCount") else 0
                })
                fetched += 1

            token = res.get("nextPageToken")
            if not token:
                break
    except HttpError as he:
        st.error("YouTube API error while fetching videos (quota or invalid request).")
        st.error(str(he))
        # proceed with whatever we have
    except Exception as e:
        st.error("Unexpected error fetching videos.")
        st.error(str(e))
        st.error(traceback.format_exc())

    return pd.DataFrame(videos)

# ---------------------------
# APP UI
# ---------------------------
st.title("📊 YouTube Analytics Dashboard")
st.write("Interactive dashboard using YouTube Data API v3. (If the app errors, check Logs in Streamlit Cloud.)")

# Fetch channel metadata and video data with spinner + safe error handling
try:
    with st.spinner("Fetching channel details..."):
        channel_info = get_channel_stats(API_KEY, CHANNEL_ID)
except Exception as e:
    st.error("Cannot fetch channel information. Check API key and Channel ID.")
    st.stop()

st.sidebar.header("Channel Info")
st.sidebar.write(f"**Channel:** {channel_info['channelName']}")
st.sidebar.write(f"**Subscribers:** {channel_info['subscribers']:,}")
st.sidebar.write(f"**Total Views:** {channel_info['views']:,}")
st.sidebar.write(f"**Videos (count):** {channel_info['totalVideos']:,}")

# Fetch video list
with st.spinner("Fetching video details (may take a few seconds)..."):
    df = get_video_details(API_KEY, channel_info["playlistId"], max_videos=200)

# Defensive: ensure DataFrame has expected columns
expected_cols = ["title", "publishedAt", "views", "likes", "comments"]
for c in expected_cols:
    if c not in df.columns:
        df[c] = pd.NA

# Convert types safely
df["publishedAt"] = pd.to_datetime(df["publishedAt"], errors="coerce")
for col in ["views", "likes", "comments"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# If no data, show friendly message
if df.empty:
    st.info("No video data available for this channel (maybe it's private or empty).")
    st.stop()

# ---------------------------
# Sidebar Filters
# ---------------------------
st.sidebar.header("Filters")
min_date = df["publishedAt"].min().date() if not df["publishedAt"].isna().all() else None
max_date = df["publishedAt"].max().date() if not df["publishedAt"].isna().all() else None

if min_date and max_date:
    date_range = st.sidebar.date_input("Select Date Range:", value=[min_date, max_date])
else:
    date_range = []

top_n = st.sidebar.slider("Top N videos (for Top Videos tab)", min_value=3, max_value=50, value=10, step=1)
metric = st.sidebar.selectbox("Metric for Top Videos", ["views", "likes", "comments"])

# Apply date filter safely
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start, end = date_range
    # convert to timestamps for comparison
    start_ts = pd.to_datetime(start)
    end_ts = pd.to_datetime(end)
    df_filtered = df[(df["publishedAt"] >= start_ts) & (df["publishedAt"] <= end_ts)].copy()
else:
    df_filtered = df.copy()

# Avoid accidental datetime columns in later aggregations
for col in ["views", "likes", "comments"]:
    df_filtered[col] = pd.to_numeric(df_filtered[col], errors="coerce").fillna(0).astype(int)

# ---------------------------
# Tabs
# ---------------------------
tab1, tab2, tab3 = st.tabs(["Overview", "Top Videos", "Trends"])

# OVERVIEW
with tab1:
    st.subheader("Overview Metrics")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Views", f"{df_filtered['views'].sum():,}")
    col2.metric("Total Likes", f"{df_filtered['likes'].sum():,}")
    col3.metric("Total Comments", f"{df_filtered['comments'].sum():,}")

    st.markdown("**Sample of fetched videos**")
    st.dataframe(df_filtered[["title", "publishedAt", "views", "likes", "comments"]].head(20))

# TOP VIDEOS
with tab2:
    st.subheader(f"Top {top_n} Videos by {metric.title()}")
    # If there are no numeric values, avoid crash
    if df_filtered[metric].isna().all():
        st.info(f"No {metric} data to display.")
    else:
        top_videos = df_filtered.sort_values(metric, ascending=False).head(top_n)
        if top_videos.empty:
            st.info("No videos available for selected filters.")
        else:
            fig = px.bar(
                top_videos,
                x=metric,
                y="title",
                orientation="h",
                text=metric,
                title=f"Top {top_n} videos by {metric}",
                color=metric,
                color_continuous_scale="Viridis"
            )
            fig.update_layout(yaxis=dict(autorange="reversed"), height=600)
            st.plotly_chart(fig, use_container_width=True)

# TRENDS (bullet-proof grouping by 'year-month' string)
with tab3:
    st.subheader("Trends Over Time (monthly)")

    try:
        # create a year-month string column (safe, no datetime aggregation)
        df_trend_source = df_filtered.copy()
        df_trend_source["year_month"] = df_trend_source["publishedAt"].dt.strftime("%Y-%m")
        # If every publishedAt is NaT, inform user
        if df_trend_source["year_month"].isna().all():
            st.info("No publish dates available to build trends.")
        else:
            # Group by year_month and aggregate only numeric columns
            grouped = df_trend_source.groupby("year_month")[["views", "likes", "comments"]].sum(min_count=1)
            # Convert the index (YYYY-MM) to a proper datetime for plotting x-axis
            grouped = grouped.reset_index()
            grouped["ts"] = pd.to_datetime(grouped["year_month"] + "-01", format="%Y-%m-%d", errors="coerce")
            grouped = grouped.sort_values("ts")

            # choose metric to display (reuse sidebar metric or let user pick)
            trend_metric = st.selectbox("Choose metric to plot", ["views", "likes", "comments"], index=0)
            if grouped.empty or grouped[trend_metric].isna().all():
                st.info("No numeric trend data to plot for the selected filters.")
            else:
                fig_line = px.line(grouped, x="ts", y=trend_metric, markers=True, title=f"{trend_metric.title()} by Month")
                fig_line.update_layout(xaxis_title="Month", yaxis_title=trend_metric.title(), height=500)
                st.plotly_chart(fig_line, use_container_width=True)
    except Exception as e:
        st.error("Error while building trends. Showing debug info in logs.")
        st.error(str(e))
        st.text(traceback.format_exc())

# ---------------------------
# Download filtered data
# ---------------------------
st.sidebar.download_button(
    "Download filtered data (CSV)",
    data=df_filtered.to_csv(index=False).encode("utf-8"),
    file_name="youtube_data_filtered.csv",
    mime="text/csv"
)
