/*
 * post-lock.js — 文章正文轻量门禁（零依赖，前端 JS 校验密码）
 *
 * 与之前的构建期真加密不同：本方案正文仍渲染在页面源码中，仅初始 hidden，
 * 由本脚本在前端校验「友情密钥」后显示。属于「防顺手党 / 随手看源码」级别，
 * 非银行级——这是 GitHub Pages 纯静态托管无法做服务端鉴权的固有上限。
 *
 * 行为：
 *  - 密码来自 post.html 注入的 window.__POST_ENC_PASS__（全局 site.encrypt_password，
 *    或文章 front-matter 的 encrypt_password 覆盖）。
 *  - 输对一次后存入 sessionStorage，本会话内其他同密码加密文自动解锁，无需重输。
 *  - 输错仅行内红字提示、可无限重试，不做「永远封印」式客户端锁死（刷新即破，纯自扰）。
 *  - 解锁后触发 vanilla-lazyload 重载图片。
 */
(function () {
  'use strict';

  var KEY = 'post_unlock_pass_v1';

  function unlockAll() {
    var bodies = document.querySelectorAll('.post__content[data-encrypted="1"]');
    Array.prototype.forEach.call(bodies, function (b) { b.hidden = false; });
    var locks = document.querySelectorAll('.post-encrypt-locked');
    Array.prototype.forEach.call(locks, function (l) { l.style.display = 'none'; });
    // 重新触发懒加载，否则隐藏期间未进入视口的图片可能不加载
    if (window.lazyLoadInstance && typeof window.lazyLoadInstance.update === 'function') {
      window.lazyLoadInstance.update();
    }
  }

  function bind(block) {
    var form = block.querySelector('.post-encrypt-form');
    var input = block.querySelector('.post-encrypt-input');
    var err = block.querySelector('.post-encrypt-err');
    if (!form || !input) return;
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var pass = input.value;
      if (!pass) return;
      var want = window.__POST_ENC_PASS__;
      if (pass === want) {
        try { sessionStorage.setItem(KEY, pass); } catch (_) {}
        unlockAll();
      } else {
        if (err) { err.textContent = '密钥不正确，请重试'; err.hidden = false; }
        input.value = '';
        input.focus();
      }
    });
  }

  function init() {
    var blocks = document.querySelectorAll('.post-encrypt-locked');
    if (!blocks.length) return;
    Array.prototype.forEach.call(blocks, bind);
    var saved;
    try { saved = sessionStorage.getItem(KEY); } catch (_) {}
    if (saved && saved === window.__POST_ENC_PASS__) {
      unlockAll();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
