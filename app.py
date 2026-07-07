import streamlit as st
import asyncio
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from scraper import (get_chart_data, analyze_data, get_product_name, 
                     create_professional_chart, get_psa_pop_from_cert_url)

# --- Google Sheets 工具函式 ---
def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp"])
    if isinstance(creds_dict.get("private_key"), str):
        creds_dict["private_key"] = creds_dict["private_key"].replace('\\n', '\n')
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def update_google_sheet(data_list):
    client = get_gspread_client()
    sheet = client.open("卡牌管理").sheet1
    df = pd.DataFrame(data_list).fillna('')
    sheet.clear()
    sheet.append_row(df.columns.values.tolist())
    sheet.append_rows(df.values.tolist())

def load_google_sheet():
    try:
        client = get_gspread_client()
        sheet = client.open("卡牌管理").sheet1
        return sheet.get_all_records()
    except:
        return []

st.set_page_config(page_title="卡牌投資管理", layout="wide")

# --- Session State 初始化 ---
if 'card_library' not in st.session_state: st.session_state['card_library'] = load_google_sheet()
if 'last_analysis' not in st.session_state: st.session_state['last_analysis'] = None

# --- 側邊欄 ---
# --- 側邊欄 ---
with st.sidebar:
    st.header("功能")
    page = st.radio("請選擇功能", ["卡牌分析", "卡牌庫"])
    
    st.markdown("---")
    st.header("搜尋與設定")
    
    # 1. 找回關鍵字搜尋
    search_input = st.text_input("輸入關鍵字 (例如: M2a 223/193)")
    if search_input:
        search_url = f"https://snkrdunk.com/search?keywords={search_input.replace(' ', '+').replace('/', '%2F')}"
        st.markdown(f"[點此前往搜尋結果頁]({search_url})")
    
    # 2. 參數設定
    product_id = st.text_input("商品 ID", value='826553')
    cost = st.number_input("持有成本 (NT$)", value=10000.0)
    analyze_btn = st.button("立即分析")
    
    st.markdown("---")
    st.header("PSA POP 查詢")
    cert_url = st.text_input("輸入 PSA 驗證網址")
    if st.button("查詢 PSA 數據"):
        with st.spinner("解析中..."):
            st.session_state['psa_data'] = get_psa_pop_from_cert_url(cert_url)

# --- 主要頁面邏輯 ---
if page == "卡牌分析":
    st.title("📊 卡牌查價")
    
    # 1. 數據獲取邏輯
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

    # 2. 顯示邏輯
    res = st.session_state.get('last_analysis')
    if res:
        st.subheader(f"卡牌名稱：{res['name']}")
        
        # PSA 結果顯示
        if 'psa_data' in st.session_state and isinstance(st.session_state['psa_data'], dict):
            d = st.session_state['psa_data']
            cp1, cp2 = st.columns(2)
            cp1.metric("總鑑定數量 (Total Pop)", d.get('total', '0'))
            cp2.metric("高於此卡數量 (Pop Higher)", d.get('higher', '0'))
        
        with st.container(border=True):
            cols = st.columns(4)
            roi = ((res['m_PSA']['latest'] - res['cost']) / res['cost']) * 100
            cols[0].metric("當前價值", f"NT${res['m_PSA']['latest']:,.0f}")
            cols[1].metric("持有成本", f"NT${res['cost']:,.0f}")
            cols[2].metric("ROI (PSA10)", f"{roi:.2f}%", delta=f"{roi:.2f}%")
            cols[3].metric("市場週均價", f"NT${res['m_PSA']['avg_1w']:,.0f}")

        if st.button("💾 存入卡牌庫"):
            new_data = {"名稱": str(res['name']), "成本": float(res['cost']), "ROI": f"{roi:.2f}%"}
            st.session_state['card_library'].append(new_data)
            update_google_sheet(st.session_state['card_library'])
            st.success("已同步至 Google Sheets")

        # 圖表區域
        c1, c2 = st.columns(2)
        c1.plotly_chart(create_professional_chart(res['data_A'], "裸卡(A品) 價格走勢"), use_container_width=True)
        c2.plotly_chart(create_professional_chart(res['data_PSA'], "鑑定卡(PSA10) 價格走勢"), use_container_width=True)

elif page == "卡牌庫":
    st.title("📂 卡牌庫")
    df_data = load_google_sheet()
    if df_data:
        df = pd.DataFrame(df_data)
        st.dataframe(df[['名稱', '成本', 'ROI']], use_container_width=True, hide_index=True)
    else:
        st.info("牌庫目前無資料。")
