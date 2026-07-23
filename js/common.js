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

    $toggle.on('click', function (e) {
      e.stopPropagation();
      var open = $more.hasClass('is-open');
      $more.toggleClass('is-open');
      $toggle.attr('aria-expanded', String(!open));
    });

    $(document).on('click', function (e) {
      if (!$(e.target).closest('.nav__more').length) {
        $more.removeClass('is-open');
        $toggle.attr('aria-expanded', 'false');
      }
    });

    $(document).on('keydown', function (e) {
      if (e.keyCode === 27) {
        $more.removeClass('is-open');
        $toggle.attr('aria-expanded', 'false');
      }
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


});