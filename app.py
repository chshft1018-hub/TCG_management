import streamlit as st
import asyncio
import pandas as pd
from scraper import get_chart_data, analyze_data, create_chart, get_product_name
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Google Sheets 更新函式 (使用 Secrets) ---
def update_google_sheet(data_list):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    # 從 Streamlit Secrets 讀取 GCP 認證資訊
    creds_dict = dict(st.secrets["gcp"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    
    client = gspread.authorize(creds)
    # 請確保試算表名稱為 "卡牌管理"
    sheet = client.open("卡牌管理").sheet1
    
    # 將資料寫入 Google Sheets
    df = pd.DataFrame(data_list)
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist())

st.set_page_config(page_title="卡牌投資管理", layout="wide")

# --- 初始化 Session State ---
if 'card_library' not in st.session_state:
    st.session_state['card_library'] = []
if 'last_analysis' not in st.session_state:
    st.session_state['last_analysis'] = None

# --- 側邊欄修改 ---
with st.sidebar:
    st.header("功能")
    page = st.radio("請選擇功能", ["卡牌分析", "卡牌庫"])
    st.markdown("---")
    st.header("參數設定")
    
    # 1. 搜尋輸入框
    search_input = st.text_input("輸入關鍵字 (例如: M2a 223/193)")
    
    # 2. 自動搜尋按鈕
    if st.button("🔍 自動搜尋 ID"):
        with st.spinner("搜尋中..."):
            found_id = asyncio.run(search_product_id_by_name(search_input))
            if found_id:
                st.session_state['temp_pid'] = found_id
                st.success(f"找到 ID: {found_id}")
            else:
                st.error("未找到結果，請手動輸入")

    # 3. 商品 ID 框 (預設填入搜尋到的 ID)
    product_id = st.text_input("商品 ID", value=st.session_state.get('temp_pid', '826553'))
    
    cost = st.number_input("持有成本 (NT$)", value=15000.0)
    analyze_btn = st.button("立即分析")

# --- 頁面邏輯 ---

if page == "卡牌分析":
    st.title("📊 卡牌查價")
    
    # 執行分析邏輯
    if analyze_btn:
        with st.spinner('正在獲取數據...'):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            data_A = loop.run_until_complete(get_chart_data(product_id, 18))
            data_PSA = loop.run_until_complete(get_chart_data(product_id, 22))
            card_name = loop.run_until_complete(get_product_name(product_id))
            
            m_A = analyze_data(data_A, cost, 0.20)
            m_PSA = analyze_data(data_PSA, cost, 0.20)
            
            st.session_state['last_analysis'] = {
                "name": card_name, "cost": cost, "m_A": m_A, "m_PSA": m_PSA,
                "chart_A": create_chart(data_A, "裸卡(A品) 價格趨勢"),
                "chart_PSA": create_chart(data_PSA, "鑑定卡(PSA10) 價格趨勢")
            }

    # --- 顯示結果 (與 analyze_btn 脫鉤，確保切換頁面後圖表依然存在) ---
    res = st.session_state['last_analysis']
    if res:
        st.subheader(f"卡牌名稱：{res['name']}")

        # 這裡確保縮排完全一致
    # 修改後按鈕邏輯
        if st.button("💾 存入卡牌庫並同步至雲端"):
            psa10_roi = ((res['m_PSA']['latest'] - res['cost']) / res['cost']) * 100
            new_data = {
                "名稱": res['name'], 
                "成本": res['cost'],
                "A品最新": res['m_A']['latest'], 
                "PSA10最新": res['m_PSA']['latest'],
                "ROI (PSA10)": f"{psa10_roi:.2f}%"
            }
            st.session_state['card_library'].append(new_data)
            
            # 同步至 Google Sheets
            try:
                update_google_sheet(st.session_state['card_library'])
                st.success("已成功儲存並同步至 Google Sheets！")
            except Exception as e:
                st.error(f"同步失敗: {e}")

        c1, c2 = st.columns(2)
        c1.metric("裸卡 (A品) 最新價", f"NT$ {res['m_A']['latest']:,.0f}")
        c2.metric("鑑定卡 (PSA10) 最新價", f"NT$ {res['m_PSA']['latest']:,.0f}")

        df_display = pd.DataFrame([res['m_A'], res['m_PSA']], index=["A品", "PSA10"]).T.rename(index={
            'latest': '最新價', 'avg_1w': '週均價', 'avg_1m': '月均價', 'avg_3m': '季均價', 'roi': 'ROI (%)'
        })
        st.dataframe(df_display.style.format('{:,.2f}'), use_container_width=True)

        st.write("---")
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.plotly_chart(res['chart_A'], use_container_width=True)
        with chart_col2:
            st.plotly_chart(res['chart_PSA'], use_container_width=True)

elif page == "卡牌庫":
    st.title("📂 卡牌庫")
    if st.session_state['card_library']:
        st.dataframe(pd.DataFrame(st.session_state['card_library']), use_container_width=True)
    else:
        st.info("牌庫目前沒有資料。")
