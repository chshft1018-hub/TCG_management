# scraper.py
import asyncio
import aiohttp
import pandas as pd
import plotly.express as px
async def get_product_name(product_id):
    url = f"https://snkrdunk.com/v1/apparels/{product_id}"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as resp:
                data = await resp.json()
                
                # 為了精確找出名稱，我們可以先印出看看 API 回傳結構
                # 在正式部署前，這能幫我們確認正確的 key
                # print(data) 
                
                # 根據一般 Snkrdunk API 結構，名稱通常位於 data 的 root 層級
                # 如果該 API 有巢狀結構，我們需要調整這裡
                name = data.get('name') or data.get('product_name') or '未知卡牌'
                return name
        except Exception as e:
            return f"Error: {str(e)}"
async def get_chart_data(product_id, option_id):
    url = f"https://snkrdunk.com/v1/apparels/{product_id}/sales-chart/used?range=all&salesChartOptionId={option_id}"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            return await resp.json() if resp.status == 200 else None

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
    if not json_data or 'points' not in json_data: return None
    df = pd.DataFrame(json_data['points'], columns=['timestamp', 'price_jpy'])
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['price_twd'] = df['price_jpy'] * rate
    
    fig = px.line(df, x='date', y='price_twd', title=title)
    
    # 關鍵：強制 Y 軸顯示完整數值格式 (d 代表整數)
    fig.update_layout(
        template="plotly_dark", 
        yaxis_title="價格 (NT$)",
        yaxis=dict(tickformat=",d") 
    )
    return fig
