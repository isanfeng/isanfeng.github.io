---
layout: post
title: Flask & Django
date: 2020-11-30 20:04
author: 三丰
description:
img: posts/flask-0-0.webp
tags: [自强不息, Python]
Study: true
---
## 前言

很早之前工作中接触了一个cms的web框架，不过也不算很了解，毕竟工作中都是以应用为主，后来接触python之后，对django有了大概了解，不过也是没有深入研究，直到这次迁移站点，切换为本静态站点，通过渲染模板知识点开始逐步了解python的web框架。
在Flask和Django中的选择中纠结了好久，最后先选择了比较灵活的Flask开始，事实证明这个思路也是正确的，Flask构建站点几乎是一砖一瓦的，基本都是自己从零开始造轮子，和Django一站式开始有着天壤的差别。

## 两者的区别

### Flask

- Flask确实很“轻”，不愧是Micro Framework，从Django转向Flask的开发者一定会如此感慨，除非二者均为深入使用过
- Flask自由、灵活，可扩展性强，第三方库的选择面广，开发时可以结合自己最喜欢用的轮子，也能结合最流行最强大的Python库
- 入门简单，即便没有多少web开发经验，也能很快做出网站
- 非常适用于小型网站
- 非常适用于开发web服务的API
- 开发大型网站无压力，但代码架构需要自己设计，开发成本取决于开发者的能力和经验
- 各方面性能均等于或优于Django
- Django自带的或第三方的好评如潮的功能，Flask上总会找到与之类似第三方库
- Flask灵活开发，Python高手基本都会喜欢Flask，但对Django却可能褒贬不一
- Flask与关系型数据库的配合使用不弱于Django，而其与NoSQL数据库的配合远远优于Django
- Flask比Django更加Pythonic，与Python的philosophy更加吻合

### Django

- Django太重了，除了web框架，自带ORM和模板引擎，灵活和自由度不够高
- Django能开发小应用，但总会有“杀鸡焉用牛刀”的感觉
- Django的自带ORM非常优秀，综合评价略高于SQLAlchemy
- Django自带的模板引擎简单好用，但其强大程度和综合评价略低于Jinja
- Django自带ORM也使Django与关系型数据库耦合度过高，如果想使用MongoDB等NoSQL数据，需要选取合适的第三方库，且总感觉Django+SQL才是天生一对的搭配，Django+NoSQL砍掉了Django的半壁江山
- Django目前支持Jinja等非官方模板引擎
- Django自带的数据库管理app好评如潮
- Django非常适合企业级网站的开发：快速、靠谱、稳定
- Django成熟、稳定、完善，但相比于Flask，Django的整体生态相对封闭
- Django是Python web框架的先驱，用户多，第三方库最丰富，最好的Python库，如果不能直接用到Django中，也一定能找到与之对应的移植
- Django上手也比较容易，开发文档详细、完善，相关资料丰富

## 学习路线资料

### Flask

- 小试牛刀：完整实践一个简单Flask Web程序：[在线阅读](https://read.helloflask.com)， [书中示例程序源码](https://github.com/greyli/watchlist)

- 庖丁解牛：从基础循序渐进详尽探索Flask框架：[Flask Web 开发实战 - 入门、进阶与原理解析，PDF下载](https://share.weiyun.com/5h4ce8wG) 密码：cthbp3,
[书中示例源码](https://github.com/greyli/helloflask),
[个人博客源码](https://github.com/greyli/bluelog)

> 如果能把上面的源码都照着手动打一遍，基本上就可以和Flask进行愉快地玩耍了。

### Django

- [官方文档](https://docs.djangoproject.com/zh-hans/3.1)
