import streamlit as st
import asyncio
import pandas as pd
import plotly.graph_objects as go
import cv2
import numpy as np
import base64
import streamlit.components.v1 as components
from PIL import Image
from io import BytesIO  # 【關鍵修復】：導入內建記憶體串流模組
from scraper import (get_chart_data, analyze_data, get_product_name, 
                     create_professional_chart, get_psa_pop_from_cert_url,
                     calculate_investment_metrics, create_combined_chart)
from app_utils import update_google_sheet, load_google_sheet

st.set_page_config(page_title="卡牌投資管理", layout="wide")

if 'card_library' not in st.session_state: st.session_state['card_library'] = load_google_sheet()
if 'last_analysis' not in st.session_state: st.session_state['last_analysis'] = None
if 'psa_data' not in st.session_state: st.session_state['psa_data'] = None
if 'current_page' not in st.session_state: st.session_state['current_page'] = "首頁"

def navigate_to(page_name):
    st.session_state['current_page'] = page_name

with st.sidebar:
    st.header("功能導航")
    page = st.radio( "功能區", ["首頁", "卡牌分析", "投資分析", "PSA 查詢", "置中檢測", "卡牌庫"], key="current_page")

# 1. 首頁
if page == "首頁":
    st.title("卡牌投資管理系統")
    st.write("功能列表：")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.button("📊 前往卡牌分析", use_container_width=True, on_click=navigate_to, args=("卡牌分析",))
    c2.button("📈 前往投資分析", use_container_width=True, on_click=navigate_to, args=("投資分析",))
    c3.button("🛡️ 前往 PSA 查詢", use_container_width=True, on_click=navigate_to, args=("PSA 查詢",))
    c4.button("📏 前往置中檢測", use_container_width=True, on_click=navigate_to, args=("置中檢測",))
    c5.button("📂 前往卡牌庫", use_container_width=True, on_click=navigate_to, args=("卡牌庫",))
    
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
            st.subheader(f"針對【{res['name']}】之計量策略預測")
            
            rsi_val = metrics['rsi']
            bias_rate = metrics['bias_rate']
            preds = metrics['predictions']
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("60日指數均價 (EMA)", f"NT${metrics['ema_60']:,.0f}")
            current_roi = ((metrics['latest'] - res['cost']) / res['cost']) * 100
            c2.metric("當前 ROI", f"{current_roi:.2f}%")
            c3.metric("當前乖離率", f"{bias_rate:.2f}%")
            c4.metric("RSI (14) 市場情緒", f"{rsi_val:.1f}")
            
            st.markdown("---")
            st.markdown("### 📊 未來 60 天價格走勢預測")
            
            pred_df = pd.DataFrame(list(preds.items()), columns=['Days', 'Predicted_Price'])
            fig_pred = go.Figure()
            fig_pred.add_trace(go.Scatter(
                x=pred_df['Days'], y=pred_df['Predicted_Price'],
                mode='lines+markers+text',
                text=[f"NT${p:,.0f}" if d in [0, 15, 60] else "" for d, p in zip(pred_df['Days'], pred_df['Predicted_Price'])],
                textposition="top center",
                line=dict(color='#9C27B0', width=3, shape='spline'),
                marker=dict(size=8, color='#9C27B0'),
                hovertemplate="預測價格: NT$%{y:,.0f}<extra></extra>" 
            ))
            fig_pred.update_layout(
                xaxis_title="未來天數", 
                yaxis=dict(title="預測價格 (NT$)", tickformat=",d"), 
                plot_bgcolor='white', hovermode="x unified", height=400,
                xaxis=dict(tickmode='array', tickvals=[0, 5, 10, 15, 30, 45, 60], ticktext=['現在', '5天', '10天', '15天', '30天', '45天', '60天'])
            )
            st.plotly_chart(fig_pred, use_container_width=True)

            st.markdown("### ⏱️ 最佳操作時機判定")
            best_sell_day = max(preds, key=preds.get)
            best_buy_day = min(preds, key=preds.get)
            
            if rsi_val >= 60:
                st.error(f"**🔴 賣出策略分析 (高檔調節)**\n\n根據動能過衝模型，預期價格的最高峰可能落在 **第 {best_sell_day} 天** (預估價: NT${preds[best_sell_day]:,.0f})。若您持有現貨，建議在此時間區間內分批獲利了結。")
            elif rsi_val <= 40:
                st.success(f"**🟢 買進策略分析 (低檔佈局)**\n\n根據均值回歸模型，預期價格的最低谷可能落在 **第 {best_buy_day} 天** (預估價: NT${preds[best_buy_day]:,.0f})。市場拋售情緒即將觸底，這將是建立底倉的最佳黃金窗口。")
            else:
                st.info(f"**🟡 中性觀望分析**\n\n目前市場動能平穩。圖表顯示價格波動區間狹窄，此時進出場的套利空間有限，建議持倉觀望。")
            
            st.markdown("---")
            st.markdown("#### 長期預測概覽 (60天後)")
            p1, p2 = st.columns(2)
            p1.metric("60天後預測價", f"NT${metrics['projected_60d']:,.0f}")
            p2.metric("預期 ROI", f"{metrics['roi_60d']:.2f}%")
            
        else:
            st.warning("數據樣本數不足，無法產生量化預測指標。")
    
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
    if not df.empty: st.dataframe(df, use_container_width=True)
    else: st.info("無庫存資料")

# 5. PSA 查詢
elif page == "PSA 查詢":
    st.title("🛡️ PSA POP 查詢")
    with st.container(border=True):
        cert_input = st.text_input("輸入 PSA 網址或編號")
        if st.button("查詢 PSA 數據"):
            with st.spinner("解析中..."):
                url = cert_input if cert_input.startswith("http") else f"https://www.psacard.com/cert/{cert_input}/psa"
                st.session_state['psa_data'] = get_psa_pop_from_cert_url(url)
    if st.session_state.get('psa_data'):
        if isinstance(st.session_state['psa_data'], dict):
            st.success("✅ 查詢成功！")
            p1, p2 = st.columns(2)
            p1.metric("總鑑定數量 (Total Pop)", st.session_state['psa_data'].get('total', '0'))
            p2.metric("高於此卡數量 (Pop Higher)", st.session_state['psa_data'].get('higher', '0'))
        else:
            st.error(st.session_state['psa_data'])

# 6. 置中檢測 (突破 Streamlit 流量阻擋版)
elif page == "置中檢測":
    st.title("📏 TAG Smart Grading v6.3 (Precision)")
    st.markdown("""
    請上傳卡牌正/背面影像。系統將使用 v6.3 引擎進行二階段精密判定：
    1. **自動外緣偵測 (ROI Focus)：** 框選卡片物理邊界，並加入 Buffer 避免畫面裁切過度。
    2. **內外框雙對齊設計：** 
       - `紅色實線`：對齊「物理最外緣」。
       - `青色虛線`：對齊「TAG Bounding Box (連續性 UI 裝飾外框或圖騰交界)」。
    """)
    
    uploaded_files = st.file_uploader("上傳卡牌圖片 (支援多張同步上傳)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    
    if uploaded_files:
        for idx, uploaded_file in enumerate(uploaded_files):
            st.subheader(f"檢測影像 {idx + 1}: {uploaded_file.name}")
            
            try:
                # 【防護核心】：強制將原始圖片轉換並壓縮，把數 MB 壓到 < 100KB
                # 這是突破 Streamlit WebSocket 傳輸大小限制 (Message Size Limit) 的唯一解法
                img_pil = Image.open(uploaded_file)
                img_pil.thumbnail((800, 800), Image.Resampling.LANCZOS)
                
                buffered = BytesIO()
                if img_pil.mode in ("RGBA", "P"):
                    img_pil = img_pil.convert("RGB")
                img_pil.save(buffered, format="JPEG", quality=75) # 提高壓縮率
                
                base64_img = base64.b64encode(buffered.getvalue()).decode("utf-8")
                img_uri = f"data:image/jpeg;base64,{base64_img}"
            except Exception as e:
                st.error(f"圖片壓縮與解析失敗: {e}")
                continue
            
            html_template = """
            <!DOCTYPE html>
            <html>
            <head>
              <meta charset="utf-8">
              <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
              <!-- 改用 Cloudflare 最穩定來源 -->
              <script async src="https://cdnjs.cloudflare.com/ajax/libs/opencv.js/4.8.0/opencv.min.js"></script>
              <style>
                body { 
                  font-family: 'Segoe UI', sans-serif; background: #050505; color: #e0e0e0; 
                  margin: 0; display: flex; flex-direction: column; align-items: center; 
                  min-height: 100vh; overscroll-behavior: none; user-select: none;
                }
                .controls {
                  position: sticky; top: 0; z-index: 100; background: #1a1a1a; width: 100%; padding: 12px 0;
                  box-shadow: 0 4px 15px rgba(0,0,0,0.7); display: flex; justify-content:
