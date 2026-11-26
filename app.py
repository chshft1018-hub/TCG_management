import streamlit as st
import asyncio
import pandas as pd
import plotly.graph_objects as go
import cv2
import numpy as np
import base64
import streamlit.components.v1 as components
from PIL import Image
from io import BytesIO
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

# 6. 置中檢測 (TAG Smart Grading v6.3 + Skill 嚴格標準整合版)
elif page == "置中檢測":
    st.title("📏 TAG Smart Grading v6.3 (Precision)")
    st.markdown("""
    請上傳卡牌正/背面影像。系統將使用 v6.3 引擎進行二階段精密判定：
    1. **自動外緣偵測 (ROI Focus)：** 框選卡片物理邊界，並加入 5% Buffer 避免畫面裁切過度。
    2. **內外框雙對齊設計：** 
       - `紅色實線`：對齊「物理最外緣」。
       - `青色虛線`：對齊「TAG Bounding Box (連續性 UI 裝飾外框或圖騰交界)」。
    """)
    
    # 開放多圖上傳
    uploaded_files = st.file_uploader("上傳卡牌圖片 (支援多張同步上傳)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    
    if uploaded_files:
        for idx, uploaded_file in enumerate(uploaded_files):
            st.subheader(f"檢測影像 {idx + 1}: {uploaded_file.name}")
            
            try:
                # 記憶體內壓縮，避免撐爆 iframe
                img_pil = Image.open(uploaded_file)
                img_pil.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
                
                buffered = BytesIO()
                if img_pil.mode in ("RGBA", "P"):
                    img_pil = img_pil.convert("RGB")
                img_pil.save(buffered, format="JPEG", quality=85)
                
                base64_img = base64.b64encode(buffered.getvalue()).decode("utf-8")
                img_uri = f"data:image/jpeg;base64,{base64_img}"
            except Exception as e:
                st.error(f"圖片解析失敗: {e}")
                continue
            
            # 整合 v6.3 介面與 Streamlit 穩定機制的 HTML
            html_template = """
            <!DOCTYPE html>
            <html>
            <head>
              <meta charset="utf-8">
              <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
              <!-- 使用 jsdelivr CDN 載入 OpenCV -->
              <script async src="https://cdn.jsdelivr.net/npm/@techstark/opencv-js@4.8.0/build/opencv.min.js"></script>
              <style>
                /* --- Global Settings --- */
                body { 
                  font-family: 'Segoe UI', sans-serif; background: #050505; color: #e0e0e0; 
                  margin: 0; display: flex; flex-direction: column; align-items: center; 
                  min-height: 100vh; overscroll-behavior: none; user-select: none;
                }
                .controls {
                  position: sticky; top: 0; z-index: 100; background: #1a1a1a; width: 100%; padding: 12px 0;
                  box-shadow: 0 4px 15px rgba(0,0,0,0.7); display: flex; justify-content: center; align-items: center; gap: 10px; flex-wrap: wrap;
                }
                .btn { padding: 8px 16px; border: none; border-radius: 20px; font-weight: bold; cursor: pointer; transition: 0.2s; font-size: 14px; white-space: nowrap;}
                .btn:active { transform: scale(0.95); }
                .btn-blue { background: #00bcd4; color: #000; }
                .btn-purple { background: linear-gradient(135deg, #7c4dff, #b388ff); color: white; box-shadow: 0 0 10px rgba(124, 77, 255, 0.6); border: 1px solid #999; }
                .btn-cyan { background: linear-gradient(135deg, #00e5ff, #00b8d4); color: #000; box-shadow: 0 0 10px rgba(0, 229, 255, 0.4); }
                .btn-gray { background: #424242; color: white; }
                
                #workspace {
                  position: relative; margin: 15px auto; box-shadow: 0 0 30px rgba(0,0,0,0.5);
                  font-size: 0; touch-action: none; max-width: 98vw; border: 1px solid #333; overflow: hidden;
                  background-image: linear-gradient(#111 1px, transparent 1px), linear-gradient(90deg, #111 1px, transparent 1px);
                  background-size: 20px 20px;
                  background-color: #000;
                }
                canvas { display: block; width: 100%; height: auto; }
                #overlay { position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }
                
                /* Step 1: Red Dots with Crosshair */
                .control-point {
                  position: absolute; width: 44px; height: 44px; transform: translate(-50%, -50%);
                  cursor: crosshair; pointer-events: auto; z-index: 20; display: flex; align-items: center; justify-content: center;
                }
                .control-point::before {
                  content: ''; width: 14px; height: 14px; background: rgba(255, 60, 60, 0.5);
                  border: 2px solid #fff; border-radius: 50%; box-shadow: 0 0 5px black;
                }
                .control-point::after {
                  content: '+'; position: absolute; color: rgba(255,255,255,0.8); 
                  font-weight: 100; font-size: 24px; pointer-events: none; top: 6px; left: 14px;
                }
                
                .guide-line { position: absolute; pointer-events: auto; z-index: 10; }
                .guide-line::after { content: ''; position: absolute; background: transparent; z-index: 11; } 
                .line-h { width: 100%; left: 0; cursor: ns-resize; } .line-h::after { top: -20px; bottom: -20px; left:0; right:0;}
                .line-v { height: 100%; top: 0; cursor: ew-resize; } .line-v::after { left: -20px; right: -20px; top:0; bottom:0;}
                
                .outer-style.line-h { height: 1px; background: #ff5252; } .outer-style.line-v { width: 1px; background: #ff5252; }
                .inner-style.line-h { height: 0; border-top: 1px dashed #00e5ff; } .inner-style.line-v { width: 0; border-left: 1px dashed #00e5ff; }
                
                #result-panel {
                  display: none; width: 90%; max-width: 500px; background: #1a1a1a; border-radius: 12px; padding: 15px;
                  margin: 20px 0; grid-template-columns: 1fr 1fr; gap: 15px;
                }
                .score-card { background: #252525; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #333; }
                .score-val { font-size: 20px; font-weight: bold; color: #fff; font-family: monospace; margin: 5px 0; }
                .badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; color:#000; }
                #status-msg { color: #888; margin: 10px; font-size: 14px; min-height: 20px;}
                #loading { color: #00bcd4; margin-top: 50px; font-weight: bold; }
              </style>
            </head>
            <body>

            <div id="loading">🚀 Loading v6.3 Engine & Aligning...</div>

            <div id="main-ui" style="display:none; width: 100%; flex-direction: column; align-items: center;">
              <div class="controls">
                <button id="autoBtnStep1" class="btn btn-purple" onclick="runFocusDetect()" style="display:none;">✨ Auto Detect</button>
                <button id="nextBtn" class="btn btn-blue" onclick="processWarp()" style="display:none;">Next</button>
                <button id="autoBtnStep2" class="btn btn-cyan" onclick="runAutoDetectInner()" style="display:none;">⚡ Align Inner</button>
                <button id="resetBtn" class="btn btn-gray" onclick="resetAll(true)" style="display:none;">Reset</button>
              </div>

              <div id="status-msg">Ready</div>

              <div id="workspace">
                <canvas id="cvCanvas"></canvas>
                <div id="overlay"></div>
              </div>

              <div id="result-panel">
                <div class="score-card">
                  <div style="color:#aaa; font-size:12px">Left / Right</div>
                  <div id="val-lr" class="score-val">--</div>
                  <div id="bdg-lr" class="badge">--</div>
                </div>
                <div class="score-card">
                  <div style="color:#aaa; font-size:12px">Top / Bottom</div>
                  <div id="val-tb" class="score-val">--</div>
                  <div id="bdg-tb" class="badge">--</div>
                </div>
              </div>
            </div>

            <script>
              const imgUri = "___IMG_URI___";
              let cvReady = false;
              let imgMat = null, warpedMat = null, currentStep = 0;
              let corners = [], guides = { outL:0, outR:1, outT:0, outB:1, inL:0.1, inR:0.9, inT:0.1, inB:0.9 };
              const PADDING_RATIO = 0.05; 

              const canvas = document.getElementById('cvCanvas');
              const overlay = document.getElementById('overlay');

              // 使用輪詢機制檢查 OpenCV 是否載入完成，不再依賴 onRuntimeInitialized
              function checkCvReady() {
                  if (typeof cv !== 'undefined' && typeof cv.Mat !== 'undefined') {
                      cvReady = true;
                      document.getElementById('loading').style.display = 'none';
                      document.getElementById('main-ui').style.display = 'flex';
                      
                      // OpenCV 載入完成後，才開始讀取圖片並進行處理
                      const img = new Image();
                      img.onload = () => {
                        setupImage(img);
                      };
                      img.src = imgUri;
                  } else {
                      setTimeout(checkCvReady, 100); // 每 100ms 檢查一次
                  }
              }
              // 啟動輪詢
              checkCvReady();

              function setupImage(img) {
                resetAll(false);
                const MAX = 800; // 降低內部運算解析度避免 iframe 撐爆
                let w = img.width, h = img.height;
                if (w > MAX || h > MAX) { const r = Math.min(MAX/w, MAX/h); w = Math.floor(w*r); h = Math.floor(h*r); }
                canvas.width = w; canvas.height = h;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, w, h);

                if(imgMat) imgMat.delete();
                // 使用 getImageData 抓像素，避免直接讀虛擬畫布造成破圖
                let imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                imgMat = cv.matFromImageData(imgData);

                corners = [{x: w*0.2, y: h*0.2, label:'TL'}, {x: w*0.8, y: h*0.2, label:'TR'}, {x: w*0.8, y: h*0.8, label:'BR'}, {x: w*0.2, y: h*0.8, label:'BL'}];
                
                currentStep = 0;
                updateUI();
                renderOverlay();
                setTimeout(runFocusDetect, 100);
              }

              // --- Step 1: Focused Detect (ROI) ---
              function runFocusDetect() {
                if(!imgMat || !cvReady) return;
                const status = document.getElementById('status-msg');
                status.innerText = "🔍 Scanning...";
                status.style.color = "#b388ff";

                try {
                  let marginX = Math.floor(imgMat.cols * 0.12);
                  let marginY = Math.floor(imgMat.rows * 0.12);
                  let roiW = imgMat.cols - (2 * marginX);
                  let roiH = imgMat.rows - (2 * marginY);
                  
                  let rectROI = new cv.Rect(marginX, marginY, roiW, roiH);
                  let srcROI = imgMat.roi(rectROI);

                  let gray = new cv.Mat(), blurred = new cv.Mat(), edges = new cv.Mat();
                  let contours = new cv.MatVector(), hierarchy = new cv.Mat();
                  
                  cv.cvtColor(srcROI, gray, cv.COLOR_RGBA2GRAY, 0);
                  cv.GaussianBlur(gray, blurred, new cv.Size(5, 5), 0);
                  cv.Canny(blurred, edges, 50, 150);
                  
                  let kernel = cv.getStructuringElement(cv.MORPH_RECT, new cv.Size(5, 5));
                  cv.morphologyEx(edges, edges, cv.MORPH_CLOSE, kernel);

                  cv.findContours(edges, contours, hierarchy, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE);

                  let maxArea = 0, bestCnt = null;
                  const minArea = (roiW * roiH) * 0.20; 

                  for (let i = 0; i < contours.size(); ++i) {
                    let cnt = contours.get(i);
                    let area = cv.contourArea(cnt);
                    if (area > maxArea && area > minArea) {
                      maxArea = area;
                      bestCnt = cnt; 
                    } else { cnt.delete(); }
                  }

                  if (bestCnt) {
                    let pts = bestCnt.data32S; 
                    let numPts = pts.length / 2;
                    let tl = {val: Infinity, x:0, y:0}, br = {val: -Infinity, x:0, y:0};
                    let tr = {val: -Infinity, x:0, y:0}, bl = {val: Infinity, x:0, y:0};

                    for (let i = 0; i < numPts; i++) {
                      let x = pts[i*2];
                      let y = pts[i*2+1];
                      let sum = x + y;
                      let diff = x - y;
                      if (sum < tl.val) tl = {val: sum, x:x, y:y, label:'TL'};
                      if (sum > br.val) br = {val: sum, x:x, y:y, label:'BR'};
                      if (diff > tr.val) tr = {val: diff, x:x, y:y, label:'TR'};
                      if (diff < bl.val) bl = {val: diff, x:x, y:y, label:'BL'};
                    }

                    corners = [
                      {x: tl.x + marginX, y: tl.y + marginY, label:'TL'},
                      {x: tr.x + marginX, y: tr.y + marginY, label:'TR'},
                      {x: br.x + marginX, y: br.y + marginY, label:'BR'},
                      {x: bl.x + marginX, y: bl.y + marginY, label:'BL'}
                    ];
                    
                    status.innerText = "✅ Card Detected";
                    status.style.color = "#00e676";
                    bestCnt.delete(); 
                  } else {
                    status.innerText = "⚠️ Manual Adjustment Needed";
                    status.style.color = "#ff5252";
                  }

                  renderOverlay();
                  srcROI.delete(); gray.delete(); blurred.delete(); edges.delete(); 
                  contours.delete(); hierarchy.delete(); kernel.delete();

                } catch (e) { console.error(e); }
              }

              // --- Step 2: Warp & Init Guides ---
              function processWarp() {
                if(!imgMat || !cvReady) return;
                
                try {
                    let srcPts = cv.matFromArray(4, 1, cv.CV_32FC2, [
                      corners[0].x, corners[0].y, corners[1].x, corners[1].y,
                      corners[2].x, corners[2].y, corners[3].x, corners[3].y
                    ]);
                    
                    let wT = Math.hypot(corners[1].x-corners[0].x, corners[1].y-corners[0].y);
                    let wB = Math.hypot(corners[2].x-corners[3].x, corners[2].y-corners[3].y);
                    let hL = Math.hypot(corners[3].x-corners[0].x, corners[3].y-corners[0].y);
                    let hR = Math.hypot(corners[2].x-corners[1].x, corners[2].y-corners[1].y);
                    
                    let cardW = Math.max(wT, wB);
                    let cardH = Math.max(hL, hR);
                    let marginX = cardW * PADDING_RATIO;
                    let marginY = cardH * PADDING_RATIO;
                    let dstW = cardW + (marginX * 2);
                    let dstH = cardH + (marginY * 2);

                    let dstPts = cv.matFromArray(4, 1, cv.CV_32FC2, [
                      marginX, marginY,               
                      dstW - marginX, marginY,        
                      dstW - marginX, dstH - marginY, 
                      marginX, dstH - marginY         
                    ]);

                    let M = cv.getPerspectiveTransform(srcPts, dstPts);
                    if(warpedMat) warpedMat.delete(); warpedMat = new cv.Mat();
                    cv.warpPerspective(imgMat, warpedMat, M, new cv.Size(dstW, dstH), cv.INTER_LINEAR, cv.BORDER_CONSTANT, new cv.Scalar(0, 0, 0, 255));
                    
                    canvas.width = dstW; canvas.height = dstH;
                    cv.imshow('cvCanvas', warpedMat);
                    srcPts.delete(); dstPts.delete(); M.delete();

                    currentStep = 1; 
                    
                    guides.outL = marginX / dstW;
                    guides.outR = (dstW - marginX) / dstW;
                    guides.outT = marginY / dstH;
                    guides.outB = (dstH - marginY) / dstH;

                    guides.inT = guides.outT + 0.088; 
                    guides.inB = guides.outT + 0.915; 
                    guides.inL = guides.outL + 0.08; 
                    guides.inR = guides.outR - 0.08;

                    updateUI(); renderOverlay();
                } catch (err) {
                    alert("Warping error: Please check the blue dots layout.");
                }
              }

              function runAutoDetectInner() {
                if(!warpedMat || !cvReady) return;
                const status = document.getElementById('status-msg');
                status.innerText = "⚡ Aligning Inner Frame...";
                status.style.color = "#00e5ff";

                try {
                  let src = warpedMat.clone();
                  let gray = new cv.Mat(), edges = new cv.Mat();
                  cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY, 0);
                  cv.Canny(gray, edges, 50, 150);

                  const W = src.cols, H = src.rows;

                  function findStrongestLine(isVertical, startPct, endPct) {
                    let bestPos = -1, maxScore = 0;
                    const minLimit = isVertical ? (guides.outL * W) : (guides.outT * H);
                    const cardSize = isVertical ? (guides.outR - guides.outL) * W : (guides.outB - guides.outT) * H;
                    
                    const startIdx = Math.floor(minLimit + (cardSize * startPct));
                    const endIdx = Math.floor(minLimit + (cardSize * endPct));

                    for (let i = startIdx; i < endIdx; i++) {
                      let score = 0;
                      for (let j = 0; j < (isVertical ? H : W); j+=2) {
                        let pixel = isVertical ? edges.ucharPtr(j, i)[0] : edges.ucharPtr(i, j)[0];
                        if (pixel > 200) score++;
                      }
                      if (score > maxScore) { maxScore = score; bestPos = i; }
                    }
                    return (maxScore > 10) ? bestPos : null;
                  }

                  let l = findStrongestLine(true, 0.06, 0.10); if(l) guides.inL = l/W;
                  let r = findStrongestLine(true, 0.90, 0.94); if(r) guides.inR = r/W;
                  let t = findStrongestLine(false, 0.06, 0.12); if(t) guides.inT = t/H;
                  let b = findStrongestLine(false, 0.88, 0.93); if(b) guides.inB = b/H;

                  renderOverlay(); calc();
                  status.innerText = "⚡ Aligned (Fine-tune cyan lines manually)";
                  src.delete(); gray.delete(); edges.delete();
                } catch(e) { console.error(e); }
              }

              function getScale() { const r = canvas.getBoundingClientRect(); return r.width ? canvas.width/r.width : 1; }

              function renderOverlay() {
                overlay.innerHTML = '';
                const scale = getScale();
                if (currentStep === 0) {
                  corners.forEach((pt, idx) => {
                    const el = document.createElement('div'); el.className = 'control-point'; el.setAttribute('data-label', pt.label);
                    el.style.left = (pt.x/scale)+'px'; el.style.top = (pt.y/scale)+'px';
                    bindDrag(el, (dx, dy) => { corners[idx].x = dx*scale; corners[idx].y = dy*scale; drawPoly(); });
                    overlay.appendChild(el);
                  });
                  drawPoly();
                } else {
                  renderLine('h', guides.outT, 'outer', (v)=>{guides.outT=v; calc();});
                  renderLine('h', guides.inT,  'inner', (v)=>{guides.inT=v; calc();});
                  renderLine('h', guides.inB,  'inner', (v)=>{guides.inB=v; calc();});
                  renderLine('h', guides.outB, 'outer', (v)=>{guides.outB=v; calc();});
                  renderLine('v', guides.outL, 'outer', (v)=>{guides.outL=v; calc();});
                  renderLine('v', guides.inL,  'inner', (v)=>{guides.inL=v; calc();});
                  renderLine('v', guides.inR,  'inner', (v)=>{guides.inR=v; calc();});
                  renderLine('v', guides.outR, 'outer', (v)=>{guides.outR=v; calc();});
                  calc();
                }
              }

              function renderLine(dir, val, style, cb) {
                const r = canvas.getBoundingClientRect();
                const el = document.createElement('div');
                el.className = `guide-line line-${dir} ${style}-style`;
                if(dir==='h') el.style.top = (val*r.height)+'px'; else el.style.left = (val*r.width)+'px';
                bindDrag(el, (x, y) => { if(dir==='h') cb(y/r.height); else cb(x/r.width); });
                overlay.appendChild(el);
              }

              function drawPoly() {
                if(!imgMat || !cvReady) return; 
                cv.imshow('cvCanvas', imgMat);
                const ctx = canvas.getContext('2d'), s = getScale();
                ctx.beginPath(); ctx.lineWidth = 2*s; ctx.strokeStyle = '#ff5252';
                ctx.moveTo(corners[0].x, corners[0].y); ctx.lineTo(corners[1].x, corners[1].y);
                ctx.lineTo(corners[2].x, corners[2].y); ctx.lineTo(corners[3].x, corners[3].y);
                ctx.closePath(); ctx.stroke();
              }

              function bindDrag(el, onMove) {
                const start = (e) => {
                  e.preventDefault(); e.stopPropagation();
                  const isTouch = e.type==='touchstart';
                  const rect = document.getElementById('workspace').getBoundingClientRect();
                  const move = (evt) => {
                    evt.preventDefault();
                    const c = isTouch ? evt.touches[0] : evt;
                    let x = Math.max(0, Math.min(c.clientX - rect.left, rect.width));
                    let y = Math.max(0, Math.min(c.clientY - rect.top, rect.height));
                    if(el.classList.contains('line-h')) el.style.top = y+'px';
                    else if(el.classList.contains('line-v')) el.style.left = x+'px';
                    else { el.style.left = x+'px'; el.style.top = y+'px'; }
                    onMove(x, y);
                  };
                  const end = () => {
                    document.removeEventListener(isTouch?'touchmove':'mousemove', move);
                    document.removeEventListener(isTouch?'touchend':'mouseup', end);
                  };
                  document.addEventListener(isTouch?'touchmove':'mousemove', move, {passive:false});
                  document.addEventListener(isTouch?'touchend':'mouseup', end);
                };
                el.addEventListener('mousedown', start); el.addEventListener('touchstart', start, {passive:false});
              }

              function calc() {
                const l = guides.inL-guides.outL, r = guides.outR-guides.inR;
                const t = guides.inT-guides.outT, b = guides.outB-guides.inB;
                const sW = l+r||0.001, sH = t+b||0.001;
                setScore('lr', (l/sW)*100, (r/sW)*100); setScore('tb', (t/sH)*100, (b/sH)*100);
              }

              // --- 🛡️ 整合 Skill 嚴格鑑定標準 ---
              function setScore(id, v1, v2) {
                if(v1<0 || v2<0) return;
                // 強制顯示小數點後兩位
                document.getElementById('val-'+id).innerText = `${v1.toFixed(2)} / ${v2.toFixed(2)}`;
                const w = Math.max(v1, v2);
                const b = document.getElementById('bdg-'+id);
                
                // 依照最新嚴格標準判定
                if(w <= 50.00) { 
                    b.innerText="BGS 10 黑標"; 
                    b.style.background="#d4af37"; b.style.color="#000";
                } else if(w < 51.00) { 
                    b.innerText="TAG 10 Pristine"; 
                    b.style.background="#2e7d32"; b.style.color="#fff";
                } else if(w <= 53.00) { 
                    b.innerText="TAG 10 Gem Mint"; 
                    b.style.background="#1565c0"; b.style.color="#fff";
                } else if(w <= 55.00) { 
                    b.innerText="PSA 10 Gem Mint"; 
                    b.style.background="#0288d1"; b.style.color="#fff";
                } else if(w <= 60.00) { 
                    b.innerText="PSA 10 (寬容極限)"; 
                    b.style.background="#ff9800"; b.style.color="#000";
                } else { 
                    b.innerText="未達 Gem Mint"; 
                    b.style.background="#d32f2f"; b.style.color="#fff";
                }
              }

              function updateUI() {
                const isStep0 = (currentStep === 0);
                const hasImg = (imgMat !== null);
                
                document.getElementById('autoBtnStep1').style.display = (isStep0 && hasImg) ? 'inline-block' : 'none';
                document.getElementById('nextBtn').style.display = (isStep0 && hasImg) ? 'inline-block' : 'none';
                document.getElementById('autoBtnStep2').style.display = (!isStep0 && hasImg) ? 'inline-block' : 'none';
                document.getElementById('resetBtn').style.display = (!isStep0) ? 'inline-block' : 'none';
                document.getElementById('result-panel').style.display = isStep0 ? 'none' : 'grid';

                if (!isStep0) {
                    document.getElementById('status-msg').innerText = "Step 2: Adjust Lines (Red for Outer Edge, Cyan for Inner UI/Box)";
                    document.getElementById('status-msg').style.color = "#aaa";
                }
              }

              function resetAll(full) {
                if(full) { 
                    currentStep = 0; 
                    if(imgMat && cvReady){cv.imshow('cvCanvas', imgMat); renderOverlay();} 
                    updateUI(); 
                }
              }
            </script>
            </body>
            </html>
            """
            
            html_code = html_template.replace("___IMG_URI___", img_uri)
            components.html(html_code, height=950)
