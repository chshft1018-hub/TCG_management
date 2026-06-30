import streamlit as st
import asyncio
import pandas as pd
from scraper import get_chart_data, analyze_data, create_chart# 直接匯入你整理好的模組

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
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 1. 取得資料
        data_A = loop.run_until_complete(get_chart_data(product_id, 18))
        data_PSA = loop.run_until_complete(get_chart_data(product_id, 22))
        
        m_A = analyze_data(data_A, cost, 0.20)
        m_PSA = analyze_data(data_PSA, cost, 0.20)
        
        # 2. 提前處理圖表與表格數據，確保變數一定被定義
        chart_A = create_chart(data_A, "裸卡(A品) 價格趨勢")
        chart_PSA = create_chart(data_PSA, "鑑定卡(PSA10) 價格趨勢")
        
        df_metrics = pd.DataFrame([m_A, m_PSA], index=["A品", "PSA10"])
        df_display = df_metrics.rename(columns={
            'latest': '最新價', 'avg_1w': '週均價', 'avg_1m': '月均價', 'avg_3m': '季均價', 'roi': 'ROI (%)'
        })

    # 3. 統一渲染區塊 (在 spinner 結束後一次呈現)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("裸卡 (A品)")
        st.metric("最新價", f"NT$ {m_A['latest']:,.0f}")
        st.metric("ROI", f"{m_A['roi']:.2f}%")
    with col2:
        st.subheader("鑑定卡 (PSA10)")
        st.metric("最新價", f"NT$ {m_PSA['latest']:,.0f}")
        st.metric("ROI", f"{m_PSA['roi']:.2f}%")

    st.write("詳細統計數據：")
    st.dataframe(df_display.style.format("{:,.0f}"))

    # 顯示圖表
    if chart_A: st.plotly_chart(chart_A, use_container_width=True, key="chart_A")
    if chart_PSA: st.plotly_chart(chart_PSA, use_container_width=True, key="chart_PSA")
