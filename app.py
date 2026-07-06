import streamlit as st
import asyncio
import requests
from bs4 import BeautifulSoup
import pandas as pd
from scraper import get_chart_data, analyze_data, create_chart, get_product_name
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from scraper import get_chart_data, analyze_data, create_professional_chart, get_product_name

# --- Google Sheets 更新函式 ---
def update_google_sheet(data_list):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp"])
    if isinstance(creds_dict.get("private_key"), str):
        creds_dict["private_key"] = creds_dict["private_key"].replace('\\n', '\n')
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("卡牌管理").sheet1
    df = pd.DataFrame(data_list).fillna('')
    sheet.clear()
    sheet.append_row(df.columns.values.tolist())
    sheet.append_rows(df.values.tolist())

# --- 搜尋函式 ---
def search_product_id_by_name(keyword):
    if not keyword or keyword.strip() == "": return None
    search_url = f"https://snkrdunk.com/search?keywords={keyword.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a', href=True)
        for link in links:
            if '/apparels/' in link['href']:
                parts = link['href'].split('/')
                for part in parts:
                    if part.isdigit() and len(part) >= 5: return part
    except: return None
    return None

st.set_page_config(page_title="卡牌投資管理", layout="wide")

# --- 初始化 Session State ---
if 'card_library' not in st.session_state: st.session_state['card_library'] = []
if 'last_analysis' not in st.session_state: st.session_state['last_analysis'] = None

# --- 側邊欄 ---
with st.sidebar:
    st.header("功能")
    page = st.radio("請選擇功能", ["卡牌分析", "卡牌庫"])
    st.markdown("---")
    st.header("參數設定")
    
    search_input = st.text_input("輸入關鍵字 (例如: M2a 223/193)")
    search_url = f"https://snkrdunk.com/search?keywords={search_input.replace(' ', '+').replace('/', '%2F')}"
    if search_input: st.markdown(f"[點此前往搜尋結果頁]({search_url})")
    
    product_id = st.text_input("商品 ID", value='826553')
    cost = st.number_input("持有成本 (NT$)", value=15000.0)
    analyze_btn = st.button("立即分析")

# --- 頁面邏輯 ---
if page == "卡牌分析":
    st.title("📊 卡牌查價")
    if analyze_btn:
        with st.spinner('正在獲取數據...'):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            data_A = loop.run_until_complete(get_chart_data(product_id, 18))
            data_PSA = loop.run_until_complete(get_chart_data(product_id, 22))
            card_name = loop.run_until_complete(get_product_name(product_id))
            st.session_state['last_analysis'] = {
                "name": card_name, "cost": cost, 
                "m_A": analyze_data(data_A, cost, 0.20), 
                "m_PSA": analyze_data(data_PSA, cost, 0.20),
                "chart_A": create_chart(data_A, "裸卡(A品) 價格趨勢"),
                "chart_PSA": create_chart(data_PSA, "鑑定卡(PSA10) 價格趨勢")
            }

    res = st.session_state['last_analysis']
    if res:
        st.subheader(f"卡牌名稱：{res['name']}")
        
        # 1. 專業 KPI 儀表板區域
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns(4)
            psa10_roi = ((res['m_PSA']['latest'] - res['cost']) / res['cost']) * 100
            
            col1.metric("當前價值", f"NT${res['m_PSA']['latest']:,.0f}")
            col2.metric("持有成本", f"NT${res['cost']:,.0f}")
            col3.metric("ROI (PSA10)", f"{psa10_roi:.2f}%", delta=f"{psa10_roi:.2f}%")
            col4.metric("市場週均價", f"NT${res['m_PSA']['avg_1w']:,.0f}")

        # 2. 存入按鈕
        if st.button("💾 存入卡牌庫"):
            # ... (保留你原本的存入資料邏輯)
            st.success("已存入資料庫")

        # 3. 專業圖表區 (調用我們剛剛在 scraper.py 寫好的新函式)
        st.write("---")
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.plotly_chart(create_professional_chart(data_A, "裸卡(A品) 價格走勢"), use_container_width=True)
        with chart_col2:
            st.plotly_chart(create_professional_chart(data_PSA, "鑑定卡(PSA10) 價格走勢"), use_container_width=True)
