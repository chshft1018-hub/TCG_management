import asyncio
import aiohttp
import pandas as pd
import plotly.express as px
import requests
from bs4 import BeautifulSoup
import plotly.graph_objects as go
from bs4 import BeautifulSoup
import requests
import numpy as np


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

def create_chart(json_data, title, rate=0.20):
    if not json_data or 'points' not in json_data: 
        return None
    
    df = pd.DataFrame(json_data['points'], columns=['timestamp', 'price_jpy'])
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['price_twd'] = df['price_jpy'] * rate
    
    fig = px.line(df, x='date', y='price_twd', title=title)
    
    # 修正重點：強制 Y 軸顯示原始完整整數，不使用 k/M 縮寫
    fig.update_layout(
        template="plotly_dark", 
        yaxis_title="價格 (NT$)",
        yaxis=dict(
            tickformat=",d",  # 使用逗號分隔的完整整數格式
            tickmode="auto"
        )
    )
    return fig

# 增加這個函式到你的 scraper.py
async def search_product_id_by_name(keyword):
    search_url = f"https://snkrdunk.com/en/search?search={keyword.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(search_url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 找到搜尋結果的第一個商品連結
    # 根據 SNKRDUNK 網頁結構，商品連結通常含有 /apparels/ 或 /products/
    first_item = soup.find('a', href=lambda x: x and ('/apparels/' in x or '/products/' in x))
    
    if first_item:
        # 從 URL 中提取編號 (例如 /apparels/722239 -> 722239)
        product_id = first_item['href'].split('/')[-1]
        return product_id
    return None

def create_professional_chart(json_data, title, rate=0.20):
    if not json_data or 'points' not in json_data: return None
    
    df = pd.DataFrame(json_data['points'], columns=['timestamp', 'price_jpy'])
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['price'] = df['price_jpy'] * rate
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['date'], y=df['price'], fill='tozeroy', mode='lines', line=dict(color='#2962FF', width=3)))
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=20, family="Arial")),
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis=dict(showgrid=True, gridcolor='#E0E0E0', title="日期"),
        yaxis=dict(
            showgrid=True, gridcolor='#E0E0E0', title="價格 (NT$)",
            tickformat=",d",        # 使用逗號分隔的整數格式
            exponentformat="none"   # 強制取消 k, M 縮寫
        ),
        hovermode="x unified",
        margin=dict(l=40, r=40, t=60, b=40)
    )
    return fig

def get_psa_pop_from_cert_url(cert_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(cert_url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 觀察到 PSA 的 POP 數據通常位於一個表格區塊中
        # 我們直接尋找包含特定文字的父級容器
        data = {"total": "0", "higher": "0"}
        
        # 尋找所有文字節點並比對
        text_content = soup.get_text()
        
        # 使用更靈活的方式尋找數字 (假設 HTML 結構為標籤後面接數字)
        # 這是最穩定的爬取方式：直接找特定區塊內的文字
        import re
        total_match = re.search(r"Total Population.*?(\d+)", text_content, re.IGNORECASE | re.DOTALL)
        higher_match = re.search(r"Pop Higher.*?(\d+)", text_content, re.IGNORECASE | re.DOTALL)
        
        if total_match: data['total'] = total_match.group(1)
        if higher_match: data['higher'] = higher_match.group(1)
        
        return data if data['total'] != "0" else "未偵測到數據，請確認網址是否正確"
    except Exception as e:
        return f"爬取失敗: {str(e)}"

def calculate_investment_metrics(json_data, cost_twd, rate=0.20):
    if not json_data or 'points' not in json_data: return None
    
    df = pd.DataFrame(json_data['points'], columns=['timestamp', 'price_jpy'])
    df['price_twd'] = df['price_jpy'] * rate
    
    # 擴大到 180 天的數據進行訓練
    now = pd.Timestamp.now()
    days_180 = (now - pd.Timedelta(days=180)).timestamp() * 1000
    df_180d = df[df['timestamp'] >= days_180].copy()
    
    if len(df_180d) < 30: # 數據量太少則不進行預測
        return None

    # 1. 計算均值 (維持 SMA60，作為短期支撐參考)
    recent_60d = df.tail(60)
    sma60 = recent_60d['price_twd'].mean()
    latest = df.iloc[-1]['price_twd']
    
    # 2. 對數回歸 (使用 180 天數據進行擬合，訓練趨勢)
    df_180d['log_price'] = np.log(df_180d['price_twd'])
    X = np.arange(len(df_180d)).reshape(-1, 1)
    y = df_180d['log_price'].values
    
    model = np.polyfit(X.flatten(), y, 1)
    
    # 3. 預測未來 60 天 (在 180 天基礎上外推 60 天)
    future_index = len(df_180d) + 60
    projected_log_price = model[0] * future_index + model[1]
    projected_60d = np.exp(projected_log_price)
    
    # 4. 乖離率與 ROI
    bias_rate = ((latest - sma60) / sma60) * 100
    roi_60d = ((projected_60d - cost_twd) / cost_twd) * 100
    
    return {
        "latest": latest,
        "sma60": sma60,
        "bias_rate": bias_rate,
        "projected_60d": projected_60d,
        "roi_60d": roi_60d
    }
