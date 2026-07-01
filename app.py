import streamlit as st
import asyncio
import pandas as pd
from scraper import get_chart_data, analyze_data, create_chart, get_product_name

st.set_page_config(page_title="卡牌投資管理", layout="wide")
st.title("📊 卡牌投資管理系統")

with st.sidebar:
    st.header("設定")
    product_id = st.text_input("輸入商品 ID", value="826553")
    cost = st.number_input("輸入成本 (NT$)", value=15000.0)
    analyze_btn = st.button("立即分析")

if analyze_btn:
    with st.spinner('正在獲取數據...'):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 抓取資料
        data_A = loop.run_until_complete(get_chart_data(product_id, 18))
        data_PSA = loop.run_until_complete(get_chart_data(product_id, 22))
        card_name = loop.run_until_complete(get_product_name(product_id))
        
        m_A = analyze_data(data_A, cost, 0.20)
        m_PSA = analyze_data(data_PSA, cost, 0.20)
        
        chart_A = create_chart(data_A, "裸卡(A品) 價格趨勢")
        chart_PSA = create_chart(data_PSA, "鑑定卡(PSA10) 價格趨勢")

    # 1. 顯示名稱標題
    card_name = loop.run_until_complete(get_product_name(product_id))
    st.subheader(f"卡牌名稱：{card_name}")

    # 2. 顯示 Metric 卡片
    col1, col2 = st.columns(2)
    with col1:
        st.metric("裸卡 (A品) 最新價", f"NT$ {m_A['latest']:,.0f}")
    with col2:
        st.metric("鑑定卡 (PSA10) 最新價", f"NT$ {m_PSA['latest']:,.0f}")

    # 3. 處理統計數據表格
    st.write("### 詳細統計數據：")
    
    # 建立 DataFrame 並轉置
    df_metrics = pd.DataFrame([m_A, m_PSA], index=["A品", "PSA10"]).T
    
    # 移除名稱列（因為已作為上方標題）
    df_display = df_metrics.drop(index='名稱')
    
    # 重新命名列索引為中文
    df_display = df_display.rename(index={
        'latest': '最新價', 
        'avg_1w': '週均價', 
        'avg_1m': '月均價', 
        'avg_3m': '季均價', 
        'roi': 'ROI (%)'
    })

    # 顯示表格
    st.dataframe(
        df_display.style.format({
            'A品': '{:,.2f}',
            'PSA10': '{:,.2f}'
        }),
        use_container_width=True
    )

    # 4. 顯示圖表
    if chart_A: st.plotly_chart(chart_A, use_container_width=True, key="chart_A")
    if chart_PSA: st.plotly_chart(chart_PSA, use_container_width=True, key="chart_PSA")
