# youtube_analytics_app.py — Enhanced version with clickable video links and stats

from googleapiclient.discovery import build
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
import numpy as np
import os, tempfile, re, subprocess

# Import configuration
try:
    from config import (
        YOUTUBE_API_KEY,
        DEFAULT_CHANNEL,
        DEFAULT_MAX_RESULTS,
        DEFAULT_ORDER,
        OLLAMA_BASE_URL,
        OLLAMA_MODEL,
        SHORT_MAX_DURATION,
        LONG_MIN_DURATION,
        RIVAL_CHANNELS,
        validate_config,
        get_config_summary
    )
    CONFIG_LOADED = True
except ImportError:
    CONFIG_LOADED = False
    # Fallback defaults
    YOUTUBE_API_KEY = ""
    DEFAULT_CHANNEL = "The Uranium Hunter"
    DEFAULT_MAX_RESULTS = 50
    DEFAULT_ORDER = "date"
    OLLAMA_BASE_URL = "http://localhost:11434"
    OLLAMA_MODEL = "gpt-oss:20b"
    SHORT_MAX_DURATION = 60
    LONG_MIN_DURATION = 1800
    RIVAL_CHANNELS = []

# LangChain components
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

try:
    from langchain_community.llms import Ollama
    OLLAMA_IMPORTED = True
except Exception:
    OLLAMA_IMPORTED = False


# ==================== Streamlit Setup ====================
st.set_page_config(page_title="YouTube Channel AI Dashboard", layout="wide")
st.title("📊 YouTube Channel Analytics + Smart Search (Free)")
st.markdown("Keyword-aware semantic search with optional offline summarization via Ollama Mistral.")


# ==================== Session State ====================
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame()
if "vectordb" not in st.session_state:
    st.session_state.vectordb = None


# ==================== Utility Functions ====================
def ollama_available() -> bool:
    if not OLLAMA_IMPORTED:
        return False
    try:
        subprocess.run(["ollama", "list"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        return False


def parse_duration_to_seconds(duration_iso: str) -> int:
    """
    Parse ISO 8601 duration string to total seconds.
    Examples: "PT1H30M15S" -> 5415, "PT5M30S" -> 330, "PT60S" -> 60
    """
    if not duration_iso or not duration_iso.startswith("PT"):
        return 0

    # Remove PT prefix
    duration = duration_iso[2:]
    total_seconds = 0

    # Parse hours
    if "H" in duration:
        hours_part = duration.split("H")[0]
        total_seconds += int(hours_part) * 3600
        duration = duration.split("H")[1] if "H" in duration else ""

    # Parse minutes
    if "M" in duration:
        minutes_part = duration.split("M")[0]
        total_seconds += int(minutes_part) * 60
        duration = duration.split("M")[1] if "M" in duration else ""

    # Parse seconds
    if "S" in duration:
        seconds_part = duration.split("S")[0]
        total_seconds += int(seconds_part)

    return total_seconds


def classify_content_type(duration_seconds: int, live_status: str = None) -> str:
    """
    Classify video content type based on duration and live status.
    Uses thresholds from config.py (SHORT_MAX_DURATION, LONG_MIN_DURATION).
    """
    # Check for live streams first (both 'live' and 'upcoming' are live streams)
    if live_status and live_status in ["live", "upcoming"]:
        return "Live"

    # Classify based on duration
    if duration_seconds <= SHORT_MAX_DURATION:
        return "Short"
    elif duration_seconds > LONG_MIN_DURATION:  # Use > not >= for exclusive threshold
        return "Long-form"
    else:
        return "Regular"


def get_channel_videos_df(api_key: str, channel_name: str, max_results: int = 50, order: str = "date") -> pd.DataFrame:
    youtube = build("youtube", "v3", developerKey=api_key)
    ch_resp = youtube.search().list(part="snippet", q=channel_name, type="channel", maxResults=1).execute()
    if not ch_resp.get("items"):
        st.error(f"No channel found for '{channel_name}'.")
        return pd.DataFrame()

    channel_id = ch_resp["items"][0]["id"]["channelId"]
    v_resp = youtube.search().list(part="snippet", channelId=channel_id, type="video", order=order, maxResults=max_results).execute()
    video_ids = [i["id"]["videoId"] for i in v_resp.get("items", [])]

    if not video_ids:
        return pd.DataFrame()

    s_resp = youtube.videos().list(part="snippet,statistics,contentDetails", id=",".join(video_ids)).execute()
    data = []
    for item in s_resp.get("items", []):
        sn = item["snippet"]
        stt = item.get("statistics", {})
        det = item.get("contentDetails", {})

        # Parse duration and classify content type
        duration_iso = det.get("duration", "")
        duration_seconds = parse_duration_to_seconds(duration_iso)
        live_status = sn.get("liveBroadcastContent", "none")
        content_type = classify_content_type(duration_seconds, live_status)

        # Calculate engagement rates
        views = int(stt.get("viewCount", 0))
        likes = int(stt.get("likeCount", 0))
        comments = int(stt.get("commentCount", 0))

        engagement_rate = (likes / views * 100) if views > 0 else 0
        comment_rate = (comments / views * 100) if views > 0 else 0

        data.append({
            "Title": sn.get("title"),
            "Published": pd.to_datetime(sn.get("publishedAt")),
            "Description": sn.get("description", ""),
            "Video_ID": item["id"],
            "URL": f"https://www.youtube.com/watch?v={item['id']}",
            "Duration": duration_iso,
            "Duration_Seconds": duration_seconds,
            "Content_Type": content_type,
            "Live_Status": live_status,
            "Views": views,
            "Likes": likes,
            "Comments": comments,
            "Engagement_Rate": round(engagement_rate, 2),
            "Comment_Rate": round(comment_rate, 2),
            "Thumbnail": sn.get("thumbnails", {}).get("high", {}).get("url", "")
        })
    return pd.DataFrame(data)


def plot_trend_over_time(df, metric="Views"):
    if df.empty:
        return
    df2 = df.sort_values("Published")
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df2["Published"], df2[metric], marker="o", linewidth=2, color="tab:blue")
    ax.set_title(f"{metric} Trend Over Time", fontsize=14, weight="bold")
    ax.set_xlabel("Published Date")
    ax.set_ylabel(metric)
    ax.grid(alpha=0.5)
    plt.xticks(rotation=30)
    st.pyplot(fig)


def plot_top_videos(df, metric="Views", top_n=10):
    if df.empty:
        return
    df2 = df.sort_values(metric, ascending=False).head(top_n)
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(df2["Title"], df2[metric], color="skyblue", edgecolor="black")
    ax.set_title(f"Top {top_n} Videos by {metric}", fontsize=14, weight="bold")
    ax.set_xlabel(metric)
    ax.set_ylabel("Video Title")
    ax.invert_yaxis()
    for bar in bars:
        ax.text(bar.get_width(), bar.get_y() + bar.get_height()/2, f"{int(bar.get_width()):,}", va="center")
    plt.tight_layout()
    st.pyplot(fig)


def plot_content_type_distribution(df):
    """Plot pie chart showing distribution of content types."""
    if df.empty or "Content_Type" not in df.columns:
        return

    content_counts = df["Content_Type"].value_counts()
    if content_counts.empty:
        return

    fig, ax = plt.subplots(figsize=(8, 8))
    colors = plt.cm.Set3(np.linspace(0, 1, len(content_counts)))
    wedges, texts, autotexts = ax.pie(
        content_counts.values,
        labels=content_counts.index,
        autopct='%1.1f%%',
        colors=colors,
        startangle=90
    )
    ax.set_title("Content Type Distribution", fontsize=14, weight="bold")
    plt.setp(autotexts, size=10, weight="bold")
    plt.setp(texts, size=11)
    st.pyplot(fig)


def plot_content_type_performance(df, metric="Views"):
    """Plot bar chart comparing performance metrics by content type."""
    if df.empty or "Content_Type" not in df.columns or metric not in df.columns:
        return

    # Calculate average metric by content type
    performance = df.groupby("Content_Type")[metric].mean().sort_values(ascending=False)

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(performance.index, performance.values, color="lightcoral", edgecolor="black")
    ax.set_title(f"Average {metric} by Content Type", fontsize=14, weight="bold")
    ax.set_xlabel("Content Type")
    ax.set_ylabel(f"Average {metric}")
    ax.grid(axis='y', alpha=0.3)

    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.01 * max(performance.values),
                f"{int(height):,}" if metric in ["Views", "Likes", "Comments"] else f"{height:.2f}",
                ha='center', va='bottom')

    plt.xticks(rotation=45)
    plt.tight_layout()
    st.pyplot(fig)


def plot_content_type_trends(df, metric="Views"):
    """Plot trend of metric over time by content type."""
    if df.empty or "Content_Type" not in df.columns or metric not in df.columns:
        return

    fig, ax = plt.subplots(figsize=(12, 6))

    # Plot each content type separately
    for content_type in df["Content_Type"].unique():
        type_data = df[df["Content_Type"] == content_type].sort_values("Published")
        if not type_data.empty:
            ax.plot(type_data["Published"], type_data[metric], marker="o", linewidth=2,
                   label=content_type, markersize=6)

    ax.set_title(f"{metric} Trend by Content Type", fontsize=14, weight="bold")
    ax.set_xlabel("Published Date")
    ax.set_ylabel(metric)
    ax.legend(title="Content Type")
    ax.grid(alpha=0.3)
    plt.xticks(rotation=30)
    plt.tight_layout()
    st.pyplot(fig)


def plot_duration_distribution(df):
    """Plot histogram of video durations."""
    if df.empty or "Duration_Seconds" not in df.columns:
        return

    fig, ax = plt.subplots(figsize=(10, 6))

    # Create bins for duration
    durations = df["Duration_Seconds"]
    max_duration = min(durations.max(), 7200)  # Cap at 2 hours for visualization

    # Create histogram
    ax.hist(durations, bins=30, range=(0, max_duration), edgecolor='black', alpha=0.7)
    ax.set_title("Video Duration Distribution", fontsize=14, weight="bold")
    ax.set_xlabel("Duration (seconds)")
    ax.set_ylabel("Number of Videos")
    ax.grid(alpha=0.3)

    # Add vertical lines for classification thresholds
    ax.axvline(x=SHORT_MAX_DURATION, color='red', linestyle='--', alpha=0.7,
              label=f'Shorts threshold ({SHORT_MAX_DURATION}s)')
    ax.axvline(x=LONG_MIN_DURATION, color='blue', linestyle='--', alpha=0.7,
              label=f'Long-form threshold ({LONG_MIN_DURATION}s)')

    ax.legend()
    plt.tight_layout()
    st.pyplot(fig)


STOP = set("a an and are as at be but by for from has have i in is it its of on or that the this to was were will with you your we our".split())
def extract_keywords(q):
    phrases = re.findall(r'"([^"]+)"', q)
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z\-']+", q) if len(w) > 3 and w.lower() not in STOP]
    return list(set([w.lower() for w in words + phrases]))


def keyword_filter_indices(df, keywords):
    if df.empty or not keywords:
        return []
    mask = False
    for kw in keywords:
        m = df["Title"].str.contains(kw, case=False, na=False) | df["Description"].str.contains(kw, case=False, na=False)
        mask = m if isinstance(mask, bool) and not mask else (mask | m)
    return df[mask].index.astype(int).tolist()


def build_vector_db(df):
    if df.empty:
        return None
    docs, metas = [], []
    for i, r in df.reset_index(drop=True).iterrows():
        text = (
            f"Title: {r['Title']}\n"
            f"Description: {r['Description']}\n"
            f"Views: {r['Views']} Likes: {r['Likes']} Comments: {r['Comments']}"
        )
        docs.append(text)
        metas.append({"row": int(i), "title": r["Title"], "views": int(r["Views"]), "url": r["URL"]})
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectordb = Chroma.from_texts(docs, embedding=embeddings, metadatas=metas)
    return vectordb


def summarize_with_ollama(question, hits):
    context = "\n\n".join([f"Title: {t}\nSnippet: {s}" for t, s, _ in hits])
    prompt = (
        f"You are an assistant summarizing YouTube videos.\n\n"
        f"Question: {question}\n\n"
        f"Relevant videos:\n{context}\n\n"
        "Summarize and list the most relevant videos with bullet points and short explanations."
    )
    llm = Ollama(model="mistral", temperature=0.2)
    return llm(prompt)


def chat_with_channel(df, vectordb, question, use_kw=True, use_sum=True):
    if vectordb is None or df.empty:
        return "Please fetch data and build knowledge base first."

    kw = extract_keywords(question) if use_kw else []
    idx = keyword_filter_indices(df, kw) if kw else []
    filt = {"row": {"$in": idx}} if idx else None

    docs = vectordb.similarity_search(question, k=5, filter=filt)
    if not docs:
        return "No relevant results found."

    hits = []
    for d in docs:
        title = d.metadata["title"]
        snippet = d.page_content[:300].replace("\n", " ").strip()
        url = d.metadata.get("url", "")
        hits.append((title, snippet, url))

    if use_sum and ollama_available():
        try:
            return summarize_with_ollama(question, hits)
        except Exception:
            pass

    # clickable results
    formatted = "🔍 **Top Related Videos:**\n\n"
    for t, s, u in hits:
        stats_row = df[df["URL"] == u]
        if not stats_row.empty:
            views = int(stats_row["Views"].iloc[0])
            likes = int(stats_row["Likes"].iloc[0])
            comments = int(stats_row["Comments"].iloc[0])
            formatted += f"🎥 **[{t}]({u})**  \n👁️ {views:,} views | 👍 {likes:,} likes | 💬 {comments:,} comments  \n{s}\n\n"
        else:
            formatted += f"🎥 **[{t}]({u})**  \n{s}\n\n"
    return formatted


# ==================== Sidebar Controls ====================
st.sidebar.header("Settings")

# Configuration status
if CONFIG_LOADED:
    config_status = "✅ Loaded"
    config_color = "green"
else:
    config_status = "⚠️ Using fallback defaults"
    config_color = "orange"

st.sidebar.markdown(f"**Config Status:** :{config_color}[{config_status}]")

# API Key input - show placeholder if config provides one
api_key_placeholder = YOUTUBE_API_KEY if YOUTUBE_API_KEY else ""
api_key = st.sidebar.text_input("YouTube API Key", value=api_key_placeholder, type="password")

# Show warning if no API key is configured
if not YOUTUBE_API_KEY:
    st.sidebar.warning("⚠️ No API key configured. Set YOUTUBE_API_KEY in .env file or enter it above.")

# Channel name input - use default from config
channel_name = st.sidebar.text_input("Channel Name", value=DEFAULT_CHANNEL)

# Other settings with config defaults
max_results = st.sidebar.slider("Number of Videos", 10, 100, DEFAULT_MAX_RESULTS)
order = st.sidebar.selectbox("Order By", ["date", "viewCount", "rating", "relevance"], index=["date", "viewCount", "rating", "relevance"].index(DEFAULT_ORDER) if DEFAULT_ORDER in ["date", "viewCount", "rating", "relevance"] else 0)

# Configuration management
with st.sidebar.expander("⚙️ Advanced Configuration"):
    st.markdown("### Configuration Summary")
    if CONFIG_LOADED:
        config_summary = get_config_summary()
        st.json(config_summary)

        if st.button("Validate Configuration"):
            if validate_config():
                st.success("Configuration is valid!")
            else:
                st.warning("Configuration has warnings (check console)")
    else:
        st.warning("Configuration file not loaded. Using fallback defaults.")

    st.markdown("### Environment Variables")
    st.code("""
# Set these in your environment or .env file:
YOUTUBE_API_KEY=your_api_key_here
DEFAULT_YOUTUBE_CHANNEL=your_channel_name
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gpt-oss:20b
DEFAULT_MAX_RESULTS=50
DEFAULT_ORDER=date
    """)

if st.sidebar.button("🚀 Fetch Channel Data"):
    if not api_key or not channel_name:
        st.warning("Please enter your YouTube API key and channel name.")
    else:
        with st.spinner("Fetching channel data..."):
            df = get_channel_videos_df(api_key, channel_name, max_results=max_results, order=order)
        if not df.empty:
            st.session_state.df = df
            st.success(f"Fetched {len(df)} videos from '{channel_name}'.")
        else:
            st.error("No data found.")


# ==================== Dashboard ====================
if not st.session_state.df.empty:
    df = st.session_state.df

    # Display dataframe with new columns
    st.markdown("### 📊 Video Data")
    display_columns = ["Title", "Published", "Content_Type", "Views", "Likes", "Comments", "Engagement_Rate", "Duration"]
    st.dataframe(df[display_columns])

    # Content Type Analytics Section
    st.markdown("### 🎬 Content Type Analytics")
    st.markdown(f"**Classification thresholds:** Shorts (< {SHORT_MAX_DURATION}s), Long-form (> {LONG_MIN_DURATION}s)")

    # Content Type Distribution
    st.markdown("#### Content Type Distribution")
    c1, c2 = st.columns(2)
    with c1:
        plot_content_type_distribution(df)
    with c2:
        plot_duration_distribution(df)

    # Content Type Performance
    st.markdown("#### Performance by Content Type")
    perf_metric = st.selectbox("Performance Metric", ["Views", "Likes", "Comments", "Engagement_Rate"], key="perf_metric")
    c3, c4 = st.columns(2)
    with c3:
        plot_content_type_performance(df, perf_metric)
    with c4:
        plot_content_type_trends(df, perf_metric)

    # Traditional Channel Visualizations
    st.markdown("### 📈 Channel Visualizations")
    metric = st.selectbox("Metric", ["Views", "Likes", "Comments"], key="main_metric")
    top_n = st.slider("Top N Videos", 5, 20, 10, key="top_n")
    c5, c6 = st.columns(2)
    with c5:
        plot_top_videos(df, metric, top_n)
    with c6:
        plot_trend_over_time(df, metric)

    st.markdown("### 🧠 Chat with the Channel (Offline)")
    use_kw = st.checkbox("Use Keyword/Entity Filter", True)
    use_sum = st.checkbox("Use Local Summarizer (Ollama)", True)
    st.write("Ollama Available:", "✅" if ollama_available() else "❌")

    if st.button("Build Channel Knowledge Base"):
        with st.spinner("Building local embeddings..."):
            vectordb = build_vector_db(df)
        if vectordb:
            st.session_state.vectordb = vectordb
            st.success("Knowledge base created successfully!")

    if st.session_state.vectordb:
        query = st.text_area("Ask about the channel:", "Videos related to Virat Kohli")
        if st.button("Ask"):
            with st.spinner("Searching and analyzing..."):
                answer = chat_with_channel(df, st.session_state.vectordb, query, use_kw, use_sum)
            st.markdown(answer)
