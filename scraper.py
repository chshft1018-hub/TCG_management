import asyncio
import aiohttp
import pandas as pd
import plotly.express as px
import requests
from bs4 import BeautifulSoup
import plotly.graph_objects as go
import numpy as np
import re
import math

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
        hovermode="x unified",
        xaxis=dict(title="日期"),
        yaxis=dict(title="價格 (NT$)", tickformat=",d") 
    )
    return fig

def get_psa_pop_from_cert_url(cert_url):
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.psacard.com/"}
    try:
        response = requests.get(cert_url, headers=headers, timeout=20)
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
    
    df = df.sort_values('timestamp').reset_index(drop=True)
    if len(df) < 30: return None

    # 1. 基礎指標計算
    df['ema_60'] = df['price_twd'].ewm(span=60, adjust=False).mean()
    delta = df['price_twd'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi_14'] = 100 - (100 / (1 + rs))
    
    current_price = df['price_twd'].iloc[-1]
    ema_60 = df['ema_60'].iloc[-1]
    rsi = df['rsi_14'].iloc[-1]
    if np.isnan(rsi): rsi = 50
    
    bias_rate = ((current_price - ema_60) / ema_60) * 100
    
    # 2. 定義目標收斂價
    target_price = ema_60
    if rsi < 30: target_price *= 1.05
    elif rsi > 70: target_price *= 0.95
        
    # 3. 計算多節點時間序列預測 (5, 10, 15, 30, 45, 60 天)
    predictions = {0: current_price}
    momentum = (rsi - 50) / 50.0  # 動能量化 (-1 到 1)
    
    for t in [5, 10, 15, 30, 45, 60]:
        # A. 均值回歸組件 (隨時間逐步向 target_price 靠近)
        reversion = current_price + (target_price - current_price) * ((t / 60.0) ** 0.8)
        
        # B. 動能過衝組件 (模擬短期非理性繁榮或恐慌，峰值約在第 15 天)
        surge = current_price * momentum * 0.12 * (t / 15.0) * math.exp(1 - (t / 15.0))
        
        predictions[t] = reversion + surge

    roi_60d = ((predictions[60] - cost_twd) / cost_twd) * 100
    
    return {
        "latest": current_price,
        "ema_60": ema_60,
        "bias_rate": bias_rate,
        "rsi": rsi,
        "predictions": predictions,
        "projected_60d": predictions[60],
        "roi_60d": roi_60d
    }
