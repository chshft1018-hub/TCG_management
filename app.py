import streamlit as st
import asyncio
import requests
from bs4 import BeautifulSoup
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from scraper import get_chart_data, analyze_data, get_product_name, create_professional_chart

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

st.set_page_config(page_title="卡牌投資管理", layout="wide")

# --- Session State 初始化 ---
if 'card_library' not in st.session_state: st.session_state['card_library'] = []
if 'last_analysis' not in st.session_state: st.session_state['last_analysis'] = None

# --- 側邊欄 ---
with st.sidebar:
    st.header("功能")
    page = st.radio("請選擇功能", ["卡牌分析", "卡牌庫"])
    st.header("參數設定")
    search_input = st.text_input("輸入關鍵字 (例如: M2a 223/193)")
    if search_input:
        st.markdown(f"[點此前往搜尋結果頁](https://snkrdunk.com/search?keywords={search_input.replace(' ', '+').replace('/', '%2F')})")
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
                "data_A": data_A, "data_PSA": data_PSA  # 儲存原始資料供繪圖用
            }

    res = st.session_state.get('last_analysis')
    if res:
        st.subheader(f"卡牌名稱：{res['name']}")
        with st.container(border=True):
            cols = st.columns(4)
            roi = ((res['m_PSA']['latest'] - res['cost']) / res['cost']) * 100
            cols[0].metric("當前價值", f"NT${res['m_PSA']['latest']:,.0f}")
            cols[1].metric("持有成本", f"NT${res['cost']:,.0f}")
            cols[2].metric("ROI (PSA10)", f"{roi:.2f}%", delta=f"{roi:.2f}%")
            cols[3].metric("市場週均價", f"NT${res['m_PSA']['avg_1w']:,.0f}")

        if st.button("💾 存入卡牌庫"):
            new_data = {"名稱": res['name'], "成本": res['cost'], "ROI": f"{roi:.2f}%"}
            st.session_state['card_library'].append(new_data)
            update_google_sheet(st.session_state['card_library'])
            st.success("已同步至 Google Sheets")

        c1, c2 = st.columns(2)
        c1.plotly_chart(create_professional_chart(res['data_A'], "裸卡(A品) 價格走勢"), use_container_width=True)
        c2.plotly_chart(create_professional_chart(res['data_PSA'], "鑑定卡(PSA10) 價格走勢"), use_container_width=True)
