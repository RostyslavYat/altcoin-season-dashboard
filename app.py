import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="Altcoin Season Dashboard", layout="wide")

# Параметры
REFRESH_HOURS = 4
DAYS_OPTIONS = [30, 90]

@st.cache_data(ttl=REFRESH_HOURS*3600)
def fetch_btc_dominance(days):
    url = f"https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days={days}"
    data = requests.get(url).json()
    market_caps = pd.DataFrame(data['market_caps'], columns=['timestamp', 'market_cap'])
    market_caps['date'] = pd.to_datetime(market_caps['timestamp'], unit='ms')
    # Заглушка доминации — реальный показатель нужно брать из другого API (например, TradingView)
    market_caps['btc_dominance'] = (market_caps['market_cap'] / market_caps['market_cap'].max()) * 50 + 25
    return market_caps[['date', 'btc_dominance']]

@st.cache_data(ttl=REFRESH_HOURS*3600)
def fetch_asi(days):
    # Здесь мы делаем заглушку — реальный ASI берется с blockchaincenter.net API
    dates = pd.date_range(end=datetime.today(), periods=days)
    asi_values = pd.Series([40 + (i % 20) for i in range(days)])
    return pd.DataFrame({'date': dates, 'asi': asi_values})

# Заголовок
st.title("📊 Altcoin Season Dashboard")
st.markdown("Отслеживание BTC Dominance и Altcoin Season Index (ASI) в реальном времени")

# Выбор периода
period = st.selectbox("Выбери период анализа (дней):", DAYS_OPTIONS)

# Получение данных
btc_dom_df = fetch_btc_dominance(period)
asi_df = fetch_asi(period)

# Объединение данных
df = pd.merge(btc_dom_df, asi_df, on="date", how="inner")

# Построение графика
fig = px.line(df, x='date', y=['btc_dominance', 'asi'], labels={'value':'%','date':'Дата'}, title=f"BTC Dominance vs ASI за последние {period} дней")
fig.update_layout(legend_title_text='Индикатор', hovermode='x unified')
st.plotly_chart(fig, use_container_width=True)

# Таблица последних значений
st.subheader("📅 Последние значения")
st.dataframe(df.tail(10).set_index('date'))
