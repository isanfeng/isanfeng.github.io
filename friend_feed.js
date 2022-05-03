
var dictaColor = ''; //文字颜色

function dowritedicta(num){
	var randid = Math.round(Math.random()*num);
	randid = randid >= num ? num-1 : randid;
	
	document.write('<font color="' + dictaColor + '">' + dictumin[randid] + '</font>');
}

var dictumin = [
	'爸爸，为什么灯下的萤火虫不亮了呀？因为他们的光太弱了，只有在黑暗的地方，才看到见。<误杀Ⅱ>',
	'我们可以忍受卑微地活着，但他们不能把我们当虫子一样随意踩死。<误杀Ⅱ>',
	'我只有演一出戏，把自己打造成恶人，才有可能赢。<误杀Ⅱ>',
	'有时候，死亡也是一种胜利。<误杀Ⅱ>',
	'有些事情肯能永远都不会被改变，但这并不意味着我们必须随波逐流，要相信，生活都是充满希望的，哪怕是最微弱的一束光，也象征着清晨很快就要到来。<误杀Ⅱ>',
	'这世界，你在意的人和在意你的人，其实就这么几个，这就是你的全部世界。<人世间>',
	'走一步看一步，走一步走好一步，苦吗，嚼嚼咽了。<人世间>',
	'一个什么都没有的人，最要有的就是自己，只要有了自己，天塌了都不怕。<人世间>',
	'当你开心的时候，回忆以前特难过的事情，也会很释然的开心；当你难过的时候，回忆以前开心的事情，不仅没那么开心，当下也会觉得更难过。<人世间>',
	'苦吗？嚼碎了，咽下去！<人世间>',
	'你跟我不一样，实惠比体面重要。<人世间>',
	'自卑，是因为自尊。<人世间>',
	'John is a constant reminder to Palm that it only takes one person to change someone"s life. He changed hers. <Infinite Storm>'
];

dowritedicta(dictumin.length);
