$(document).ready(function() {
  'use strict';

  var menuOpenIcon = $(".nav__icon-menu"),
    menuCloseIcon = $(".nav__icon-close"),
    menuList = $(".menu-overlay"),
    searchOpenIcon = $(".search-button"),
    searchCloseIcon = $(".search__close"),
    searchBox = $(".search"),
    searchInput = $(".search__text");


  /* =======================
  // Menu and Search
  ======================= */
  menuOpenIcon.click(function () {
    menuOpen();
  })

  menuCloseIcon.click(function () {
    menuClose();
  })

  searchOpenIcon.click(function () {
    searchOpen();
  });

  searchCloseIcon.click(function () {
    searchClose();
  });

  function menuOpen() {
    menuList.addClass("is-open");
  }

  function menuClose() {
    menuList.removeClass("is-open");
  }

  function searchOpen() {
    searchBox.addClass("is-visible");
    setTimeout(function () {
      searchInput.focus();
    }, 150);
  }

  function searchClose() {
    searchBox.removeClass("is-visible");
  }

  $('.search, .search__box').on('click keyup', function(event) {
    if (event.target == this || event.keyCode == 27) {
      $('.search').removeClass('is-visible');
    }
  });


  /* =======================
  // Nav overflow -> "More" dropdown
  // 窗口变窄、菜单放不下时，把溢出（最右侧）的菜单项收进下拉框；
  // logo 与 search 始终完整显示，不参与收起。
  ======================= */
  (function () {
    var $topNav = $('.top-nav');
    if (!$topNav.length) return;

    var $list = $topNav.find('.nav__list');
    var $more = $list.children('.nav__more');
    if (!$more.length) return;
    var $moreList = $more.children('.nav__more-list');
    var $toggle = $more.children('.nav__more-toggle');

    // 把下拉里的项还原回主列表（按原顺序，置于 More 之前）
    function restore() {
      $moreList.children('.nav__item').each(function () {
        $more.before(this);
      });
    }

    function relayout() {
      if (window.innerWidth <= 576) return; // 手机端走汉堡菜单，不处理
      restore();
      // 先让 More 可见，量出它自身占用的宽度（含 margin）
      $more.prop('hidden', false);
      var moreWidth = $more.outerWidth(true) || 0;
      // 隐藏 More 再量“真实菜单项”宽度，避免 More 自身宽度污染测量
      $more.prop('hidden', true);

      var list = $list[0];
      var avail = list.clientWidth;
      // 布局尚未就绪（clientWidth=0，常见于 document.ready 早于 CSS 计算）时直接返回，
      // 留给 load / resize / rAF 再算，避免把全部菜单误收进 More。
      if (!avail) return;

      // 逐个量出每个菜单项的真实宽度（含 margin），用 sum 判断是否放得下，
      // 不再依赖 flex 容器 scrollWidth（nowrap 下 scrollWidth 可能不随项移出而正确下降）。
      var $items = $list.children('.nav__item:not(.nav__more)');
      var widths = [];
      var total = 0;
      $items.each(function () {
        var w = $(this).outerWidth(true);
        widths.push(w);
        total += w;
      });

      // 全部能直接铺满整行（不含 More）→ 保持隐藏，done
      if (total <= avail + 1) {
        return;
      }

      // 放不下：从【左】往右累加，能放进“可用宽 - More 占位”的保留在主列表，
      // 放不下的（最右侧溢出项）才收进 More —— 因此只有真正溢出的项进下拉，不会全收。
      var keep = 0;
      var moveCount = 0;
      for (var j = 0; j < widths.length; j++) {
        if (keep + widths[j] <= avail - moreWidth + 1) {
          keep += widths[j];
        } else {
          moveCount++;
        }
      }
      // 把最右侧 moveCount 个项收进下拉（prepend 保持原顺序）
      for (var m = 0; m < moveCount; m++) {
        $moreList.prepend($list.children('.nav__item:not(.nav__more)').last());
      }
      // 依据是否真有溢出项决定 More 显隐
      $more.prop('hidden', $moreList.children().length === 0);
    }

    function openMore() {
      $more.addClass('is-open');
      $toggle.attr('aria-expanded', 'true');
    }
    function closeMore() {
      $more.removeClass('is-open');
      $toggle.attr('aria-expanded', 'false');
    }

    // 桌面（支持 hover）：鼠标移入 More 即展开下拉，移开即收齐
    var canHover = window.matchMedia && window.matchMedia('(hover: hover)').matches;
    if (canHover) {
      // 绑定在 $more 整体（含 toggle 与下拉列表），鼠标在二者间移动不会误触发收齐
      $more.on('mouseenter', openMore);
      $more.on('mouseleave', closeMore);
    } else {
      // 触屏（无 hover）：点击切换展开/收齐，点击外部收齐
      $toggle.on('click', function (e) {
        e.stopPropagation();
        if ($more.hasClass('is-open')) { closeMore(); } else { openMore(); }
      });
      $(document).on('click', function (e) {
        if (!$(e.target).closest('.nav__more').length) { closeMore(); }
      });
    }

    // 键盘 Escape 收齐（两类设备通用）
    $(document).on('keydown', function (e) {
      if (e.keyCode === 27) { closeMore(); }
    });

    relayout();
    // 布局就绪后再算一次（document.ready 时 clientWidth 可能为 0，已加 !avail 保护，这里双保险）
    if (window.requestAnimationFrame) requestAnimationFrame(relayout);
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(relayout);
    }
    $(window).on('load', relayout);
    var rt;
    $(window).on('resize', function () {
      clearTimeout(rt);
      rt = setTimeout(relayout, 120);
    });
  })();


  /* =======================
  // Animation Load Page
  ======================= */
  setTimeout(function(){
    $('body').addClass('is-in');
  },150)

  // 入场 / 滚动揭示动画（P1-8）
  initReveal();


  /* =======================
  // Hero parallax effect
  ======================= */
  hero();

  function hero() {
    $(window).on('scroll', function () {
      var scroll = $(this).scrollTop();

      $('.hero__image img').css({
        transform: 'translate3d(0, ' + scroll / 3 + 'px, 0)'
      });
    });
  }


  // =====================
  // Simple Jekyll Search
  // =====================
  SimpleJekyllSearch({
    searchInput: document.getElementById('js-search-input'),
    resultsContainer: document.getElementById('js-results-container'),
    json: "/search.json",
    searchResultTemplate: "<div class='search-results__item'><a class='search-results__image' href='{url}' style='background-image: url({image})'></a> <a class='search-results__link' href='{url}'><span class='search-results-date'> <time datetime='{date}'>{date}</time></span><div class='search-result-title'>{title}</div></a></div>",
    noResultsText: "<li class='no-results'><h3>No results found</h3></li>"
  });


  /* =======================
  // WebP Picture Upgrade
  // 把所有 .lazy 图片（含 kramdown 渲染的正文图）包成 <picture>，
  // 优先加载同名 .webp 副本；不支持 webp 的浏览器自动回退原 jpg。
  // 必须在 new LazyLoad() 之前执行，vanilla-lazyload 才会接管 <picture>。
  ======================= */
  upgradeToWebP();

  function upgradeToWebP() {
    var imgs = document.querySelectorAll('img.lazy');
    for (var i = 0; i < imgs.length; i++) {
      var img = imgs[i];
      if (img.parentNode && img.parentNode.tagName === 'PICTURE') continue;
      var src = img.getAttribute('data-src') || img.getAttribute('src') || '';
      if (!/\.(jpe?g|JPE?G)$/.test(src)) continue;
      var webp = src.replace(/\.(jpe?g|JPE?G)$/, '.webp');
      var pic = document.createElement('picture');
      var source = document.createElement('source');
      source.setAttribute('type', 'image/webp');
      source.setAttribute('data-srcset', webp);
      img.parentNode.insertBefore(pic, img);
      pic.appendChild(source);
      pic.appendChild(img);
    }
  }

  /* =======================
  // LazyLoad Images
  ======================= */
  var lazyLoadInstance = new LazyLoad({
    elements_selector: '.lazy'
  })


  /* =======================
  // Responsive Videos
  ======================= */
  $(".post__content, .page__content").fitVids({
    customSelector: ['iframe[src*="ted.com"]', 'iframe[src*="player.twitch.tv"]', 'iframe[src*="facebook.com"]']
  });


  /* =======================
  // Exclusive Media (互斥播放)
  // 文章/页面内的多个视频(Bilibili iframe 或 HTML5 <video>)互斥:
  //  1) 默认不自动播放 —— Bilibili URL 带 autoplay=0(源层), 加载后再发一次 pause 命令双保险
  //  2) 一个开始播放时, 其余自动停止 —— 跨域 iframe 无法由父页 pause(), 故用"重载其余 iframe"
  //     (重置 src 即停止播放) 实现互斥; 触发信号仅用 iframe focus(用户点击内部即获焦点,
  //     父文档元素级 focus 监听可靠触发, 跨域不影响) —— 不依赖播放器回传的 play 事件(滚动/预览
  //     都会触发回传, 会导致误暂停/死循环重载, 已移除)
  ======================= */
  function setupExclusiveMedia() {
    var biliFrames = document.querySelectorAll('.post__content iframe[src*="player.bilibili.com"], .page__content iframe[src*="player.bilibili.com"]');
    var htmlVideos = document.querySelectorAll('.post__content video, .page__content video');
    if (!biliFrames.length && !htmlVideos.length) return;

    // 记录各 Bilibili iframe 的原始 src。跨域 iframe 无法由父页直接 pause(),
    // "暂停"的可靠手段是重置 src(重载即停止播放), 完全不依赖播放器是否响应 postMessage。
    var biliSrc = [];
    biliFrames.forEach(function (f, i) { biliSrc[i] = f.getAttribute('src'); });

    // 停止除 exceptIdx 之外的所有 Bilibili iframe(重载), 并暂停 HTML5 video
    function stopOthers(exceptIdx) {
      biliFrames.forEach(function (f, i) {
        if (i === exceptIdx) return;
        try { f.setAttribute('src', biliSrc[i]); } catch (e) {}
      });
      htmlVideos.forEach(function (v) { v.pause(); });
    }

    // 暴露给音乐播放器(music-player.html): 暂停"所有" Bilibili 视频(音频↔视频互斥)
    window.__pauseAllBilibili = function () { stopOthers(-1); };
    // 暂停音乐播放器(若不存在则空操作)
    function pauseMusicIfAny() { if (window.__pauseMusic) window.__pauseMusic(); }

    // 1) 默认不自动播放: 加载后发一次 pause 命令(双保险, 播放器若支持则生效)
    biliFrames.forEach(function (f) {
      f.addEventListener('load', function () {
        try { f.contentWindow.postMessage(JSON.stringify({ command: 'pause' }), '*'); } catch (e) {}
      });
    });

    // 2) 互斥核心: 用户点击进入某 iframe -> 重载其余, 其余必然停止播放。
    //    激活信号: iframe 元素自身的 focus 事件 —— 点击跨域 iframe 内部会使其获得焦点,
    //    父文档绑在 iframe 元素上的 focus 监听可靠触发(这是 HTML 规范行为, 跨域不影响此级焦点事件)。
    //    注意: 不依赖 window blur 兜底 —— 跨域 iframe 失焦时父窗口会 blur, 但此时 document.activeElement
    //    时序上可能仍是刚失焦的旧 iframe, 会误判"激活者"从而把用户真正点击的目标重载掉(表现为点不回去)。
    function activateFrame(idx) {
      if (idx < 0) return;
      window.__videoFocusAt = Date.now();
      pauseMusicIfAny();
      stopOthers(idx);
    }
    biliFrames.forEach(function (f, i) {
      f.addEventListener('focus', function () { activateFrame(i); });
    });

    // 3) HTML5 <video> 互斥: 一个播放 -> 暂停其余 video 并停止所有 Bilibili
    htmlVideos.forEach(function (v) {
      v.addEventListener('play', function () {
        htmlVideos.forEach(function (o) { if (o !== v) o.pause(); });
        pauseMusicIfAny();
        stopOthers(-1);
      });
    });
  }

  setupExclusiveMedia();


  /* =======================
  // Zoom Image
  ======================= */
  $(".page img, .post img").attr("data-action", "zoom");
  $(".page a img, .post a img").removeAttr("data-action", "zoom");


  /* =======================
  // Scroll Top Button
  ======================= */
  $(".top").click(function() {
    $("html, body")
      .stop()
      .animate({ scrollTop: 0 }, "slow", "swing");
  });
  $(window).scroll(function() {
    if ($(this).scrollTop() > $(window).height()) {
      $(".top").addClass("is-active");
    } else {
      $(".top").removeClass("is-active");
    }
  });

  /* =======================
  // Theme Toggle (Dark/Light)
  // 点击导航栏左侧 logo 循环切换深色/浅色模式，并记住用户选择。
  ======================= */
  initTheme();

  function initTheme() {
    var saved = localStorage.getItem('theme');
    var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    var isDark = saved === 'dark' || (!saved && prefersDark);
    document.body.classList.toggle('theme-dark', isDark);
    document.body.classList.toggle('theme-light', !isDark);
  }

  function toggleTheme() {
    if (document.body.classList.contains('theme-dark')) {
      document.body.classList.remove('theme-dark');
      document.body.classList.add('theme-light');
      localStorage.setItem('theme', 'light');
    } else {
      document.body.classList.remove('theme-light');
      document.body.classList.add('theme-dark');
      localStorage.setItem('theme', 'dark');
    }
  }

  $('.logo__link').on('click', function (event) {
    event.preventDefault();
    toggleTheme();
  });


  /* =======================
  // Reveal on scroll (P1-8)
  // 给带 .reveal 的元素加 .is-visible，触发错落淡入；
  // 尊重 prefers-reduced-motion，无 IntersectionObserver 时直接显示；
  // 2.5s 兜底强制显示，避免任何异常导致内容永久隐藏。
  ======================= */
  function initReveal() {
    var els = document.querySelectorAll('.reveal');
    if (!els.length) return;

    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce || !('IntersectionObserver' in window)) {
      for (var i = 0; i < els.length; i++) els[i].classList.add('is-visible');
      return;
    }

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });

    for (var j = 0; j < els.length; j++) io.observe(els[j]);

    setTimeout(function () {
      var pending = document.querySelectorAll('.reveal:not(.is-visible)');
      for (var k = 0; k < pending.length; k++) pending[k].classList.add('is-visible');
    }, 2500);
  }

});