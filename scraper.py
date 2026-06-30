# scraper.py
import asyncio
import aiohttp
import pandas as pd

async def get_chart_data(product_id, option_id):
    url = f"https://snkrdunk.com/v1/apparels/{product_id}/sales-chart/used?range=all&salesChartOptionId={option_id}"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            return await resp.json() if resp.status == 200 else None

def analyze_data(json_data, cost_twd, rate=0.20):
    if not json_data or 'points' not in json_data:
        return {"latest": 0, "avg_1w": 0, "avg_1m": 0, "roi": 0}
    
    df = pd.DataFrame(json_data['points'], columns=['timestamp', 'price_jpy'])
    df['price_twd'] = df['price_jpy'] * rate
    
    now = pd.Timestamp.now()
    latest = df.iloc[-1]['price_twd']
    avg_1w = df[df['timestamp'] >= (now - pd.Timedelta(days=7)).timestamp() * 1000]['price_twd'].mean()
    
    return {
        "latest": latest, 
        "avg_1w": avg_1w,
        "roi": ((latest - cost_twd) / cost_twd * 100)
    }