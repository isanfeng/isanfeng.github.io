
var dictaColor = ''; //文字颜色

function dowritedicta(num){
	var randid = Math.round(Math.random()*num);
	randid = randid >= num ? num-1 : randid;
	
	document.write('<font color="' + dictaColor + '">' + dictumin[randid] + '</font>');
}

var dictumin = [
	'为什么灯下的萤火虫不亮了呀？因为他们的光太弱了，只有在黑暗的地方，才看到见。',
	'我们可以忍受卑微地活着，但他们不能把我们当虫子一样随意踩死。',
	'有时候，死亡也是一种胜利。',
	'有些事情肯能永远都不会被改变，但这并不意味着我们必须随波逐流，要相信，生活都是充满希望的，哪怕是最微弱的一束光，也象征着清晨很快就要到来。',
	'这世界，你在意的人和在意你的人，其实就这么几个，这就是你的全部世界。',
	'当你开心的时候，回忆以前特难过的事情，也会很释然的开心；当你难过的时候，回忆以前开心的事情，不仅没那么开心，当下也会觉得更难过。',
	'自卑，是因为自尊。',
	'John is a constant reminder to Palm that it only takes one person to change someone"s life. He changed hers. - Infinite Storm ',
	'我们曾经还会花钱买铃声，但是现在如果我的手机发出一点声音就会毁了我一整天的快乐。',
	'我不会结婚生子，世俗，生活，带给我太多不美好，不想再让另一个生命来走这一遭。',
	'牡丹饼吃不下三个 - [没有养老的资金]',
	'公权：法无授权不可为；私权：法无禁止即自由',
	'好好活着',
	'去你妈的，我就是傻逼怎么了，我就是要活出个傻逼的样子，给你瞧瞧',
	'我想那就是我人生的高光时刻就是，在学潜水时，因为本身不会游泳，有一刻在水下感觉快窒息的时候，突然看到的那一道光吧'
];

dowritedicta(dictumin.length);
