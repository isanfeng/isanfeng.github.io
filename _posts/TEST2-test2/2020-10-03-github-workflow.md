---
layout: post
title: Hello World！我的个人网站
date:  2018-02-07 21:16:00 +0900
description: Hello World！
img: post-7.jpg # Add image post (optional)
tags: [TEST2, TEST1]
author: # Add name author (optional)
test_b: true
---
{{site.label1}} <a href="https://isanfeng.github.io" target="\_blank">isanfeng</a> {{site.label2}}

#Github Workflow
###第一步：从仓库中fork项目
1. 访问目标仓库：https://
2. 点击页面上的fork，将目标项目复制到自己的仓库中
>**clone和fork的区别**<br>
>比如在仓库的主人（A）没有把我们添加为项目合作者的前提下，我们将A的某个仓库名为“B”的仓库clone到自己的电脑中，在自己的电脑进行修改，但是我们会发现我们没办法通过push将代码贡献到B中。所以要想将你的代码贡献到B中，
>我们应该：
>在A的仓库中fork项目B （此时我们自己的github就有一个一模一样的仓库B，但是URL不同）, 将我们修改的代码push到自己github中的仓库B中pull request ，主人就会收到请求，并决定要不要接受你的代码
###第二步：Clone刚fork的项目到本地

    mkdir -p $working_dir
    cd $working_dir
    git clone https://github.com/$user/github-workflow.git
    # or: git clone git@github.com:$user/github-workflow.git
   
    cd $working_dir/github-workflow
    git remote add upstream https://github.com/yangwenmai/github-workflow.git
    # or: git remote add upstream git@github.com:yangwenmai/github-workflow.git
    # Never push to the upstream master.
    git remote set-url --push upstream no_push
    # Confirm that your remotes make sense:
    # It should look like:
    # origin    git@github.com:$(user)/github-workflow.git (fetch)
    # origin    git@github.com:$(user)/github-workflow.git (push)
    # upstream  https://github.com/yangwenmai/github-workflow (fetch)
    # upstream  no_push (push)
    git remote -v
    
###第三步：开新分支

    cd $working_dir/github-workflow
    git fetch upstream
    git checkout master
    git rebase upstream/master
从master分支开新的特性分支
 
    git checkout -b myfeature
    # or: gcb myfeature
###第四步：开发
####编码
你可以在你新创建的 myfeature 分支下编码。
###第五步：保持你的特性分支 myfeature 是一直同步原始仓库的最新 master 代码

    # While on your myfeature branch.
    git fetch upstream
    git rebase upstream/master
请不要用 git pull 代替 fetch/rebase，git pull 会创建一个 merge，并且会创建 merge commits。这些会使提交记录混乱和违反规则。你也可以考虑改变你的 .git/config 文件，通过 git config branch.autoSetupRebase 来改变 git pull 行为。
###第六步：提交
提交你的变更

    git commit
###第七步：推送

    git push --set-upstream ${your_remote_name} myfeature
###第八步：创建一个push request
1. 访问你 fork 的项目：https://github.com/$user/github-workflow
2. 点击 Compare & Pull Request 按钮，基于你的 myfeature 分支
3. 填充必要的 PR 模板信息。
***
接下来你就只需要等待原始项目的开发人员来审核你的提交即可。
以后如果你还要再开发新的特性或者修复一些 bug，你需要先同步更新项目，然后再创建新的分支，然后都可以按照以上步骤执行。
