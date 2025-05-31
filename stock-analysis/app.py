import streamlit as st

st.set_page_config(layout="wide", page_icon="📈")
st.title('Real-Time Stock Dashboard')


import pandas as pd
import plotly.graph_objects as go
import requests
import ta
import time
from random import uniform

try:
    TWELVE_DATA_KEY = st.secrets["TWELVE_DATA_KEY"]
except Exception:
    TWELVE_DATA_KEY = "a8064b85699348b2aa3d94b08f3cd443"

SYMBOLS = ['AAPL', 'GOOGL', 'AMZN', 'MSFT', 'TSLA', 'NVDA']
MAX_RETRIES = 3
BASE_DELAY = 1.5

# --- Twelve Data fetch ---
def fetch_twelvedata_data(ticker, interval, outputsize=100):
    url = "https://api.twelvedata.com/time_series"
    params = {
        'symbol': ticker,
        'interval': interval,
        'outputsize': outputsize,
        'apikey': TWELVE_DATA_KEY,
        'format': 'JSON'
    }
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            # if "values" not in data:
            #     st.warning(f"API response: {data}")
            #     return pd.DataFrame()
            df = pd.DataFrame(data["values"])
            df = df.rename(columns={
                'datetime': 'Datetime',
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            })
            df['Datetime'] = pd.to_datetime(df['Datetime'])
            df = df.sort_values('Datetime')
            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            return df.dropna()
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(BASE_DELAY * (2 ** attempt) + uniform(0, 0.5))
            else:
                st.error(f"Failed to fetch data after {MAX_RETRIES} attempts: {str(e)}")
                return pd.DataFrame()

@st.cache_data(ttl=300)
def fetch_stock_data(ticker, period):
    # Map period to interval and outputsize for Twelve Data
    period_map = {
        '1d': ('5min', 78),     # 6.5h * 12 = 78 intervals for 1 trading day
        '1wk': ('30min', 65),   # 5 days * 13 intervals = 65
        '1mo': ('1h', 160),     # 20 trading days * 8 intervals = 160
        '1y': ('1day', 252),    # 252 trading days in a year
        'max': ('1day', 5000)   # max available
    }
    interval, outputsize = period_map.get(period, ('1day', 100))
    return fetch_twelvedata_data(ticker, interval, outputsize)

def process_data(data):
    if not data.empty:
        df = data.copy()
        return df.dropna()
    return pd.DataFrame()

def calculate_metrics(df):
    last_close = df['Close'].iloc[-1]
    first_close = df['Close'].iloc[0]
    change = last_close - first_close
    pct_change = (change / first_close) * 100 if first_close != 0 else 0
    high = df['High'].max()
    low = df['Low'].min()
    volume = df['Volume'].sum()
    return {
        'last_close': last_close,
        'change': change,
        'pct_change': pct_change,
        'high': high,
        'low': low,
        'volume': volume
    }

def add_technical_indicators(df):
    df['SMA_20'] = ta.trend.sma_indicator(df['Close'], window=20)
    df['EMA_20'] = ta.trend.ema_indicator(df['Close'], window=20)
    return df

# --- Streamlit UI ---
if 'main_ticker' not in st.session_state:
    st.session_state.main_ticker = 'AAPL'

with st.sidebar:
    st.header('Controls')
    st.session_state.main_ticker = st.selectbox('Ticker', SYMBOLS, index=SYMBOLS.index(st.session_state.main_ticker))
    time_period = st.selectbox('Time Period', ['1d', '1wk', '1mo', '1y', 'max'])
    chart_type = st.selectbox('Chart Type', ['Candlestick', 'Line'])
    indicators = st.multiselect('Technical Indicators', ['SMA 20', 'EMA 20'])
    st.header('Index Prices')
    for symbol in SYMBOLS:
        data = fetch_stock_data(symbol, '1d')
        df = process_data(data)
        if not df.empty:
            metrics = calculate_metrics(df)
            st.metric(symbol, 
                      f"{metrics['last_close']:.2f}", 
                      f"{metrics['change']:.2f} ({metrics['pct_change']:.2f}%)")

if st.sidebar.button('Refresh Data'):
    st.cache_data.clear()

try:
    main_data = fetch_stock_data(st.session_state.main_ticker, time_period)
    main_df = process_data(main_data)
    if not main_df.empty:
        main_df = add_technical_indicators(main_df)
        metrics = calculate_metrics(main_df)
        col1, col2, col3 = st.columns(3)
        col1.metric("Current Price", f"{metrics['last_close']:.2f}", 
                  f"{metrics['change']:.2f} ({metrics['pct_change']:.2f}%)")
        col2.metric("Session High", f"{metrics['high']:.2f}")
        col3.metric("Session Low", f"{metrics['low']:.2f}")
        fig = go.Figure()
        if chart_type == 'Candlestick':
            fig.add_trace(go.Candlestick(
                x=main_df['Datetime'],
                open=main_df['Open'],
                high=main_df['High'],
                low=main_df['Low'],
                close=main_df['Close'],
                name='OHLC'
            ))
        else:
            fig.add_trace(go.Scatter(
                x=main_df['Datetime'],
                y=main_df['Close'],
                mode='lines',
                name='Price'
            ))
        for indicator in indicators:
            if indicator == 'SMA 20':
                fig.add_trace(go.Scatter(
                    x=main_df['Datetime'],
                    y=main_df['SMA_20'],
                    line=dict(color='orange', width=1),
                    name='SMA 20'
                ))
            elif indicator == 'EMA 20':
                fig.add_trace(go.Scatter(
                    x=main_df['Datetime'],
                    y=main_df['EMA_20'],
                    line=dict(color='blue', width=1),
                    name='EMA 20'
                ))
        fig.update_layout(
            height=600,
            hovermode='x unified',
            xaxis_rangeslider_visible=False,
            template='plotly_dark',
            margin=dict(r=20, t=40, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)
        with st.expander("Historical Data"):
            st.dataframe(main_df[['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume']])
        with st.expander("Technical Indicators"):
            st.dataframe(main_df[['Datetime', 'SMA_20', 'EMA_20']])
    else:
        st.warning("No data available for this ticker and time period.")
except Exception as e:
    st.error(f"Application error: {str(e)}")
