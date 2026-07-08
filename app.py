import streamlit as st
import asyncio
import pandas as pd
from scraper import (get_chart_data, analyze_data, get_product_name, 
                     create_professional_chart, get_psa_pop_from_cert_url,
                     calculate_investment_metrics, create_combined_chart)
from app_utils import get_gspread_client, update_google_sheet, load_google_sheet

st.set_page_config(page_title="卡牌投資管理", layout="wide")

# --- 初始化 Session ---
if 'card_library' not in st.session_state: st.session_state['card_library'] = load_google_sheet()
if 'last_analysis' not in st.session_state: st.session_state['last_analysis'] = None

# --- 側邊欄 ---
with st.sidebar:
    st.header("功能導航")
    page = st.radio("請選擇功能", ["卡牌分析", "卡牌庫"])

# --- 主要頁面 ---
if page == "卡牌分析":
    st.title("📊 卡牌分析中心")
    
    # 搜尋與分析設定
    with st.expander("🔍 搜尋與分析設定", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            product_id = st.text_input("商品 ID", value='826553')
            search_input = st.text_input("關鍵字搜尋 (選填)")
            if search_input:
                query = search_input.replace(' ', '+').replace('/', '%2F')
                st.markdown(f"[前往 SNKRDUNK 搜尋](https://snkrdunk.com/search?keywords={query})")
        with col2:
            cost = st.number_input("持有成本 (NT$)", value=10000.0)
            analyze_btn = st.button("🚀 執行卡牌分析")
            
    # PSA 查詢
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
        
        if st.button("💾 存入卡牌庫"):
            roi_val = ((res['m_PSA']['latest'] - res['cost']) / res['cost']) * 100
            new_data = {"名稱": str(res['name']), "成本": float(res['cost']), "ROI": f"{roi_val:.2f}%"}
            st.session_state['card_library'].append(new_data)
            update_google_sheet(st.session_state['card_library'])
            st.success("已存入資料庫")

        # 顯示指標 (PSA 與 ROI)
        if 'psa_data' in st.session_state and isinstance(st.session_state['psa_data'], dict):
            d = st.session_state['psa_data']
            c1, c2 = st.columns(2)
            c1.metric("總鑑定數量", d.get('total', '0'))
            c2.metric("高於此卡數量", d.get('higher', '0'))
        
        cols = st.columns(4)
        roi = ((res['m_PSA']['latest'] - res['cost']) / res['cost']) * 100
        cols[0].metric("當前價值", f"NT${res['m_PSA']['latest']:,.0f}")
        cols[1].metric("持有成本", f"NT${res['cost']:,.0f}")
        cols[2].metric("ROI (PSA10)", f"{roi:.2f}%")
        cols[3].metric("市場週均價", f"NT${res['m_PSA']['avg_1w']:,.0f}")

        # 顯示疊圖
        st.subheader("📊 價格趨勢疊加分析")
        fig = create_combined_chart(res['data_A'], res['data_PSA'], "走勢比較")
        st.plotly_chart(fig, use_container_width=True)

elif page == "卡牌庫":
    st.title("📂 卡牌庫")
    df_data = load_google_sheet()
    if df_data:
        st.dataframe(pd.DataFrame(df_data), use_container_width=True)
    else:
        st.info("牌庫目前無資料。")
