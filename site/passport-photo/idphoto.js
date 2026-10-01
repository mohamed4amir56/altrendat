/*
 * أداة صور الجواز والتأشيرة — engine/idphoto.py ينسخ هذا الملف إلى
 * site/passport-photo/idphoto.js ويضع بيانات المستندات في <script id="idp-data">.
 *
 * كل المعالجة داخل متصفح الزائر: الصورة لا تُرفع إلى أي خادم. المكتبات
 * والنماذج فقط هي التي تُحمَّل من الشبكة (مرة واحدة ثم تبقى في الكاش):
 *   - MediaPipe (Apache-2.0): نقاط الوجه + قناع تقريبي للشخص.
 *   - MODNet عبر onnxruntime-web (Apache-2.0 / MIT): فصل الخلفية بحواف ناعمة.
 *
 * الوجه نفسه لا يُعدَّل: نقصّ وندوّر ونستبدل الخلفية فقط.
 */
const MP = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1";
const ORT = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.30.0/dist/";
const GCS = "https://storage.googleapis.com/mediapipe-models/";
const FACE_MODEL = GCS + "face_landmarker/face_landmarker/float16/1/face_landmarker.task";
const SEG_MODEL = GCS + "image_segmenter/selfie_segmenter/float16/1/selfie_segmenter.tflite";
const HF = "https://huggingface.co/Xenova/modnet/resolve/fa2fa546052fba4c08921230a26cc69a333fca12/onnx/";
const MODNET = [HF + "model_fp16.onnx", HF + "model.onnx"];   // الثاني احتياطي لو رفض المتصفح fp16

const MAX_SIDE = 2800;        // أكبر ضلع للصورة الأصلية بعد التحميل (حد ذاكرة الموبايل)
const ROI_SPAN = 2.5;         // ضلع منطقة العمل بوحدة ارتفاع الرأس
// المسافة من العين إلى الذقن ÷ ارتفاع الرأس (قمة الجمجمة → الذقن). قِيست على وجوه
// حليقة الرأس بتعبير محايد ووجه مواجه: 0.495–0.504. الابتسامة العريضة ترفعها إلى ~0.56.
const EYE_TO_CHIN = 0.50;
const HAIR_ALLOW = 0.06;      // ما يُحسب من الشعر فوق قمة الجمجمة ضمن ارتفاع الرأس
const CROWN_DROP = 0.14;      // أقصى نزول لقمة الرأس الظاهرة تحت التقدير (حماية من قناع أكل من الرأس)

const $ = (id) => document.getElementById(id);
const DATA = JSON.parse($("idp-data").textContent);
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const smooth = (a, b, v) => { const t = clamp((v - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const mkCanvas = (w, h) => { const c = document.createElement("canvas"); c.width = w; c.height = h; return c; };

const S = {
  spec: DATA.docs[DATA.current], src: null, roi: null, cutout: null, cov: null, R: 0, k: 1,
  geo: null, face: null, adj: { zoom: 1, dx: 0, dy: 0, rot: 0 }, bgOn: true, bgColor: "#ffffff", guides: true, busy: false, job: 0,
};

// ── تحميل المكتبات والنماذج (عند أول صورة فقط) ───────────────────────────

let visionP = null, faceP = null, segP = null, modnetP = null;

function once(get, set, make) {
  if (!get()) set(make().catch((e) => { set(null); throw e; }));
  return get();
}
const vision = () => once(() => visionP, (v) => (visionP = v), async () => {
  const m = await import(MP + "/vision_bundle.mjs");
  return { m, fs: await m.FilesetResolver.forVisionTasks(MP + "/wasm") };
});
const faceModel = () => once(() => faceP, (v) => (faceP = v), async () => {
  const { m, fs } = await vision();
  return m.FaceLandmarker.createFromOptions(fs, {
    baseOptions: { modelAssetPath: FACE_MODEL }, runningMode: "IMAGE", numFaces: 4,
    outputFaceBlendshapes: true, outputFacialTransformationMatrixes: true });
});
const segModel = () => once(() => segP, (v) => (segP = v), async () => {
  const { m, fs } = await vision();
  return m.ImageSegmenter.createFromOptions(fs, {
    baseOptions: { modelAssetPath: SEG_MODEL }, runningMode: "IMAGE",
    outputCategoryMask: false, outputConfidenceMasks: true });
});

// النموذج 13 ميجا: نحفظه في Cache Storage حتى لا يُحمَّل في كل زيارة
async function fetchCached(url, onProgress) {
  let cache = null;
  try { cache = await caches.open("idphoto-models-1"); } catch (e) { /* تصفح خاص */ }
  if (cache) {
    const hit = await cache.match(url);
    if (hit) return hit.arrayBuffer();
  }
  const res = await fetch(url);
  if (!res.ok) throw new Error("HTTP " + res.status);
  const total = +res.headers.get("content-length") || 0;
  let buf;
  if (res.body && total) {
    const reader = res.body.getReader(), chunks = [];
    let got = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value); got += value.length;
      if (onProgress) onProgress(got / total);
    }
    const all = new Uint8Array(got);
    let o = 0;
    for (const c of chunks) { all.set(c, o); o += c.length; }
    buf = all.buffer;
  } else {
    buf = await res.arrayBuffer();
  }
  if (cache) { try { await cache.put(url, new Response(buf.slice(0))); } catch (e) { /* مساحة ممتلئة */ } }
  return buf;
}

const modnet = (onProgress) => once(() => modnetP, (v) => (modnetP = v), async () => {
  const ort = await import(ORT + "ort.wasm.min.mjs");
  ort.env.wasm.wasmPaths = ORT;
  ort.env.wasm.numThreads = 1;
  let last = null;
  for (const url of MODNET) {
    try {
      const buf = await fetchCached(url, onProgress);
      const session = await ort.InferenceSession.create(buf, { executionProviders: ["wasm"] });
      return { ort, session };
    } catch (e) { last = e; }
  }
  throw last;
});

// ── أدوات المصفوفات ─────────────────────────────────────────────────────

function boxFilter(src, w, h, r) {
  const tmp = new Float32Array(w * h), dst = new Float32Array(w * h);
  for (let y = 0; y < h; y++) {
    const o = y * w;
    let s = 0;
    for (let x = -r; x <= r; x++) s += src[o + clamp(x, 0, w - 1)];
    for (let x = 0; x < w; x++) {
      tmp[o + x] = s;
      s += src[o + Math.min(w - 1, x + r + 1)] - src[o + Math.max(0, x - r)];
    }
  }
  const n = (2 * r + 1) * (2 * r + 1);
  for (let x = 0; x < w; x++) {
    let s = 0;
    for (let y = -r; y <= r; y++) s += tmp[clamp(y, 0, h - 1) * w + x];
    for (let y = 0; y < h; y++) {
      dst[y * w + x] = s / n;
      s += tmp[Math.min(h - 1, y + r + 1) * w + x] - tmp[Math.max(0, y - r) * w + x];
    }
  }
  return dst;
}

function resizeF(src, sw, sh, dw, dh) {
  const dst = new Float32Array(dw * dh);
  for (let y = 0; y < dh; y++) {
    const fy = (y + 0.5) * sh / dh - 0.5, y0 = clamp(Math.floor(fy), 0, sh - 1),
      y1 = Math.min(sh - 1, y0 + 1), ty = clamp(fy - y0, 0, 1);
    for (let x = 0; x < dw; x++) {
      const fx = (x + 0.5) * sw / dw - 0.5, x0 = clamp(Math.floor(fx), 0, sw - 1),
        x1 = Math.min(sw - 1, x0 + 1), tx = clamp(fx - x0, 0, 1);
      dst[y * dw + x] = (src[y0 * sw + x0] * (1 - tx) + src[y0 * sw + x1] * tx) * (1 - ty) +
        (src[y1 * sw + x0] * (1 - tx) + src[y1 * sw + x1] * tx) * ty;
    }
  }
  return dst;
}

// مرشّح موجَّه سريع: المعاملات تُحسب بدقة منخفضة ثم تُطبَّق على الصورة الكاملة،
// فتلتصق حافة القناع بحافة الشخص الحقيقية بدل حافة الشبكة الخشنة.
function guidedUpsample(alpha, aw, ah, guide, W, H, lw, r, eps) {
  const n = lw * lw, I = resizeF(guide, W, H, lw, lw), p = resizeF(alpha, aw, ah, lw, lw);
  const II = new Float32Array(n), Ip = new Float32Array(n);
  for (let i = 0; i < n; i++) { II[i] = I[i] * I[i]; Ip[i] = I[i] * p[i]; }
  const mI = boxFilter(I, lw, lw, r), mp = boxFilter(p, lw, lw, r),
    mII = boxFilter(II, lw, lw, r), mIp = boxFilter(Ip, lw, lw, r);
  const a = new Float32Array(n), b = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    a[i] = (mIp[i] - mI[i] * mp[i]) / (mII[i] - mI[i] * mI[i] + eps);
    b[i] = mp[i] - a[i] * mI[i];
  }
  const A = resizeF(boxFilter(a, lw, lw, r), lw, lw, W, H), B = resizeF(boxFilter(b, lw, lw, r), lw, lw, W, H);
  for (let i = 0; i < W * H; i++) A[i] = clamp(A[i] * guide[i] + B[i], 0, 1);
  return A;
}

// ── الصورة والوجه ───────────────────────────────────────────────────────

class UserError extends Error {}

async function loadSource(file) {
  let bmp;
  try {
    bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch (e) {
    bmp = await new Promise((ok, bad) => {
      const im = new Image();
      im.onload = () => ok(im);
      im.onerror = () => bad(new UserError("تعذّر فتح الملف. اختر صورة بصيغة JPG أو PNG."));
      im.src = URL.createObjectURL(file);
    });
  }
  const w = bmp.width || bmp.naturalWidth, h = bmp.height || bmp.naturalHeight;
  const s = Math.min(1, MAX_SIDE / Math.max(w, h));
  const c = mkCanvas(Math.round(w * s), Math.round(h * s)), x = c.getContext("2d");
  x.imageSmoothingQuality = "high";
  x.drawImage(bmp, 0, 0, c.width, c.height);
  if (bmp.close) bmp.close();
  return c;
}

async function detectFace(src) {
  const model = await faceModel();
  const res = model.detect(src);
  const faces = res.faceLandmarks || [];
  if (!faces.length) throw new UserError("لم نجد وجهًا واضحًا في الصورة. التقط صورة أقرب بإضاءة جيدة والوجه مواجه للكاميرا.");
  let idx = 0, best = 0;
  faces.forEach((f, i) => { const d = Math.hypot(f[152].x - f[10].x, f[152].y - f[10].y); if (d > best) { best = d; idx = i; } });
  const lm = faces[idx], W = src.width, H = src.height;
  const P = (i) => ({ x: lm[i].x * W, y: lm[i].y * H });
  const mid = (a, b) => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });
  const iris = lm.length > 473;
  let e1 = iris ? P(468) : mid(P(33), P(133)), e2 = iris ? P(473) : mid(P(362), P(263));
  if (e1.x > e2.x) [e1, e2] = [e2, e1];
  const eye = mid(e1, e2), chin = P(152);
  let roll = Math.atan2(e2.y - e1.y, e2.x - e1.x);
  // الذقن يجب أن يكون «تحت» العينين؛ لو لا، فالصورة مقلوبة
  if ((chin.x - eye.x) * -Math.sin(roll) + (chin.y - eye.y) * Math.cos(roll) < 0) roll += Math.PI;
  const down = { x: -Math.sin(roll), y: Math.cos(roll) };
  const eyeToChin = (chin.x - eye.x) * down.x + (chin.y - eye.y) * down.y;
  const top10 = P(10), eyeToForehead = -((top10.x - eye.x) * down.x + (top10.y - eye.y) * down.y);
  const faceWidth = Math.hypot(P(454).x - P(234).x, P(454).y - P(234).y);

  const shapes = {};
  const bs = res.faceBlendshapes && res.faceBlendshapes[idx];
  if (bs) for (const c of bs.categories) shapes[c.categoryName] = c.score;
  let yaw = 0, pitch = 0;
  const mx = res.facialTransformationMatrixes && res.facialTransformationMatrixes[idx];
  if (mx) {
    const d = mx.data;                       // عمود-أولًا: العمود الثالث اتجاه الوجه
    yaw = Math.atan2(d[8], d[10]) * 180 / Math.PI;
    pitch = Math.atan2(-d[9], Math.hypot(d[8], d[10])) * 180 / Math.PI;
  }
  return { eye, chin, roll, down, h: eyeToChin / EYE_TO_CHIN, eyeToChin, eyeToForehead, faceWidth, shapes, yaw, pitch, count: faces.length,
    eyeDist: Math.hypot(e2.x - e1.x, e2.y - e1.y) };
}

// منطقة عمل مربعة حول الرأس، معدولة (العينان أفقيتان)، تكفي كل المقاسات
function buildROI(src, f) {
  const side = ROI_SPAN * f.h;
  const R = Math.round(clamp(side, 640, 1408));
  const k = side / R;
  const C = { x: f.eye.x + f.down.x * 0.25 * f.h, y: f.eye.y + f.down.y * 0.25 * f.h };
  const place = (ctx) => {
    ctx.translate(R / 2, R / 2); ctx.rotate(-f.roll); ctx.scale(1 / k, 1 / k); ctx.translate(-C.x, -C.y);
  };
  const roi = mkCanvas(R, R), x = roi.getContext("2d", { willReadFrequently: true });
  x.fillStyle = "#fff"; x.fillRect(0, 0, R, R);
  x.imageSmoothingQuality = "high";
  x.save(); place(x); x.drawImage(src, 0, 0); x.restore();
  const cc = mkCanvas(R, R), cx = cc.getContext("2d", { willReadFrequently: true });
  cx.save(); place(cx); cx.fillStyle = "#000"; cx.fillRect(0, 0, src.width, src.height); cx.restore();
  const cd = cx.getImageData(0, 0, R, R).data, cov = new Uint8Array(R * R);
  for (let i = 0; i < R * R; i++) cov[i] = cd[4 * i + 3] > 250 ? 1 : 0;
  const hR = f.h / k, eyeY = R / 2 - 0.25 * hR;
  const geo = { eyeX: R / 2, eyeY, chinY: eyeY + EYE_TO_CHIN * hR, skullY: eyeY - (1 - EYE_TO_CHIN) * hR,
    hairY: null, crownY: eyeY - (1 - EYE_TO_CHIN) * hR, h: hR };
  return { roi, cov, R, k, geo };
}

// ── فصل الخلفية ─────────────────────────────────────────────────────────

async function computeAlpha(roi, cov, R, onProgress) {
  const rx = roi.getContext("2d", { willReadFrequently: true });
  const px = rx.getImageData(0, 0, R, R).data;
  const guide = new Float32Array(R * R);
  for (let i = 0; i < R * R; i++) guide[i] = (0.299 * px[4 * i] + 0.587 * px[4 * i + 1] + 0.114 * px[4 * i + 2]) / 255;

  // قناع تقريبي للشخص: يمنع MODNet من إبقاء بقع من الخلفية بعيدة عن الجسم
  let gate = null;
  try {
    const seg = await segModel();
    const r = seg.segment(roi), mk = r.confidenceMasks[r.confidenceMasks.length - 1];
    const g = mk.getAsFloat32Array().slice(), gw = mk.width, gh = mk.height;
    r.close();
    const blur = boxFilter(g, gw, gh, Math.max(2, Math.round(gw * 0.018)));
    for (let i = 0; i < blur.length; i++) blur[i] = smooth(0.06, 0.31, blur[i]);
    gate = resizeF(blur, gw, gh, R, R);
  } catch (e) { /* بدون القناع التقريبي نكمل بـ MODNet وحده */ }

  const { ort, session } = await modnet(onProgress);
  const N = 512, small = mkCanvas(N, N), sx = small.getContext("2d", { willReadFrequently: true });
  sx.imageSmoothingQuality = "high";
  sx.drawImage(roi, 0, 0, N, N);
  const d = sx.getImageData(0, 0, N, N).data, t = new Float32Array(3 * N * N);
  for (let i = 0; i < N * N; i++) {
    t[i] = d[4 * i] / 127.5 - 1; t[N * N + i] = d[4 * i + 1] / 127.5 - 1; t[2 * N * N + i] = d[4 * i + 2] / 127.5 - 1;
  }
  const out = await session.run({ [session.inputNames[0]]: new ort.Tensor("float32", t, [1, 3, N, N]) });
  const raw = out[session.outputNames[0]].data;
  const alpha = guidedUpsample(raw, N, N, guide, R, R, 512, 4, 1e-4);
  for (let i = 0; i < R * R; i++) {
    // حافة أحدّ قليلًا: المناطق نصف الشفافة العريضة تظهر هالةً حول الأذن والكتف في صورة رسمية
    alpha[i] = smooth(0.14, 0.86, alpha[i] * (gate ? gate[i] : 1) * cov[i]);
  }
  return alpha;
}

// أعلى نقطة ظاهرة من الرأس (شعر أو غطاء) فوق الوجه
function findHairTop(alpha, R, geo) {
  const x0 = Math.round(clamp(geo.eyeX - 0.3 * geo.h, 0, R - 1)), x1 = Math.round(clamp(geo.eyeX + 0.3 * geo.h, 0, R - 1));
  const need = Math.max(3, (x1 - x0) * 0.12);
  for (let y = 0; y < geo.eyeY; y++) {
    let n = 0;
    for (let x = x0; x <= x1; x++) if (alpha[y * R + x] > 0.5) n++;
    if (n >= need) return y;
  }
  return null;
}

// نقاط من جسم الشخص ملاصقة لحافة الصورة الأصلية: لو دخلت الإطار فالجسم مقصوص فعلًا
function findCutPoints(alpha, cov, R) {
  const pts = [], d = 3;
  for (let y = d; y < R - d; y += 2) for (let x = d; x < R - d; x += 2) {
    const p = y * R + x;
    if (cov[p] && alpha[p] > 0.5 && !(cov[p - d] && cov[p + d] && cov[p - d * R] && cov[p + d * R])) pts.push(x, y);
  }
  return pts;
}

// الشخص مقصوصًا بقناة شفافية، مع تنظيف لون الخلفية القديمة من الحواف نصف الشفافة
function makeCutout(roi, alpha, R) {
  const id = roi.getContext("2d", { willReadFrequently: true }).getImageData(0, 0, R, R), d = id.data;
  const h = R >> 1, n = h * h;
  const num = [new Float32Array(n), new Float32Array(n), new Float32Array(n)], den = new Float32Array(n);
  for (let y = 0; y < h; y++) for (let x = 0; x < h; x++) {
    let w = 0, r = 0, g = 0, b = 0;
    for (let j = 0; j < 2; j++) for (let i = 0; i < 2; i++) {
      const p = (2 * y + j) * R + 2 * x + i, ww = smooth(0.85, 0.97, alpha[p]);
      w += ww; r += d[4 * p] * ww; g += d[4 * p + 1] * ww; b += d[4 * p + 2] * ww;
    }
    const o = y * h + x;
    den[o] = w; num[0][o] = r; num[1][o] = g; num[2][o] = b;
  }
  const r1 = Math.max(3, Math.round(h * 0.012)), r2 = r1 * 3;
  const near = [boxFilter(den, h, h, r1), ...num.map((c) => boxFilter(c, h, h, r1))];
  const far = [boxFilter(den, h, h, r2), ...num.map((c) => boxFilter(c, h, h, r2))];
  for (let y = 0; y < R; y++) for (let x = 0; x < R; x++) {
    const p = y * R + x, a = alpha[p];
    if (a > 0.004 && a < 0.97) {
      const o = Math.min(h - 1, y >> 1) * h + Math.min(h - 1, x >> 1);
      const src = near[0][o] > 0.08 ? near : far[0][o] > 0.02 ? far : null;
      if (src) {
        const t = 1 - smooth(0.75, 0.97, a);
        for (let c = 0; c < 3; c++) d[4 * p + c] += (src[c + 1][o] / src[0][o] - d[4 * p + c]) * t;
      }
    }
    d[4 * p + 3] = Math.round(a * 255);
  }
  const c = mkCanvas(R, R);
  c.getContext("2d").putImageData(id, 0, 0);
  return c;
}

// ── الإطار والرسم ───────────────────────────────────────────────────────

function frame(spec, geo, adj) {
  const head = geo.chinY - geo.crownY;
  const H0 = head / spec.head, W0 = H0 * spec.w / spec.h;
  const top = spec.eye ? geo.eyeY - (1 - spec.eye) * H0 : geo.crownY - spec.top * H0;
  const Hf = H0 / adj.zoom, Wf = W0 / adj.zoom;
  return { cx: geo.eyeX - adj.dx * Wf, cy: top + H0 / 2 - adj.dy * Hf, Wf, Hf };
}

function outSize(spec) {
  if (spec.px) return { W: spec.px[0], H: spec.px[1] };
  return { W: Math.round(spec.w / 25.4 * 600), H: Math.round(spec.h / 25.4 * 600) };
}

function paint(ctx, W, H, F, rot, useCutout, bg) {
  ctx.save();
  ctx.fillStyle = useCutout ? bg : "#fff";
  ctx.fillRect(0, 0, W, H);
  const s = W / F.Wf;
  ctx.translate(W / 2, H / 2); ctx.rotate(rot * Math.PI / 180); ctx.scale(s, s); ctx.translate(-F.cx, -F.cy);
  ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = "high";
  ctx.drawImage(useCutout ? S.cutout : S.roi, 0, 0);
  ctx.restore();
}

// نقطة من إحداثيات الإطار (0..1) إلى إحداثيات منطقة العمل، مع الدوران اليدوي
function frameToROI(F, rot, u, v) {
  const a = -rot * Math.PI / 180, x = (u - 0.5) * F.Wf, y = (v - 0.5) * F.Hf;
  return { x: F.cx + x * Math.cos(a) - y * Math.sin(a), y: F.cy + x * Math.sin(a) + y * Math.cos(a) };
}

function checks() {
  const spec = S.spec, g = S.geo, f = S.face, F = frame(spec, g, S.adj), out = [];
  const add = (level, text) => out.push({ level, text });
  const head = (g.chinY - g.crownY) / F.Hf;
  if (spec.head_min) {
    const ok = head >= spec.head_min - 0.004 && head <= spec.head_max + 0.004;
    const txt = spec.px
      ? "ارتفاع الرأس " + Math.round(head * 100) + "% من الصورة (المطلوب " + Math.round(spec.head_min * 100) + "–" + Math.round(spec.head_max * 100) + "%)"
      : "ارتفاع الرأس " + (head * spec.h).toFixed(1) + " مم (المطلوب " + Math.round(spec.head_min * spec.h) + "–" + Math.round(spec.head_max * spec.h) + " مم)";
    add(ok ? "ok" : "bad", txt);
  } else {
    add("ok", "ارتفاع الرأس " + (head * spec.h / 10).toFixed(1) + " سم من " + (spec.h / 10) + " سم (لا يوجد شرط رسمي منشور لحجم الرأس)");
  }
  if (spec.eye_min) {
    const e = (F.cy + F.Hf / 2 - g.eyeY) / F.Hf;
    add(e >= spec.eye_min && e <= spec.eye_max ? "ok" : "bad",
      "العينان على ارتفاع " + Math.round(e * 100) + "% (المطلوب " + Math.round(spec.eye_min * 100) + "–" + Math.round(spec.eye_max * 100) + "%)");
  }
  // هل الصورة الأصلية تغطي الإطار كله؟
  let covered = true;
  for (const [u, v] of [[0, 0], [1, 0], [0, 1], [1, 1], [0.5, 0], [0.5, 1], [0, 0.5], [1, 0.5]]) {
    const p = frameToROI(F, S.adj.rot, u * 0.98 + 0.01, v * 0.98 + 0.01), x = Math.round(p.x), y = Math.round(p.y);
    if (x < 0 || y < 0 || x >= S.R || y >= S.R || !S.cov[y * S.R + x]) covered = false;
  }
  let bodyCut = false;
  if (S.cutPts) {
    const a = -S.adj.rot * Math.PI / 180, ca = Math.cos(a), sa = Math.sin(a);
    for (let i = 0; i < S.cutPts.length && !bodyCut; i += 2) {
      const dx = S.cutPts[i] - F.cx, dy = S.cutPts[i + 1] - F.cy;
      const u = (dx * ca + dy * sa) / F.Wf + 0.5, v = (-dx * sa + dy * ca) / F.Hf + 0.5;
      bodyCut = u > 0.01 && u < 0.99 && v > 0.01 && v < 0.99;
    }
  }
  if (bodyCut) add("bad", "الجسم أو الشعر مقصوص عند حافة الصورة الأصلية — التقط صورة من مسافة أبعد تُظهر الكتفين ومساحة فوق الرأس");
  else if (covered) add("ok", "الصورة تغطي الإطار كاملًا");
  else if (S.bgOn && S.cutout) add("ok", "أكملنا الخلفية الناقصة عند حافة الصورة");
  else add("warn", "الصورة الأصلية لا تغطي الإطار كله، والجزء الناقص سيظهر أبيض — فعّل استبدال الخلفية أو التقط صورة من مسافة أبعد");
  if (g.hairY !== null && g.hairY < F.cy - F.Hf / 2 + 0.01 * F.Hf) add("warn", "أعلى الشعر أو غطاء الرأس مقصوص — صغّر الصورة قليلًا");
  const rollDeg = Math.abs(((f.roll * 180 / Math.PI + 540) % 360) - 180);
  if (rollDeg > 12) add("warn", "الرأس مائل بوضوح (" + Math.round(rollDeg) + "°) — عدّلناه، والأفضل إعادة التصوير والرأس مستقيم");
  else add("ok", rollDeg > 2 ? "عدّلنا ميل الرأس (" + Math.round(rollDeg) + "°)" : "الرأس مستقيم");
  if (Math.abs(f.yaw) > 12 || Math.abs(f.pitch) > 20) add("warn", "الوجه ليس مواجهًا للكاميرا تمامًا — انظر إلى العدسة مباشرة والهاتف في مستوى العين");
  else add("ok", "الوجه مواجه للكاميرا");
  const sh = f.shapes;
  if (Math.max(sh.eyeBlinkLeft || 0, sh.eyeBlinkRight || 0) > 0.6) add("bad", "العينان تبدوان مغمضتين — يجب أن تكونا مفتوحتين");
  if (((sh.mouthSmileLeft || 0) + (sh.mouthSmileRight || 0)) / 2 > 0.45 || (sh.jawOpen || 0) > 0.3)
    add("warn", "المطلوب تعبير محايد وفم مغلق (بلا ابتسامة ظاهرة)");
  // دقة الطباعة الفعلية: بكسلات الرأس في الأصل ÷ مقاسه المطبوع
  const headMm = head * spec.h, srcDpi = f.h / headMm * 25.4;
  if (srcDpi < (spec.px ? 180 : 220)) add("warn", "دقة الصورة الأصلية منخفضة — قد تظهر الصورة المطبوعة غير حادّة");
  if (f.count > 1) add("warn", "في الصورة أكثر من وجه — استخدمنا الأكبر. الصورة الرسمية لشخص واحد فقط");
  if (!S.bgOn && S.bgStat) {
    if (S.bgStat.mean < 0.74 || S.bgStat.std > 0.085) add("warn", "الخلفية الأصلية ليست فاتحة وموحّدة — صوّر أمام حائط فاتح، أو فعّل خيار الخلفية في أدوات الضبط");
    else add("ok", "الخلفية الأصلية فاتحة وموحّدة");
  }
  return { list: out, F, head };
}

function backgroundStat(roi, alpha, R, geo) {
  const d = roi.getContext("2d", { willReadFrequently: true }).getImageData(0, 0, R, R).data;
  let n = 0, s = 0, s2 = 0;
  const y1 = Math.min(R, Math.round(geo.chinY + 0.3 * geo.h));
  for (let y = 0; y < y1; y += 2) for (let x = 0; x < R; x += 2) {
    const p = y * R + x;
    if (alpha[p] > 0.02 || !S.cov[p]) continue;
    const l = (0.299 * d[4 * p] + 0.587 * d[4 * p + 1] + 0.114 * d[4 * p + 2]) / 255;
    n++; s += l; s2 += l * l;
  }
  if (n < 200) return null;
  const mean = s / n;
  return { mean, std: Math.sqrt(Math.max(0, s2 / n - mean * mean)) };
}

// ── الواجهة ─────────────────────────────────────────────────────────────

function status(text, pct) {
  const el = $("idp-status");
  el.hidden = !text;
  el.querySelector("span").textContent = text || "";
  const bar = el.querySelector("i");
  bar.style.width = pct == null ? "0" : Math.round(pct * 100) + "%";
  bar.parentNode.hidden = pct == null;
}

function fail(text) {
  const el = $("idp-error");
  el.hidden = !text;
  el.textContent = text || "";
}

function render() {
  if (!S.roi) return;
  const { W, H } = outSize(S.spec), cv = $("idp-canvas"), { list, F } = checks();
  if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; }
  cv.style.aspectRatio = W + " / " + H;
  const useCut = S.bgOn && !!S.cutout, ctx = cv.getContext("2d");
  paint(ctx, W, H, F, S.adj.rot, useCut, S.bgColor);
  if (S.guides) drawGuides(ctx, W, H, F);
  $("idp-checks").innerHTML = list.map((c) =>
    "<li class='" + c.level + "'>" + (c.level === "ok" ? "✓" : c.level === "bad" ? "✗" : "!") + " " + c.text + "</li>").join("");
  const bad = list.some((c) => c.level === "bad");
  $("idp-verdict").className = "idp-verdict " + (bad ? "bad" : "ok");
  const warn = list.some((c) => c.level === "warn");
  $("idp-verdict").textContent = bad ? "الصورة تحتاج تعديلًا قبل الاستخدام"
    : warn ? "المقاس مطابق، وهناك ملاحظات تستحق المراجعة قبل الاستخدام"
      : "المقاس والوضع مطابقان — راجع بقية الشروط أسفل الصفحة";
}

function drawGuides(ctx, W, H, F) {
  const g = S.geo, toY = (y) => (y - (F.cy - F.Hf / 2)) / F.Hf * H;
  ctx.save();
  ctx.lineWidth = Math.max(1.5, W / 300);
  ctx.setLineDash([W / 40, W / 60]);
  ctx.strokeStyle = "rgba(0,150,90,.85)";
  if (Math.abs(S.adj.rot) < 0.5) {
    for (const y of [toY(g.crownY), toY(g.chinY)]) { ctx.beginPath(); ctx.moveTo(W * 0.08, y); ctx.lineTo(W * 0.92, y); ctx.stroke(); }
  }
  ctx.strokeStyle = "rgba(40,110,220,.55)";
  ctx.beginPath(); ctx.moveTo(W / 2, H * 0.03); ctx.lineTo(W / 2, H * 0.97); ctx.stroke();
  ctx.restore();
}

function syncControls() {
  $("idp-zoom").value = S.adj.zoom; $("idp-rot").value = S.adj.rot;
  $("idp-bg").checked = S.bgOn; $("idp-guides").checked = S.guides;
  $("idp-bg").disabled = !S.cutout;
  $("idp-bgnote").hidden = !(S.bgOn && S.spec.unaltered);
  $("idp-bgcolor-row").hidden = !(S.bgOn && S.spec.bgs.length > 1);
  $("idp-bg").parentNode.lastChild.textContent = S.spec.bgs.length > 1 ? " استبدال الخلفية" : " تبييض الخلفية";
}

function applySpec(slug) {
  S.spec = DATA.docs[slug];
  S.adj = { zoom: 1, dx: 0, dy: 0, rot: 0 };
  S.bgOn = !!S.spec.bg_default;
  S.bgColor = S.spec.bgs[0][1];
  $("idp-bgcolor").innerHTML = S.spec.bgs.map((b) => "<option value='" + b[1] + "'>" + b[0] + "</option>").join("");
  document.querySelectorAll("[data-idp-size]").forEach((el) => (el.textContent = S.spec.label));
  $("idp-dl-photo").textContent = "تحميل الصورة — " + (S.spec.px ? S.spec.px.join("×") + " بكسل" : S.spec.label);
  syncControls();
  render();
}

async function handleFile(file) {
  if (!file || S.busy) return;
  const job = ++S.job;
  let cropped = false;
  S.busy = true;
  fail("");
  $("idp-work").hidden = true;
  try {
    status("فتح الصورة…");
    const src = await loadSource(file);
    status("تحميل أدوات المعالجة (مرة واحدة فقط)…");
    const face = await detectFace(src);
    const { roi, cov, R, k, geo } = buildROI(src, face);
    Object.assign(S, { src, face, roi, cov, R, k, geo, cutout: null, bgStat: null, cutPts: null,
      adj: { zoom: 1, dx: 0, dy: 0, rot: 0 }, bgOn: !!S.spec.bg_default });
    $("idp-work").hidden = false;
    $("idp-drop").classList.add("done");
    syncControls();
    render();                                  // قصّ فوري بالخلفية الأصلية
    cropped = true;
    $("idp-work").scrollIntoView({ behavior: "smooth", block: "start" });
    status("تجهيز فصل الخلفية…", 0);
    const alpha = await computeAlpha(roi, cov, R, (p) => { if (job === S.job) status("تحميل نموذج فصل الخلفية… " + Math.round(p * 100) + "%", p); });
    if (job !== S.job) return;
    const hair = findHairTop(alpha, R, geo);
    geo.hairY = hair;
    // قمة الرأس = قمة الجمجمة المقدَّرة، ويُحسب معها الشعر حتى حد صغير فوقها
    if (hair !== null) geo.crownY = Math.min(Math.max(hair, geo.skullY - HAIR_ALLOW * geo.h), geo.skullY + CROWN_DROP * geo.h);
    S.cutPts = findCutPoints(alpha, cov, R);
    S.bgStat = backgroundStat(roi, alpha, R, geo);
    S.cutout = makeCutout(roi, alpha, R);
    status("");
    syncControls();
    render();
  } catch (e) {
    status("");
    if (e instanceof UserError) fail(e.message);
    else if (cropped) { fail("تعذّر تحميل نموذج فصل الخلفية. يمكنك تحميل الصورة بخلفيتها الأصلية، أو إعادة المحاولة بعد التأكد من الاتصال."); syncControls(); render(); }
    else fail("تعذّر تحميل أدوات المعالجة. تأكد من الاتصال بالإنترنت ثم أعد المحاولة.");
    console.error(e);
  } finally {
    if (job === S.job) S.busy = false;
  }
}

// ── التحميل ─────────────────────────────────────────────────────────────

const toJpeg = (c, q) => new Promise((ok) => c.toBlob(ok, "image/jpeg", q));

// يكتب الدقة (DPI) في ترويسة JFIF ليُطبع الملف بمقاسه الحقيقي
async function setDpi(blob, dpi) {
  const b = new Uint8Array(await blob.arrayBuffer());
  if (b[2] === 0xff && b[3] === 0xe0 && b[6] === 0x4a && b[7] === 0x46 && b[8] === 0x49 && b[9] === 0x46) {
    b[13] = 1; b[14] = dpi >> 8; b[15] = dpi & 255; b[16] = dpi >> 8; b[17] = dpi & 255;
  }
  return new Blob([b], { type: "image/jpeg" });
}

function save(blob, name) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 60000);
}

function photoCanvas(W, H) {
  const c = mkCanvas(W, H), F = frame(S.spec, S.geo, S.adj);
  paint(c.getContext("2d"), W, H, F, S.adj.rot, S.bgOn && !!S.cutout, S.bgColor);
  return c;
}

async function downloadPhoto() {
  const { W, H } = outSize(S.spec), c = photoCanvas(W, H);
  let q = 0.95, blob = await toJpeg(c, q);
  while (S.spec.max_kb && blob.size > S.spec.max_kb * 1024 && q > 0.4) { q -= 0.06; blob = await toJpeg(c, q); }
  save(await setDpi(blob, Math.round(W / (S.spec.w / 25.4))), "photo-" + S.spec.slug + ".jpg");
}

// ورقة 10×15 سم (4×6 بوصة) بأكبر عدد من النسخ وخطوط قص
async function downloadSheet() {
  const DPI = 600, mm = (v) => v / 25.4 * DPI, spec = S.spec;
  const margin = 4, gap = 2, strip = 5;
  let best = null;
  for (const [pw, ph] of [[101.6, 152.4], [152.4, 101.6]]) {
    const nx = Math.floor((pw - 2 * margin + gap) / (spec.w + gap)), ny = Math.floor((ph - 2 * margin - strip + gap) / (spec.h + gap));
    if (nx > 0 && ny > 0 && (!best || nx * ny > best.nx * best.ny)) best = { pw, ph, nx, ny };
  }
  if (!best) return;
  const { pw, ph, nx, ny } = best, sheet = mkCanvas(Math.round(mm(pw)), Math.round(mm(ph))), ctx = sheet.getContext("2d");
  ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, sheet.width, sheet.height);
  const w = Math.round(mm(spec.w)), h = Math.round(mm(spec.h)), photo = photoCanvas(w, h);
  const usedW = nx * spec.w + (nx - 1) * gap, usedH = ny * spec.h + (ny - 1) * gap;
  const x0 = (pw - usedW) / 2, y0 = (ph - strip - usedH) / 2;
  ctx.strokeStyle = "#b5b5b5"; ctx.lineWidth = 2;
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
    const x = Math.round(mm(x0 + i * (spec.w + gap))), y = Math.round(mm(y0 + j * (spec.h + gap)));
    ctx.drawImage(photo, x, y);
    ctx.strokeRect(x - 1, y - 1, w + 2, h + 2);
  }
  ctx.fillStyle = "#666"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.direction = "rtl";
  const note = spec.label + " · اطبع على ورق 10×15 سم بالحجم الفعلي دون تكبير · altrendat.com";
  let size = Math.round(mm(2.6));
  ctx.font = size + "px Cairo, Tahoma, Arial, sans-serif";
  const fit = (sheet.width - mm(2 * margin)) / ctx.measureText(note).width;
  if (fit < 1) ctx.font = Math.floor(size * fit) + "px Cairo, Tahoma, Arial, sans-serif";
  ctx.fillText(note, sheet.width / 2, sheet.height - mm(margin + strip / 2 - 1));
  save(await setDpi(await toJpeg(sheet, 0.93), DPI), "print-10x15-" + spec.slug + ".jpg");
}

// ── ربط الأحداث ─────────────────────────────────────────────────────────

function init() {
  for (const id of ["idp-file", "idp-cam"]) {
    const el = $(id);
    if (el) el.addEventListener("change", () => { const f = el.files[0]; el.value = ""; handleFile(f); });
  }
  const drop = $("idp-drop");
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); handleFile(e.dataTransfer.files[0]); });

  $("idp-zoom").addEventListener("input", (e) => { S.adj.zoom = +e.target.value; render(); });
  $("idp-rot").addEventListener("input", (e) => { S.adj.rot = +e.target.value; render(); });
  $("idp-bg").addEventListener("change", (e) => { S.bgOn = e.target.checked; syncControls(); render(); });
  $("idp-bgcolor").addEventListener("change", (e) => { S.bgColor = e.target.value; render(); });
  $("idp-guides").addEventListener("change", (e) => { S.guides = e.target.checked; render(); });
  $("idp-reset").addEventListener("click", () => { S.adj = { zoom: 1, dx: 0, dy: 0, rot: 0 }; syncControls(); render(); });
  document.querySelectorAll("[data-idp-move]").forEach((b) => b.addEventListener("click", () => {
    const [dx, dy] = b.getAttribute("data-idp-move").split(",").map(Number);
    S.adj.dx += dx * 0.01; S.adj.dy += dy * 0.01; render();
  }));
  const doc = $("idp-doc");
  if (doc) doc.addEventListener("change", () => applySpec(doc.value));

  // سحب الصورة داخل الإطار بالماوس (على اللمس تُستخدم الأسهم حتى لا يتعطل تمرير الصفحة)
  const cv = $("idp-canvas");
  let drag = null;
  cv.addEventListener("pointerdown", (e) => { if (e.pointerType !== "mouse") return; drag = { x: e.clientX, y: e.clientY, dx: S.adj.dx, dy: S.adj.dy }; cv.setPointerCapture(e.pointerId); });
  cv.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const r = cv.getBoundingClientRect();
    S.adj.dx = drag.dx + (e.clientX - drag.x) / r.width;
    S.adj.dy = drag.dy + (e.clientY - drag.y) / r.height;
    render();
  });
  const end = () => { drag = null; };
  cv.addEventListener("pointerup", end);
  cv.addEventListener("pointercancel", end);

  $("idp-dl-photo").addEventListener("click", downloadPhoto);
  $("idp-dl-sheet").addEventListener("click", downloadSheet);
  $("idp-again").addEventListener("click", () => { $("idp-work").hidden = true; $("idp-drop").classList.remove("done"); $("idp-drop").scrollIntoView({ behavior: "smooth", block: "center" }); });
  applySpec(DATA.current);
  window.__idp = { S, handleFile, photoCanvas, checks };   // للفحص اليدوي من الكونسول
}

init();
