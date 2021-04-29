---
layout: post
title: 带父母去旅游.西安.2019
date: 2019-03-27 20:56
author: 三丰
description:
img: posts/Xian-0.webp
tags: [带父母去旅游, 环游国内]
Bikepacking-domestic: true
---
<script>
    function password()
    {
        var i=1;
            var passwd=prompt('亲爱滴，这个页面需要信任密码哦:','');//这是输入密码的提示语，可以改为你想要显示的内容，比如本站地址之类的
        while(i<3)
        {
            if(passwd=="sanfeng's world")//这是密码
            {
            alert('恭喜你！');//这是输入正确后的提示，可以改为自己想要的提示语
            break;
            }
            i++;
            var passwd=prompt('密码错误!请重新输入:\n你还有'+(4-i)+'次机会。');
        }
        if(password!="vip.zan.smarted"&&i==3)
        {
            alert('亲爱滴，信任是交流的第一步。');
            location.href="https://iwangsanfeng.gitee.io";//这是密码输入错误超过3次后转到的错误页面，也可设为别的页面
        }
        return "";
    }
        password();
</script>
