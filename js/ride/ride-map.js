// 内联骑行轨迹地图：优先用 ride.gpx 真实轨迹，否则退化到正文 geo-pin 锚点连线。
// 地图用 Leaflet（开源无 key）；默认高德底图（GCJ-02，国内可直连），含卫星/路网/
// 暗色/地形等多套样式可切换；海拔剖面用 amCharts 5（独立 canvas）。
(function () {
  "use strict";

  // 第三方底图 key（均为前端公开 key）。统一从 _config.yml 经 post.html 注入的
  // window.RIDE_MAP_CONFIG 读取，不在代码里硬编码，便于集中管理与轮换。
  var CFG = (typeof window !== "undefined" && window.RIDE_MAP_CONFIG) || {};
  var TIANDITU_KEY = CFG.tiandituKey || "";         // 天地图：地形回退源（OpenTopoMap 被墙时自动切换）
  var AMAP_WEB_KEY = CFG.amapKey || "";             // 高德 Web 端(JS API) key
  var AMAP_WEB_SERVICE_KEY = CFG.amapWebServiceKey || ""; // 高德 Web 服务(REST) key，预留给地理编码/路径规划等

  var canvas = document.getElementById("ride-map-canvas");
  if (!canvas) return;

  var statusEl = document.getElementById("ride-map-status");
  function setStatus(msg, kind) {
    if (!statusEl) return;
    statusEl.className = "ride-map__status" + (kind ? " " + kind : "");
    statusEl.textContent = msg;
    statusEl.style.display = ""; // 任何新状态都确保可见（覆盖之前的隐藏）
  }
  function showError(label, err) {
    var detail = (err && (err.stack || err.message)) || String(err);
    console.error("[ride-map]", label, err);
    setStatus("✗ " + label + "\n" + detail, "err");
  }

  // 收集正文 geo-pin 锚点（按文档顺序）
  function collectAnchors() {
    var els = document.querySelectorAll(".geo-pin[data-lat][data-lng]");
    var pts = [];
    els.forEach(function (el) {
      var lat = parseFloat(el.getAttribute("data-lat"));
      var lng = parseFloat(el.getAttribute("data-lng"));
      if (isNaN(lat) || isNaN(lng)) return;
      pts.push({ latitude: lat, longitude: lng, title: (el.textContent || "").trim() });
    });
    return pts;
  }

  // WGS-84 -> GCJ-02（高德/智图等国内瓦片是 GCJ-02 坐标系，GPX 是 WGS-84，
  // 必须偏移后才能和底图道路对齐，否则路线会"飘"在路外侧几十~几百米）
  function wgs84ToGcj02(lng, lat) {
    var pi = Math.PI, a = 6378245.0, ee = 0.00669342162296594323;
    function outOfChina(l, t) { return l < 72.004 || l > 137.8347 || t < 0.8293 || t > 55.8271; }
    function tLat(x, y) { var r = -100 + 2*x + 3*y + 0.2*y*y + 0.1*x*y + 0.2*Math.sqrt(Math.abs(x));
      r += (20*Math.sin(6*x*pi) + 20*Math.sin(2*x*pi))*2/3;
      r += (20*Math.sin(y*pi) + 40*Math.sin(y/3*pi))*2/3;
      r += (160*Math.sin(y/12*pi) + 320*Math.sin(y*pi/30))*2/3; return r; }
    function tLng(x, y) { var r = 300 + x + 2*y + 0.1*x*x + 0.1*x*y + 0.1*Math.sqrt(Math.abs(x));
      r += (20*Math.sin(6*x*pi) + 20*Math.sin(2*x*pi))*2/3;
      r += (20*Math.sin(x*pi) + 40*Math.sin(x/3*pi))*2/3;
      r += (150*Math.sin(x/12*pi) + 300*Math.sin(x/30*pi))*2/3; return r; }
    if (outOfChina(lng, lat)) return [lng, lat];
    var dLat = tLat(lng - 105, lat - 35), dLng = tLng(lng - 105, lat - 35);
    var radLat = lat / 180 * pi, magic = Math.sin(radLat);
    magic = 1 - ee * magic * magic; var sm = Math.sqrt(magic);
    dLat = (dLat * 180) / ((a * (1 - ee)) / (magic * sm) * pi);
    dLng = (dLng * 180) / (a / sm * Math.cos(radLat) * pi);
    return [lng + dLng, lat + dLat];
  }
  // 把 GPX 点 {latitude,longitude} 转成 Leaflet 需要的 [lat,lng]（已转 GCJ-02）
  function toGcj(p) { var g = wgs84ToGcj02(p.longitude, p.latitude); return [g[1], g[0]]; }

  // Haversine 两点间距离（km），用于把 GPS 点换算成累计里程
  function haversine(a, b) {
    var R = 6371, toRad = function (d) { return d * Math.PI / 180; };
    var dLat = toRad(b.latitude - a.latitude), dLng = toRad(b.longitude - a.longitude);
    var la1 = toRad(a.latitude), la2 = toRad(b.latitude);
    var h = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
              Math.cos(la1) * Math.cos(la2) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return 2 * R * Math.asin(Math.sqrt(h));
  }

  // 由带海拔的点生成海拔剖面：[{distance, elevation, grade}]（distance=累计 km）
  // grade 为当前点相对前一点的坡度（%），首点为 null。
  // 任一缺海拔则整段放弃（返回 null），调用方据此隐藏剖面，优雅降级。
  function buildProfile(pts) {
    var prof = [], cum = 0;
    for (var i = 0; i < pts.length; i++) {
      if (pts[i].elevation == null) return null;
      if (i > 0) cum += haversine(pts[i - 1], pts[i]);
      var grade = null;
      if (i > 0) {
        var segDist = haversine(pts[i - 1], pts[i]);
        grade = segDist > 0 ? ((pts[i].elevation - pts[i - 1].elevation) / (segDist * 1000)) * 100 : 0;
        grade = +grade.toFixed(1);
      }
      prof.push({
        distance: +cum.toFixed(2),
        elevation: Math.round(pts[i].elevation),
        grade: grade,
        gradeText: grade == null ? "—" : ((grade > 0 ? "+" : "") + grade + "%"),
        latitude: pts[i].latitude,    // 联动地图临时点需要经纬度
        longitude: pts[i].longitude
      });
    }
    return prof.length >= 2 ? prof : null;
  }

  // 抽稀：profile 点数过多（真实轨迹常几百~上千点）时，均匀抽稀到 maxN 个点，
  // 避免下面"每段一个系列"的坡度分色逻辑创建过多 series 拖慢渲染。末端点必保留。
  function decimateProfile(prof, maxN) {
    if (!prof || prof.length <= maxN) return prof;
    var step = prof.length / maxN, out = [];
    for (var i = 0; i < maxN; i++) out.push(prof[Math.floor(i * step)]);
    out.push(prof[prof.length - 1]);
    return out;
  }

  // 坡度分类：抽稀点 ~750m/点，相邻点坡度噪声大，会在 3%/6% 阈值附近反复横跳，
  // 导致海拔图被切成无数色阶。这里用"固定距离窗口"平滑：点 j 的段坡度 = 从 j 出发
  // 接下来一段距离内（默认约 3% 总长，0.5–3km 自适应）的累计爬升/距离，再按 SLOPE_TIERS
  // 归入 5 档。这样同一段路只有一种颜色，与图例完全一致。
  function recomputeGrades(prof) {
    if (!prof || prof.length < 2) return prof;
    var n = prof.length;
    var total = prof[n - 1].distance;
    // 自适应窗口：3% 总里程，最小 0.5km、最大 3km；短路线不至于过度平滑，长路线足够压住噪声。
    var windowDist = Math.max(0.5, Math.min(total * 0.03, 3.0));
    var minWindowPts = 3; // 至少往前看 3 个点，避免窗口比抽稀间距还短导致没平滑效果

    // 1) 先保留每个点本身的 raw grade（前一点→当前点），给 tooltip 保留细节坡度
    for (var i = 1; i < n; i++) {
      var d = prof[i].distance - prof[i - 1].distance;
      var g = 0;
      if (d > 0) {
        g = +(((prof[i].elevation - prof[i - 1].elevation) / (d * 1000)) * 100).toFixed(1);
      } else if (prof[i - 1].grade != null) {
        g = prof[i - 1].grade;
      }
      prof[i] = Object.assign({}, prof[i], { grade: g, gradeText: (g > 0 ? "+" : "") + g + "%" });
    }
    if (prof[0].grade == null) {
      var g0 = n > 1 ? prof[1].grade : 0;
      prof[0] = Object.assign({}, prof[0], { grade: g0, gradeText: (g0 > 0 ? "+" : "") + g0 + "%" });
    }

    // 2) 用窗口计算"段坡度"，决定分类与海拔图填充颜色
    var smoothed = [];
    for (var j = 0; j < n - 1; j++) {
      var sumDist = 0, sumElev = 0;
      var k = j;
      while (k < n - 1 && (sumDist < windowDist || (k - j) < minWindowPts)) {
        var d = prof[k + 1].distance - prof[k].distance;
        sumDist += d;
        sumElev += prof[k + 1].elevation - prof[k].elevation;
        k++;
      }
      var g = sumDist > 0 ? +(sumElev / (sumDist * 1000) * 100).toFixed(1) : 0;
      smoothed.push(g);
    }
    var lastSmooth = smoothed.length ? smoothed[smoothed.length - 1] : 0;

    // 3) 写入每个点的 segment* 字段：tooltip/单车/海拔图填充全部同源
    for (var j = 0; j < n - 1; j++) {
      var g = smoothed[j];
      prof[j] = Object.assign({}, prof[j], {
        segmentGrade: g,
        segmentGradeText: (g > 0 ? "+" : "") + g + "%",
        segmentHex: slopeHex(g)
      });
    }
    prof[n - 1] = Object.assign({}, prof[n - 1], {
      segmentGrade: lastSmooth,
      segmentGradeText: (lastSmooth > 0 ? "+" : "") + lastSmooth + "%",
      segmentHex: slopeHex(lastSmooth)
    });

    // 4) 去掉短噪声段：连续同色的点如果少于 2 个点（相当于~1.5km），且左右邻居同色，
    //    把它并到邻居里去，防止窗口边界偶尔冒出一个孤点色块。
    var minRun = 2;
    for (var pass = 0; pass < 3; pass++) { // 最多 3 轮，稳定即止
      var runStart = 0;
      var changed = false;
      for (var i = 1; i <= n; i++) {
        var curHex = prof[Math.min(i, n - 1)].segmentHex;
        var prevHex = prof[runStart].segmentHex;
        if (i === n || curHex !== prevHex) {
          var runLen = i - runStart;
          if (runLen < minRun && i < n && runStart > 0) {
            var leftHex = prof[runStart - 1].segmentHex;
            var rightHex = prof[i].segmentHex;
            var targetHex = leftHex;
            if (leftHex === rightHex) targetHex = leftHex;
            else if (rightHex === prevHex) targetHex = rightHex; // 优先延到不同侧
            for (var m = runStart; m < i; m++) {
              prof[m] = Object.assign({}, prof[m], { segmentHex: targetHex });
            }
            changed = true;
          }
          runStart = i;
        }
      }
      if (!changed) break;
    }
    return prof;
  }

  // 合并相邻同色坡度段，每个 segment 是一段连续 profile 点，用同一颜色填充到 yMin。
  // 与 recomputeGrades 的窗口平滑配合，最终海拔图只有图例 5 档色块，不再碎成色阶。
  function buildSegments(prof) {
    var segs = [];
    if (!prof || prof.length < 2) return segs;
    var start = 0;
    for (var i = 1; i < prof.length; i++) {
      var curHex = prof[start].segmentHex || slopeHex(prof[start].grade);
      var nextHex = prof[i].segmentHex || slopeHex(prof[i].grade);
      if (nextHex !== curHex) {
        segs.push({ hex: curHex, data: prof.slice(start, i + 1) }); // 重叠 1 点保曲线连续
        start = i;
      }
    }
    segs.push({
      hex: prof[start].segmentHex || slopeHex(prof[start].grade),
      data: prof.slice(start, prof.length)
    });
    return segs;
  }

  // 爬坡分级：参考 Velonews 权威口径，综合「长度 + 平均坡度」两个指标。
  // 该定义本身带主观性，这里把模糊描述落地为可计算的边界，逐级下探取最高满足档。
  //   HC ：≥10km 且 ≥7.5%，或 ≥25km 且 ≥6%
  //   1级：≥8km  且 ≥8%，  或 ≥20km 且 ≥5%
  //   2级：≥5km  且 ≥8%，  或 ≥15km 且 ≥4%
  //   3级：≥1.6km 且 ≥10%，或 ≥9.6km 且 ≥1%（中长缓坡）
  //   4级：其余真实爬坡（默认兜底，最轻松）
  function classifyClimb(lenKm, avgGrad) {
    if (lenKm >= 25 && avgGrad >= 6) return "HC";
    if (lenKm >= 10 && avgGrad >= 7.5) return "HC";
    if (lenKm >= 20 && avgGrad >= 5) return "1";
    if (lenKm >= 8 && avgGrad >= 8) return "1";
    if (lenKm >= 15 && avgGrad >= 4) return "2";
    if (lenKm >= 5 && avgGrad >= 8) return "2";
    if (lenKm >= 9.6 && avgGrad >= 1) return "3";
    if (lenKm >= 1.6 && avgGrad >= 10) return "3";
    return "4";
  }

  // 从完整海拔剖面自动识别爬坡段：距离窗口平滑去 GPS 噪声 → 找连续「净上升」段
  // → 每段算长度/爬升/平均坡度并按 Velonews 定级。返回每段峰顶坐标供图上标等级徽标。
  function detectClimbs(prof) {
    var climbs = [];
    if (!prof || prof.length < 2) return climbs;
    var n = prof.length;
    // 距离窗口平滑（±0.15km）：抹掉气压/里程计的短噪声，但保留真实爬坡形态
    var HALF = 0.15, i, k;
    var smooth = new Array(n);
    for (i = 0; i < n; i++) {
      var s = 0, c = 0;
      for (k = 0; k < n; k++) {
        if (Math.abs(prof[k].distance - prof[i].distance) <= HALF) { s += prof[k].elevation; c++; }
      }
      smooth[i] = s / c;
    }
    var MIN_LEN = 0.4, MIN_GAIN = 150; // 短于 0.4km 或爬升 <150m 不当作独立爬坡
    i = 1;
    while (i < n) {
      if (smooth[i] > smooth[i - 1] + 0.5) {
        var start = i - 1, j = i;
        // 连续「非下降」段（容忍 <0.5m 的小起伏，避免一个爬坡被切成多段）
        while (j < n && smooth[j] >= smooth[j - 1] - 0.5) j++;
        var end = j - 1;
        var lenKm = prof[end].distance - prof[start].distance;
        var gain = prof[end].elevation - prof[start].elevation;
        if (lenKm >= MIN_LEN && gain >= MIN_GAIN) {
          var peakIdx = start;
          for (var p = start; p <= end; p++) {
            if (prof[p].elevation > prof[peakIdx].elevation) peakIdx = p;
          }
          var avgGrad = lenKm > 0 ? gain / (lenKm * 10) : 0;
          climbs.push({
            startDist: prof[start].distance, endDist: prof[end].distance,
            peak: { distance: prof[peakIdx].distance, elevation: prof[peakIdx].elevation },
            lengthKm: +lenKm.toFixed(2),
            gainM: Math.round(gain),
            avgGrad: +avgGrad.toFixed(1),
            category: classifyClimb(lenKm, avgGrad)
          });
        }
        i = j;
      } else {
        i++;
      }
    }
    return climbs;
  }

  // 比赛风起点/终点标记：起点=三角绿旗 pennant（尖角飘旗，更经典的「发车」视觉），
  // 终点=黑白棋盘格旗 + 旗杆顶圆球 finial（金色，像颁奖/终点门顶饰）。
  // 用 SVG + divIcon 渲染，不依赖外部图片，且能浮在任意底图上（固定色，随主题不变）。
  var FLAG_POLE = "#4a4a4a";   // 旗杆
  var FINIAL = "#e0a82e";       // 终点杆顶圆球（金，finisher 顶饰）
  var FINIAL_ED = "#b9861f";
  var START_FLAG_SVG =
    '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" xmlns="http://www.w3.org/2000/svg">' +
      '<line x1="6" y1="3" x2="6" y2="21.5" stroke="' + FLAG_POLE + '" stroke-width="1.7" stroke-linecap="round"/>' +
      '<path d="M6 4 L18 7.5 L6 11 Z" fill="#1faa4b" stroke="#157a37" stroke-width="0.6" stroke-linejoin="round"/>' +
    '</svg>';
  var FINISH_FLAG_SVG =
    '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" xmlns="http://www.w3.org/2000/svg">' +
      '<line x1="6" y1="3.8" x2="6" y2="21.5" stroke="' + FLAG_POLE + '" stroke-width="1.7" stroke-linecap="round"/>' +
      '<circle cx="6" cy="2.4" r="1.7" fill="' + FINIAL + '" stroke="' + FINIAL_ED + '" stroke-width="0.4"/>' +
      '<defs><pattern id="rideChkFin" width="3.3" height="3.3" patternUnits="userSpaceOnUse">' +
        '<rect width="3.3" height="3.3" fill="#ffffff"/>' +
        '<rect width="1.65" height="1.65" fill="#1a1a1a"/>' +
        '<rect x="1.65" y="1.65" width="1.65" height="1.65" fill="#1a1a1a"/>' +
      '</pattern></defs>' +
      '<rect x="6" y="4" width="13" height="9" fill="url(#rideChkFin)" stroke="#1a1a1a" stroke-width="0.4"/>' +
    '</svg>';

  // 注入地图图例浮层（起点/终点/路线；无 GPX 时含途经点），避免与地图原生控件混用
  // showWaypoint=false（有 GPX）：只起/终/路线，不显示途经点；
  // showWaypoint=true（无 GPX，用正文 geo-pin 锚点）：含途经点。
  function addLegend(showWaypoint) {
    if (!canvas || canvas.querySelector(".ride-map__legend")) return;
    var legend = document.createElement("div");
    legend.className = "ride-map__legend";
    legend.setAttribute("aria-hidden", "true");
    legend.innerHTML =
      '<span class="lg-item"><i class="lg-flag">' + START_FLAG_SVG + '</i>起点</span>' +
      (showWaypoint ? '<span class="lg-item"><i class="lg-dot lg-waypoint"></i>途经点</span>' : '') +
      '<span class="lg-item"><i class="lg-flag">' + FINISH_FLAG_SVG + '</i>终点</span>' +
      '<span class="lg-item"><i class="lg-line"></i>路线</span>';
    canvas.appendChild(legend);
  }

  // 海拔剖面图：地图下方沿里程的海拔起伏曲线（带坡度分色填充）
  // profile = [{distance, elevation, grade}]；无数据则隐藏容器优雅降级
  // 双模式：记录最近一次海拔图绘制参数，供主题切换时重绘使用
  var lastElevProfile = null, lastElevHooks = null, elevRoot = null;
  // 与站点 common.js 的主题判定保持一致：body.theme-dark 即深色
  function rideIsDark() {
    return document.body.classList.contains("theme-dark");
  }

  // 坡度 → CSS 颜色串（与海拔图分段配色同源）。供地图联动单车图标复用：
  // hover 时按当前点坡度取色，使单车与海拔图 1:1 联动。
  // 坡度配色单一数据源：上坡=暖色、下坡=冷色、平路=中性绿。
  // 平路 <3%、缓 ±3~6%、陡 >±6%。图表分段 + 悬停单车 + 下方 colorbar 均从此查，改一处全改。
  var SLOPE_TIERS = [
    { test: function (g) { return g >  6; }, hex: "#ff5a5a", label: "陡上", range: ">6%" },     // 陡上坡 红
    { test: function (g) { return g >  3; }, hex: "#ffb347", label: "缓上", range: "3%–6%" },  // 缓上坡 橙
    { test: function (g) { return g < -6; }, hex: "#4a90e2", label: "陡下", range: "<-6%" },    // 陡下坡 蓝
    { test: function (g) { return g < -3; }, hex: "#87ceeb", label: "缓下", range: "-6%–-3%" }, // 缓下坡 浅蓝
    { test: function (g) { return true;  }, hex: "#7ed321", label: "平路", range: "±3% 内" }      // 平路 绿（兜底）
  ];
  function slopeHex(g) {
    if (g == null) g = 0;
    for (var i = 0; i < SLOPE_TIERS.length; i++) {
      if (SLOPE_TIERS[i].test(g)) return SLOPE_TIERS[i].hex;
    }
    return "#7ed321";
  }

  // 海拔图分段 series 引用 + 当前坡度过滤态（供图例点击过滤）。模块级，主题重绘时刷新。
  var elevSegSeries = [];
  var elevLineSeries = null;
  var elevTierFilter = null; // 激活过滤的坡度色 hex；null = 显示全部
  var elevCursorTip = null; // 自制 cursor tooltip 容器（挂 .ride-elevation 下，绕开 amCharts tooltip 堆叠上下文）
  // 按 elevTierFilter 高亮/压暗各分段：匹配的保持原色，未匹配的降到近乎透明，
  // 脊线(lineSeries)始终保留但压暗，使路线轮廓不丢失。图例 data-tier 与分段 _tierHex
  // 均为 SLOPE_TIERS 的同一 hex 字符串，点击即按色精确匹配——这也是配色一致性的反向证明。
  function applyTierFilter() {
    if (!elevSegSeries || !elevSegSeries.length) return;
    for (var s = 0; s < elevSegSeries.length; s++) {
      var seg = elevSegSeries[s];
      var on = !elevTierFilter || seg._tierHex === elevTierFilter;
      // 过滤：未选中分段直接隐藏；amCharts 5 对 Series 的 visible 设置立即可生效，
      // 比改模板/遍历 sprite/改容器 opacity 都可靠。脊线(lineSeries)始终保留作为路线轮廓。
      seg.set("visible", on);
    }
    if (elevLineSeries) {
      // 有过滤时脊线稍微压暗，让选中段更突出；无过滤时恢复正常
      elevLineSeries.set("opacity", elevTierFilter ? 0.35 : 1);
    }
  }

  // amCharts 5 免费版署名 logo（branding）：Root 创建后即插入 DOM，但延迟约 3 秒
  // 才动画可见；该元素无稳定 class（非 .am5-logo），无授权即强制显示、API 关不掉。
  // 这里按它写死的 svgPath 特征精准移除，并用持久 MutationObserver 对主题重绘兜底。
  // 购商业授权后改用 root.set("logo", false) 合规移除即可，本函数可整体删除。
  var amLogoKillerInstalled = false;
  function installAmLogoKiller() {
    function removeBranding() {
      var conts = document.querySelectorAll(".am5-tooltip-container");
      for (var c = 0; c < conts.length; c++) {
        var kids = conts[c].children;
        for (var k = 0; k < kids.length; k++) {
          var g = kids[k];
          if (!g.querySelectorAll) continue;
          var paths = g.querySelectorAll("path");
          for (var p = 0; p < paths.length; p++) {
            var d = paths[p].getAttribute("d") || "";
            // amCharts branding 写死的两条 svgPath 前缀，精确命中、不误伤真实 tooltip
            if (d.indexOf("M5 25 L13") === 0 || d.indexOf("M83.4 25h-31") === 0) {
              if (g.parentNode) g.parentNode.removeChild(g);
              return;
            }
          }
        }
      }
    }
    if (!amLogoKillerInstalled) {
      amLogoKillerInstalled = true;
      removeBranding();
      // 监听文档子树：branding 在 root init 时即创建（仅 3 秒后可见）；
      // 主题切换重绘会 dispose 旧 root 并 new 新 root、重建 branding，observer 持续兜底。
      var mo = new MutationObserver(function () { removeBranding(); });
      mo.observe(document.documentElement, { childList: true, subtree: true });
    } else {
      removeBranding();
    }
  }

  // 把"最高海拔/平均坡度"等指标回填到骑行数据卡片（.ride-stats）。
  // 幂等：已存在同 data-stat 的元素（作者 front matter 静态填的）只更新数值不重复追加，
  // 也不覆盖作者填的静态值（检测到存在即跳过 append）。无 GPX 的文章不调用本函数。
  function injectRideStat(key, val, label) {
    var box = document.querySelector(".ride-stats");
    if (!box) return;
    var existing = box.querySelector('.ride-stat[data-stat="' + key + '"]');
    if (existing) {
      var v = existing.querySelector(".ride-stat__val");
      if (v) v.textContent = val;
      return;
    }
    var el = document.createElement("div");
    el.className = "ride-stat";
    el.setAttribute("data-stat", key);
    el.innerHTML = '<span class="ride-stat__val">' + val + '</span>' +
                   '<span class="ride-stat__label">' + label + '</span>';
    box.appendChild(el);
  }

  function drawElevation(profile, hooks) {
    var elevCanvas = document.getElementById("ride-elevation-canvas");
    if (!elevCanvas) return null;
    // 外层容器（.ride-elevation）负责定位和放置 overlay 药丸/info 面板；
    // 内层 #ride-elevation-canvas 是 amCharts root，保持 overflow:hidden 圆角。
    var elevWrap = elevCanvas.parentElement;
    // 主题切换重绘：先释放旧根，避免同容器重复 new Root 抛 "already in use"
    if (elevRoot) { try { elevRoot.dispose(); } catch (e) {} elevRoot = null; }
    // 主题重绘：清空上一次的分段 series 引用与坡度过滤态（图例是兄弟节点，不随 dispose 销毁）
    elevSegSeries = [];
    elevLineSeries = null;
    elevTierFilter = null;
    if (!profile || profile.length < 2 || typeof am5xy === "undefined" ||
        typeof am5themes_Animated === "undefined") {
      // 无逐点海拔（无 GPX / 锚点缺海拔）：隐藏整个海拔图区域，避免留下空白盒子
      elevCanvas.hidden = true;
      if (elevWrap) elevWrap.style.display = "none";
      return null;
    }
    // 有数据：恢复显示（主题重绘或首次绘制都可能需要复位）
    elevCanvas.hidden = false;
    if (elevWrap) elevWrap.style.display = "";
    // 鼠标离开海拔图区域时，通知地图隐藏联动临时单车点（onLeave 由调用方注入）
    elevCanvas.onmouseleave = function () {
      if (elevCursorTip) elevCursorTip.style.display = "none";
      if (hooks && hooks.onLeave) hooks.onLeave();
    };
    try {
      // 海拔剖面派生统计：最高海拔 + 平均坡度，回填到骑行数据卡片。
      // 用抽稀前的完整 profile 算，maxElev/ascent 更准；作者 front matter 已填则保留静态值。
      var _elevsAll = profile.map(function (p) { return p.elevation; });
      var maxElev = Math.round(Math.max.apply(null, _elevsAll));
      var minElev = Math.round(Math.min.apply(null, _elevsAll));
      var _ascentAll = 0;
      for (var _ai = 1; _ai < profile.length; _ai++) {
        var _dE = profile[_ai].elevation - profile[_ai - 1].elevation;
        if (_dE > 0) _ascentAll += _dE;
      }
      var _totalKmAll = profile.length ? profile[profile.length - 1].distance : 0;
      // 平均坡度(%) = 累计上升(m) / 总距离(m) * 100（与码表"平均坡度"口径一致）
      var _avgGradePct = _totalKmAll > 0 ? +(_ascentAll / (_totalKmAll * 10)).toFixed(1) : 0;
      injectRideStat("max_elevation", maxElev, "最高海拔 m");
      injectRideStat("min_elevation", minElev, "最低海拔 m");
      injectRideStat("avg_grade", _avgGradePct + "%", "平均坡度");

      // 爬坡分级标志：在完整轨迹上识别每段连续爬坡并按 Velonews(长度+坡度)定级，
      // 在海拔图每个爬坡峰顶放等级徽标（drawElevation 末尾绘制）。用完整 profile 更准。
      var _climbs = detectClimbs(profile);
      if (_climbs.length) {
        var _rank = { "4": 1, "3": 2, "2": 3, "1": 4, "HC": 5 };
        var _top = _climbs[0];
        for (var _ci = 1; _ci < _climbs.length; _ci++) {
          if (_rank[_climbs[_ci].category] > _rank[_top.category]) _top = _climbs[_ci];
        }
        injectRideStat("hardest_climb", _top.category === "HC" ? "HC" : _top.category + "级", "最难爬坡");
      }

      // 真实轨迹可能几百~上千点：抽稀到 ≤200 点，避免分段系列过多拖慢渲染
      profile = decimateProfile(profile, 200);
      // 抽稀后把每个点的 grade/gradeText 重算为"段坡度"（前一点→本点），
      // 让段着色、图例过滤(_tierHex)、tooltip 坡度、地图联动单车配色统一口径。
      profile = recomputeGrades(profile);

      // 海拔轴不从 0 起，改为"最低海拔附近"起步并紧贴最高海拔、收紧范围，
      // 让起伏在有限高度内更突出（用户要求）。留少量上下余量防端点贴边。
      // 用完整轨迹的极值（而非抽稀后）定轴范围，确保爬坡峰顶徽标不被裁切。
      var _eMin = Math.min.apply(null, _elevsAll);
      var _eMax = Math.max.apply(null, _elevsAll);
      var eRange = (_eMax - _eMin) || 1;
      var yMin = Math.floor(_eMin - eRange * 0.10);
      var yMax = Math.ceil(_eMax + eRange * 0.08);
      // 总里程 = 剖面最后一个点的累计距离，x 轴上限钉到这里，避免末尾空白。
      var totalDistance = profile.length ? profile[profile.length - 1].distance : 0;

      var root = am5.Root.new("ride-elevation-canvas");
      // 删除 amCharts 5 免费版强制署名 logo（见 installAmLogoKiller 说明）
      installAmLogoKiller();
      // 应用站点自定义字体（Orbitron 为主、中文回退到正文栈），让坐标轴标签/
      // 轴标题/图例/tooltip 等所有图表文字与全站视觉一致。amCharts 5 通过
      // 自定义 theme 的 rule("Label")/rule("Text") 覆盖默认字体族即可全局生效。
      var ELEV_FONT = "'Orbitron', 'Proza Libre', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif";
      var fontTheme = am5.Theme.new(root);
      fontTheme.rule("Label").setAll({ fontFamily: ELEV_FONT });
      fontTheme.rule("Text").setAll({ fontFamily: ELEV_FONT });
      root.setThemes([am5themes_Animated.new(root), fontTheme]);

      // 双模式配色：坐标轴文字 / 描边 / 网格线随主题切换，保证两种模式都可读
      var isDark = rideIsDark();
      var AXIS_TEXT = isDark ? am5.color(0xb8bcc0) : am5.color(0x9a9a9a); // 轴文字
      var OUTLINE   = isDark ? am5.color(0xe2e6ea) : am5.color(0x2c2c2c); // 全程描边
      var GRID_COL  = isDark ? am5.color(0x3a3f45) : am5.color(0xe6e6e6); // 网格线

      var chart = root.container.children.push(am5xy.XYChart.new(root, {
        panX: false, panY: false, wheelX: "none", wheelY: "none",
        layout: root.verticalLayout,
        // 图顶留白条：用 chart padding 真实腾出 56px，药丸以 HTML overlay 浮在此处，
        // 不压剖面曲线；比用 amCharts bullet 在绘图区边缘硬挤更稳。
        paddingTop: 56
      }));

      // x 轴：累计里程 (km)，min=0、max=GPX 总距离，strictMinMax 关掉默认取整，
      // 使曲线末端正好顶到轴右端、不留空白。
      var xAxis = chart.xAxes.push(am5xy.ValueAxis.new(root, {
        renderer: am5xy.AxisRendererX.new(root, { minGridDistance: 60 }),
        min: 0, max: totalDistance, strictMinMax: true
      }));
      xAxis.children.push(am5.Label.new(root, {
        text: "里程 (km)", fontSize: 11, fontWeight: "500", fill: AXIS_TEXT,
        x: am5.percent(100), centerX: am5.percent(100), paddingRight: 4, paddingTop: 4
      }));

      // y 轴：海拔。不从 0 起，改为从"最低海拔附近"(yMin) 紧贴最高(yMax)，
      // strictMinMax 关掉默认内边距，让起伏填满纵向空间、更突出。
      var yAxis = chart.yAxes.push(am5xy.ValueAxis.new(root, {
        renderer: am5xy.AxisRendererY.new(root, { minGridDistance: 60, paddingLeft: 0, paddingRight: 0 }),
        min: yMin, max: yMax, strictMinMax: true
      }));
      // y 轴标签：缩小字号+弱化颜色，避免数字喧宾夺主（海拔曲线才是主体）
      var yLabels = yAxis.get("renderer").labels.template;
      yLabels.setAll({ fontSize: 10, fontWeight: "400", fill: AXIS_TEXT, paddingLeft: 0, paddingRight: 0 });
      // 数字缩写：≥1000 → "2K"（2000→2K、1669→1.7K），缩短标签、减小左侧占用
      yLabels.adapters.add("text", function (text) {
        var n = parseFloat(String(text).replace(/[^0-9.\-]/g, ""));
        if (isNaN(n) || n < 1000) return text;
        var k = n / 1000, r = Math.round(k);
        return (Math.abs(k - r) < 0.05 ? r : k.toFixed(1)) + "K";
      });
      // x 轴里程数字：与 y 轴标签同色，随主题切换。
      // ⚠️ 双模式坑：amCharts Animated 主题不设文字色，轴刻度数字默认落到 amCharts
      //    基色（深色）；dark 模式下黑字压在深底上直接隐身。必须显式设为 AXIS_TEXT
      //    才同时覆盖两种模式（y 轴已如此处理，x 轴此前漏设 → 仅 dark 模式失效）。
      var xLabels = xAxis.get("renderer").labels.template;
      xLabels.setAll({ fontSize: 10, fontWeight: "400", fill: AXIS_TEXT, paddingTop: 2, paddingBottom: 0 });
      // 网格线随主题：深色模式用暗灰避免“无网格”，浅色模式用浅灰
      xAxis.get("renderer").grid.template.setAll({ stroke: GRID_COL });
      yAxis.get("renderer").grid.template.setAll({ stroke: GRID_COL });
      // 竖排标题「海拔 (m)」已删：单位已在 hover tooltip 中显示，避免左侧占位。

      // 坡度配色：统一从 IIFE 级 SLOPE_TIERS 查（与悬停单车、colorbar 同源），避免漂移
      function gradeColor(g) {
        return parseInt(slopeHex(g).slice(1), 16);
      }
      function gradeText(g) {
        if (g == null) return "—";
        return (g > 0 ? "+" : "") + g + "%";
      }

      // 1) 分段面积系列：合并相邻同色坡度段，减少 series 数量、提升视觉连贯性，
      // 避免原先 200 个独立小段把海拔图切成细碎竖条。
      var segments = buildSegments(profile);
      for (var s = 0; s < segments.length; s++) {
        var seg = segments[s];
        var color = am5.color(parseInt(seg.hex.slice(1), 16));
        var segSeries = chart.series.push(am5xy.LineSeries.new(root, {
          xAxis: xAxis, yAxis: yAxis,
          valueXField: "distance", valueYField: "elevation"
        }));
        segSeries.strokes.template.setAll({ stroke: color, strokeWidth: 2.5 });
        // amCharts 5 LineSeries 默认会给 fill 加一个垂直 fillGradient，导致纯色被
        // 冲淡/渐变成其他色阶，和图例 5 档纯色对不上。这里用一个两端同色的
        // "伪渐变" 覆盖默认 gradient，确保填充就是 SLOPE_TIERS 的纯色。
        var solidFill = am5.LinearGradient.new(root, {
          stops: [{ color: color }, { color: color }]
        });
        segSeries.fills.template.setAll({ fill: color, fillOpacity: 1, fillGradient: solidFill, visible: true });
        segSeries.data.setAll(seg.data);
        segSeries._tierHex = seg.hex; // 供图例点击过滤时按色精确匹配
        elevSegSeries.push(segSeries);
      }

      // 2) 完整描边 + tooltip：覆盖全程的细线，悬停显示距离/海拔/坡度
      var lineSeries = chart.series.push(am5xy.LineSeries.new(root, {
        xAxis: xAxis, yAxis: yAxis,
        valueXField: "distance", valueYField: "elevation",
        tooltip: am5.Tooltip.new(root, {
          labelHTML: '<div style="font-size:12px;line-height:1.5">'
            + '<div>距离：{valueX} km</div>'
            + '<div>海拔：{valueY} m</div>'
            + '<div>坡度：{segmentGradeText}</div>'
            + '</div>'
        })
      }));
      // 中性 spine：脊线更细（1.5）且不抢戏，坡度色主要靠下方 0.55 填充面积强读
      lineSeries.strokes.template.setAll({ stroke: OUTLINE, strokeWidth: 1.5 });
      lineSeries.fills.template.setAll({ visible: false });
      lineSeries.data.setAll(profile);
      elevLineSeries = lineSeries; // 供图例过滤时压暗脊线、保留路线轮廓

      // 悬停联动：光标吸附到曲线最近点，把当前点回传给地图。
      var cursor = chart.set("cursor", am5xy.XYCursor.new(root, {
        behavior: "none", xAxis: xAxis, yAxis: yAxis, snapToSeries: [lineSeries]
      }));
      cursor.lineY.set("visible", false); // 隐藏水平参考线
      // 竖直指示线：默认贯穿整个绘图区且太抢眼。改成极淡的细短划线，
      // 仅作 x 位置参照，不抢海拔曲线主体（深/浅主题分别取接近背景的中灰）。
      cursor.lineX.setAll({
        stroke: am5.color(isDark ? 0x4b5563 : 0xd1d5db),
        strokeDasharray: [2, 6],
        strokeOpacity: 0.15,
        strokeWidth: 1
      });
      // 正确取数：amCharts 5 当前悬停的数据项在 series 的 tooltipDataItem
      // （不是 tooltip.dataItem——Tooltip 实例无公开 dataItem 属性，取它会恒为 undefined）。
      // 两条监听互为兜底：datatooltipchanged 在 tooltip 显隐/切换时触发；
      // cursormoved 在光标移动时持续触发，确保即使前者漏触发也能联动。
      function emitHover() {
        var di = lineSeries.get("tooltipDataItem");
        if (di && di.dataContext) {
          var d = di.dataContext;
          // 自制 cursor tooltip：填充距离/海拔/坡度并跟随光标定位（z-index:200 稳压药丸条）
          if (elevCursorTip) {
            elevCursorTip.innerHTML =
              '<div class="rect-row"><span class="rect-k">距离</span><span class="rect-v">' + Number(d.distance).toFixed(1) + ' km</span></div>'
              + '<div class="rect-row"><span class="rect-k">海拔</span><span class="rect-v">' + Math.round(d.elevation) + ' m</span></div>'
              + '<div class="rect-row"><span class="rect-k">坡度</span><span class="rect-v">' + (d.segmentGradeText || "-") + '</span></div>';
            elevCursorTip.style.display = "block";
            var p = cursor.point;
            if (p) {
              var tw = elevCursorTip.offsetWidth || 132, th = elevCursorTip.offsetHeight || 64;
              // position:fixed + body 挂载：用 canvas 视口坐标把 amCharts 内部点(p.x/p.y 相对 canvas)
              // 换算成视口坐标，彻底脱离图表卡片的堆叠上下文。
              var rect = elevCanvas.getBoundingClientRect();
              var left = rect.left + p.x + 14, top = rect.top + p.y + 14;
              if (left + tw > window.innerWidth) left = rect.left + p.x - tw - 14;
              if (top + th > window.innerHeight) top = rect.top + p.y - th - 14;
              elevCursorTip.style.position = "fixed";
              elevCursorTip.style.left = left + "px";
              elevCursorTip.style.top = top + "px";
            }
          }
          // 地图联动（复用同源 segmentHex，保证单车/海拔段/图例三处一致）
          if (hooks && hooks.onHover) hooks.onHover(Object.assign({}, d));
        } else {
          if (elevCursorTip) elevCursorTip.style.display = "none";
          if (hooks && hooks.onLeave) hooks.onLeave();
        }
      }
      lineSeries.events.on("datatooltipchanged", emitHover);
      cursor.events.on("cursormoved", emitHover);

      // 爬坡分级标志（A3+B3+C+D1+E1 综合方案）：
      //  · 药丸用 HTML overlay 浮在图顶「留白条」里，不压剖面曲线(A3)；
      //  · 灰阶深浅编码难度：HC 最深 → 4级 最浅，与坡度色条零冲突(B3)；
      //  · 药丸两行：上行等级、下行「长度·爬升」(D1)，悬停看该段完整实测(C)；
      //  · 多爬坡挨近时按 x 距离就近分到两行错开，避免重叠(E1)；
      //  · 仅一条极淡虚线从图顶(yMax)到峰顶作位置参照。
      if (_climbs && _climbs.length) {
        // 灰阶难度：HC 最深 → 4级 最浅，与 grill 预览一致（越来越淡）
        var CLIMB_GRAY = {
          "HC": { bg: 0x1f2937, fg: 0xffffff },
          "1":  { bg: 0x374151, fg: 0xffffff },
          "2":  { bg: 0x4b5563, fg: 0xffffff },
          "3":  { bg: 0x6b7280, fg: 0xffffff },
          "4":  { bg: 0xd1d5db, fg: 0x111111 }  // 4级最浅，黑字确保可读
        };
        var GUIDE_COL = isDark ? am5.color(0x4b5563) : am5.color(0xc4c9d0);
        // E1：按峰值 x 距离就近分到 row0/row1 两行，挤不下换行错开
        var _cGap = (totalDistance || 1) * 0.06;
        var _lastR0 = -Infinity, _lastR1 = -Infinity;
        _climbs.forEach(function (cl) {
          if (cl.peak.distance - _lastR0 >= _cGap) { cl._row = 0; _lastR0 = cl.peak.distance; }
          else if (cl.peak.distance - _lastR1 >= _cGap) { cl._row = 1; _lastR1 = cl.peak.distance; }
          else { cl._row = (_lastR0 <= _lastR1) ? 0 : 1;
                 if (cl._row === 0) _lastR0 = cl.peak.distance; else _lastR1 = cl.peak.distance; }
        });
        // 极淡虚线：图顶(yMax) → 峰顶，仅作位置参照
        _climbs.forEach(function (cl) {
          var guide = chart.series.push(am5xy.LineSeries.new(root, {
            xAxis: xAxis, yAxis: yAxis,
            valueXField: "distance", valueYField: "elevation"
          }));
          guide.strokes.template.setAll({
            stroke: GUIDE_COL, strokeWidth: 1,
            strokeDasharray: [3, 3], strokeOpacity: 0.5
          });
          guide.data.setAll([
            { distance: cl.peak.distance, elevation: yMax },
            { distance: cl.peak.distance, elevation: cl.peak.elevation }
          ]);
        });
        // HTML overlay 药丸条：放在 .ride-elevation 顶部（chart paddingTop 区域）
        var existingStrip = elevWrap.querySelector(".ride-elev-climbs");
        if (!existingStrip) {
          var climbStrip = document.createElement("div");
          climbStrip.className = "ride-elev-climbs";
          var _PILL_FONT = "'Orbitron','Proza Libre',\"PingFang SC\",\"Hiragino Sans GB\",\"Microsoft YaHei\",sans-serif";
          _climbs.forEach(function (cl) {
            var _gc = CLIMB_GRAY[cl.category] || CLIMB_GRAY["4"];
            var _cat = cl.category === "HC" ? "HC" : cl.category + "级";
            var _sub = "起点 " + cl.startDist.toFixed(1) + "km · 长 " + cl.lengthKm + "km";
            var _tip = _cat + " · 起点 " + cl.startDist.toFixed(1) + "km  长 " + cl.lengthKm + "km  爬升 " + cl.gainM
                     + "m  均坡 " + cl.avgGrad + "%";
            var _pill = document.createElement("div");
            _pill.className = "rec-climb rec-climb--r" + (cl._row || 0);
            _pill.style.left = ((cl.peak.distance / totalDistance) * 100) + "%";
            _pill.style.backgroundColor = "#" + _gc.bg.toString(16).padStart(6, "0");
            _pill.style.color = "#" + _gc.fg.toString(16).padStart(6, "0");
            _pill.style.fontFamily = _PILL_FONT;
            _pill.innerHTML = '<span class="rec-cat">' + _cat + '</span>'
              + '<span class="rec-sub">' + _sub + '</span>'
              + '<span class="rec-tip" style="font-family:' + _PILL_FONT + '">' + _tip + '</span>';
            climbStrip.appendChild(_pill);
          });
          elevWrap.appendChild(climbStrip);
        }
      }

      chart.appear(1000, 100);
      // 自制 cursor tooltip（方案④，根治 Issue①）：彻底绕开 amCharts 自带 tooltip 容器——
      // 原生 .am5-tooltip-container 挂在 canvas(amCharts root) 内，被其堆叠上下文困住、
      // 再高 z-index 也压不过图顶药丸条(.ride-elev-climbs z5)；且 amCharts 重绘/lazy show
      // 会把容器重新挂回 canvas，一次性移出/MutationObserver 兜底均不可靠（前 3 次尝试均失败）。
      // 这里改用普通 DOM div；关键：挂到 document.body 并用 position:fixed 定位，
      // 使其处于根堆叠上下文、z-index:99999，彻底脱离图表卡片(.ride-elevation)的层级体系——
      // 图表内任何 overlay(图顶药丸条 .ride-elev-climbs / 药丸 hover .rec-tip)都不可能盖过它。
      // 此前挂在 .ride-elevation 内的方案(即使 z-index:200)在真浏览器仍被药丸条压住，
      // 根因是 .ride-elevation 或其祖先形成的堆叠上下文把 200 困在了卡片内；body 级 fixed 无此问题。
      // amCharts 原生 tooltip 由 _ride.scss 的 display:none 隐藏，但 tooltip 配置保留，
      // 以确保 tooltipDataItem 仍被更新（地图联动 hover 取数不丢）。
      if (elevCursorTip && elevCursorTip.parentNode) elevCursorTip.parentNode.removeChild(elevCursorTip);
      elevCursorTip = document.createElement("div");
      elevCursorTip.className = "ride-elev-cursor-tip";
      elevCursorTip.setAttribute("aria-hidden", "true");
      elevCursorTip.style.display = "none";
      document.body.appendChild(elevCursorTip);
      lastElevProfile = profile; lastElevHooks = hooks; elevRoot = root;

      // 坡度 colorbar 图例：从 SLOPE_TIERS 自动生成，插在图表容器之后；
      // 单一数据源保证与分段/单车配色一致。点击某档可过滤高亮对应坡度段（反向验证配色一致）。
      // 用独立 try 包裹：图例构建失败绝不连累已渲染好的图表（catch 仅 warn）。
      try {
        var elevWrap = elevCanvas.parentElement;
        // 图例放在 .ride-elevation 外部（作为下一个兄弟），避免被图表 canvas/overlay 遮挡，
        // 同时保留在 ride-summary 内随主题一起出现/消失。
        var legHost = elevWrap && elevWrap.parentElement;
        if (legHost) {
          var existingLeg = document.getElementById("ride-elev-legend");
          if (!existingLeg) {
            var leg = document.createElement("div");
            leg.id = "ride-elev-legend";
            leg.className = "ride-elev-legend";
            // 图例按直观顺序展示（平路→上坡→下坡），颜色/文字仍取自 SLOPE_TIERS
            var LEGEND_ORDER = ["平路", "缓上", "陡上", "缓下", "陡下"];
            var legHtml = "";
            for (var o = 0; o < LEGEND_ORDER.length; o++) {
              for (var t = 0; t < SLOPE_TIERS.length; t++) {
                if (SLOPE_TIERS[t].label === LEGEND_ORDER[o]) {
                  // data-tier 与分段内部 _tierHex 同为 SLOPE_TIERS 的 hex 字符串，点击即按色精确匹配
                  legHtml += '<span class="rel-item" role="button" tabindex="0" aria-pressed="false"'
                           + ' data-tier="' + SLOPE_TIERS[t].hex + '">'
                           + '<i style="background:' + SLOPE_TIERS[t].hex + '"></i>'
                           + '<span class="rel-label">' + SLOPE_TIERS[t].label + '</span>'
                           + '<span class="rel-range">' + SLOPE_TIERS[t].range + '</span>'
                           + '</span>';
                  break;
                }
              }
            }
            leg.innerHTML = legHtml;
            // 放在 .ride-elevation 之后，确保不在 absolute 图表内部、不被任何 overlay 盖住
            elevWrap.insertAdjacentElement("afterend", leg);
            existingLeg = leg;
            // 仅首次构建时绑定交互（图例是外部兄弟节点，dispose 不销毁，重绘会重复进入此块）
            var legItems = existingLeg.querySelectorAll(".rel-item");
            Array.prototype.forEach.call(legItems, function (it) {
              function toggle() {
                var hex = it.getAttribute("data-tier");
                elevTierFilter = (elevTierFilter === hex) ? null : hex; // 再次点同档=取消过滤
                Array.prototype.forEach.call(legItems, function (o) {
                  var on = (o === it) && !!elevTierFilter;
                  o.setAttribute("aria-pressed", on ? "true" : "false");
                  o.classList.toggle("is-active", on);
                });
                applyTierFilter();
              }
              it.addEventListener("click", toggle);
              it.addEventListener("keydown", function (e) {
                if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
              });
            });
          }
          // 每次重绘都清掉图例高亮态（模块级 filter 已在开头重置为 null）
          var allItems = existingLeg.querySelectorAll(".rel-item");
          Array.prototype.forEach.call(allItems, function (o) {
            o.setAttribute("aria-pressed", "false");
            o.classList.remove("is-active");
          });
        }
      } catch (le) {
        console.warn("[ride-elevation] legend build skipped:", le);
      }

      // 爬坡分级说明（C：info 图标 + 可展开面板，列出 5 级定义，本程出现的等级高亮）。
      // 右上角 ℹ 点开看完整分级体系，平时零占用；药丸悬停则看该段实测(C 单段联动)。
      try {
      // 爬坡分级说明（C）：右上角 ℹ 点开看完整 5 级定义面板。
      // 必须 append 到 elevCanvas 自身（.ride-elevation，position:relative），
      // 之前 append 到 parentElement（.ride-summary，无 relative）导致绝对定位跑偏。
      if (_climbs && _climbs.length && elevCanvas) {
          if (!elevWrap.querySelector(".ride-elev-info")) {
            var _CTIERS = [
              { c: "HC", cond: "≥10km 且 ≥7.5%，或 ≥25km 且 ≥6%" },
              { c: "1",  cond: "≥8km 且 ≥8%，或 ≥20km 且 ≥5%" },
              { c: "2",  cond: "≥5km 且 ≥8%，或 ≥15km 且 ≥4%" },
              { c: "3",  cond: "≥1.6km 且 ≥10%，或 ≥9.6km 且 ≥1%" },
              { c: "4",  cond: "其余真实爬坡（最轻松）" }
            ];
            // 灰阶难度：HC 最深 → 4级 最浅，与 grill 预览一致（越来越淡）；4级最浅(#d1d5db)配黑字保证可读
            var _CGRAY = { "HC": "#1f2937", "1": "#374151", "2": "#4b5563", "3": "#6b7280", "4": "#d1d5db" };
            var _rows = "";
            for (var _i = 0; _i < _CTIERS.length; _i++) {
              var _t = _CTIERS[_i];
              // 说明面板是「分级体系解释」，5 级说明文字统一由 CSS 控制（颜色/字体一致），
              // 不在 JS 里写 inline style，避免 HTML 属性引号冲突导致 4级 样式解析异常。
              _rows += '<div class="rel-climb-row">'
                + '<span class="rel-climb-pill" style="background:' + _CGRAY[_t.c] + ';color:' + (_t.c === "4" ? "#111" : "#fff") + '">'
                + (_t.c === "HC" ? "HC" : _t.c + "级") + '</span>'
                + '<span class="rel-climb-cond">' + _t.cond + '</span></div>';
            }
            var _FONT = "'Orbitron','Proza Libre','PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif";
            var _btn = document.createElement("button");
            _btn.type = "button";
            _btn.className = "ride-elev-info";
            _btn.setAttribute("aria-label", "爬坡分级说明");
            _btn.setAttribute("aria-expanded", "false");
            _btn.textContent = "i";
            // 兜底：即使 CSS 未加载或 specificity 被覆盖，也确保在 .ride-elevation 右上角
            _btn.style.cssText = "position:absolute;top:5px;right:5px;z-index:10;font-family:" + _FONT + ";";
            var _panel = document.createElement("div");
            _panel.className = "ride-elev-climb-legend";
            _panel.setAttribute("role", "dialog");
            _panel.setAttribute("aria-label", "爬坡分级定义");
            _panel.style.cssText = "font-family:" + _FONT + ";";
            _panel.innerHTML = '<h4 style="font-family:' + _FONT + '">爬坡分级（Velonews）</h4>' + _rows;
            _btn.addEventListener("click", function (e) {
              e.stopPropagation();
              var _open = _panel.classList.toggle("is-open");
              _btn.setAttribute("aria-expanded", _open ? "true" : "false");
            });
            document.addEventListener("click", function (e) {
              if (_panel.classList.contains("is-open") && e.target !== _btn && !_panel.contains(e.target)) {
                _panel.classList.remove("is-open");
                _btn.setAttribute("aria-expanded", "false");
              }
            });
            elevWrap.appendChild(_btn);
            elevWrap.appendChild(_panel);
          }
        }
      } catch (ie) {
        console.warn("[ride-elevation] climb-info skipped:", ie);
      }
      return profile;
    } catch (e) {
      elevCanvas.hidden = true;
      console.error("[ride-elevation]", e);
      return null;
    }
  }

  // 解析 GPX：trkpt / rtept / wpt，取 lat/lon + 内嵌 <ele> 海拔（自闭合无 ele 则 elevation=null）
  function parseGpx(text) {
    var pts = [];
    var startRe = /<(trkpt|rtept|wpt)\b([^>]*)>/g; // 起始标签（兼容自闭合 .../>）
    var m;
    while ((m = startRe.exec(text)) !== null) {
      var attrs = m[2];
      var ll = /lat="([-\d.]+)"\s+lon="([-\d.]+)"/.exec(attrs) ||
                /lon="([-\d.]+)"\s+lat="([-\d.]+)"/.exec(attrs); // 兼容 lon 在前
      if (!ll) continue;
      // 取该点起始标签之后、到对应闭合标签（</trkpt> 或 />）之间的片段，找 <ele>
      var after = text.slice(m.index + m[0].length);
      var closeIdx = after.search(/<\/(?:trkpt|rtept|wpt)>|\/>/);
      var seg = closeIdx >= 0 ? after.slice(0, closeIdx) : "";
      var ele = /<ele>([-\d.]+)<\/ele>/.exec(seg);
      pts.push({
        latitude: parseFloat(ll[1]),
        longitude: parseFloat(ll[2]),
        elevation: ele ? parseFloat(ele[1]) : null,
        title: ""
      });
    }
    return pts;
  }

  function initMap(points, showWaypoint) {
    if (typeof L === "undefined") {
      showError("Leaflet 资源未加载", "请检查 /js/vendors/leaflet/leaflet.js 是否 200");
      return;
    }
    try {
      // 真实地形底图引擎：Leaflet（开源、无 key）。
      // fitBounds 是 Leaflet 原生能力，把路线边界框进视口，彻底根治 amCharts 下
      // 「初始占比怎么调都不放大」的问题。
      var map = L.map("ride-map-canvas", {
        attributionControl: true,
        zoomControl: true,
        scrollWheelZoom: true,
        minZoom: 2 // 防止默认/异常时缩到世界视图，导致高德无瓦片而黑屏
      });
      // 关键：建图后立即给一个初始视图，让地图先完成初始化（_loaded=true）。
      // 否则下方 fitBounds 若被 whenReady 卡住，地图会永远停在「未初始化」状态
      // （getCenter/getZoom 抛 "Set map center and zoom first" → 瓦片与绿线全黑）。
      map.setView([34.85, 104.1], 5); // 甘南附近，fitBounds 会立即覆盖为路线视图
      window.__rideMap = map; // 调试用：Chrome Console 可查 window.__rideMap.getZoom() / .fitBounds(...)

      // 国内可直连的底图样式（高德系带 Web key；地形 OpenTopoMap 优先，失败自动回退天地图）。
      // gcj：该底图是否 GCJ-02 坐标系（true=是，false=WGS-84）。路线坐标会据此在
      //   GCJ-02 / WGS-84 间自动切换，保证与底图道路对齐；否则路线会飘在路外侧。
      //   高德系全部 GCJ-02；地形 OpenTopoMap 与天地图回退源 ter_w/cta_w 均为 WGS-84，一致。
      //   注：原「智图 Geoq(灰底/暖色/紫底)」服务已停服(国内亦不可达)，改为
      //   复用高德道路瓦片 + CSS 滤镜着色，保证可靠、坐标对齐。
      // className：可选，给瓦片 <img> 加 class（暗色/着色滤镜用）。
      // fallback：可选，主源加载失败时自动切换的兜底源（地形专用）。
      // 高德(AutoNavi)栅格子域：道路/路网 webrd01-04、卫星 webst01-04，已带 key。
      var BASE_MAXZOOM = 18;
      var baseStyles = [
        { key: "road",      label: "道路", sub: "1234", max: 18, gcj: true,
          url: "https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=7&x={x}&y={y}&z={z}" + "&key=" + AMAP_WEB_KEY,
          attr: "© 高德地图 AutoNavi" },
        { key: "satellite", label: "卫星", sub: "1234", max: 18, gcj: true,
          url: "https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}" + "&key=" + AMAP_WEB_KEY,
          attr: "© 高德地图 AutoNavi 卫星影像" },
        { key: "hybrid",    label: "卫星混合", sub: "1234", max: 18, gcj: true,
          url: "https://webst0{s}.is.autonavi.com/appmaptile?style=8&x={x}&y={y}&z={z}" + "&key=" + AMAP_WEB_KEY,
          attr: "© 高德地图 AutoNavi 卫星影像 + 路网" },
        { key: "network",   label: "路网", sub: "1234", max: 18, gcj: true,
          url: "https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}" + "&key=" + AMAP_WEB_KEY,
          attr: "© 高德地图 AutoNavi" },
        { key: "gray",      label: "灰底", sub: "1234", max: 18, gcj: true, className: "ride-gray-tiles",
          url: "https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=7&x={x}&y={y}&z={z}" + "&key=" + AMAP_WEB_KEY,
          attr: "© 高德地图 AutoNavi" },
        { key: "warm",      label: "暖色", sub: "1234", max: 18, gcj: true, className: "ride-warm-tiles",
          url: "https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=7&x={x}&y={y}&z={z}" + "&key=" + AMAP_WEB_KEY,
          attr: "© 高德地图 AutoNavi" },
        { key: "purple",    label: "紫底", sub: "1234", max: 18, gcj: true, className: "ride-purple-tiles",
          url: "https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=7&x={x}&y={y}&z={z}" + "&key=" + AMAP_WEB_KEY,
          attr: "© 高德地图 AutoNavi" },
        { key: "dark",      label: "暗色", sub: "1234", max: 18, gcj: true, className: "ride-dark-tiles",
          url: "https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=7&x={x}&y={y}&z={z}" + "&key=" + AMAP_WEB_KEY,
          attr: "© 高德地图 AutoNavi" },
        { key: "terrain",   label: "地形", sub: "abc", max: 17, gcj: false,
          url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
          attr: "© OpenTopoMap (CC-BY-SA) · © OpenStreetMap 贡献者",
          fallback: {
            sub: "01234567", max: 18,
            url: "https://t{s}.tianditu.gov.cn/ter_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=ter&STYLE=default&TILEMATRIXSET=w&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&FORMAT=tiles&tk=" + TIANDITU_KEY,
            labelUrl: "https://t{s}.tianditu.gov.cn/cta_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=cta&STYLE=default&TILEMATRIXSET=w&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&FORMAT=tiles&tk=" + TIANDITU_KEY,
            attr: "© 天地图 GS(2023)332号"
          } }
      ];
      var currentBaseKey = "gray";   // 默认灰底图
      var currentBaseLayer = null;
      var switched = false;          // 防 tileerror 风暴重复切换
      function applyBase(key) {
        var cfg = null;
        for (var i = 0; i < baseStyles.length; i++) {
          if (baseStyles[i].key === key) { cfg = baseStyles[i]; break; }
        }
        if (!cfg) return;
        switched = false;
        if (currentBaseLayer && map.hasLayer(currentBaseLayer)) map.removeLayer(currentBaseLayer);
        currentBaseLayer = null;
        var tileOpts = { subdomains: cfg.sub, maxZoom: cfg.max, attribution: cfg.attr };
        if (cfg.className) tileOpts.className = cfg.className; // 暗色/着色滤镜等

        if (cfg.fallback) {
          // 地形：先上 OpenTopoMap；若被墙(国内常事)则在 tileerror 自动切天地图
          // (ter_w + cta_w 标注层，同 WGS-84，与 OpenTopoMap 坐标一致，路线无需二次切换)。
          var grp = L.layerGroup();
          var primary = L.tileLayer(cfg.url, tileOpts);
          var fellBack = false;
          primary.on("tileerror", function () {
            if (fellBack) return;
            fellBack = true;
            if (map.hasLayer(primary)) map.removeLayer(primary);
            grp.removeLayer(primary);
            var fb = cfg.fallback;
            var fbGroup = L.layerGroup();
            L.tileLayer(fb.url, { subdomains: fb.sub, maxZoom: fb.max, attribution: fb.attr }).addTo(fbGroup);
            if (fb.labelUrl) {
              L.tileLayer(fb.labelUrl, { subdomains: fb.sub, maxZoom: fb.max, attribution: fb.attr }).addTo(fbGroup);
            }
            fbGroup.addTo(map);
            grp.addLayer(fbGroup);
            currentBaseLayer = grp;
            setStatus("⚠ OpenTopoMap 加载失败，已自动切换天地图地形", "warn");
          });
          grp.addLayer(primary);
          grp.addTo(map);
          currentBaseLayer = grp;
        } else {
          currentBaseLayer = L.tileLayer(cfg.url, tileOpts).addTo(map);
          currentBaseLayer.on("tileerror", function () {
            if (switched) return;
            switched = true;
            if (key !== "road") {
              setStatus("⚠ 底图「" + cfg.label + "」加载失败，已切回道路图", "warn");
              applyBase("road");
            } else {
              setStatus("✗ 底图加载失败：请检查网络或挂代理后刷新", "err");
            }
          });
        }

        currentBaseKey = key;
        // 坐标系切换：地形图(OpenTopoMap / 天地图回退源)是 WGS-84，其余 GCJ-02。切换时
        // 重建轨迹/标记使路线与新底图对齐（否则错位几十~几百米）。首屏 applyBase
        // 时轨迹尚未绘制（routeUseGcj 未定义），此处跳过、由 drawRoute(true) 兜底。
        // 注：天地图回退源 ter_w/cta_w 同为 WGS-84，与 OpenTopoMap 一致，无需二次切换。
        var useGcj = (cfg.gcj !== false);
        if (typeof routeUseGcj !== "undefined" && useGcj !== routeUseGcj) {
          drawRoute(useGcj);
        }
        // 更新样式切换按钮高亮态 + 读屏选中态
        if (canvas) {
          var btns = canvas.querySelectorAll(".ride-map__style-btn");
          for (var b = 0; b < btns.length; b++) {
            var on = btns[b].getAttribute("data-key") === key;
            btns[b].classList.toggle("is-active", on);
            btns[b].setAttribute("aria-pressed", on ? "true" : "false");
          }
        }
      }
      // 地图样式切换按钮组（右上角），点击实时换底图，不影响当前视图
      function addStyleBar() {
        if (!canvas || canvas.querySelector(".ride-map__stylebar")) return;
        var bar = document.createElement("div");
        bar.className = "ride-map__stylebar";
        bar.setAttribute("role", "group");
        bar.setAttribute("aria-label", "地图样式");
        baseStyles.forEach(function (s) {
          var btn = document.createElement("button");
          btn.type = "button";
          var on = s.key === currentBaseKey;
          btn.className = "ride-map__style-btn" + (on ? " is-active" : "");
          btn.textContent = s.label;
          btn.setAttribute("data-key", s.key);
          btn.setAttribute("aria-pressed", on ? "true" : "false");
          btn.setAttribute("title", "切换为" + s.label + "底图");
          btn.addEventListener("click", function () { applyBase(s.key); });
          bar.appendChild(btn);
        });
        canvas.appendChild(bar);
      }
      applyBase(currentBaseKey);
      addStyleBar();

      // 经纬度按底图坐标系取：GCJ-02（国内瓦片）或 WGS-84（Esri 地形）。
      // 路线/标记随底图坐标系切换而重建，保证与底图道路对齐（否则错位几十~几百米）。
      function latLngOf(p, useGcj) {
        return useGcj ? toGcj(p) : [p.latitude, p.longitude];
      }
      function buildLineCoords(pts, useGcj) {
        return pts.map(function (p) { return latLngOf(p, useGcj); });
      }

      // 标记配置（途经点用灰点；起/终点用比赛风旗帜，见下方 drawRoute 的 divIcon）
      var WAYPOINT_GRAY = "#83807a";
      var pointData = points.map(function (p, i) {
        var isStart = (i === 0);
        var isEnd = (i === points.length - 1);
        // 有 GPX（showWaypoint=false）：真实轨迹点密集，只标起/终，不画途经点；
        // 无 GPX（showWaypoint=true，正文 geo-pin 锚点）：中间锚点即途经点，全部标出。
        var isWaypoint = showWaypoint && !isStart && !isEnd;
        var role = isStart ? "起点" : (isEnd ? "终点" : (isWaypoint ? "途经点" : ""));
        return {
          latitude: p.latitude, longitude: p.longitude,
          title: p.title || role || ("点 " + (i + 1)),
          isStart: isStart, isEnd: isEnd, isWaypoint: isWaypoint
        };
      }).filter(function (p) {
        return p.isStart || p.isEnd || p.isWaypoint; // 只保留起/终/途经
      });

      // 轨迹线 + 标记 + hover 临时点：随底图坐标系（GCJ-02 / WGS-84）重建
      var routeLine = null;
      var routeMarkers = [];
      var hoverMarker = null;
      var routeUseGcj = true;
      function clearRoute() {
        if (routeLine) { map.removeLayer(routeLine); routeLine = null; }
        routeMarkers.forEach(function (m) { map.removeLayer(m); });
        routeMarkers = [];
        if (hoverMarker && map.hasLayer(hoverMarker)) map.removeLayer(hoverMarker);
        // 注意：重绘路线时只把联动临时点从地图移除、不置空 hoverMarker 引用，
        // 否则切底图触发 drawRoute 后会丢失 bike 标记对象，hover 时 setLatLng 报错。
      }
      function drawRoute(useGcj) {
        clearRoute();
        routeUseGcj = useGcj;
        // 轨迹线（品牌绿）
        routeLine = L.polyline(buildLineCoords(points, useGcj), {
          color: "#00ff6d", weight: 3, opacity: 0.95,
          lineJoin: "round", lineCap: "round"
        }).addTo(map);
        // 标记点：起/终点用比赛风旗帜（绿旗=起点、棋盘格=终点），
        // 途经点保持灰点。旗帜用 divIcon + 内联 SVG，固定色、随主题不变。
        pointData.forEach(function (p) {
          var latlng = latLngOf(p, useGcj);
          if (p.isStart || p.isEnd) {
            var flagIcon = L.divIcon({
              className: "ride-flag-icon",
              html: p.isStart ? START_FLAG_SVG : FINISH_FLAG_SVG,
              iconSize: [24, 24], iconAnchor: [6, 21] // 旗杆底部对准 GPS 点
            });
            var mk = L.marker(latlng, {
              icon: flagIcon, riseOnHover: true,
              zIndexOffset: p.isEnd ? 600 : 500
            }).bindTooltip(p.title, { direction: "top", offset: [0, -10] }).addTo(map);
            routeMarkers.push(mk);
          } else {
            var mk2 = L.circleMarker(latlng, {
              radius: 4, color: WAYPOINT_GRAY, weight: 2, fillColor: WAYPOINT_GRAY, fillOpacity: 1
            }).bindTooltip(p.title, { direction: "top", offset: [0, -4] }).addTo(map);
            routeMarkers.push(mk2);
          }
        });
      }
      drawRoute(true); // 默认 GCJ-02（与高德/智图对齐）

      // 初始视图：fitBounds 原生把路线边界框进视口；
      // padding 取容器较小边的 8%，使路线占约 84%（即用户要的 80-90% 占比）。
      function fitToRoute() {
        try {
          var size = map.getSize();
          if (!size || size.x < 5 || size.y < 5) { requestAnimationFrame(fitToRoute); return; }
          var bounds = routeLine.getBounds();
          if (!bounds || !bounds.isValid || !bounds.isValid()) {
            throw new Error("路线边界无效 (bounds=" + bounds + ")");
          }
          var pad = Math.round(Math.min(size.x, size.y) * 0.08);
          map.fitBounds(bounds, { padding: [pad, pad], maxZoom: 15, animate: false });
          // 强制 Leaflet 重新计算容器尺寸，避免初始化时容器尚未完成布局导致空白
          setTimeout(function () { map.invalidateSize({ animate: false }); }, 50);
        } catch (e) {
          console.error("[ride-map] fitBounds 失败", e);
          // 降级：取路线中心点，固定 zoom 10，确保至少能看到内容
          try {
            var ll = routeLine.getLatLngs();
            var flat = Array.isArray(ll[0]) ? ll[0] : ll; // polyline 返回一维数组
            var sumLat = 0, sumLng = 0, n = 0;
            flat.forEach(function (pt) { sumLat += pt.lat; sumLng += pt.lng; n++; });
            if (n > 0) {
              map.setView([sumLat / n, sumLng / n], 10, { animate: false });
              setTimeout(function () { map.invalidateSize({ animate: false }); }, 50);
            }
            setStatus("⚠ 自动聚焦失败，已降级显示中心区域", "warn");
          } catch (e2) {
            showError("无法聚焦路线", e);
          }
        }
      }
      // 注意：不能用 map.whenReady(fitToRoute) —— whenReady 在「地图首次 setView」后
      // 才触发，而首次 setView 正是 fitToRoute 里的 fitBounds，会形成死锁，地图永远
      // 不初始化（瓦片/绿线全黑）。地图建图时已 setView 完成初始化，直接调用即可；
      // 若此刻容器还没撑开（宽高<5），fitToRoute 内的 rAF 会重试直到尺寸就绪。
      fitToRoute();
      // 再兜底一次：容器可能在脚本执行后才被布局撑开
      setTimeout(function () { map.invalidateSize({ animate: false }); }, 300);

      // 悬停联动：海拔图 hover → 地图动态临时点（对应 GPS 坐标）。
      // 用单车图标（divIcon + 内联 SVG）替代原绿点：白色光晕描边 + 坡度色核心，
      // 在任意底图上都清晰；颜色由 showHoverPoint 按当前点坡度（slopeHex）改写，
      // 使单车与海拔图 1:1 联动。interactive:false 避免遮挡地图交互。
      var BIKE_PATHS =
        '<circle cx="5.5" cy="16.5" r="3"/>' +
        '<circle cx="18.5" cy="16.5" r="3"/>' +
        '<path d="M5.5 16.5l3-7h4.5L18.5 16.5"/>' +
        '<path d="M8.5 9.5L13 16.5"/>' +
        '<path d="M13 9.5h3.2"/>' +
        '<path d="M8.5 9.5l-1.2-2"/>';
      var bikeIcon = L.divIcon({
        className: "ride-hover-bike",
        html: '<svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke-linecap="round" stroke-linejoin="round">' +
                '<g stroke="#ffffff" stroke-width="3.6">' + BIKE_PATHS + '</g>' +   // 白色光晕描边（恒显，保证与绿线分离）
                '<g stroke="currentColor" stroke-width="1.7">' + BIKE_PATHS + '</g>' + // 坡度色核心（JS 按坡度改写容器 color）
              '</svg>',
        iconSize: [30, 30],
        iconAnchor: [15, 15]
      });
      var lastHoverKey = "";
      var hoverMarker = L.marker([0, 0], { icon: bikeIcon, interactive: false, keyboard: false, zIndexOffset: 1000 });
      function showHoverPoint(ctx) {
        if (!ctx || ctx.latitude == null || ctx.longitude == null) return;
        var key = ctx.distance + ":" + ctx.elevation;
        if (key === lastHoverKey) return; // 去抖：同一剖面点不重复重绘
        lastHoverKey = key;
        hoverMarker.setLatLng(latLngOf(ctx, routeUseGcj));
        if (!map.hasLayer(hoverMarker)) hoverMarker.addTo(map);
        // 坡度联动：单车颜色跟随海拔图"当前段"坡度（红陡上/橙缓上/绿平/蓝下），
        // 与海拔图填充段颜色 1:1 对齐；优先用预计算的 segmentHex，回退到点坡度。
        var el = hoverMarker.getElement();
        if (el) el.style.color = ctx.segmentHex || slopeHex(ctx.grade);
      }
      function clearHoverPoint() {
        lastHoverKey = "";
        if (map.hasLayer(hoverMarker)) map.removeLayer(hoverMarker);
      }

      addLegend(showWaypoint);
      // 海拔剖面：仅当轨迹含逐点海拔（GPX <ele>）时绘制，否则隐藏。
      // 传 hooks 实现「海拔 hover → 地图临时点」联动。
      drawElevation(buildProfile(points), {
        onHover: showHoverPoint,
        onLeave: clearHoverPoint
      });
      setStatus("✓ 路线已加载（" + points.length + " 个点）", "ok");
      setTimeout(function () { if (statusEl && statusEl.classList.contains("ok")) statusEl.style.display = "none"; }, 2500);

      // 兜底诊断：1.2s 后如果地图还停留在默认世界视图(zoom<=1 或中心接近 0,0)，
      // 说明 fitBounds / whenReady 没生效，强制回到路线中心 zoom 10。
      setTimeout(function () {
        if (!map) return;
        try {
          var z = map.getZoom(), c = map.getCenter();
          if (z <= 1 || (Math.abs(c.lat) < 1 && Math.abs(c.lng) < 1)) {
            var ll = routeLine.getLatLngs();
            var flat = Array.isArray(ll[0]) ? ll[0] : ll;
            var sumLat = 0, sumLng = 0, n = 0;
            flat.forEach(function (pt) { sumLat += pt.lat; sumLng += pt.lng; n++; });
            if (n > 0) {
              map.setView([sumLat / n, sumLng / n], 10, { animate: false });
              map.invalidateSize({ animate: false });
              setStatus("⚠ 初始视图异常，已强制居中到路线区域", "warn");
            }
          }
        } catch (e) { console.warn("[ride-map] 兜底诊断失败", e); }
      }, 1200);
    } catch (e) {
      showError("地图初始化失败", e);
    }
  }

  var gpx = window.__rideGpx || "";
  var anchors = collectAnchors();

  if (gpx) {
    fetch(gpx).then(function (r) {
      if (!r.ok) throw new Error("GPX 请求 " + r.status);
      return r.text();
    }).then(function (txt) {
      var pts = parseGpx(txt);
      if (pts.length >= 2) initMap(pts, false); // 有 GPX：只起/终，不显示途经点
      else if (anchors.length >= 2) initMap(anchors, true); // 退化锚点：显示途经点
      else canvas.style.display = "none";
    }).catch(function (e) {
      // GPX 失败则退化到锚点连线（显示途经点）
      if (anchors.length >= 2) initMap(anchors, true);
      else { canvas.style.display = "none"; console.warn("[ride-map] GPX 失败且无锚点:", e); }
    });
  } else {
    if (anchors.length >= 2) initMap(anchors, true); // 无 GPX：正文锚点含途经点
    else canvas.style.display = "none";
  }

  // 双模式：监听 body 的 theme-dark/theme-light 切换，主题变化时重绘海拔图。
  // 原因：amCharts 不自动感知站点主题，且 common.js 的 toggleTheme 不派发事件。
  if (typeof MutationObserver !== "undefined") {
    var rideLastDark = rideIsDark();
    new MutationObserver(function () {
      var now = rideIsDark();
      if (now !== rideLastDark) {
        rideLastDark = now;
        if (lastElevProfile) drawElevation(lastElevProfile, lastElevHooks);
      }
    }).observe(document.body, { attributes: true, attributeFilter: ["class"] });
  }
})();
