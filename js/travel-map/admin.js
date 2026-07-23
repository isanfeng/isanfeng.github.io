/* a_travel-map 本地写作后台 UI（仅由 ?admin=TOKEN 注入；线上 Pages 无后端不加载） */
(function () {
  var params = new URLSearchParams(location.search);
  var token = params.get("admin");
  if (!token) return;
  var API = "/api/markers?token=" + encodeURIComponent(token);
  var GREEN = "#00853a";
  var GREEN_BRIGHT = "#00b34a";

  /* ---------- 顶部添加栏 ---------- */
  var bar = document.createElement("div");
  bar.style.cssText =
    "position:fixed;top:0;left:0;right:0;z-index:9999;background:#fff;" +
    "border-bottom:2px solid " + GREEN + ";padding:10px 14px;" +
    "box-shadow:0 2px 10px rgba(0,0,0,.15);font-family:inherit";
  bar.innerHTML =
    '<b style="font-size:15px">TRAVEL-MAP 写作后台</b>' +
    ' <a href="/admin" style="margin-left:10px;font-size:12px">新开后台</a>' +
    '<div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap;align-items:flex-start">' +
      '<input id="m-title" placeholder="地点名称*" style="width:160px">' +
      '<input id="m-country" placeholder="国家(着色)" style="width:110px">' +
      '<input id="m-lat" placeholder="纬度*" style="width:90px">' +
      '<input id="m-lng" placeholder="经度*" style="width:90px">' +
      '<input id="m-url" placeholder="跳转URL" style="width:200px">' +
      '<label style="font-size:12px"><input type="checkbox" id="m-tail">末尾</label>' +
      '<button id="m-add" style="background:' + GREEN + ';color:#fff;border:0;padding:6px 14px;cursor:pointer">添加</button>' +
      '<span id="m-status" style="font-size:12px;color:' + GREEN + '"></span>' +
    "</div>";
  document.body.appendChild(bar);

  function setStatus(t) {
    var s = document.getElementById("m-status");
    if (s) s.textContent = t || "";
  }
  function reloadSoon() {
    setStatus("已保存，正在重建站点（约十几秒）…");
    setTimeout(function () {
      location.reload();
    }, 14000);
  }

  document.getElementById("m-add").addEventListener("click", function () {
    var title = document.getElementById("m-title").value.trim();
    var lat = parseFloat(document.getElementById("m-lat").value);
    var lng = parseFloat(document.getElementById("m-lng").value);
    var country = document.getElementById("m-country").value.trim();
    var url = document.getElementById("m-url").value.trim();
    if (!title) { alert("地点名称不能为空"); return; }
    if (isNaN(lat) || isNaN(lng)) { alert("纬度/经度必须是数字"); return; }
    var payload = {
      title: title,
      latitude: lat,
      longitude: lng,
      country: country || null,
      url: url || null,
      prepend: !document.getElementById("m-tail").checked
    };
    setStatus("保存中…");
    fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (j.error) { alert(j.error); setStatus(""); }
        else { reloadSoon(); }
      })
      .catch(function (e) { alert("请求失败：" + e); setStatus(""); });
  });

  /* ---------- 右侧 marker 列表面板 ---------- */
  var panel = document.createElement("div");
  panel.style.cssText =
    "position:fixed;top:64px;right:0;bottom:0;width:430px;z-index:9998;background:rgba(255,255,255,.97);" +
    "border-left:2px solid " + GREEN + ";overflow:auto;padding:10px 12px;box-shadow:-2px 0 10px rgba(0,0,0,.12);font-family:inherit";
  panel.innerHTML =
    '<div style="font-size:13px;margin-bottom:8px;color:#333">标注点列表（点击编辑 / 删除）</div>' +
    '<div id="mk-list"></div>';
  document.body.appendChild(panel);

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function renderList() {
    setStatus("读取列表中…");
    fetch(API)
      .then(function (r) { return r.json(); })
      .then(function (list) {
        setStatus("");
        var box = document.getElementById("mk-list");
        if (!list.length) { box.innerHTML = '<div style="color:#888;font-size:12px">暂无标注点</div>'; return; }
        var rows = list.map(function (it) {
          var coords = (it.latitude != null) ? (it.latitude.toFixed(4) + ", " + it.longitude.toFixed(4)) : "";
          return '<div style="border:1px solid #eee;border-radius:6px;padding:6px 8px;margin-bottom:6px">' +
            '<div style="display:flex;justify-content:space-between;align-items:center">' +
              '<b style="font-size:13px">#' + it.index + ' ' + esc(it.title) + '</b>' +
              '<span>' +
                '<button data-edit="' + it.index + '" style="font-size:11px;padding:1px 7px;cursor:pointer">编辑</button> ' +
                '<button data-del="' + it.index + '" style="font-size:11px;padding:1px 7px;cursor:pointer;color:#c0392b">删除</button>' +
              '</span>' +
            '</div>' +
            '<div style="font-size:11px;color:#666;margin-top:2px">' +
              (it.country ? ('国家: ' + esc(it.country) + '  ') : '') +
              (coords ? ('坐标: ' + esc(coords)) : '') +
            '</div>' +
            (it.url ? '<div style="font-size:11px;color:#888;margin-top:2px;word-break:break-all">URL: ' + esc(it.url) + '</div>' : '') +
            '</div>';
        }).join("");
        box.innerHTML = rows;

        Array.prototype.forEach.call(box.querySelectorAll("[data-edit]"), function (b) {
          b.addEventListener("click", function () {
            var idx = parseInt(b.getAttribute("data-edit"), 10);
            var item = list.find(function (x) { return x.index === idx; });
            if (item) openModal(idx, item);
          });
        });
        Array.prototype.forEach.call(box.querySelectorAll("[data-del]"), function (b) {
          b.addEventListener("click", function () {
            var idx = parseInt(b.getAttribute("data-del"), 10);
            if (!confirm("确认删除 #" + idx + " ？")) return;
            setStatus("删除 #" + idx + " 中…");
            fetch("/api/markers/" + idx + "?" + new URLSearchParams({ token: token }), { method: "DELETE" })
              .then(function (r) { return r.json(); })
              .then(function (j) {
                if (j.error) { alert(j.error); setStatus(""); }
                else { reloadSoon(); }
              })
              .catch(function (e) { alert("请求失败：" + e); setStatus(""); });
          });
        });
      })
      .catch(function (e) { alert("读取列表失败：" + e); setStatus(""); });
  }

  /* ---------- 编辑弹窗 ---------- */
  var modal = document.createElement("div");
  modal.style.cssText =
    "position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,.4);display:none;align-items:flex-start;justify-content:center";
  modal.innerHTML =
    '<div style="background:#fff;margin-top:70px;padding:18px;width:min(520px,92vw);border-radius:8px;' +
      'font-family:inherit;box-shadow:0 8px 30px rgba(0,0,0,.3)">' +
      '<div style="font-size:16px;margin-bottom:8px">编辑 #<span id="ed-idx"></span></div>' +
      '<div style="display:flex;gap:6px;flex-wrap:wrap">' +
        '<input id="ed-title" placeholder="地点名称（留空=不变，- =清空）" style="width:100%">' +
      '</div>' +
      '<div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap">' +
        '<input id="ed-country" placeholder="国家（留空=不变，- =清空）" style="width:48%">' +
        '<input id="ed-lat" placeholder="纬度（留空=不变）" style="width:24%">' +
        '<input id="ed-lng" placeholder="经度（留空=不变）" style="width:24%">' +
      '</div>' +
      '<div style="margin-top:6px">' +
        '<input id="ed-url" placeholder="跳转URL（留空=不变，- =清空）" style="width:100%">' +
      '</div>' +
      '<div style="margin-top:12px;text-align:right">' +
        '<button id="ed-cancel" style="margin-right:8px;padding:6px 14px;cursor:pointer">取消</button>' +
        '<button id="ed-save" style="background:' + GREEN + ';color:#fff;border:0;padding:6px 14px;cursor:pointer">保存</button>' +
      '</div>' +
    '</div>';
  document.body.appendChild(modal);

  function openModal(idx, item) {
    document.getElementById("ed-idx").textContent = idx;
    document.getElementById("ed-title").value = item.title || "";
    document.getElementById("ed-country").value = item.country || "";
    document.getElementById("ed-lat").value = (item.latitude != null) ? item.latitude : "";
    document.getElementById("ed-lng").value = (item.longitude != null) ? item.longitude : "";
    document.getElementById("ed-url").value = item.url || "";
    modal.style.display = "flex";
    modal._idx = idx;
  }
  function closeModal() { modal.style.display = "none"; }
  document.getElementById("ed-cancel").addEventListener("click", closeModal);
  document.getElementById("ed-save").addEventListener("click", function () {
    var idx = modal._idx;
    var payload = {};
    var title = document.getElementById("ed-title").value;
    var country = document.getElementById("ed-country").value;
    var lat = document.getElementById("ed-lat").value.trim();
    var lng = document.getElementById("ed-lng").value.trim();
    var url = document.getElementById("ed-url").value;
    if (title !== "") payload.title = (title === "-") ? "" : title;
    if (country !== "") payload.country = (country === "-") ? "" : country;
    if (lat !== "") {
      var f = parseFloat(lat);
      if (isNaN(f)) { alert("纬度必须是数字"); return; }
      payload.latitude = f;
    }
    if (lng !== "") {
      var g = parseFloat(lng);
      if (isNaN(g)) { alert("经度必须是数字"); return; }
      payload.longitude = g;
    }
    if (url !== "") payload.url = (url === "-") ? "" : url;
    closeModal();
    setStatus("保存 #" + idx + " 中…");
    fetch("/api/markers/" + idx + "?" + new URLSearchParams({ token: token }), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (j.error) { alert(j.error); setStatus(""); }
        else { reloadSoon(); }
      })
      .catch(function (e) { alert("请求失败：" + e); setStatus(""); });
  });

  renderList();
})();
