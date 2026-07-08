import streamlit as st
import asyncio
import pandas as pd
from scraper import (get_chart_data, analyze_data, get_product_name, 
                     create_professional_chart, get_psa_pop_from_cert_url,
                     calculate_investment_metrics, create_combined_chart)
from app_utils import get_gspread_client, update_google_sheet, load_google_sheet

st.set_page_config(page_title="卡牌投資管理", layout="wide")

# --- 初始化 ---
if 'card_library' not in st.session_state: st.session_state['card_library'] = load_google_sheet()
if 'last_analysis' not in st.session_state: st.session_state['last_analysis'] = None

# --- 側邊欄：僅留功能導航 ---
with st.sidebar:
    st.header("功能導航")
    page = st.radio("請選擇功能", ["卡牌分析", "卡牌庫"])

# --- 主要頁面 ---
if page == "卡牌分析":
    st.title("📊 卡牌分析中心")
    
    # 將搜尋與設定移至中間區塊
    with st.expander("🔍 搜尋與分析設定", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            product_id = st.text_input("商品 ID", value='826553')
            search_input = st.text_input("輸入關鍵字 (例如: M2a 223/193)")
    if search_input:
        # 將搜尋處理與 URL 組裝分開，避免 F-string 括號地獄
        query = search_input.replace(' ', '+').replace('/', '%2F')
        search_url = f"https://snkrdunk.com/search?keywords={query}"
        # 這裡的括號現在完全對稱了
        st.markdown(f"[前往 SNKRDUNK 搜尋]({search_url})")
        with col2:
            cost = st.number_input("持有成本 (NT$)", value=10000.0)
            analyze_btn = st.button("🚀 執行卡牌分析")
            
    # PSA 查詢區塊
    with st.expander("🛡️ PSA POP 查詢"):
        cert_input = st.text_input("輸入 PSA 網址或編號")
        if st.button("查詢數據"):
            url = cert_input if cert_input.startswith("http") else f"https://www.psacard.com/cert/{cert_input}/psa"
            st.session_state['psa_data'] = get_psa_pop_from_cert_url(url)

    # 執行分析邏輯
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
                "data_A": data_A, "data_PSA": data_PSA
            }

    res = st.session_state.get('last_analysis')
    if res:
        st.subheader(f"當前分析：{res['name']}")
        
        # 顯示指標與操作
        if st.button("💾 存入卡牌庫"):
            roi_val = ((res['m_PSA']['latest'] - res['cost']) / res['cost']) * 100
            new_data = {"名稱": str(res['name']), "成本": float(res['cost']), "ROI": f"{roi_val:.2f}%"}
            st.session_state['card_library'].append(new_data)
            update_google_sheet(st.session_state['card_library'])
            st.success("已存入資料庫")

        # 顯示各項數據指標... (維持原邏輯)
        # 顯示疊圖... (維持原邏輯)

elif page == "卡牌庫":
    st.title("📂 卡牌庫")
    df_data = load_google_sheet()
    if df_data:
        st.dataframe(pd.DataFrame(df_data), use_container_width=True)
    else:
        st.info("牌庫目前無資料。")
