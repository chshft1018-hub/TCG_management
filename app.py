# ---------------------------------------------------------------- 置中檢測 HTML (TAG 背面 52/48 Pristine 校準版 + 畫布座標自適應修復)
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
  .btn-side { background:#2e7d32; color:#fff; border:1px solid #66bb6a; }
  .btn-side.back-mode { background:#1565c0; border:1px solid #42a5f5; }

  /* 確保 workspace 的寬高緊貼 Canvas，避免比例失真 */
  #workspace { position:relative; margin:15px auto; box-shadow:0 0 30px rgba(0,0,0,.5);
               font-size:0; touch-action:none; border:1px solid #333; overflow:hidden;
               background-color:#000; display: inline-block; }
  
  /* 讓 Canvas 的 CSS 大小限制最大寬度與高度，並保持正確比例 */
  canvas { display:block; max-width: 98vw; max-height: 70vh; width: auto; height: auto; object-fit: contain; }
  
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

  #result-panel { display:none; width:92%; max-width:540px; background:#1a1a1a; border-radius:12px;
                  padding:15px; margin:20px 0; grid-template-columns:1fr 1fr; gap:12px; }
  .score-card { background:#252525; padding:12px; border-radius:8px; text-align:center; border:1px solid #333; }
  .score-card.full-width { grid-column: 1 / -1; background:#1e242b; border-color:#37474f; }
  .score-val { font-size:20px; font-weight:bold; color:#fff; font-family:monospace; margin:5px 0; }
  .badge { display:inline-block; padding:4px 10px; border-radius:4px; font-size:12px; font-weight:bold; color:#000; margin:2px; }
  .grade-summary { font-size:13px; color:#cfd8dc; margin-top:6px; line-height:1.5; }
  #status-msg { color:#888; margin:10px; font-size:14px; min-height:20px; text-align:center; }
  #loading { color:#00bcd4; margin-top:50px; font-weight:bold; line-height:1.6; text-align:center; }
</style>
</head>
<body>
<div id="loading">⏳ 圖片接收中...</div>

<div id="main-ui" style="display:none; width:100%; flex-direction:column; align-items:center;">
  <div class="controls">
    <button id="sideToggleBtn" class="btn btn-side" onclick="toggleSide()">🃏 目前：正面 (Front)</button>
    <button id="autoBtnStep1" class="btn btn-purple" onclick="runFocusDetect()">✨ Auto Detect</button>
    <button id="nextBtn" class="btn btn-blue" onclick="processWarp()">Next</button>
    <button id="autoBtnStep2" class="btn btn-cyan" onclick="runAutoDetectInner()">⚡ Align Inner</button>
    <button id="resetBtn" class="btn btn-gray" onclick="resetAll()">Reset</button>
  </div>
  <div id="status-msg">Ready</div>
  <div id="workspace"><canvas id="cvCanvas"></canvas><div id="overlay"></div></div>
  <div id="result-panel">
    <div class="score-card"><div style="color:#aaa;font-size:12px">Left / Right (左右)</div>
      <div id="val-lr" class="score-val">--</div><div id="bdg-lr" class="badge">--</div></div>
    <div class="score-card"><div style="color:#aaa;font-size:12px">Top / Bottom (上下)</div>
      <div id="val-tb" class="score-val">--</div><div id="bdg-tb" class="badge">--</div></div>
    <div class="score-card full-width">
      <div style="color:#90caf9;font-size:12px;font-weight:bold;">🏆 綜合鑑定標準評估 (以最弱軸判定)</div>
      <div id="val-worst" class="score-val" style="font-size:18px;">Worst Axis: --</div>
      <div id="grade-badges" class="grade-summary">--</div>
    </div>
  </div>
</div>

<script>
const imgUri = "___IMG_URI___";
const MAX = ___MAX___;
const PADDING_RATIO = 0.05;
const CV_URLS = [
  "https://docs.opencv.org/4.8.0/opencv.js",
  "https://cdnjs.cloudflare.com/ajax/libs/opencv.js/4.8.0/opencv.min.js"
];

const $ = (id) => document.getElementById(id);
const canvas = $('cvCanvas'), overlay = $('overlay');
const clamp = (v) => Math.max(0, Math.min(1, v));

let imgMat = null, warpedMat = null, srcCanvas = null, currentStep = 0, started = false;
let cvLoadFailed = false, manualAdjusted = false;
let isFront = true;
let corners = [];
let guides = { outL:0, outR:1, outT:0, outB:1, inL:.1, inR:.9, inT:.1, inB:.9 };

function setStatus(msg, color) { const s = $('status-msg'); s.innerText = msg; s.style.color = color || '#888'; }
function loadingMsg(html) { $('loading').innerHTML = html; }

function toggleSide() {
  isFront = !isFront;
  const btn = $('sideToggleBtn');
  if (isFront) {
    btn.innerText = "🃏 目前：正面 (Front)";
    btn.classList.remove("back-mode");
  } else {
    btn.innerText = "🔄 目前：背面 (Back)";
    btn.classList.add("back-mode");
  }
  if (currentStep === 1) calc();
}

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
        if (bestCnt) bestCnt.delete();
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
    const W = warpedMat.cols, H = warpedMat.rows, E = edges.data;

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
      return max > (j1 - j0) * 0.05 ? best : null;
    }

    const l = strongest(true, .06, .10);  if (l !== null) guides.inL = l / W;
    const r = strongest(true, .90, .94);  if (r !== null) guides.inR = r / W;
    const t = strongest(false, .06, .12); if (t !== null) guides.inT = t / H;
    const b = strongest(false, .88, .93); if (b !== null) guides.inB = b / H;

    renderOverlay(); calc();
    setStatus("⚡ Aligned（請再手動微調青色虛線）", "#00e5ff");
  } catch (e) { console.error(e); }
  finally { [gray, edges].forEach(m => { if (m) m.delete(); }); }
}

/* ---------- Overlay (修復與實際 Canvas 對應問題) ---------- */
function renderOverlay() {
  overlay.innerHTML = '';
  if (currentStep === 0) {
    corners.forEach((pt, idx) => {
      const el = document.createElement('div');
      el.className = 'control-point';
      // 確保將內部像素座標轉換為正確的百分比
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
  ctx.drawImage(srcCanvas, 0, 0);
  // 不再依賴縮放比例 s，直接用絕對像素值畫線
  ctx.beginPath(); ctx.lineWidth = 4; ctx.strokeStyle = '#ff5252';
  ctx.moveTo(corners[0].x, corners[0].y);
  for (let i = 1; i < 4; i++) ctx.lineTo(corners[i].x, corners[i].y);
  ctx.closePath(); ctx.stroke();
}

function bindDrag(el, onMove) {
  el.addEventListener('pointerdown', (e) => {
    e.preventDefault(); e.stopPropagation();
    manualAdjusted = true;
    el.setPointerCapture(e.pointerId);
    
    // 取得畫布在網頁上真實的寬高
    const move = (ev) => {
      const r = canvas.getBoundingClientRect();
      const fx = clamp((ev.clientX - r.left) / r.width);
      const fy = clamp((ev.clientY - r.top) / r.height);
      
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

function calc() {
  const l = guides.inL - guides.outL, r = guides.outR - guides.inR;
  const t = guides.inT - guides.outT, b = guides.outB - guides.inB;
  const sW = (l + r) || 0.001, sH = (t + b) || 0.001;

  const lr1 = (l / sW) * 100, lr2 = (r / sW) * 100;
  const tb1 = (t / sH) * 100, tb2 = (b / sH) * 100;

  const wLR = setScore('lr', lr1, lr2);
  const wTB = setScore('tb', tb1, tb2);

  updateOverallEvaluation(wLR, wTB);
}

function setScore(id, v1, v2) {
  const val = $('val-' + id), bdg = $('bdg-' + id);
  if (v1 < 0 || v2 < 0) {
    val.innerText = '--'; bdg.innerText = '線位置無效'; bdg.style.background = '#555'; bdg.style.color = '#fff';
    return null;
  }
  val.innerText = `${v1.toFixed(2)} / ${v2.toFixed(2)}`;
  const w = Math.max(v1, v2);
  const set = (txt, bg, fg) => { bdg.innerText = txt; bdg.style.background = bg; bdg.style.color = fg; };

  if (isFront) {
    if (w <= 50.00) set("BGS 10 黑標", "#d4af37", "#000");
    else if (w < 51.00) set("TAG / CGC Pristine", "#2e7d32", "#fff");
    else if (w <= 52.00) set("BGS 9.5 門檻", "#00897b", "#fff");
    else if (w <= 55.00) set("PSA 10 / TAG 10", "#1565c0", "#fff");
    else set("超出 55/45", "#d32f2f", "#fff");
  } else {
    if (w <= 52.00) set("TAG Pristine (<=52/48)", "#2e7d32", "#fff");
    else if (w <= 55.00) set("BGS 黑標 / CGC Pristine", "#00897b", "#fff");
    else if (w <= 60.00) set("BGS 9.5 門檻", "#0288d1", "#fff");
    else if (w <= 75.00) set("PSA 10 / CGC 10", "#1565c0", "#fff");
    else set("超出 75/25", "#d32f2f", "#fff");
  }
  return w;
}

function updateOverallEvaluation(wLR, wTB) {
  const worstEl = $('val-worst'), badgesEl = $('grade-badges');
  if (wLR === null || wTB === null) {
    worstEl.innerText = "Worst Axis: --";
    badgesEl.innerHTML = "請調整紅線與青線至有效範圍內";
    return;
  }
  const worst = Math.max(wLR, wTB);
  const minor = (100 - worst).toFixed(2);
  worstEl.innerText = `最弱軸: ${worst.toFixed(2)} / ${minor} (${isFront ? '正面' : '背面'})`;

  let tags = [];
  if (isFront) {
    if (worst <= 50.00) tags.push(`<span class="badge" style="background:#d4af37;color:#000;">🏆 BGS 10 Black Label</span>`);
    if (worst < 51.00) tags.push(`<span class="badge" style="background:#2e7d32;color:#fff;">✨ TAG 10 Pristine / CGC Pristine</span>`);
    if (worst <= 52.00) tags.push(`<span class="badge" style="background:#00897b;color:#fff;">💎 BGS 9.5 Gem Mint</span>`);
    if (worst <= 55.00) tags.push(`<span class="badge" style="background:#1565c0;color:#fff;">✅ PSA 10 / CGC 10 / TAG 10</span>`);
    if (tags.length === 0) tags.push(`<span class="badge" style="background:#d32f2f;color:#fff;">❌ 未達 Gem Mint 正面標準 (>55/45)</span>`);
  } else {
    if (worst <= 52.00) tags.push(`<span class="badge" style="background:#2e7d32;color:#fff;">✨ TAG Pristine 門檻 (<=52/48)</span>`);
    if (worst <= 55.00) tags.push(`<span class="badge" style="background:#00897b;color:#fff;">🏆 BGS 黑標 / CGC Pristine</span>`);
    if (worst <= 60.00) tags.push(`<span class="badge" style="background:#0288d1;color:#fff;">💎 BGS 9.5 Gem Mint</span>`);
    if (worst <= 75.00) tags.push(`<span class="badge" style="background:#1565c0;color:#fff;">✅ PSA 10 / CGC Gem Mint 10</span>`);
    if (tags.length === 0) tags.push(`<span class="badge" style="background:#d32f2f;color:#fff;">❌ 未達 Gem Mint 背面標準 (>75/25)</span>`);
  }
  badgesEl.innerHTML = tags.join(" ");
}

function updateUI() {
  const s0 = currentStep === 0;
  $('autoBtnStep1').style.display = s0 ? 'inline-block' : 'none';
  $('nextBtn').style.display = s0 ? 'inline-block' : 'none';
  $('autoBtnStep2').style.display = s0 ? 'none' : 'inline-block';
  $('resetBtn').style.display = s0 ? 'none' : 'inline-block';
  $('result-panel').style.display = s0 ? 'none' : 'grid';
  if (!s0) setStatus("Step 2：紅線＝物理外緣，青色虛線＝TAG 測量錨點 (UI框/圖騰交界)", "#aaa");
}

function resetAll() {
  currentStep = 0;
  showBase(); updateUI(); renderOverlay();
  setStatus("Ready");
}

window.addEventListener('resize', () => { if (currentStep === 0) drawPoly(); });
</script>
</body>
</html>
"""
