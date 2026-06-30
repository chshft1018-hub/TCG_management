import streamlit as st
import asyncio
import pandas as pd
from scraper import get_chart_data, analyze_data  # 直接匯入你整理好的模組

# 網頁設定
st.set_page_config(page_title="卡牌投資管理", layout="wide")
st.title("📊 卡牌投資管理系統")

# 側邊欄：輸入區
with st.sidebar:
    st.header("設定")
    product_id = st.text_input("輸入商品 ID", value="826553")
    cost = st.number_input("輸入成本 (NT$)", value=15000.0)
    analyze_btn = st.button("立即分析")

# 顯示區
if analyze_btn:
    with st.spinner('正在從 Snkrdunk 獲取數據...'):
        # 執行異步任務
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        data_A = loop.run_until_complete(get_chart_data(product_id, 18))
        data_PSA = loop.run_until_complete(get_chart_data(product_id, 22))
        
        m_A = analyze_data(data_A, cost, 0.20)
        m_PSA = analyze_data(data_PSA, cost, 0.20)

    # 呈現 Dashboard
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("裸卡 (A品)")
        st.metric("最新價", f"NT$ {m_A['latest']:,.0f}")
        st.metric("ROI", f"{m_A['roi']:.2f}%", delta_color="normal")
        
    with col2:
        st.subheader("鑑定卡 (PSA10)")
        st.metric("最新價", f"NT$ {m_PSA['latest']:,.0f}")
        st.metric("ROI", f"{m_PSA['roi']:.2f}%", delta_color="normal")

    # 顯示原始數據細節
    st.write("---")
    st.write("詳細統計數據：", pd.DataFrame([m_A, m_PSA], index=["A品", "PSA10"]))