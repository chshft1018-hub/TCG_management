import streamlit as st
import asyncio
import pandas as pd
from scraper import (get_chart_data, analyze_data, get_product_name, 
                     create_professional_chart, get_psa_pop_from_cert_url,
                     calculate_investment_metrics, create_combined_chart)
from app_utils import update_google_sheet, load_google_sheet

st.set_page_config(page_title="卡牌投資管理", layout="wide")

# --- 初始化 Session State ---
if 'card_library' not in st.session_state: st.session_state['card_library'] = load_google_sheet()
if 'last_analysis' not in st.session_state: st.session_state['last_analysis'] = None
if 'psa_data' not in st.session_state: st.session_state['psa_data'] = None

# 初始化當前頁面
if 'current_page' not in st.session_state:
    st.session_state['current_page'] = "首頁"

# --- 定義導航回呼函式 (Callback) ---
# 這是解決 API Exception 的關鍵，讓狀態更新在畫面重繪之前完成
def navigate_to(page_name):
    st.session_state['current_page'] = page_name

# --- 側邊欄：導航 ---
with st.sidebar:
    st.header("功能導航")
    # 將 radio 綁定到 session_state['current_page']
    page = st.radio( "功能區",
        ["首頁", "卡牌分析", "投資分析", "PSA 查詢", "卡牌庫"], 
        key="current_page"
    )

# --- 主要頁面邏輯 ---

# 1. 首頁 (Dashboard)
if page == "首頁":
    st.title("卡牌投資管理系統")
    st.write("功能列表：")
    
    # 建立 4 個欄位放置按鈕，並綁定 on_click 事件
    c1, c2, c3, c4 = st.columns(4)
    c1.button("📊 前往卡牌分析", use_container_width=True, on_click=navigate_to, args=("卡牌分析",))
    c2.button("📈 前往投資分析", use_container_width=True, on_click=navigate_to, args=("投資分析",))
    c3.button("🛡️ 前往 PSA 查詢", use_container_width=True, on_click=navigate_to, args=("PSA 查詢",))
    c4.button("📂 前往卡牌庫", use_container_width=True, on_click=navigate_to, args=("卡牌庫",))

# 2. 卡牌分析
elif page == "卡牌分析":
    st.title("📊 卡牌分析中心")
    
    with st.expander("🔍 搜尋與分析設定", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            search_input = st.text_input("輸入關鍵字 (例如: M2a 223/193)")
            if search_input:
                query = search_input.replace(' ', '+').replace('/', '%2F')
                st.markdown(f"[前往 SNKRDUNK 搜尋](https://snkrdunk.com/search?keywords={query})")
            product_id = st.text_input("商品 ID", value='826553')
        with col2:
            cost = st.number_input("持有成本 (NT$)", value=10000.0)
            analyze_btn = st.button("🚀 執行卡牌分析")

    if analyze_btn:
        with st.spinner('正在獲取數據...'):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            data_A = loop.run_until_complete(get_chart_data(product_id, 18))
            data_PSA = loop.run_until_complete(get_chart_data(product_id, 22))
            card_name = loop.run_until_complete(get_product_name(product_id))
            st.session_state['last_analysis'] = {
                "name": card_name, "cost": cost, "data_A": data_A, "data_PSA": data_PSA,
                "m_A": analyze_data(data_A, cost, 0.20), "m_PSA": analyze_data(data_PSA, cost, 0.20)
            }

    res = st.session_state.get('last_analysis')
    if res:
        st.subheader(f"當前分析：{res['name']}")
        
        if st.button("💾 存入卡牌庫"):
            new_data = {"名稱": res['name'], "成本": float(res['cost']), "ROI": f"{((res['m_PSA']['latest']-res['cost'])/res['cost']*100):.2f}%"}
            st.session_state['card_library'].append(new_data)
            update_google_sheet(st.session_state['card_library'])
            st.session_state['card_library'] = load_google_sheet()
            st.success("已同步至 Google Sheets")
            
        fig = create_combined_chart(res['data_A'], res['data_PSA'], "走勢比較")
        st.plotly_chart(fig, use_container_width=True)

# 3. 投資分析
elif page == "投資分析":
    st.title("📈 進階投資分析")
    
    res = st.session_state.get('last_analysis')
    if res:
        metrics = calculate_investment_metrics(res['data_PSA'], res['cost'])
        if metrics:
            st.subheader("針對最新查詢卡牌之計量策略預測")
            
            # 第一排：趨勢與動能
            c1, c2, c3 = st.columns(3)
            c1.metric("60日指數均價 (EMA)", f"NT${metrics['ema_60']:,.0f}")
            c2.metric("乖離率", f"{metrics['bias_rate']:.2f}%")
            
            # 根據 RSI 給予不同顏色的市場情緒提示
            rsi_val = metrics['rsi']
            if rsi_val >= 70:
                rsi_status = "🔴 超買 (高風險)"
            elif rsi_val <= 30:
                rsi_status = "🟢 超賣 (反彈契機)"
            else:
                rsi_status = "🟡 中性盤整"
            c3.metric("RSI (14) 市場情緒", f"{rsi_val:.1f}", delta=rsi_status, delta_color="off")
            
            st.markdown("---")
            
            # 第二排：均值回歸預測
            st.markdown("#### 基於均值回歸理論之 60 天預估")
            p1, p2 = st.columns(2)
            p1.metric("模型預測價", f"NT${metrics['projected_60d']:,.0f}")
            p2.metric("預期 ROI", f"{metrics['roi_60d']:.2f}%")
            
        else:
            st.warning("數據樣本數不足 (需大於30筆交易紀錄)，無法產生量化預測指標。")
    
    st.markdown("---")
    if st.button("🔄 計算整體組合績效"):
        df = pd.DataFrame(load_google_sheet())
        if not df.empty:
            st.metric("總持有資產成本", f"NT${df['成本'].sum():,.0f}")
            st.dataframe(df, use_container_width=True)
        else: 
            st.warning("請先在卡牌分析頁面存入卡牌。")

# 4. 卡牌庫
elif page == "卡牌庫":
    st.title("📂 卡牌庫")
    df = pd.DataFrame(load_google_sheet())
    if not df.empty: 
        st.dataframe(df, use_container_width=True)
    else: 
        st.info("無庫存資料")

# 5. PSA 查詢
elif page == "PSA 查詢":
    st.title("🛡️ PSA POP 查詢")
    st.write("請輸入 PSA 鑑定網址或憑證編號以獲取卡牌的 Population 數據。")
    
    with st.container(border=True):
        cert_input = st.text_input("輸入 PSA 網址或編號")
        if st.button("查詢 PSA 數據"):
            with st.spinner("解析中..."):
                url = cert_input if cert_input.startswith("http") else f"https://www.psacard.com/cert/{cert_input}/psa"
                st.session_state['psa_data'] = get_psa_pop_from_cert_url(url)
    
    # 顯示查詢結果
    if st.session_state.get('psa_data'):
        if isinstance(st.session_state['psa_data'], dict):
            st.success("✅ 查詢成功！")
            p1, p2 = st.columns(2)
            p1.metric("總鑑定數量 (Total Pop)", st.session_state['psa_data'].get('total', '0'))
            p2.metric("高於此卡數量 (Pop Higher)", st.session_state['psa_data'].get('higher', '0'))
        else:
            st.error(st.session_state['psa_data'])
