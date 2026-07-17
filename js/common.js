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