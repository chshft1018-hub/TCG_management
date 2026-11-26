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

# 6. 置中檢測 (TAG 邊界基準版 - 修正 OpenCV 載入與圖片壓縮問題)
elif page == "置中檢測":
    st.title("📏 專業級卡牌置中檢測 (TAG / PSA 嚴格標準)")
    st.markdown("""
    請上傳卡牌正/背面影像。系統採用二階段判定：
    1. **校正外框透視：** 拖拉藍點對齊卡牌「物理最外邊緣」。
    2. **標定 TAG 測量錨點：** 拖拉紅線對齊內部基準線。
       - **無邊框卡/全圖卡 (Front)：** 請對齊「**連續性 UI 裝飾框架的最外圍邊界**」。
       - **實體邊框卡 (Front)：** 直接對齊實體印製外框。
       - **航海王卡背 (Back)：** 請對齊「**深藍色實心外框與內部淺色網格圖騰的交界線**」。
    """)
    
    uploaded_files = st.file_uploader("上傳卡牌圖片 (可同時上傳多張)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    
    if uploaded_files:
        from io import BytesIO
        
        for idx, uploaded_file in enumerate(uploaded_files):
            st.subheader(f"檢測影像 {idx + 1}: {uploaded_file.name}")
            
            # 【重要修正】利用 PIL 進行圖片壓縮與縮放，避免 Base64 字串撐爆 Streamlit iframe
            try:
                img_pil = Image.open(uploaded_file)
                # 限制最大長寬為 1200px，維持高品質濾鏡
                img_pil.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
                
                # 轉存為記憶體中的 JPEG，並壓縮品質
                buffered = BytesIO()
                # 若原本是 RGBA (如 PNG)，先轉為 RGB 才能存為 JPEG
                if img_pil.mode in ("RGBA", "P"):
                    img_pil = img_pil.convert("RGB")
                img_pil.save(buffered, format="JPEG", quality=85)
                
                base64_img = base64.b64encode(buffered.getvalue()).decode("utf-8")
                img_uri = f"data:image/jpeg;base64,{base64_img}"
            except Exception as e:
                st.error(f"圖片解析失敗: {e}")
                continue
            
            # 純前端 HTML/JS 互動畫布模板
            html_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <!-- 【重要修正】改用 cdnjs 來源，且移除 onload 屬性 -->
                <script src="https://cdnjs.cloudflare.com/ajax/libs/opencv.js/4.8.0/opencv.min.js"></script>
                <style>
                    body { font-family: sans-serif; text-align: center; color: #333; margin: 0; padding: 10px; }
                    #canvas-container { display: inline-block; position: relative; margin-top: 10px; }
                    canvas { border: 2px dashed #999; max-width: 100%; height: auto; touch-action: none; cursor: crosshair; }
                    .btn { padding: 12px 24px; font-size: 16px; font-weight: bold; color: white; background-color: #4CAF50; border: none; border-radius: 8px; cursor: pointer; margin: 5px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
                    .btn-reset { background-color: #f44336; }
                    .btn:active { transform: translateY(2px); box-shadow: none; }
                    #status { font-weight: bold; font-size: 18px; margin: 5px 0; }
                    #result-text { font-size: 16px; margin: 5px 0; font-family: monospace; }
                </style>
            </head>
            <body>
                <h3 id="msg">🚀 影像處理引擎載入中...</h3>
                <p id="sub-msg">(若卡住超過 10 秒，請重整網頁)</p>
                
                <button id="btn-next" class="btn" style="display:none;">✅ 確認外框 (進行透視拉平)</button>
                <button id="btn-reset" class="btn btn-reset" style="display:none;">🔄 重新校正外框</button>
                
                <div id="result-area" style="display:none; background:#f1f8e9; border:1px solid #c5e1a5; border-radius:8px; padding:10px; margin:10px auto; max-width:600px;">
                    <div id="result-text">L/R: -- | T/B: --</div>
                    <div id="status"></div>
                </div>

                <div id="canvas-container">
                    <canvas id="canvas"></canvas>
                </div>

                <script>
                    const imgUri = "___IMG_URI___";
                    const canvas = document.getElementById('canvas');
                    const ctx = canvas.getContext('2d');
                    
                    let phase = 0; 
                    let img = new Image();
                    let imgCanvas = document.createElement('canvas');
                    let warpedCanvas = document.createElement('canvas');
                    
                    let corners = [];
                    let lines = {};
                    let dragObj = null;

                    // 【重要修正】強制作動的輪詢機制 (Polling)
                    function waitForOpenCV() {
                        try {
                            // 檢查 cv 是否存在，且核心函式是否已經載入完成
                            if (typeof cv !== 'undefined' && typeof cv.Mat !== 'undefined') {
                                document.getElementById('msg').innerText = "✅ 引擎載入成功，準備圖片...";
                                initApp();
                            } else {
                                // 若未載入，0.5 秒後再檢查一次
                                setTimeout(waitForOpenCV, 500);
                            }
                        } catch (e) {
                            setTimeout(waitForOpenCV, 500);
                        }
                    }

                    function initApp() {
                        if(phase !== 0) return; // 避免重複執行
                        
                        img.src = imgUri;
                        img.onload = () => {
                            try {
                                const maxW = window.innerWidth * 0.9;
                                const maxH = window.innerHeight * 0.7;
                                const scale = Math.min(maxW / img.width, maxH / img.height, 1);
                                
                                imgCanvas.width = img.width * scale;
                                imgCanvas.height = img.height * scale;
                                imgCanvas.getContext('2d').drawImage(img, 0, 0, imgCanvas.width, imgCanvas.height);
                                
                                canvas.width = imgCanvas.width;
                                canvas.height = imgCanvas.height;

                                let w = canvas.width, h = canvas.height;
                                let ix = w * 0.1, iy = h * 0.1;
                                corners = [
                                    {x: ix, y: iy}, {x: w - ix, y: iy}, 
                                    {x: w - ix, y: h - iy}, {x: ix, y: h - iy}
                                ];

                                phase = 1;
                                document.getElementById('msg').innerText = "📍 第一階段：拉動四個藍點，對齊卡牌「物理最外邊框」";
                                document.getElementById('sub-msg').innerText = "這能修正拍照透視傾斜 (轉換為標準 630x880 比例)";
                                document.getElementById('btn-next').style.display = "inline-block";
                                
                                draw();
                            } catch (err) {
                                document.getElementById('msg').innerText = "❌ 圖片渲染失敗";
                                document.getElementById('sub-msg').innerText = err.message;
                            }
                        };
                    }

                    function draw() {
                        ctx.clearRect(0, 0, canvas.width, canvas.height);

                        if (phase === 1) {
                            ctx.drawImage(imgCanvas, 0, 0);
                            ctx.beginPath();
                            ctx.moveTo(corners[0].x, corners[0].y);
                            for(let i=1; i<4; i++) ctx.lineTo(corners[i].x, corners[i].y);
                            ctx.closePath();
                            ctx.lineWidth = 2; ctx.strokeStyle = '#00BFFF'; ctx.stroke();

                            ctx.fillStyle = 'rgba(0, 191, 255, 0.6)';
                            corners.forEach(c => {
                                ctx.beginPath(); ctx.arc(c.x, c.y, 12, 0, Math.PI * 2);
                                ctx.fill(); ctx.stroke();
                            });
                        } 
                        else if (phase === 2) {
                            ctx.drawImage(warpedCanvas, 0, 0);
                            ctx.lineWidth = 3; ctx.strokeStyle = '#FF2A2A';
                            ctx.beginPath(); ctx.moveTo(lines.lx, 0); ctx.lineTo(lines.lx, canvas.height); ctx.stroke();
                            ctx.beginPath(); ctx.moveTo(lines.rx, 0); ctx.lineTo(lines.rx, canvas.height); ctx.stroke();
                            ctx.beginPath(); ctx.moveTo(0, lines.ty); ctx.lineTo(canvas.width, lines.ty); ctx.stroke();
                            ctx.beginPath(); ctx.moveTo(0, lines.by); ctx.lineTo(canvas.width, lines.by); ctx.stroke();

                            calculateResult();
                        }
                    }

                    document.getElementById('btn-next').onclick = () => {
                        try {
                            let src = cv.imread(imgCanvas);
                            let dst = new cv.Mat();
                            
                            let srcTri = cv.matFromArray(4, 1, cv.CV_32FC2, [
                                corners[0].x, corners[0].y, corners[1].x, corners[1].y,
                                corners[2].x, corners[2].y, corners[3].x, corners[3].y
                            ]);

                            let cardW = 504, cardH = 704;
                            let dstTri = cv.matFromArray(4, 1, cv.CV_32FC2, [
                                0, 0, cardW, 0, cardW, cardH, 0, cardH
                            ]);

                            let M = cv.getPerspectiveTransform(srcTri, dstTri);
                            cv.warpPerspective(src, dst, M, new cv.Size(cardW, cardH));

                            warpedCanvas.width = cardW; warpedCanvas.height = cardH;
                            cv.imshow(warpedCanvas, dst);
                            
                            src.delete(); dst.delete(); M.delete(); srcTri.delete(); dstTri.delete();

                            canvas.width = cardW; canvas.height = cardH;
                            
                            lines = { lx: cardW*0.05, rx: cardW*0.95, ty: cardH*0.05, by: cardH*0.95 };
                            
                            phase = 2;
                            document.getElementById('btn-next').style.display = 'none';
                            document.getElementById('btn-reset').style.display = 'inline-block';
                            document.getElementById('result-area').style.display = 'block';
                            document.getElementById('msg').innerText = "📍 第二階段：拖動四條紅線，對齊「測量錨點 (Bounding Box)」";
                            document.getElementById('sub-msg').innerHTML = "實體邊框對齊實心印製線；無邊框對齊裝飾外緣。TAG Pristine 10 嚴格標準為 <strong>&lt; 51/49</strong>";
                            draw();
                        } catch (err) {
                            alert("變形運算發生錯誤，請確認四個藍點是否形成交叉或異常形狀。\\n" + err.message);
                        }
                    };

                    document.getElementById('btn-reset').onclick = () => {
                        phase = 1;
                        canvas.width = imgCanvas.width; canvas.height = imgCanvas.height;
                        document.getElementById('btn-next').style.display = 'inline-block';
                        document.getElementById('btn-reset').style.display = 'none';
                        document.getElementById('result-area').style.display = 'none';
                        document.getElementById('msg').innerText = "📍 第一階段：拉動四個藍點，對齊卡牌「物理最外邊框」";
                        document.getElementById('sub-msg').innerText = "這能修正拍照透視傾斜 (轉換為標準 630x880 比例)";
                        draw();
                    };

                    function calculateResult() {
                        let leftM = lines.lx;
                        let rightM = canvas.width - lines.rx;
                        let topM = lines.ty;
                        let bottomM = canvas.height - lines.by;

                        let lr = (leftM / (leftM + rightM)) * 100 || 50;
                        let tb = (topM / (topM + bottomM)) * 100 || 50;

                        document.getElementById('result-text').innerText = 
                            `左右置中 (L/R): ${lr.toFixed(2)} / ${(100-lr).toFixed(2)} | 上下置中 (T/B): ${tb.toFixed(2)} / ${(100-tb).toFixed(2)}`;

                        let lrMax = Math.max(lr, 100 - lr);
                        let tbMax = Math.max(tb, 100 - tb);
                        let worstRatio = Math.max(lrMax, tbMax);
                        
                        let stat = document.getElementById('status');
                        
                        if (worstRatio <= 50.00) {
                            stat.innerHTML = "🏆 判定：BGS 10 黑標 (極致完美 50/50)";
                            stat.style.color = "#d4af37"; 
                        } else if (worstRatio < 51.00) {
                            stat.innerHTML = "✨ 判定：TAG 10 Pristine / CGC 10 Pristine (符合 < 51/49 嚴格邊界標準)";
                            stat.style.color = "#2e7d32";
                        } else if (worstRatio <= 55.00) {
                            stat.innerHTML = "✅ 判定：PSA 10 Gem Mint / BGS 9.5 (符合 <= 55/45 標準)";
                            stat.style.color = "#1565c0";
                        } else if (worstRatio <= 60.00) {
                            stat.innerHTML = "⚠️ 判定：符合 PSA 10 寬容極限 (最寬 60/40) 或卡背標準";
                            stat.style.color = "#ff9800";
                        } else {
                            stat.innerHTML = "❌ 判定：未達 Gem Mint 置中要求 (超過 60/40 極限)";
                            stat.style.color = "#d32f2f";
                        }
                    }

                    function getPos(e) {
                        let rect = canvas.getBoundingClientRect();
                        let clientX = e.touches ? e.touches[0].clientX : e.clientX;
                        let clientY = e.touches ? e.touches[0].clientY : e.clientY;
                        return {
                            x: (clientX - rect.left) * (canvas.width / rect.width),
                            y: (clientY - rect.top) * (canvas.height / rect.height)
                        };
                    }

                    function onDown(e) {
                        let {x, y} = getPos(e);
                        dragObj = null;
                        if (phase === 1) {
                            for (let i=0; i<4; i++) {
                                if (Math.hypot(x - corners[i].x, y - corners[i].y) < 30) {
                                    dragObj = i; break;
                                }
                            }
                        } else if (phase === 2) {
                            let t = 20;
                            if (Math.abs(x - lines.lx) < t) dragObj = 'lx';
                            else if (Math.abs(x - lines.rx) < t) dragObj = 'rx';
                            else if (Math.abs(y - lines.ty) < t) dragObj = 'ty';
                            else if (Math.abs(y - lines.by) < t) dragObj = 'by';
                        }
                        if (dragObj !== null && e.cancelable) e.preventDefault();
                    }

                    function onMove(e) {
                        if (dragObj === null) return;
                        let {x, y} = getPos(e);
                        if (phase === 1) {
                            corners[dragObj].x = x; corners[dragObj].y = y;
                        } else if (phase === 2) {
                            if (dragObj === 'lx') lines.lx = Math.max(0, Math.min(x, lines.rx - 10));
                            if (dragObj === 'rx') lines.rx = Math.min(canvas.width, Math.max(x, lines.lx + 10));
                            if (dragObj === 'ty') lines.ty = Math.max(0, Math.min(y, lines.by - 10));
                            if (dragObj === 'by') lines.by = Math.min(canvas.height, Math.max(y, lines.ty + 10));
                        }
                        draw();
                        if (e.cancelable) e.preventDefault();
                    }

                    function onUp() { dragObj = null; }

                    canvas.addEventListener('mousedown', onDown);
                    canvas.addEventListener('mousemove', onMove);
                    window.addEventListener('mouseup', onUp);
                    canvas.addEventListener('touchstart', onDown, {passive: false});
                    canvas.addEventListener('touchmove', onMove, {passive: false});
                    window.addEventListener('touchend', onUp);
                    
                    // 啟動輪詢機制
                    waitForOpenCV();
                </script>
            </body>
            </html>
            """
            
            html_code = html_template.replace("___IMG_URI___", img_uri)
            # iframe 高度設為 900，提供充足的繪圖空間
            components.html(html_code, height=900)
        html_code = html_template.replace("___IMG_URI___", img_uri)
        components.html(html_code, height=1000)
