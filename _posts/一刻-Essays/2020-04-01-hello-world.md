---
layout: post
title: 网站的前生今世
date:  2020-04-01 21:16:00 +0900
description: Hello World！
img: posts/fo-0.jpg
tags: [一刻]
author: # Add name author (optional)
Essays: true
---
{{site.label1}} <a href="/about">{{page.author}}</a> {{site.label2}}

## 前生
先是使用二级域名成品网站，后又折腾过wordpress和ghost之后，最后选择了专一的静态站点。

## 今世
我想人最终还是要找一个宣泄情感的出口吧，记录下一点点的感受，让时间来见证一些东西，看惯了哪些国家特色的媒体工具，最后只能选择自己自立更生。
后续本站主要作为旅行日志及心情发泄主要工具。

> 部分内容是从之前的wordpress和ghost中迁移过来，有些数据丢失的问题，后面需慢慢修复。

**本网站特色及可操作功能：**
* 网站托管于github（https://isanfeng.github.io）同时为了提高国内访问体验，基于gitee做了镜像(http://iwangsanfeng.gitee.io)可大大提高访问速度。
* 此二级域名永久有效，同时可以使用便于记忆的一级域名（.ml/.tk/.ga/.cf/.gq）进行访问，如（http://isanfeng.ml 其中ml的含义为“美丽”）
* 基于jekyll配置及编译生成，文章可使用markdown和html生成
* 兼容移动端浏览；
* 支持分类，TAGS的功能
* 支持搜索的功能
* 支持评论留言的功能
* 支持分享（国内限定为Weibo及国外的fb，twitter）的功能
* 基于网易云音乐，支持播放自己的定制歌单播放的功能
* 支持冯唐语录的功能
* 支持上线总运行时间计算的功能
* 支持访问统计功能
* 支持font-awesome和font-google定制图标和字体

**针对前端做了部分的性能优化**
* 使用google的[PageSpeed](https://developers.google.cn/speed/pagespeed/insights) 进行分析，参考建议优化。
* 使用CDN， 对于公有的静态资源，比如jquery.min.js、highlight.min.js等文件全部使用CDN，提高网站的访问速度。
* 合并静态文件
* 压缩静态文件
* 使用浏览器缓存

