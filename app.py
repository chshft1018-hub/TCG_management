import asyncio
import base64
from io import BytesIO

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageOps

from scraper import (get_chart_data, analyze_data, get_product_name,
                     get_psa_pop_from_cert_url, calculate_investment_metrics,
                     create_combined_chart)
from app_utils import update_google_sheet, load_google_sheet

st.set_page_config(page_title="卡牌投資管理", layout="wide")

# ---------------------------------------------------------------- 常數
RAW_ID = 18      # 一般品(裸卡)走勢
PSA10_ID = 22    # PSA 10 走勢
MAX_IMG = 1280   # 置中檢測圖片長邊上限(越大越精準，但傳輸越大)
PAGES = ["首頁", "卡牌分析", "投資分析", "PSA 查詢", "置中檢測", "卡牌庫"]


# ---------------------------------------------------------------- 工具函式
def safe_load_library():
    """讀取 Google Sheet；失敗時回傳空 list，避免整個 App 無法啟動。"""
    try:
        data = load_google_sheet()
        if isinstance(data, pd.DataFrame):
            return data.to_dict("records")
        return list(data) if data else []
    except Exception as e:
        st.warning(f"無法讀取 Google Sheets：{e}")
        return []


async def fetch_all(product_id):
    # 三個請求並行，比循序執行快
    return await asyncio.gather(
        get_chart_data(product_id, RAW_ID),
        get_chart_data(product_id, PSA10_ID),
        get_product_name(product_id),
    )


@st.cache_data(show_spinner=False)
def image_to_data_uri(file_bytes: bytes) -> str:
    """修正手機照片 EXIF 旋轉、轉 RGB、縮圖、轉 base64。結果會被快取，rerun 不會重算。"""
    img = Image.open(BytesIO(file_bytes))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((MAX_IMG, MAX_IMG), Image.Resampling.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


def navigate_to(page_name):
    st.session_state["current_page"] = page_name


# ---------------------------------------------------------------- 置中檢測 HTML
CENTERING_HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<style>
  body { font-family: 'Segoe UI', sans-serif; background:#050505; color:#e0e0e0; margin:0;
         display:flex; flex-direction:column; align-items:center; min-height:100vh;
         overscroll-behavior:none; user-select:none; }
  .controls { position:sticky; top:0; z-index:100; background:#1a1a1a; width:100%; padding:12px 0;
              box-shadow:0 4px 15px rgba(0,0,0,.7); display:flex; justify-content:center;
              align-items:center; gap:10px; flex-wrap:wrap; }
  .btn { padding:8px 16px; border:none; border-radius:20px; font-weight:bold; cursor:pointer;
         transition:.2s; font-size:14px; white-space:nowrap; }
  .btn:active { transform:scale(.95); }
  .btn-blue { background:#00bcd4; color:#000; }
  .btn-purple { background:linear-gradient(135deg,#7c4dff,#b388ff); color:#fff; border:1px solid #999; }
  .btn-cyan { background:linear-gradient(135deg,#00e5ff,#00b8d4); color:#000; }
  .btn-gray { background:#424242; color:#fff; }

  #workspace { position:relative; margin:15px auto; box-shadow:0 0 30px rgba(0,0,0,.5);
               font-size:0; touch-action:none; max-width:98vw; border:1px solid #333; overflow:hidden;
               background-color:#000; }
  canvas { display:block; width:100%; height:auto; }
  #overlay { position:absolute; inset:0; pointer-events:none; }

  .control-point { position:absolute; width:44px; height:44px; transform:translate(-50%,-50%);
                   cursor:crosshair; pointer-events:auto; z-index:20; touch-action:none;
                   display:flex; align-items:center; justify-content:center; }
  .control-point::before { content:''; width:14px; height:14px; background:rgba(255,60,60,.5);
                           border:2px solid #fff; border-radius:50%; box-shadow:0 0 5px #000; }

  .guide-line { position:absolute; pointer-events:auto; z-index:10; touch-action:none; }
  .guide-line::after { content:''; position:absolute; background:transparent; z-index:11; }
  .line-h { width:100%; left:0; cursor:ns-resize; } .line-h::after { top:-20px; bottom:-20px; left:0; right:0; }
  .line-v { height:100%; top:0; cursor:ew-resize; } .line-v::after { left:-20px; right:-20px; top:0; bottom:0; }
  .outer-style.line-h { height:1px; background:#ff5252; } .outer-style.line-v { width:1px; background:#ff5252; }
  .inner-style.line-h { height:0; border-top:1px dashed #00e5ff; } .inner-style.line-v { width:0; border-left:1px dashed #00e5ff; }

  #result-panel { display:none; width:90%; max-width:500px; background:#1a1a1a; border-radius:12px;
                  padding:15px; margin:20px 0; grid-template-columns:1fr 1fr; gap:15px; }
  .score-card { background:#252525; padding:10px; border-radius:8px; text-align:center; border:1px solid #333; }
  .score-val { font-size:20px; font-weight:bold; color:#fff; font-family:monospace; margin:5px 0; }
  .badge { display:inline-block; padding:4px 8px; border-radius:4px; font-size:12px; font-weight:bold; color:#000; }
  #status-msg { color:#888; margin:10px; font-size:14px; min-height:20px; }
  #loading { color:#00bcd4; margin-top:50px; font-weight:bold; line-height:1.6; text-align:center; }
</style>
</head>
<body>
<div id="loading">⏳ 圖片接收中...</div>

<div id="main-ui" style="display:none; width:100%; flex-direction:column; align-items:center;">
  <div class="controls">
    <button id="autoBtnStep1" class="btn btn-purple" onclick="runFocusDetect()">✨ Auto Detect</button>
    <button id="nextBtn" class="btn btn-blue" onclick="processWarp()">Next</button>
    <button id="autoBtnStep2" class="btn btn-cyan" onclick="runAutoDetectInner()">⚡ Align Inner</button>
    <button id="resetBtn" class="btn btn-gray" onclick="resetAll()">Reset</button>
  </div>
  <div id="status-msg">Ready</div>
  <div id="workspace"><canvas id="cvCanvas"></canvas><div id="overlay"></div></div>
  <div id="result-panel">
    <div class="score-card"><div style="color:#aaa;font-size:12px">Left / Right</div>
      <div id="val-lr" class="score-val">--</div><div id="bdg-lr" class="badge">--</div></div>
    <div class="score-card"><div style="color:#aaa;font-size:12px">Top / Bottom</div>
      <div id="val-tb" class="score-val">--</div><div id="bdg-tb" class="badge">--</div></div>
  </div>
</div>

<script>
const imgUri = "___IMG_URI___";
const MAX = ___MAX___;
const PADDING_RATIO = 0.05;
// 依序嘗試的 OpenCV.js 來源（前一個失敗會自動換下一個）
const CV_URLS = [
  "https://docs.opencv.org/4.8.0/opencv.js",
  "https://cdnjs.cloudflare.com/ajax/libs/opencv.js/4.8.0/opencv.min.js"
];

const $ = (id) => document.getElementById(id);
const canvas = $('cvCanvas'), overlay = $('overlay');
const clamp = (v) => Math.max(0, Math.min(1, v));

let imgMat = null, warpedMat = null, srcCanvas = null, currentStep = 0, started = false;
let cvLoadFailed = false, manualAdjusted = false;
let corners = [];
let guides = { outL:0, outR:1, outT:0, outB:1, inL:.1, inR:.9, inT:.1, inB:.9 };

function setStatus(msg, color) { const s = $('status-msg'); s.innerText = msg; s.style.color = color || '#888'; }
function loadingMsg(html) { $('loading').innerHTML = html; }

/* ---------- 載入流程：先顯示圖片，再載入 OpenCV ---------- */
const img = new Image();
img.onload = () => {
  $('loading').style.display = 'none';
  $('main-ui').style.display = 'flex';
  setupImage(img);
  loadCv(0);
  waitCv();
};
img.onerror = () => loadingMsg("❌ 圖片解析失敗，請確認圖片格式。");
img.src = imgUri;

function loadCv(i) {
  if (i >= CV_URLS.length) {
    cvLoadFailed = true;
    setStatus("⚠️ OpenCV 無法載入；可手動調整角點並繼續下一步。", "#ff9800");
    return;
  }
  const s = document.createElement('script');
  s.async = true; s.src = CV_URLS[i];
  s.onerror = () => {
    s.remove();
    if (i + 1 < CV_URLS.length) loadCv(i + 1);
    else {
      cvLoadFailed = true;
      setStatus("⚠️ OpenCV 無法載入；可手動調整角點並繼續下一步。", "#ff9800");
    }
  };
  document.head.appendChild(s);
}

let polls = 0;
function waitCv() {
  if (cvLoadFailed) return;
  if (typeof cv !== 'undefined') {
    if (cv.Mat) return onReady();
    // 部分 OpenCV.js 版本的 cv 是 Promise
    if (typeof cv.then === 'function' && !cv.__waiting) {
      cv.__waiting = true;
      cv.then((m) => { window.cv = m; onReady(); });
    }
  }
  if (++polls > 300) {
    setStatus("⚠️ OpenCV 載入逾時；可手動調整角點並繼續下一步。", "#ff9800");
    return;
  }
  setTimeout(waitCv, 200);
}

function onReady() {
  if (started) return; started = true;
  try {
    const sctx = srcCanvas.getContext('2d');
    imgMat = cv.matFromImageData(sctx.getImageData(0, 0, srcCanvas.width, srcCanvas.height));
    if (currentStep === 0 && !manualAdjusted) {
      setStatus("✅ OpenCV 已載入，正在自動偵測卡片…", "#b388ff");
      setTimeout(runFocusDetect, 100);
    } else if (currentStep === 0) {
      setStatus("✅ OpenCV 已載入，保留手動調整的角點。", "#00e676");
    }
  } catch (e) {
    console.error(e);
    setStatus("⚠️ OpenCV 初始化失敗；仍可手動調整角點並繼續。", "#ff9800");
  }
}

/* ---------- 影像初始化 ---------- */
function setupImage(im) {
  let w = im.naturalWidth, h = im.naturalHeight;
  if (w > MAX || h > MAX) { const r = Math.min(MAX / w, MAX / h); w = Math.floor(w * r); h = Math.floor(h * r); }
  srcCanvas = document.createElement('canvas');
  srcCanvas.width = w; srcCanvas.height = h;
  const sctx = srcCanvas.getContext('2d');
  sctx.drawImage(im, 0, 0, w, h);
  imgMat = (typeof cv !== 'undefined' && cv.Mat && cv.matFromImageData)
    ? cv.matFromImageData(sctx.getImageData(0, 0, w, h)) : null;

  corners = [{x:w*.2,y:h*.2,label:'TL'},{x:w*.8,y:h*.2,label:'TR'},{x:w*.8,y:h*.8,label:'BR'},{x:w*.2,y:h*.8,label:'BL'}];
  showBase();
  currentStep = 0;
  updateUI(); renderOverlay();
  if (imgMat) setTimeout(runFocusDetect, 100);
  else setStatus("✅ 圖片已載入；拖曳紅點框住卡片後，按 Next 繼續。", "#00e676");
}

function showBase() {
  canvas.width = srcCanvas.width; canvas.height = srcCanvas.height;
  canvas.getContext('2d').drawImage(srcCanvas, 0, 0);
}

/* ---------- Step 1：偵測卡片外緣 ---------- */
function runFocusDetect() {
  if (!imgMat) {
    setStatus("⚠️ 自動偵測尚不可用；請手動調整四個紅點。", "#ff9800");
    return;
  }
  setStatus("🔍 Scanning...", "#b388ff");
  let srcROI, gray, blurred, edges, contours, hierarchy, kernel, bestCnt = null;
  try {
    const marginX = Math.floor(imgMat.cols * 0.12), marginY = Math.floor(imgMat.rows * 0.12);
    const roiW = imgMat.cols - 2 * marginX, roiH = imgMat.rows - 2 * marginY;
    srcROI = imgMat.roi(new cv.Rect(marginX, marginY, roiW, roiH));
    gray = new cv.Mat(); blurred = new cv.Mat(); edges = new cv.Mat();
    contours = new cv.MatVector(); hierarchy = new cv.Mat();

    cv.cvtColor(srcROI, gray, cv.COLOR_RGBA2GRAY, 0);
    cv.GaussianBlur(gray, blurred, new cv.Size(5, 5), 0);
    cv.Canny(blurred, edges, 50, 150);
    kernel = cv.getStructuringElement(cv.MORPH_RECT, new cv.Size(5, 5));
    cv.morphologyEx(edges, edges, cv.MORPH_CLOSE, kernel);
    cv.findContours(edges, contours, hierarchy, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE);

    let maxArea = 0;
    const minArea = roiW * roiH * 0.20;
    for (let i = 0; i < contours.size(); ++i) {
      const cnt = contours.get(i);
      const area = cv.contourArea(cnt);
      if (area > maxArea && area > minArea) {
        if (bestCnt) bestCnt.delete();   // 修正：舊的最佳輪廓要釋放，避免記憶體洩漏
        maxArea = area; bestCnt = cnt;
      } else { cnt.delete(); }
    }

    if (bestCnt) {
      const pts = bestCnt.data32S, n = pts.length / 2;
      let tl = {v:Infinity}, br = {v:-Infinity}, tr = {v:-Infinity}, bl = {v:Infinity};
      for (let i = 0; i < n; i++) {
        const x = pts[i*2], y = pts[i*2+1], sum = x + y, diff = x - y;
        if (sum < tl.v) tl = {v:sum, x, y};
        if (sum > br.v) br = {v:sum, x, y};
        if (diff > tr.v) tr = {v:diff, x, y};
        if (diff < bl.v) bl = {v:diff, x, y};
      }
      corners = [
        {x: tl.x + marginX, y: tl.y + marginY, label:'TL'}, {x: tr.x + marginX, y: tr.y + marginY, label:'TR'},
        {x: br.x + marginX, y: br.y + marginY, label:'BR'}, {x: bl.x + marginX, y: bl.y + marginY, label:'BL'}
      ];
      setStatus("✅ Card Detected（可手動微調四角）", "#00e676");
    } else {
      setStatus("⚠️ 未偵測到卡片，請手動拖曳四個角", "#ff5252");
    }
    renderOverlay();
  } catch (e) {
    console.error(e); setStatus("⚠️ 偵測失敗，請手動調整", "#ff5252");
  } finally {
    [srcROI, gray, blurred, edges, contours, hierarchy, kernel, bestCnt].forEach(m => { if (m) m.delete(); });
  }
}

/* ---------- OpenCV 無法載入時的 Canvas 透視校正 ---------- */
function solveLinearSystem(a, b) {
  const n = b.length;
  for (let col = 0; col < n; col++) {
    let pivot = col;
    for (let row = col + 1; row < n; row++)
      if (Math.abs(a[row][col]) > Math.abs(a[pivot][col])) pivot = row;
    if (Math.abs(a[pivot][col]) < 1e-12) return null;
    [a[col], a[pivot]] = [a[pivot], a[col]];
    [b[col], b[pivot]] = [b[pivot], b[col]];
    const scale = a[col][col];
    for (let j = col; j < n; j++) a[col][j] /= scale;
    b[col] /= scale;
    for (let row = 0; row < n; row++) {
      if (row === col) continue;
      const factor = a[row][col];
      for (let j = col; j < n; j++) a[row][j] -= factor * a[col][j];
      b[row] -= factor * b[col];
    }
  }
  return b;
}

function drawPerspectiveFallback(source, quad, dstW, dstH, mx, my) {
  const dstPts = [[mx, my], [dstW - mx, my], [dstW - mx, dstH - my], [mx, dstH - my]];
  const a = [], b = [];
  for (let i = 0; i < 4; i++) {
    const x = dstPts[i][0], y = dstPts[i][1], u = quad[i].x, v = quad[i].y;
    a.push([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.push(u);
    a.push([0, 0, 0, x, y, 1, -v * x, -v * y]); b.push(v);
  }
  const h = solveLinearSystem(a, b);
  if (!h) throw new Error("無法計算透視轉換");

  const srcCtx = source.getContext('2d');
  const src = srcCtx.getImageData(0, 0, source.width, source.height);
  canvas.width = dstW; canvas.height = dstH;
  const ctx = canvas.getContext('2d');
  const out = ctx.createImageData(dstW, dstH);
  for (let y = 0; y < dstH; y++) {
    for (let x = 0; x < dstW; x++) {
      const denom = h[6] * x + h[7] * y + 1;
      if (Math.abs(denom) < 1e-12) continue;
      const sx = Math.round((h[0] * x + h[1] * y + h[2]) / denom);
      const sy = Math.round((h[3] * x + h[4] * y + h[5]) / denom);
      if (sx < 0 || sy < 0 || sx >= source.width || sy >= source.height) continue;
      const si = (sy * source.width + sx) * 4, di = (y * dstW + x) * 4;
      out.data[di] = src.data[si]; out.data[di + 1] = src.data[si + 1];
      out.data[di + 2] = src.data[si + 2]; out.data[di + 3] = src.data[si + 3];
    }
  }
  ctx.putImageData(out, 0, 0);
}

/* ---------- 透視校正 ---------- */
function processWarp() {
  if (!srcCanvas) return;
  let srcPts, dstPts, M;
  try {
    const d = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
    const cardW = Math.max(d(corners[0], corners[1]), d(corners[3], corners[2]));
    const cardH = Math.max(d(corners[0], corners[3]), d(corners[1], corners[2]));
    if (cardW < 20 || cardH < 20) { alert("四個角點太靠近，請重新調整。"); return; }

    const mx = cardW * PADDING_RATIO, my = cardH * PADDING_RATIO;
    const dstW = Math.round(cardW + 2 * mx), dstH = Math.round(cardH + 2 * my);

    if (imgMat && typeof cv !== 'undefined') {
      srcPts = cv.matFromArray(4, 1, cv.CV_32FC2, corners.flatMap(c => [c.x, c.y]));
      dstPts = cv.matFromArray(4, 1, cv.CV_32FC2, [mx, my, dstW - mx, my, dstW - mx, dstH - my, mx, dstH - my]);
      M = cv.getPerspectiveTransform(srcPts, dstPts);
      if (warpedMat) warpedMat.delete();
      warpedMat = new cv.Mat();
      cv.warpPerspective(imgMat, warpedMat, M, new cv.Size(dstW, dstH), cv.INTER_LINEAR,
                         cv.BORDER_CONSTANT, new cv.Scalar(0, 0, 0, 255));
      cv.imshow('cvCanvas', warpedMat);
    } else {
      if (warpedMat) { warpedMat.delete(); warpedMat = null; }
      drawPerspectiveFallback(srcCanvas, corners, dstW, dstH, mx, my);
    }

    currentStep = 1;
    guides.outL = mx / dstW; guides.outR = (dstW - mx) / dstW;
    guides.outT = my / dstH; guides.outB = (dstH - my) / dstH;
    // 修正：內框預設位置以「卡片尺寸」為基準，而非整張影像
    const cw = guides.outR - guides.outL, ch = guides.outB - guides.outT;
    guides.inT = guides.outT + 0.088 * ch; guides.inB = guides.outT + 0.915 * ch;
    guides.inL = guides.outL + 0.08 * cw;  guides.inR = guides.outR - 0.08 * cw;

    updateUI(); renderOverlay();
  } catch (err) {
    console.error(err); alert("透視校正失敗：請確認四個紅點位置是否正確。");
  } finally {
    [srcPts, dstPts, M].forEach(m => { if (m) m.delete(); });
  }
}

/* ---------- Step 2：自動對齊內框 ---------- */
function runAutoDetectInner() {
  if (!warpedMat || typeof cv === 'undefined') {
    setStatus("⚠️ 自動內框對齊需要 OpenCV；請手動拖曳青色虛線。", "#ff9800");
    return;
  }
  setStatus("⚡ Aligning Inner Frame...", "#00e5ff");
  let gray, edges;
  try {
    gray = new cv.Mat(); edges = new cv.Mat();
    cv.cvtColor(warpedMat, gray, cv.COLOR_RGBA2GRAY, 0);
    cv.Canny(gray, edges, 50, 150);
    const W = warpedMat.cols, H = warpedMat.rows, E = edges.data;   // 直接讀 data，比 ucharPtr 快很多

    function strongest(isV, a, b) {
      const o0 = isV ? guides.outL * W : guides.outT * H;
      const size = isV ? (guides.outR - guides.outL) * W : (guides.outB - guides.outT) * H;
      const s = Math.floor(o0 + size * a), e = Math.floor(o0 + size * b);
      const j0 = Math.floor(isV ? guides.outT * H : guides.outL * W);
      const j1 = Math.floor(isV ? guides.outB * H : guides.outR * W);
      let best = -1, max = 0;
      for (let i = s; i < e; i++) {
        let score = 0;
        for (let j = j0; j < j1; j++) if (E[isV ? j * W + i : i * W + j] > 200) score++;
        if (score > max) { max = score; best = i; }
      }
      return max > (j1 - j0) * 0.05 ? best : null;   // 至少要有 5% 長度是邊緣才採用
    }

    const l = strongest(true, .06, .10);  if (l !== null) guides.inL = l / W;
    const r = strongest(true, .90, .94);  if (r !== null) guides.inR = r / W;
    const t = strongest(false, .06, .12); if (t !== null) guides.inT = t / H;
    const b = strongest(false, .88, .93); if (b !== null) guides.inB = b / H;

    renderOverlay();
    setStatus("⚡ Aligned（請再手動微調青色虛線）", "#00e5ff");
  } catch (e) { console.error(e); }
  finally { [gray, edges].forEach(m => { if (m) m.delete(); }); }
}

/* ---------- Overlay（全部用百分比定位，視窗縮放不會跑掉） ---------- */
function renderOverlay() {
  overlay.innerHTML = '';
  if (currentStep === 0) {
    corners.forEach((pt, idx) => {
      const el = document.createElement('div');
      el.className = 'control-point';
      el.style.left = (pt.x / canvas.width * 100) + '%';
      el.style.top = (pt.y / canvas.height * 100) + '%';
      bindDrag(el, (fx, fy) => { corners[idx].x = fx * canvas.width; corners[idx].y = fy * canvas.height; drawPoly(); });
      overlay.appendChild(el);
    });
    drawPoly();
  } else {
    [['h','outT','outer'],['h','inT','inner'],['h','inB','inner'],['h','outB','outer'],
     ['v','outL','outer'],['v','inL','inner'],['v','inR','inner'],['v','outR','outer']]
      .forEach(([dir, key, style]) => {
        const el = document.createElement('div');
        el.className = `guide-line line-${dir} ${style}-style`;
        if (dir === 'h') el.style.top = (guides[key] * 100) + '%'; else el.style.left = (guides[key] * 100) + '%';
        bindDrag(el, (fx, fy) => { guides[key] = dir === 'h' ? fy : fx; calc(); });
        overlay.appendChild(el);
      });
    calc();
  }
}

function drawPoly() {
  if (!srcCanvas || currentStep !== 0) return;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(srcCanvas, 0, 0);          // 修正：用離屏 canvas 重繪，不再每次拖曳都呼叫 cv.imshow
  const r = canvas.getBoundingClientRect();
  const s = r.width ? canvas.width / r.width : 1;
  ctx.beginPath(); ctx.lineWidth = 2 * s; ctx.strokeStyle = '#ff5252';
  ctx.moveTo(corners[0].x, corners[0].y);
  for (let i = 1; i < 4; i++) ctx.lineTo(corners[i].x, corners[i].y);
  ctx.closePath(); ctx.stroke();
}

// 修正：改用 Pointer Events + setPointerCapture，滑鼠移出 iframe 也不會卡住拖曳；
// 座標以 canvas 為基準（原本用 workspace，含 1px 邊框會有偏移）
function bindDrag(el, onMove) {
  el.addEventListener('pointerdown', (e) => {
    e.preventDefault(); e.stopPropagation();
    manualAdjusted = true;
    el.setPointerCapture(e.pointerId);
    const move = (ev) => {
      const r = canvas.getBoundingClientRect();
      const fx = clamp((ev.clientX - r.left) / r.width), fy = clamp((ev.clientY - r.top) / r.height);
      if (el.classList.contains('line-h')) el.style.top = (fy * 100) + '%';
      else if (el.classList.contains('line-v')) el.style.left = (fx * 100) + '%';
      else { el.style.left = (fx * 100) + '%'; el.style.top = (fy * 100) + '%'; }
      onMove(fx, fy);
    };
    const end = () => {
      el.removeEventListener('pointermove', move);
      el.removeEventListener('pointerup', end);
      el.removeEventListener('pointercancel', end);
    };
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerup', end);
    el.addEventListener('pointercancel', end);
  });
}

/* ---------- 計分（參考用門檻，非官方標準） ---------- */
function calc() {
  const l = guides.inL - guides.outL, r = guides.outR - guides.inR;
  const t = guides.inT - guides.outT, b = guides.outB - guides.inB;
  const sW = (l + r) || 0.001, sH = (t + b) || 0.001;
  setScore('lr', (l / sW) * 100, (r / sW) * 100);
  setScore('tb', (t / sH) * 100, (b / sH) * 100);
}

function setScore(id, v1, v2) {
  const val = $('val-' + id), bdg = $('bdg-' + id);
  if (v1 < 0 || v2 < 0) { val.innerText = '--'; bdg.innerText = '線位置無效'; bdg.style.background = '#555'; bdg.style.color = '#fff'; return; }
  val.innerText = `${v1.toFixed(2)} / ${v2.toFixed(2)}`;
  const w = Math.max(v1, v2);
  const set = (txt, bg, fg) => { bdg.innerText = txt; bdg.style.background = bg; bdg.style.color = fg; };
  if (w <= 50.00) set("BGS 10 黑標", "#d4af37", "#000");
  else if (w < 51.00) set("TAG 10 Pristine", "#2e7d32", "#fff");
  else if (w <= 53.00) set("TAG 10 Gem Mint", "#1565c0", "#fff");
  else if (w <= 55.00) set("PSA 10 Gem Mint", "#0288d1", "#fff");
  else if (w <= 60.00) set("PSA 10 (寬容極限)", "#ff9800", "#000");
  else set("未達 Gem Mint", "#d32f2f", "#fff");
}

/* ---------- UI ---------- */
function updateUI() {
  const s0 = currentStep === 0;
  $('autoBtnStep1').style.display = s0 ? 'inline-block' : 'none';
  $('nextBtn').style.display = s0 ? 'inline-block' : 'none';
  $('autoBtnStep2').style.display = s0 ? 'none' : 'inline-block';
  $('resetBtn').style.display = s0 ? 'none' : 'inline-block';
  $('result-panel').style.display = s0 ? 'none' : 'grid';
  if (!s0) setStatus("Step 2：紅線＝外緣，青色虛線＝內框", "#aaa");
}

function resetAll() {
  currentStep = 0;
  showBase(); updateUI(); renderOverlay();
  setStatus("Ready");        // 修正：Reset 後狀態文字不再停留在 Step 2
}

window.addEventListener('resize', () => { if (currentStep === 0) drawPoly(); });
</script>
</body>
</html>
"""


# ---------------------------------------------------------------- Session 初始化
if "card_library" not in st.session_state:
    st.session_state["card_library"] = safe_load_library()
st.session_state.setdefault("last_analysis", None)
st.session_state.setdefault("psa_data", None)
st.session_state.setdefault("current_page", "首頁")

with st.sidebar:
    st.header("功能導航")
    page = st.radio("功能區", PAGES, key="current_page")

# ---------------------------------------------------------------- 1. 首頁
if page == "首頁":
    st.title("卡牌投資管理系統")
    st.write("功能列表：")
    cols = st.columns(5)
    targets = [("📊 前往卡牌分析", "卡牌分析"), ("📈 前往投資分析", "投資分析"),
               ("🛡️ 前往 PSA 查詢", "PSA 查詢"), ("📏 前往置中檢測", "置中檢測"),
               ("📂 前往卡牌庫", "卡牌庫")]
    for col, (label, target) in zip(cols, targets):
        col.button(label, use_container_width=True, on_click=navigate_to, args=(target,))

# ---------------------------------------------------------------- 2. 卡牌分析
elif page == "卡牌分析":
    st.title("📊 卡牌分析中心")
    with st.expander("🔍 搜尋與分析設定", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            search_input = st.text_input("輸入關鍵字 (例如: M2a 223/193)")
            if search_input:
                query = search_input.replace(" ", "+").replace("/", "%2F")
                st.markdown(f"[前往 SNKRDUNK 搜尋](https://snkrdunk.com/search?keywords={query})")
            product_id = st.text_input("商品 ID", value="826553").strip()
        with col2:
            cost = st.number_input("持有成本 (NT$)", value=10000.0, min_value=0.0)
            analyze_btn = st.button("🚀 執行卡牌分析")

    if analyze_btn:
        if not product_id.isdigit():
            st.error("商品 ID 必須是數字。")
        elif cost <= 0:
            st.error("持有成本必須大於 0。")
        else:
            try:
                with st.spinner("正在獲取數據..."):
                    data_A, data_PSA, card_name = asyncio.run(fetch_all(product_id))
                    st.session_state["last_analysis"] = {
                        "name": card_name, "cost": cost,
                        "data_A": data_A, "data_PSA": data_PSA,
                        "m_A": analyze_data(data_A, cost, 0.20),
                        "m_PSA": analyze_data(data_PSA, cost, 0.20),
                    }
            except Exception as e:
                st.error(f"取得資料失敗：{e}")

    res = st.session_state.get("last_analysis")
    if res:
        st.subheader(f"當前分析：{res['name']}")
        latest = (res.get("m_PSA") or {}).get("latest")

        if st.button("💾 存入卡牌庫"):
            if latest is None or res["cost"] <= 0:
                st.error("缺少最新價格或成本，無法計算 ROI。")
            elif any(c.get("名稱") == res["name"] and float(c.get("成本", 0)) == res["cost"]
                     for c in st.session_state["card_library"]):
                st.warning("卡牌庫已有相同名稱與成本的紀錄。")
            else:
                roi = (latest - res["cost"]) / res["cost"] * 100
                new_row = {"名稱": res["name"], "成本": float(res["cost"]), "ROI": f"{roi:.2f}%"}
                try:
                    updated = st.session_state["card_library"] + [new_row]
                    update_google_sheet(updated)
                    st.session_state["card_library"] = safe_load_library()
                    st.success("已同步至 Google Sheets")
                except Exception as e:
                    st.error(f"同步失敗：{e}")

        st.plotly_chart(create_combined_chart(res["data_A"], res["data_PSA"], "走勢比較"),
                        use_container_width=True)

# ---------------------------------------------------------------- 3. 投資分析
elif page == "投資分析":
    st.title("📈 進階投資分析")
    res = st.session_state.get("last_analysis")

    if not res:
        st.info("請先到「卡牌分析」執行一次分析。")
    else:
        metrics = calculate_investment_metrics(res["data_PSA"], res["cost"])
        if not metrics:
            st.warning("數據樣本數不足，無法產生量化預測指標。")
        else:
            st.subheader(f"針對【{res['name']}】之計量策略預測")
            rsi_val = metrics["rsi"]
            preds = metrics["predictions"]

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("60日指數均價 (EMA)", f"NT${metrics['ema_60']:,.0f}")
            current_roi = (metrics["latest"] - res["cost"]) / res["cost"] * 100
            c2.metric("當前 ROI", f"{current_roi:.2f}%")
            c3.metric("當前乖離率", f"{metrics['bias_rate']:.2f}%")
            c4.metric("RSI (14) 市場情緒", f"{rsi_val:.1f}")

            st.markdown("---")
            st.markdown("### 📊 未來 60 天價格走勢預測")
            pred_df = pd.DataFrame(list(preds.items()), columns=["Days", "Predicted_Price"])
            fig_pred = go.Figure(go.Scatter(
                x=pred_df["Days"], y=pred_df["Predicted_Price"],
                mode="lines+markers+text",
                text=[f"NT${p:,.0f}" if d in (0, 15, 60) else ""
                      for d, p in zip(pred_df["Days"], pred_df["Predicted_Price"])],
                textposition="top center",
                line=dict(color="#9C27B0", width=3, shape="spline"),
                marker=dict(size=8, color="#9C27B0"),
                hovertemplate="預測價格: NT$%{y:,.0f}<extra></extra>",
            ))
            fig_pred.update_layout(
                # 修正：原本同時傳 xaxis_title 與 xaxis=dict(...)，合併成同一個 dict
                xaxis=dict(title="未來天數", tickmode="array",
                           tickvals=[0, 5, 10, 15, 30, 45, 60],
                           ticktext=["現在", "5天", "10天", "15天", "30天", "45天", "60天"]),
                yaxis=dict(title="預測價格 (NT$)", tickformat=",d"),
                plot_bgcolor="white", hovermode="x unified", height=400,
            )
            st.plotly_chart(fig_pred, use_container_width=True)

            st.markdown("### ⏱️ 最佳操作時機判定")
            # 修正：排除第 0 天(就是現在)，否則可能出現「第 0 天賣出/買進」
            future = {d: p for d, p in preds.items() if d > 0}
            if future:
                best_sell_day = max(future, key=future.get)
                best_buy_day = min(future, key=future.get)
                if rsi_val >= 60:
                    st.error(f"**🔴 賣出策略分析 (高檔調節)**\n\n模型預期價格高點可能落在 **第 {best_sell_day} 天** "
                             f"(預估價: NT${future[best_sell_day]:,.0f})。若持有現貨，可考慮分批獲利了結。")
                elif rsi_val <= 40:
                    st.success(f"**🟢 買進策略分析 (低檔佈局)**\n\n模型預期價格低點可能落在 **第 {best_buy_day} 天** "
                               f"(預估價: NT${future[best_buy_day]:,.0f})，可考慮分批建立底倉。")
                else:
                    st.info("**🟡 中性觀望分析**\n\n目前市場動能平穩，價格波動區間狹窄，建議持倉觀望。")
            st.caption("⚠️ 以上為統計模型的推估，不保證實際走勢，亦不構成投資建議。")

            st.markdown("---")
            st.markdown("#### 長期預測概覽 (60天後)")
            p1, p2 = st.columns(2)
            p1.metric("60天後預測價", f"NT${metrics['projected_60d']:,.0f}")
            p2.metric("預期 ROI", f"{metrics['roi_60d']:.2f}%")

    st.markdown("---")
    if st.button("🔄 計算整體組合績效"):
        st.session_state["card_library"] = safe_load_library()
        df = pd.DataFrame(st.session_state["card_library"])
        if df.empty or "成本" not in df.columns:
            st.warning("請先在卡牌分析頁面存入卡牌。")
        else:
            st.metric("總持有資產成本", f"NT${pd.to_numeric(df['成本'], errors='coerce').sum():,.0f}")
            st.dataframe(df, use_container_width=True)

# ---------------------------------------------------------------- 4. 卡牌庫
elif page == "卡牌庫":
    st.title("📂 卡牌庫")
    if st.button("🔄 重新整理"):
        st.session_state["card_library"] = safe_load_library()
    df = pd.DataFrame(st.session_state["card_library"])
    if df.empty:
        st.info("無庫存資料")
    else:
        st.dataframe(df, use_container_width=True)

# ---------------------------------------------------------------- 5. PSA 查詢
elif page == "PSA 查詢":
    st.title("🛡️ PSA POP 查詢")
    with st.container(border=True):
        cert_input = st.text_input("輸入 PSA 網址或編號").strip()
        if st.button("查詢 PSA 數據"):
            if not cert_input:
                st.warning("請輸入 PSA 網址或編號。")
            else:
                url = (cert_input if cert_input.startswith("http")
                       else f"https://www.psacard.com/cert/{cert_input}/psa")
                try:
                    with st.spinner("解析中..."):
                        st.session_state["psa_data"] = get_psa_pop_from_cert_url(url)
                except Exception as e:
                    st.session_state["psa_data"] = f"查詢失敗：{e}"

    psa = st.session_state.get("psa_data")
    if psa:
        if isinstance(psa, dict):
            st.success("✅ 查詢成功！")
            p1, p2 = st.columns(2)
            p1.metric("總鑑定數量 (Total Pop)", psa.get("total", "0"))
            p2.metric("高於此卡數量 (Pop Higher)", psa.get("higher", "0"))
        else:
            st.error(psa)

# ---------------------------------------------------------------- 6. 置中檢測
elif page == "置中檢測":
    st.title("📏 卡牌置中檢測 (v6.4)")
    st.markdown("""
    請上傳卡牌正/背面影像，系統分兩階段判定：
    1. **自動外緣偵測：** 框出卡片物理邊界，並加入 Buffer 避免裁切過度。
    2. **內外框雙對齊：**
       - `紅色實線`：對齊「物理最外緣」。
       - `青色虛線`：對齊「內框 (連續性 UI 裝飾外框或圖騰交界)」。

    ⚠️ 判定標籤為自訂的參考門檻，並非各鑑定公司的官方標準。
    """)

    uploaded_files = st.file_uploader("上傳卡牌圖片 (可多張)", type=["jpg", "jpeg", "png"],
                                      accept_multiple_files=True)
    if uploaded_files:
        # 修正：一次只載入一個檢測器，避免每張圖都各載一份 opencv.js (約 10MB)
        idx = st.selectbox("選擇要檢測的影像", range(len(uploaded_files)),
                           format_func=lambda i: uploaded_files[i].name)
        f = uploaded_files[idx]
        try:
            img_uri = image_to_data_uri(f.getvalue())
        except Exception as e:
            st.error(f"圖片解析失敗：{e}")
        else:
            html_code = (CENTERING_HTML
                         .replace("___IMG_URI___", img_uri)
                         .replace("___MAX___", str(MAX_IMG)))
            components.html(html_code, height=950)
