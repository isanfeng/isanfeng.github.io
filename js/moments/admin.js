/* b_moments 本地写作后台 UI（仅由 ?admin=TOKEN 注入；线上 Pages 无后端不加载） */
(function () {
  var params = new URLSearchParams(location.search);
  var token = params.get("admin");
  if (!token) return;
  var API = "/api/moments?token=" + encodeURIComponent(token);

  /* ---------- 顶部添加栏 ---------- */
  var bar = document.createElement("div");
  bar.style.cssText =
    "position:fixed;top:0;left:0;right:0;z-index:9999;background:#fffdf3;" +
    "border-bottom:2px solid #00853a;padding:10px 14px;font-family:'Long Cang',cursive;" +
    "box-shadow:0 2px 10px rgba(0,0,0,.15)";
  bar.innerHTML =
    '<b style="font-size:16px">MOMENTS 写作后台</b>' +
    ' <span style="font-size:12px;font-weight:normal;color:#00853a">（卡片可拖动排序）</span>' +
    ' <a href="/admin" style="margin-left:10px;font-size:12px">新开后台</a>' +
    '<div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap;align-items:flex-start">' +
      '<textarea id="m-text" rows="2" placeholder="正文（可多行）" style="flex:1;min-width:240px;font-family:inherit"></textarea>' +
      '<input id="m-title" placeholder="标题" style="width:120px">' +
      '<input id="m-date" placeholder="日期" style="width:110px">' +
      '<input id="m-image" placeholder="图片URL" style="width:140px">' +
      '<input id="m-video" placeholder="视频URL" style="width:140px">' +
      '<input id="m-link" placeholder="跳转URL" style="width:140px">' +
      '<label style="font-size:12px"><input type="checkbox" id="m-tail">末尾</label>' +
      '<button id="m-add" style="background:#00853a;color:#fff;border:0;padding:6px 14px;cursor:pointer">添加</button>' +
      '<span id="m-status" style="font-size:12px;color:#00853a"></span>' +
    "</div>";
  document.body.appendChild(bar);

  /* ---------- 拖拽排序 ---------- */
  var dndStyle = document.createElement("style");
  dndStyle.textContent =
    ".box-article.dragging{opacity:.4}" +
    ".box-article.drop-before{box-shadow:inset 0 3px 0 #00853a}" +
    ".box-article.drop-after{box-shadow:inset 0 -3px 0 #00853a}" +
    ".mm-grip{cursor:grab;font-size:15px;line-height:1;user-select:none;margin-right:5px}";
  document.head.appendChild(dndStyle);

  var dragSrc = null;

  function commitOrder() {
    var order = [];
    Array.prototype.forEach.call(
      document.querySelectorAll("article.box-article"),
      function (art) {
        order.push(parseInt(art.dataset.pageN, 10));
      }
    );
    setStatus("已重排，正在重建站点（约十几秒）…");
    fetch("/api/moments/reorder?" + new URLSearchParams({ token: token }), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ order: order })
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (j) {
        if (j.error) {
          alert(j.error);
          setStatus("");
        } else {
          reloadSoon();
        }
      })
      .catch(function (e) {
        alert("请求失败：" + e);
        setStatus("");
      });
  }

  function makeDraggable(art) {
    art.draggable = true;
    art.dataset.pageN = art._pageN;
    art.addEventListener("dragstart", function (e) {
      if (e.target.closest && e.target.closest("button")) {
        e.preventDefault();
        return;
      }
      dragSrc = art;
      e.dataTransfer.effectAllowed = "move";
      try {
        e.dataTransfer.setData("text/plain", String(art.dataset.pageN));
      } catch (_) {}
      try {
        e.dataTransfer.setDragImage(art, 20, 20);
      } catch (_) {}
      setTimeout(function () {
        art.classList.add("dragging");
      }, 0);
    });
    art.addEventListener("dragover", function (e) {
      if (!dragSrc || dragSrc === art) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      var r = art.getBoundingClientRect();
      var after = (e.clientY - r.top) / r.height > 0.5;
      art.classList.toggle("drop-after", after);
      art.classList.toggle("drop-before", !after);
    });
    art.addEventListener("dragleave", function () {
      art.classList.remove("drop-before", "drop-after");
    });
    art.addEventListener("drop", function (e) {
      e.preventDefault();
      art.classList.remove("drop-before", "drop-after");
      if (!dragSrc || dragSrc === art) return;
      var r = art.getBoundingClientRect();
      var after = (e.clientY - r.top) / r.height > 0.5;
      if (after) art.parentNode.insertBefore(dragSrc, art.nextSibling);
      else art.parentNode.insertBefore(dragSrc, art);
      commitOrder();
    });
    art.addEventListener("dragend", function () {
      art.classList.remove("dragging");
      Array.prototype.forEach.call(
        document.querySelectorAll("article.box-article"),
        function (c) {
          c.classList.remove("drop-before", "drop-after");
        }
      );
      dragSrc = null;
    });
  }

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
    var payload = {
      text: document.getElementById("m-text").value,
      title: document.getElementById("m-title").value,
      date: document.getElementById("m-date").value,
      image: document.getElementById("m-image").value,
      video: document.getElementById("m-video").value,
      link: document.getElementById("m-link").value,
      prepend: !document.getElementById("m-tail").checked
    };
    if (!payload.text.trim()) {
      alert("正文不能为空");
      return;
    }
    setStatus("保存中…");
    fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (j) {
        if (j.error) {
          alert(j.error);
          setStatus("");
        } else {
          reloadSoon();
        }
      })
      .catch(function (e) {
        alert("请求失败：" + e);
        setStatus("");
      });
  });

  /* ---------- 编辑弹窗 ---------- */
  var modal = document.createElement("div");
  modal.style.cssText =
    "position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,.4);display:none;align-items:flex-start;justify-content:center";
  modal.innerHTML =
    '<div style="background:#fffdf3;margin-top:60px;padding:18px;width:min(680px,92vw);border-radius:8px;' +
      'font-family:\'Long Cang\',cursive;box-shadow:0 8px 30px rgba(0,0,0,.3)">' +
      '<div style="font-size:16px;margin-bottom:8px">编辑 #<span id="ed-idx"></span></div>' +
      '<textarea id="ed-text" rows="5" style="width:100%;font-family:inherit;box-sizing:border-box"></textarea>' +
      '<div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">' +
        '<input id="ed-title" placeholder="标题（留空=不变，- =清空）" style="width:32%">' +
        '<input id="ed-date" placeholder="日期（留空=不变，- =清空）" style="width:24%">' +
        '<input id="ed-image" placeholder="图片URL（留空=不变）" style="width:42%">' +
      "</div>" +
      '<div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap">' +
        '<input id="ed-video" placeholder="视频URL（留空=不变）" style="width:49%">' +
        '<input id="ed-link" placeholder="跳转URL（留空=不变）" style="width:49%">' +
      "</div>" +
      '<div style="margin-top:12px;text-align:right">' +
        '<button id="ed-cancel" style="margin-right:8px;padding:6px 14px;cursor:pointer">取消</button>' +
        '<button id="ed-save" style="background:#00853a;color:#fff;border:0;padding:6px 14px;cursor:pointer">保存</button>' +
      "</div>" +
    "</div>";
  document.body.appendChild(modal);

  function openModal(idx, item) {
    document.getElementById("ed-idx").textContent = idx;
    document.getElementById("ed-text").value = item.text || "";
    document.getElementById("ed-title").value = item.title || "";
    document.getElementById("ed-date").value = item.date || "";
    document.getElementById("ed-image").value = item.image || "";
    document.getElementById("ed-video").value = item.video || "";
    document.getElementById("ed-link").value = item.link || "";
    modal.style.display = "flex";
    modal._idx = idx;
  }
  function closeModal() {
    modal.style.display = "none";
  }
  document.getElementById("ed-cancel").addEventListener("click", closeModal);
  document.getElementById("ed-save").addEventListener("click", function () {
    var idx = modal._idx;
    var payload = { text: document.getElementById("ed-text").value };
    var t = document.getElementById("ed-title").value;
    var dt = document.getElementById("ed-date").value;
    var im = document.getElementById("ed-image").value;
    var vi = document.getElementById("ed-video").value;
    var lk = document.getElementById("ed-link").value;
    if (t !== "") payload.title = t === "-" ? "" : t;
    if (dt !== "") payload.date = dt === "-" ? "" : dt;
    if (im !== "") payload.image = im === "-" ? "" : im;
    if (vi !== "") payload.video = vi === "-" ? "" : vi;
    if (lk !== "") payload.link = lk === "-" ? "" : lk;
    if (!payload.text.trim()) {
      alert("正文不能为空");
      return;
    }
    closeModal();
    setStatus("保存 #" + idx + " 中…");
    fetch("/api/moments/" + idx + "?" + new URLSearchParams({ token: token }), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (j) {
        if (j.error) {
          alert(j.error);
          setStatus("");
        } else {
          reloadSoon();
        }
      })
      .catch(function (e) {
        alert("请求失败：" + e);
        setStatus("");
      });
  });

  /* ---------- 每张卡片挂 编辑/删除 ---------- */
  function bindCard(article, idx) {
    var box = document.createElement("div");
    box.style.cssText =
      "position:absolute;top:6px;right:6px;display:flex;gap:4px;z-index:5";
    var grip = document.createElement("span");
    grip.className = "mm-grip";
    grip.textContent = "⠿";
    grip.title = "拖动排序";
    box.appendChild(grip);
    var e = document.createElement("button");
    e.textContent = "编辑";
    e.style.cssText = "font-size:11px;padding:1px 6px;cursor:pointer";
    var d = document.createElement("button");
    d.textContent = "删除";
    d.style.cssText = "font-size:11px;padding:1px 6px;cursor:pointer;color:#c0392b";
    box.appendChild(e);
    box.appendChild(d);
    article.style.position = article.style.position || "relative";
    article.appendChild(box);

    d.addEventListener("click", function () {
      if (!confirm("确认删除 #" + idx + " ？")) return;
      setStatus("删除 #" + idx + " 中…");
      fetch("/api/moments/" + idx + "?" + new URLSearchParams({ token: token }), {
        method: "DELETE"
      })
        .then(function (r) {
          return r.json();
        })
        .then(function (j) {
          if (j.error) {
            alert(j.error);
            setStatus("");
          } else {
            reloadSoon();
          }
        })
        .catch(function (e) {
          alert("请求失败：" + e);
          setStatus("");
        });
    });

    e.addEventListener("click", function () {
      setStatus("读取 #" + idx + " 中…");
      fetch(API)
        .then(function (r) {
          return r.json();
        })
        .then(function (list) {
          var item = list.find(function (x) {
            return x.index === idx;
          });
          if (!item) {
            alert("未找到该条目");
            setStatus("");
            return;
          }
          openModal(idx, item);
        })
        .catch(function (e) {
          alert("请求失败：" + e);
          setStatus("");
        });
    });
  }

  var cards = document.querySelectorAll("article.box-article");
  Array.prototype.forEach.call(cards, function (art) {
    var span = art.querySelector(".moment-index");
    if (!span) return;
    var m = /#(\d+)/.exec(span.textContent);
    if (!m) return;
    var idx = parseInt(m[1], 10);
    art._pageN = idx;
    bindCard(art, idx);
    makeDraggable(art);
  });
})();
