---
layout: post
title: 笔记的前生今世
date:  2020-04-01 21:16:00 +0900
description: Hello World！
img: posts/fo-0.webp
tags: [自强不息, 一刻]
author: 三丰
Essays: true
---
{{site.label1}} <a href="/about">{{page.author}}</a> {{site.label2}}

## 前生
先前博客还流行的时候，使用过二级域名成品网站，折腾过wordpress和ghost之后，不过浮躁的都没有好好的去记录，终究失去了学生时代认真记笔记，写读后感的能力，用微信，微博零碎的记录着只言片语，后来慢慢发现没有任何积累。
再加上这个被控制的媒体工具有时根本不是让自己说一些实话，为了不再受寄人篱下之苦，也是再找一个新的自由的宣泄情感的出口，记录下余生的点点滴滴，让时间来见证一些东西。

## 今世
自力更生，自强不息，不需要繁琐的部署维护，不需要严谨的后端，少量的前端工程，全部聚焦在内容的输出（markdown文件内容），所有的资料都能自己掌握，这基本是选择github pages的原因。

> 部分内容是从之前的wordpress和ghost中迁移过来，有部分数据丢失的问题，后面需慢慢修复。

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
* 图片格式全部使用webp格式
* 合并静态文件
* 压缩静态文件
* 使用浏览器缓存

