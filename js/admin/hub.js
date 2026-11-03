/* 写作后台中转页：读取 URL 的 ?admin=TOKEN，给两个入口按钮注入带 token 的链接。
   同时在本地（localhost/127.0.0.1）探测后端 /api/moments 是否可达：
   - 不可达（404/网络失败）：提示先启动 scripts/serve.py
   - 可达但 token 无效（403）：提示重新打开 8000 后台以取得有效 token
   线上静态站（非本地 host）不做探测，保持静默。 */
(function () {
  var token = new URLSearchParams(location.search).get("admin");
  var hint = document.getElementById("hub-hint");

  function showHint(text, color) {
    if (!hint) return;
    hint.style.display = "block";
    hint.style.color = color;
    hint.innerHTML = text;
  }

  if (token) {
    function setHref(id, path) {
      var el = document.getElementById(id);
      if (el) el.href = path + "?admin=" + encodeURIComponent(token);
    }
    setHref("hub-moments", "/moments");
    setHref("hub-map", "/travel-map");
    var hintToken = document.getElementById("hub-token");
    if (hintToken) hintToken.textContent = "当前 token：" + token;
  }

  if (!/^(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])$/i.test(location.hostname)) return;

  var CMD = "bundle exec jekyll build &amp;&amp; python3 scripts/serve.py";

  fetch("/api/moments?token=" + encodeURIComponent(token || ""))
    .then(function (r) {
      if (r.status === 403) {
        showHint(
          "后台服务已启动，但当前链接的 token 无效。请重新打开 " +
          "<b>http://127.0.0.1:8000/admin</b>（服务会自动带上有效 token）。",
          "#b8860b"
        );
      } else if (!r.ok) {
        showHint(
          "未检测到本地后台服务。请先在仓库根目录运行：<br><code>" + CMD + "</code><br>" +
          "然后访问 <b>http://127.0.0.1:8000/admin</b>。",
          "#c0392b"
        );
      }
    })
    .catch(function () {
      showHint(
        "未检测到本地后台服务。请先在仓库根目录运行：<br><code>" + CMD + "</code><br>" +
        "然后访问 <b>http://127.0.0.1:8000/admin</b>。",
        "#c0392b"
      );
    });
})();
