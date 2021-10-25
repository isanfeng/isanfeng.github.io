---
layout: post
title: 环琵琶湖.NS
date: 2020-04-01 00:09
author: 三丰
description:
img: posts/PipaLake-0.webp
tags: [Bikepacking, 分时分段环游地球, Japan, 『㊕🚲㊙』]
Bikepacking-Hike-Abroad: true
---

<script>
    function password()
    {
        var i=1;
            var passwd=prompt('此文章已被三丰设置为私密，请寻求三丰授权后再考虑踏足此地吧！','');//这是输入密码的提示语，可以改为你想要显示的内容，比如本站地址之类的
        while(i<3)
        {
            if(passwd=="i love isanfeng")//这是密码
            {
            alert('已被授权，请进！');//这是输入正确后的提示，可以改为自己想要的提示语
            break;
            }
            i++;
            var passwd=prompt('未被授权!请重新输入:\n你还有'+(4-i)+'次机会。');
        }
        if(password!="vip.zan.smarted"&&i==3)
        {
            alert('看来此处不值得踏足，再见喽，亲爱滴，希望你能有更美好的发现。');
            location.href="/";//这是密码输入错误超过3次后转到的错误页面，也可设为别的页面
        }
        return "";
    }
        password();
</script>
