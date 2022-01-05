---
layout: page
title: Elements
permalink: /elements/
image: '/images/81.jpg'
---

A paragraph looks like this — Haec et tu ita posuisti, et verba vestra sunt. Idemne potest esse dies saepius, qui semel fuit? Ampulla enim sit necne sit, quis non iure optimo caelo irrideatur, silaboret? Ego vero volo in virtute vim esse quam maximam serpere anguiculos, nare anaticulas, evolare merulas, cornibus uti videmus boves, nepas aculeis. Conferam tecum, quam cuique verso rem subicias si longus, levis. In qua quid brooklyn boni praeter summam voluptatem, et eam cur post. Tarentum ad Archytam? Qua ex cognitione facilior facta est investigatio rerum occultissimarum. Natura sic ab iis investigata est, ut nulla pars caelo deinde optimum nullo modo ad sapientiam possent, verses te huc atque necesse.

***

## Headings by default:

# H1 Default styles for headings
## H2 Default styles for headings
### H3 Default styles for headings
#### H4 Default styles for headings
##### H5 Default styles for headings
###### H6 Default styles for headings

***

## Lists

#### Ordered list example:

1. Poutine drinking vinegar bitters.
2. Coloring book distillery fanny pack.
3. Venmo biodiesel gentrify enamel pin meditation.
4. Jean shorts shaman listicle pickled portland.
5. Salvia mumblecore brunch iPhone migas.

***

#### Unordered list example:

* Bitters semiotics vice thundercats synth.
* Literally cred narwhal bitters wayfarers.
* Kale chips chartreuse paleo tbh street art marfa.
* Mlkshk polaroid sriracha brooklyn.
* Pug you probably haven't heard of them air plant man bun.

***

### Table

<div class="table-container">
  <table>
    <tr><th>Header 1</th><th>Header 2</th><th>Header 3</th><th>Header 4</th><th>Header 5</th></tr>
    <tr><td>Row:1 Cell:1</td><td>Row:1 Cell:2</td><td>Row:1 Cell:3</td><td>Row:1 Cell:4</td><td>Row:1 Cell:5</td></tr>
    <tr><td>Row:2 Cell:1</td><td>Row:2 Cell:2</td><td>Row:2 Cell:3</td><td>Row:2 Cell:4</td><td>Row:2 Cell:5</td></tr>
    <tr><td>Row:3 Cell:1</td><td>Row:3 Cell:2</td><td>Row:3 Cell:3</td><td>Row:3 Cell:4</td><td>Row:3 Cell:5</td></tr>
    <tr><td>Row:4 Cell:1</td><td>Row:4 Cell:2</td><td>Row:4 Cell:3</td><td>Row:4 Cell:4</td><td>Row:4 Cell:5</td></tr>
    <tr><td>Row:5 Cell:1</td><td>Row:5 Cell:2</td><td>Row:5 Cell:3</td><td>Row:5 Cell:4</td><td>Row:5 Cell:5</td></tr>
    <tr><td>Row:6 Cell:1</td><td>Row:6 Cell:2</td><td>Row:6 Cell:3</td><td>Row:6 Cell:4</td><td>Row:6 Cell:5</td></tr>
  </table>
</div>

***

## Quotes

#### A quote looks like this:

> The longer I live, the more I realize that I am never wrong about anything, and that all the pains I have so humbly taken to verify my notions have only wasted my time!
>
> <cite>George Bernard Shaw</cite>

***



## Syntax Highlighter

{% highlight css %}
  body {
    margin: 0;
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100vh;
    width: 100vw;
    background-color: #1c2021;
  }

  li {
    width: 200px;
    min-height: 250px;
    border: 1px solid #000;
    display: inline-block;
    vertical-align: top;
    margin: 5px;
  }
{% endhighlight %}

{% highlight js %}
  $('.top').click(function () {
    $('html, body').stop().animate({ scrollTop: 0 }, 'slow', 'swing');
  });
  $(window).scroll(function () {
    if ($(this).scrollTop() > $(window).height()) {
      $('.top').addClass("top-active");
    } else {
      $('.top').removeClass("top-active");
    };
  });
{% endhighlight %}

***

## Images

<div class="gallery-box">
  <div class="gallery">
    <img src="/images/23.jpg">
    <img src="/images/25.jpg">
    <img src="/images/24.jpg">
    <img src="/images/30.jpg">
    <img src="/images/35.jpg">
    <img src="/images/32.jpg">
  </div>
  <em>Beautiful places / <a href="https://www.pexels.com/" target="_blank">Gallery</a></em>
</div>

![Dreams come true]({{site.baseurl}}/images/40.jpg)
*Dreams come true / [Pexels](https://www.pexels.com/)*

***

## Youtube Embed

<p><iframe src="https://www.youtube.com/embed/_Q673Utczgs" frameborder="0" allowfullscreen></iframe></p>

## Vimeo Embed

<p><iframe src="https://player.vimeo.com/video/107654760" width="640" height="360" frameborder="0" allowfullscreen></iframe></p>

***