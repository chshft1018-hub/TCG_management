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
    with st.spinner('正在從 Snkrdunk 獲取數據...'):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        data_A = loop.run_until_complete(get_chart_data(product_id, 18))
        data_PSA = loop.run_until_complete(get_chart_data(product_id, 22))
        card_name = loop.run_until_complete(get_product_name(product_id))
        m_A = analyze_data(data_A, cost, 0.20)
        m_PSA = analyze_data(data_PSA, cost, 0.20)
        m_A['名稱'] = card_name
        m_PSA['名稱'] = card_name
        chart_A = create_chart(data_A, "裸卡(A品) 價格趨勢")
        chart_PSA = create_chart(data_PSA, "鑑定卡(PSA10) 價格趨勢")

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
    # 1. 準備 DataFrame，此時欄位名稱仍為英文
    df_metrics = pd.DataFrame([m_A, m_PSA], index=["A品", "PSA10"])
    
    # 2. 先進行轉置 (Transpose)，讓 A品/PSA10 變成欄位，原本的指標變成 Index
    df_display = df_metrics.T
    
    # 3. 重新命名 Index (將 latest, avg_1w 等英文改成中文)
    df_display = df_display.rename(index={
        'latest': '最新價', 
        'avg_1w': '週均價', 
        'avg_1m': '月均價', 
        'avg_3m': '季均價', 
        'roi': 'ROI (%)'
    })
    
    # 4. 移除不需要的名稱列 (因為名稱已經作為標題)
    if '名稱' in df_display.index:
        df_display = df_display.drop(index='名稱')
    
    # 5. 使用 style 進行格式化，確保小數點取到百分位 (四捨五入)
    # 注意：這裡對所有數據列進行格式化
st.write("詳細統計數據：")

    # 確保這一區塊的所有程式碼頂格對齊 (4個空格)
    df_metrics = pd.DataFrame([m_A, m_PSA], index=["A品", "PSA10"]).T
    df_display = df_metrics.drop(index='名稱')
    df_display = df_display.rename(index={
        'latest': '最新價', 
        'avg_1w': '週均價', 
        'avg_1m': '月均價', 
        'avg_3m': '季均價', 
        'roi': 'ROI (%)'
    })

    st.dataframe(
        df_display.style.format({
            'A品': '{:,.2f}',
            'PSA10': '{:,.2f}'
        }),
        use_container_width=True
    )
    
    if chart_A: st.plotly_chart(chart_A, use_container_width=True, key="chart_A")
    if chart_PSA: st.plotly_chart(chart_PSA, use_container_width=True, key="chart_PSA")
