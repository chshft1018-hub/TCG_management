import asyncio
import aiohttp
import pandas as pd
import plotly.express as px
import requests
from bs4 import BeautifulSoup
import plotly.graph_objects as go

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
        response = requests.get(cert_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 定位 Pop 數據的區塊
        # PSA 驗證頁面上，通常會用 <span class="pop-count"> 或類似的標籤標示
        # 由於網頁結構可能會有變化，我們使用 find 找尋特定的 text 關鍵字
        pop_data = {}
        
        # 搜尋 "Total Population" 和 "Pop Higher" 這些標籤
        labels = soup.find_all('div', class_='label')
        for label in labels:
            if "Total Population" in label.text:
                pop_data['total'] = label.find_next_sibling('div').text.strip()
            if "Pop Higher" in label.text:
                pop_data['higher'] = label.find_next_sibling('div').text.strip()
        
        return pop_data if pop_data else "未找到 POP 數據"
    except Exception as e:
        return f"爬取失敗: {str(e)}"
