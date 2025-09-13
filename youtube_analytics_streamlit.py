# youtube_analytics_streamlit.py
import streamlit as st
import pandas as pd
import plotly.express as px
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import traceback
from datetime import date as datecls

st.set_page_config(page_title="YouTube Analytics Dashboard", page_icon="📊", layout="wide")
st.warning("🚀 NEW VERSION LOADED — DATE FILTER BUGFIX")

# ---------------------------
# CONFIG (replace key if you want private use)
# ---------------------------
API_KEY = "AIzaSyCxjHXpZKCFFTrhtPg_MELMd7ajnGb2yeA"
CHANNEL_ID = "UCX6OQ3DkcsbYNE6H8uQQuVA"

# ---------------------------
# HELPERS
# ---------------------------
def build_youtube(api_key):
    return build("youtube", "v3", developerKey=api_key)

def get_channel_stats(api_key, channel_id):
    youtube = build_youtube(api_key)
    req = youtube.channels().list(part="snippet,contentDetails,statistics", id=channel_id)
    res = req.execute()
    if not res.get("items"):
        raise ValueError("Channel not found or API returned no items.")
    it = res["items"][0]
    return {
        "channelName": it["snippet"].get("title", "Unknown"),
        "subscribers": int(it["statistics"].get("subscriberCount", 0)),
        "views": int(it["statistics"].get("viewCount", 0)),
        "totalVideos": int(it["statistics"].get("videoCount", 0)),
        "playlistId": it["contentDetails"]["relatedPlaylists"]["uploads"]
    }

def get_video_details(api_key, playlist_id, max_videos=200):
    youtube = build_youtube(api_key)
    videos = []
    token = None
    fetched = 0
    while True:
        to_fetch = 50
        if max_videos is not None:
            to_fetch = min(to_fetch, max_videos - fetched)
            if to_fetch <= 0:
                break
        req = youtube.playlistItems().list(part="contentDetails", playlistId=playlist_id,
                                           maxResults=to_fetch, pageToken=token)
        res = req.execute()
        ids = [i["contentDetails"]["videoId"] for i in res.get("items", []) if i.get("contentDetails")]
        if not ids:
            break
        vid_req = youtube.videos().list(part="snippet,statistics", id=",".join(ids))
        vid_res = vid_req.execute()
        for v in vid_res.get("items", []):
            sn = v.get("snippet", {})
            stts = v.get("statistics", {})
            videos.append({
                "title": sn.get("title", ""),
                "publishedAt": sn.get("publishedAt", None),
                "views": int(stts.get("viewCount", 0)) if stts.get("viewCount") else 0,
                "likes": int(stts.get("likeCount", 0)) if stts.get("likeCount") else 0,
                "comments": int(stts.get("commentCount", 0)) if stts.get("commentCount") else 0,
            })
            fetched += 1
        token = res.get("nextPageToken")
        if not token:
            break
    return pd.DataFrame(videos)

# ---------------------------
# APP START
# ---------------------------
st.title("📊 YouTube Analytics Dashboard")
st.write("Robust date filter / debug mode included. If anything errors, the app will show a clear message and stack trace.")

# Fetch channel and videos
try:
    with st.spinner("Fetching channel info..."):
        channel_info = get_channel_stats(API_KEY, CHANNEL_ID)
except Exception as e:
    st.error("Failed to fetch channel info. See details below.")
    st.error(str(e))
    st.stop()

st.sidebar.header("Channel Info")
st.sidebar.write(f"**Channel:** {channel_info['channelName']}")
st.sidebar.write(f"**Subscribers:** {channel_info['subscribers']:,}")
st.sidebar.write(f"**Total Views:** {channel_info['views']:,}")
st.sidebar.write(f"**Videos:** {channel_info['totalVideos']:,}")

with st.spinner("Fetching video details..."):
    df = get_video_details(API_KEY, channel_info["playlistId"], max_videos=500)

# Ensure columns exist
for col in ["title", "publishedAt", "views", "likes", "comments"]:
    if col not in df.columns:
        df[col] = pd.NA

# Convert types
df["publishedAt"] = pd.to_datetime(df["publishedAt"], errors="coerce")
for c in ["views", "likes", "comments"]:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

# Debug toggle
debug = st.sidebar.checkbox("Show debug info (types & date_range)", value=False)

# Determine min/max dates available
has_dates = df["publishedAt"].notna().any()
min_date = df["publishedAt"].min().date() if has_dates else None
max_date = df["publishedAt"].max().date() if has_dates else None

# Date input with safe defaults
st.sidebar.header("Filters")
if min_date and max_date:
    date_input_value = st.sidebar.date_input("Select Date Range (pick one or two dates):", value=[min_date, max_date])
else:
    date_input_value = st.sidebar.date_input("Select Date Range (no publish dates available):")

# Top N and metric
top_n = st.sidebar.slider("Top N videos", 3, 50, 10)
metric = st.sidebar.selectbox("Metric for Top Videos", ["views", "likes", "comments"])

# SAFE parsing of date_input_value into start_ts, end_ts
start_ts = None
end_ts = None
try:
    # Case: user selected a list/tuple (range) from the widget
    if isinstance(date_input_value, (list, tuple)):
        if len(date_input_value) == 2:
            start, end = date_input_value
        elif len(date_input_value) == 1:
            start = end = date_input_value[0]
        else:
            start = min_date
            end = max_date
    else:
        # Single date (could be a datetime.date or pandas Timestamp)
        start = end = date_input_value

    # If any are None (or still not set), fallback to full range
    if start is None or (isinstance(start, float) and pd.isna(start)):
        start = min_date
    if end is None or (isinstance(end, float) and pd.isna(end)):
        end = max_date

    if start is not None:
        # convert date -> timestamp at start of day
        start_ts = pd.to_datetime(start).normalize()
    if end is not None:
        # include full day for end_ts (set to 23:59:59)
        end_ts = pd.to_datetime(end).normalize() + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

except Exception as e:
    st.error("Error parsing the date input. Falling back to full dataset.")
    st.error(str(e))
    st.text(traceback.format_exc())
    start_ts = None
    end_ts = None

if debug:
    st.write("DEBUG: date_input_value:", date_input_value)
    st.write("DEBUG: min_date, max_date:", min_date, max_date)
    st.write("DEBUG: start_ts, end_ts:", start_ts, end_ts)
    st.write("DEBUG: publishedAt dtype:", df["publishedAt"].dtype)
    st.write("DEBUG: sample publishedAt values:", df["publishedAt"].head().tolist())

# Apply filter safely
try:
    if start_ts is not None and end_ts is not None:
        df_filtered = df[(df["publishedAt"] >= start_ts) & (df["publishedAt"] <= end_ts)].copy()
    else:
        df_filtered = df.copy()
except Exception as e:
    st.error("Unexpected error while applying the date filter.")
    st.error(str(e))
    st.text(traceback.format_exc())
    # fallback
    df_filtered = df.copy()

# If empty after filtering, show message
if df_filtered.empty:
    st.info("No videos match the selected filter. Try widening the date range or disable the filter.")
    # still continue to show empty tables/charts (or stop)
    # st.stop()

# ---------- UI Tabs ----------
tab1, tab2, tab3 = st.tabs(["Overview", "Top Videos", "Trends"])

with tab1:
    st.subheader("Overview")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Views", f"{df_filtered['views'].sum():,}")
    c2.metric("Total Likes", f"{df_filtered['likes'].sum():,}")
    c3.metric("Total Comments", f"{df_filtered['comments'].sum():,}")
    st.markdown("### Sample videos")
    st.dataframe(df_filtered[["title", "publishedAt", "views", "likes", "comments"]].head(20))

with tab2:
    st.subheader(f"Top {top_n} videos by {metric}")
    if df_filtered[metric].isna().all():
        st.info(f"No {metric} data available for the selected filter.")
    else:
        top = df_filtered.sort_values(metric, ascending=False).head(top_n)
        fig = px.bar(top, x=metric, y="title", orientation="h", text=metric, color=metric, color_continuous_scale="viridis")
        fig.update_layout(yaxis=dict(autorange="reversed"), height=600)
        st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("Trends (monthly)")
    # Build year-month string to avoid summing datetimes
    df_trend_source = df_filtered.copy()
    df_trend_source["year_month"] = df_trend_source["publishedAt"].dt.strftime("%Y-%m")
    if df_trend_source["year_month"].isna().all():
        st.info("No publish dates available to build a trends chart.")
    else:
        grouped = df_trend_source.groupby("year_month")[["views", "likes", "comments"]].sum(min_count=1).reset_index()
        grouped["ts"] = pd.to_datetime(grouped["year_month"] + "-01", format="%Y-%m-%d", errors="coerce")
        grouped = grouped.sort_values("ts")
        trend_metric = st.selectbox("Metric to plot", ["views", "likes", "comments"], index=0, key="trend_metric")
        if grouped.empty or grouped[trend_metric].isna().all():
            st.info("No numeric trend data for selected filters.")
        else:
            fig2 = px.line(grouped, x="ts", y=trend_metric, markers=True, title=f"{trend_metric.title()} by month")
            fig2.update_layout(xaxis_title="Month", yaxis_title=trend_metric.title(), height=450)
            st.plotly_chart(fig2, use_container_width=True)

# Download
st.sidebar.download_button("Download filtered CSV", df_filtered.to_csv(index=False).encode("utf-8"), "youtube_filtered.csv", "text/csv")
