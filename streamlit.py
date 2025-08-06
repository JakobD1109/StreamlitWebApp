import streamlit as st
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import timedelta
import os
import plotly.graph_objects as go

# Load environment variables
load_dotenv()
url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

st.set_page_config(page_title="Bitcoin Dashboard", layout="wide")

# Force no caching
if 'data_refresh' not in st.session_state:
    st.session_state.data_refresh = 0

if st.button("🔄 Refresh Data"):
    st.session_state.data_refresh += 1
    st.rerun()

st.title("Bitcoin Dashboard")
# --- Fetch Bitcoin value data ---
value_response = supabase.table("value").select("*").execute()
value_data = value_response.data

if value_data:
    df_value = pd.DataFrame(value_data)
    df_value["open_time"] = pd.to_datetime(df_value["open_time"], errors="coerce")
    df_value = df_value.sort_values("open_time")
    df_value["open_time"] = df_value["open_time"].dt.tz_localize(None)

    # --- Quick Stats Cards for Last Full Day ---
    st.subheader("")

    # Remove time from open_time for grouping
    df_value["date_only"] = df_value["open_time"].dt.date

    # Find the last full day (exclude today if today is not complete)
    all_days = df_value["date_only"].unique()
    all_days_sorted = sorted(all_days)
    today = pd.Timestamp.now().date()
    if all_days_sorted[-1] == today:
        last_full_day = all_days_sorted[-2] if len(all_days_sorted) > 1 else all_days_sorted[-1]
    else:
        last_full_day = all_days_sorted[-1]

    df_last_day = df_value[df_value["date_only"] == last_full_day]

    # Calculate stats for the last full day
    close_val = df_last_day.iloc[-1]["close"]
    high_val = df_last_day["high"].max()
    low_val = df_last_day["low"].min()
    volume_val = df_last_day["volume"].sum()

    def euro_style(val):
        return f"${val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    stats_html = f"""
    <div style='display: flex; gap: 60px; margin-bottom: 24px;'>
    <div style='text-align:center;'>
        <div style='font-size:18px; color:#666;'>Close</div>
        <div style='font-size:32px; font-weight:bold;'>{euro_style(close_val)}</div>
    </div>
    <div style='text-align:center;'>
        <div style='font-size:18px; color:#666;'>High</div>
        <div style='font-size:32px; font-weight:bold;'>{euro_style(high_val)}</div>
    </div>
    <div style='text-align:center;'>
        <div style='font-size:18px; color:#666;'>Low</div>
        <div style='font-size:32px; font-weight:bold;'>{euro_style(low_val)}</div>
    </div>
    <div style='text-align:center;'>
        <div style='font-size:18px; color:#666;'>Volume</div>
        <div style='font-size:32px; font-weight:bold;'>
        {volume_val:,.2f}&nbsp;<span style="font-size:20px; font-weight:normal;">BTC</span>
        </div>
    </div>
    </div>
    """

    st.markdown(stats_html, unsafe_allow_html=True)

    # --- Time range buttons ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        range_btn_1d = st.button("1d")
    with col2:
        range_btn_3d = st.button("3d")
    with col3:
        range_btn_7d = st.button("7d")
    with col4:
        range_btn_max = st.button("Max")

    now = pd.Timestamp.now().normalize()  # Make sure this is also naive
    time_filter = df_value["open_time"].min()
    if range_btn_1d:
        time_filter = now - pd.Timedelta(days=1)
    elif range_btn_3d:
        time_filter = now - pd.Timedelta(days=3)
    elif range_btn_7d:
        time_filter = now - pd.Timedelta(days=7)
    elif range_btn_max:
        time_filter = df_value["open_time"].min()

    # Ensure time_filter is also naive
    if hasattr(time_filter, "tzinfo") and time_filter.tzinfo is not None:
        time_filter = time_filter.tz_localize(None)

    df_plot = df_value[df_value["open_time"] >= time_filter]
    if df_plot.empty:
        df_plot = df_value.tail(50)
        st.info("No data available for the selected time range. Showing the most recent available data instead.")

    # --- Plotly line chart with formatted y-axis ---
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_plot["open_time"],
        y=df_plot["close"],
        mode='lines',
        name='Bitcoin Value'
    ))
    fig.update_layout(
        yaxis_title="Bitcoin Value (USD)",
        xaxis_title="Time",
        yaxis=dict(tickformat=","),
        height=400,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    # --- Percentage Change Indicator ---
    if not df_plot.empty:
        start_val = df_plot["close"].iloc[0]
        end_val = df_plot["close"].iloc[-1]
        pct_change = ((end_val - start_val) / start_val) * 100 if start_val != 0 else 0
        start_date = df_plot["open_time"].iloc[0].strftime("%b %d")
        arrow = "▲" if pct_change >= 0 else "▼"
        color = "green" if pct_change >= 0 else "red"
        st.markdown(
            f"<div style='font-size:20px; font-weight:bold; color:{color}; margin-bottom:8px;'>"
            f"{arrow} {pct_change:+.2f}% since {start_date}"
            "</div>",
            unsafe_allow_html=True
        )

    st.plotly_chart(fig, use_container_width=True)

    # --- Additional Charts ---
    st.subheader("Volume of Trade")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=df_value["open_time"],
        y=df_value["volume"],
        mode='lines',
        name='Volume'
    ))
    fig2.add_trace(go.Scatter(
        x=df_value["open_time"],
        y=df_value["number_of_trades"],
        mode='lines',
        name='Number of Trades',
        yaxis='y2'
    ))
    fig2.update_layout(
        yaxis_title="Volume",
        yaxis2=dict(title="Number of Trades", overlaying='y', side='right'),
        xaxis_title="Time",
        height=300,
        legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
    )
    st.plotly_chart(fig2, use_container_width=True)

    # --- Expandable: Show full raw data ---
    with st.expander("Show full raw value table"):
        st.dataframe(df_value, use_container_width=True)

    # --- Bitcoin/USD Converter ---
    st.subheader("Bitcoin/USD Converter")
    conversion_mode = st.selectbox("Select input currency:", ["Bitcoin (BTC)", "US Dollar (USD)"])
    latest_close = df_value["close"].iloc[-1] if not df_value.empty else None

    if latest_close is not None:
        if conversion_mode == "Bitcoin (BTC)":
            btc_amount = st.number_input("Enter amount in Bitcoin (BTC):", min_value=0.0, value=1.0, step=0.01)
            usd_value = btc_amount * float(latest_close)
            st.success(f"{btc_amount} BTC ≈ ${usd_value:,.2f} USD")
        else:
            usd_amount = st.number_input("Enter amount in US Dollar (USD):", min_value=0.0, value=1000.0, step=1.0)
            btc_value = usd_amount / float(latest_close) if latest_close else 0
            st.success(f"${usd_amount:,.2f} ≈ {btc_value:.8f} BTC")
    else:
        st.warning("No Bitcoin value data available for conversion.")

else:
    st.warning("No Bitcoin value data found in the database.")
    st.stop()

# --- Fetch articles data ---
response = supabase.table("articles").select("*").execute()
data = response.data
if data:
    df = pd.DataFrame(data)
else:
    st.warning("No articles found in the database.")
    st.stop()

def robust_parse(raw_date):
    # Try ISO first
    try:
        return pd.to_datetime(raw_date, format="%Y-%m-%dT%H:%M:%S", errors="raise")
    except Exception:
        pass
    try:
        return pd.to_datetime(raw_date, format="%Y-%m-%d %H:%M:%S", errors="raise")
    except Exception:
        pass
    # Try dayfirst formats
    try:
        return pd.to_datetime(raw_date, format="%Y-%d-%mT%H:%M:%S", errors="raise")
    except Exception:
        pass
    try:
        return pd.to_datetime(raw_date, format="%Y-%d-%m %H:%M:%S", errors="raise")
    except Exception:
        pass
    # Try with dayfirst=True for ambiguous cases
    try:
        return pd.to_datetime(raw_date, dayfirst=True, errors="raise")
    except Exception:
        pass
    # Fallback
    return pd.to_datetime(raw_date, errors="coerce")

df["datetime_parsed"] = df["datetime"].apply(robust_parse)
df["datetime_parsed"] = df["datetime_parsed"].dt.tz_localize(None)

# --- Bitcoin News Sentiment Analysis ---
st.subheader("Sentiment Analysis of Bitcoin News")

day_option = st.selectbox("Show sentiment for:", ["Today", "Yesterday", "Day Before Yesterday"])

# Always use midnight as the reference point
now = pd.Timestamp.now().normalize()

if day_option == "Today":
    start_date = now
    end_date = now + pd.Timedelta(days=1)
elif day_option == "Yesterday":
    start_date = now - pd.Timedelta(days=1)
    end_date = now
elif day_option == "Day Before Yesterday":
    start_date = now - pd.Timedelta(days=2)
    end_date = now - pd.Timedelta(days=1)

# --- Filter for selected day ---
mask = (df["datetime_parsed"] >= start_date) & (df["datetime_parsed"] < end_date)
day_articles = df[mask]

if not day_articles.empty and "sentiment" in day_articles.columns:
    total = len(day_articles)
    positive_count = (day_articles["sentiment"] == "positive").sum()
    neutral_count = (day_articles["sentiment"] == "neutral").sum()
    negative_count = (day_articles["sentiment"] == "negative").sum()

    percent_positive = 100 * positive_count / total
    percent_neutral = 100 * neutral_count / total
    percent_negative = 100 * negative_count / total

    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        y=[f"Sentiment ({day_option})"],
        x=[percent_negative],
        name="Negative",
        orientation='h',
        marker=dict(color="#FF5A5F", line=dict(width=0)),
        width=0.5,  # Thicker bar for rounded look
        offset=0
    ))
    fig_bar.add_trace(go.Bar(
        y=[f"Sentiment ({day_option})"],
        x=[percent_neutral],
        name="Neutral",
        orientation='h',
        marker=dict(color="#FFD700", line=dict(width=0)),
        width=0.5,
        offset=0
    ))
    fig_bar.add_trace(go.Bar(
        y=[f"Sentiment ({day_option})"],
        x=[percent_positive],
        name="Positive",
        orientation='h',
        marker=dict(color="#2ECC40", line=dict(width=0)),
        width=0.5,
        offset=0
    ))

    fig_bar.update_layout(
        barmode='stack',
        height=120,
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(range=[0, 100], title="Percentage", showgrid=False, zeroline=False),
        yaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor='rgba(0,0,0,0)'
        )
    )
    # Remove bar borders for a cleaner look
    for trace in fig_bar.data:
        trace.marker.line.width = 0

    st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

    st.markdown(
        f"<div style='text-align:center;font-size:18px; margin-top:12px;'>"
        f"Negative: <b>{percent_negative:.0f}%</b> &nbsp;|&nbsp; "
        f"Neutral: <b>{percent_neutral:.0f}%</b> &nbsp;|&nbsp; "
        f"Positive: <b>{percent_positive:.0f}%</b>"
        "</div>",
        unsafe_allow_html=True
    )

    st.markdown("</div>", unsafe_allow_html=True)

# --- Fetch and display articles table ---
st.subheader("Bitcoin News")
response = supabase.table("articles").select("*").execute()
data = response.data

if data:
    df = pd.DataFrame(data)
    if "id" in df.columns:
        df = df.drop(columns=["id"])
    st.dataframe(df)
else:
    st.write("No articles found in the database.")