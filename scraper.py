import asyncio
import aiohttp
import pandas as pd
import plotly.express as px
import requests
from bs4 import BeautifulSoup
import plotly.graph_objects as go
import numpy as np
import re

# --- 資料獲取與處理 ---

async def get_chart_data(product_id, option_id):
    url = f"https://snkrdunk.com/v1/apparels/{product_id}/sales-chart/used?range=all&salesChartOptionId={option_id}"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            return await resp.json() if resp.status == 200 else None

async def get_product_name(product_id):
    url = f"https://snkrdunk.com/v1/apparels/{product_id}"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as resp:
                data = await resp.json()
                return data.get('name', '未知卡牌')
        except:
            return '未知卡牌'

def analyze_data(json_data, cost_twd, rate=0.20):
    if not json_data or 'points' not in json_data:
        return {"latest": 0, "avg_1w": 0, "avg_1m": 0, "avg_3m": 0, "roi": 0}
    df = pd.DataFrame(json_data['points'], columns=['timestamp', 'price_jpy'])
    df['price_twd'] = df['price_jpy'] * rate
    now = pd.Timestamp.now()
    latest = df.iloc[-1]['price_twd']
    return {
        "latest": latest,
        "avg_1w": df[df['timestamp'] >= (now - pd.Timedelta(days=7)).timestamp()*1000]['price_twd'].mean(),
        "avg_1m": df[df['timestamp'] >= (now - pd.Timedelta(days=30)).timestamp()*1000]['price_twd'].mean(),
        "avg_3m": df[df['timestamp'] >= (now - pd.Timedelta(days=90)).timestamp()*1000]['price_twd'].mean(),
        "roi": ((latest - cost_twd) / cost_twd * 100)
    }

# --- 圖表繪製 ---

def create_professional_chart(json_data, title, rate=0.20):
    if not json_data or 'points' not in json_data: return None
    df = pd.DataFrame(json_data['points'], columns=['timestamp', 'price_jpy'])
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['price'] = df['price_jpy'] * rate
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['date'], y=df['price'], fill='tozeroy', mode='lines', line=dict(color='#2962FF', width=3)))
    fig.update_layout(title=title, plot_bgcolor='white', xaxis_title="日期", yaxis_title="價格 (NT$)", tickformat=",d")
    return fig

def create_combined_chart(data_A, data_PSA, title):
    fig = go.Figure()
    
    if data_A and 'points' in data_A:
        df_A = pd.DataFrame(data_A['points'], columns=['timestamp', 'price_jpy'])
        df_A['date'] = pd.to_datetime(df_A['timestamp'], unit='ms')
        df_A['price'] = df_A['price_jpy'] * 0.20
        fig.add_trace(go.Scatter(x=df_A['date'], y=df_A['price'], name='裸卡 (A品)', line=dict(color='#FF9800', width=2)))
        
    if data_PSA and 'points' in data_PSA:
        df_PSA = pd.DataFrame(data_PSA['points'], columns=['timestamp', 'price_jpy'])
        df_PSA['date'] = pd.to_datetime(df_PSA['timestamp'], unit='ms')
        df_PSA['price'] = df_PSA['price_jpy'] * 0.20
        fig.add_trace(go.Scatter(x=df_PSA['date'], y=df_PSA['price'], name='鑑定卡 (PSA10)', line=dict(color='#2962FF', width=3)))
    
    fig.update_layout(
        title=title,
        plot_bgcolor='white',
        paper_bgcolor='white',
        hovermode="x unified",
        xaxis=dict(showgrid=True, gridcolor='#E0E0E0', title="日期"),
        yaxis=dict(showgrid=True, gridcolor='#E0E0E0', title="價格 (NT$)", tickformat=",d")
    )
    return fig
# --- 工具與分析 ---

def get_psa_pop_from_cert_url(cert_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(cert_url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        text_content = soup.get_text()
        data = {"total": "0", "higher": "0"}
        total_match = re.search(r"Total Population.*?(\d+)", text_content, re.IGNORECASE | re.DOTALL)
        higher_match = re.search(r"Pop Higher.*?(\d+)", text_content, re.IGNORECASE | re.DOTALL)
        if total_match: data['total'] = total_match.group(1)
        if higher_match: data['higher'] = higher_match.group(1)
        return data if data['total'] != "0" else "未偵測到數據"
    except Exception as e:
        return f"爬取失敗: {str(e)}"

def calculate_investment_metrics(json_data, cost_twd, rate=0.20):
    if not json_data or 'points' not in json_data: return None
    df = pd.DataFrame(json_data['points'], columns=['timestamp', 'price_jpy'])
    df['price_twd'] = df['price_jpy'] * rate
    now = pd.Timestamp.now()
    
    # 動態回退邏輯
    for days in [180, 60, 30]:
        cutoff = (now - pd.Timedelta(days=days)).timestamp() * 1000
        df_period = df[df['timestamp'] >= cutoff].copy()
        if len(df_period) >= 20: break
    
    if len(df_period) < 20: return None

    # 對數回歸
    df_period['log_price'] = np.log(df_period['price_twd'])
    X = np.arange(len(df_period)).reshape(-1, 1)
    y = df_period['log_price'].values
    model = np.polyfit(X.flatten(), y, 1)
    
    projected_log_price = model[0] * (len(df_period) + 60) + model[1]
    projected_60d = np.exp(projected_log_price)
    
    return {
        "latest": df.iloc[-1]['price_twd'],
        "sma_period": df_period['price_twd'].mean(),
        "bias_rate": ((df.iloc[-1]['price_twd'] - df_period['price_twd'].mean()) / df_period['price_twd'].mean()) * 100,
        "projected_60d": projected_60d,
        "roi_60d": ((projected_60d - cost_twd) / cost_twd) * 100
    }
