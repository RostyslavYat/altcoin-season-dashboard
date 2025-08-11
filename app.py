import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
from time import sleep

st.set_page_config(page_title="Altcoin Season Monitor v4", layout="wide")

API_BASE = "https://api.coingecko.com/api/v3"
REFRESH_HOURS = 4

@st.cache_data(ttl=REFRESH_HOURS*3600)
def get_top_coins(n=50):
    url = f"{API_BASE}/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": n,
        "page": 1,
        "price_change_percentage": "90d,30d,7d"
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return pd.DataFrame(r.json())

@st.cache_data(ttl=REFRESH_HOURS*3600)
def get_market_chart(coin_id, days=90):
    url = f"{API_BASE}/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": days, "interval": "daily"}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    j = r.json()
    mc = pd.DataFrame(j.get('market_caps', []), columns=['ts','market_cap'])
    pr = pd.DataFrame(j.get('prices', []), columns=['ts','price'])
    if mc.empty or pr.empty:
        return None
    df = mc.merge(pr, on='ts')
    df['date'] = pd.to_datetime(df['ts'], unit='ms').dt.normalize()
    df = df[['date','market_cap','price']]
    return df

def build_sample_series(top_coins, days=90, sample_limit=20):
    coins = top_coins['id'].tolist()
    sample = coins[:sample_limit]
    mc_series = {}
    price_series = {}
    for cid in sample:
        try:
            df = get_market_chart(cid, days=days)
            if df is None:
                continue
            mc_series[cid] = df.set_index('date')['market_cap']
            price_series[cid] = df.set_index('date')['price']
            sleep(0.4)
        except Exception as e:
            continue
    if not mc_series:
        return None, None
    mc_df = pd.concat(mc_series, axis=1).fillna(0)
    price_df = pd.concat(price_series, axis=1).fillna(method='ffill').fillna(method='bfill')
    mc_df.index = pd.to_datetime(mc_df.index)
    price_df.index = pd.to_datetime(price_df.index)
    return mc_df, price_df

def compute_asi_history(price_df):
    if 'bitcoin' not in price_df.columns:
        return None
    first = price_df.iloc[0]
    changes = price_df.divide(first) - 1.0
    asi = []
    alt_coins = [c for c in changes.columns if c != 'bitcoin']
    for idx in changes.index:
        btc_ch = changes.loc[idx, 'bitcoin']
        beat = (changes.loc[idx, alt_coins] > btc_ch).sum()
        asi.append(100.0 * beat / len(alt_coins) if alt_coins else None)
    return pd.Series(asi, index=changes.index)

st.title("📊 Altcoin Season Monitor — v4 (real historical sample)")
st.write("Дашборд строит исторические ряды BTC Dominance и ASI по выборке топ-монет (sample). Это приближённая, но живая оценка.")

st.sidebar.header("Параметры")
days = st.sidebar.selectbox("Период (дней)", options=[30, 60, 90], index=2)
sample_limit = st.sidebar.slider("Число монет в выборке (API-heavy)", min_value=10, max_value=40, value=20, step=5)
st.sidebar.markdown("Данные берутся с CoinGecko. Исторические запросы выполняются по каждому монету выборки — это может занять время.")

with st.spinner("Запрашиваю топ-50 монет..."):
    top50 = get_top_coins(50)

global_resp = requests.get(f"{API_BASE}/global", timeout=20).json()
btc_dom_now = global_resp['data']['market_cap_percentage'].get('btc', None)
total_mc_now = global_resp['data']['total_market_cap'].get('usd', None)

asi_now = None
if 'price_change_percentage_90d_in_currency' in top50.columns and 'bitcoin' in top50['id'].values:
    btc_change = top50[top50['id']=='bitcoin']['price_change_percentage_90d_in_currency'].iloc[0]
    alt_df = top50[top50['id'] != 'bitcoin']
    count = (alt_df['price_change_percentage_90d_in_currency'] > btc_change).sum()
    asi_now = round(100.0 * count / len(alt_df), 1)

col1, col2, col3, col4 = st.columns(4)
col1.metric("BTC Dominance (now %)", f"{btc_dom_now:.2f}" if btc_dom_now is not None else 'N/A')
col2.metric("ASI (now %)", f"{asi_now} %" if asi_now is not None else 'N/A')
col3.metric("Sample Altcap (USD)", f"${top50[top50['id']!='bitcoin']['market_cap'].sum()/1e9:.2f}B")
col4.metric("Total Market Cap (USD)", f"${total_mc_now/1e9:.2f}B" if total_mc_now else 'N/A')

st.markdown('---')
st.subheader(f'Формирую исторические ряды по выборке: {sample_limit} монет, период: {days} дней')
with st.spinner('Загружаю исторические данные (это может занять время)...'):
    mc_df, price_df = build_sample_series(top50, days=days, sample_limit=sample_limit)

if mc_df is None or price_df is None:
    st.error('Не удалось получить исторические ряды. Попробуйте уменьшить sample_limit или выбрать меньший период.')
else:
    if 'bitcoin' in mc_df.columns:
        total_sample_mc = mc_df.sum(axis=1)
        btc_dom_hist = 100.0 * mc_df['bitcoin'] / total_sample_mc.replace(0, np.nan)
    else:
        btc_dom_hist = None

    asi_hist = compute_asi_history(price_df) if 'bitcoin' in price_df.columns else None

    combined = pd.DataFrame({'btc_dom': btc_dom_hist, 'asi': asi_hist}).dropna()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=combined.index, y=combined['btc_dom'], name='BTC Dominance (%)', line=dict(color='blue')))
    fig.add_trace(go.Scatter(x=combined.index, y=combined['asi'], name='ASI (%)', line=dict(color='orange')))
    fig.update_layout(title=f'BTC Dominance vs ASI (sample {sample_limit}, last {days} days)', xaxis_title='Date', yaxis_title='%',
                      hovermode='x unified', template='plotly_dark', height=500)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('---')
    st.subheader('Топ выборки (последние значения)')
    latest_prices = price_df.iloc[-1].rename('latest_price')
    changes_90d = top50.set_index('id')['price_change_percentage_90d_in_currency'].to_dict() if 'price_change_percentage_90d_in_currency' in top50.columns else {}
    sample_table = pd.DataFrame({
        'market_cap': mc_df.iloc[-1],
        'latest_price': latest_prices,
        'pct_change_90d': [changes_90d.get(cid, None) for cid in mc_df.columns]
    })
    st.dataframe(sample_table.sort_values('market_cap', ascending=False))

st.markdown('---')
st.caption('Примечание: методика использует выборку топ-монет и дает приближённый исторический ASI и BTC Dominance. Для точных аналитических рядов требуются платные агрегированные источники.')    