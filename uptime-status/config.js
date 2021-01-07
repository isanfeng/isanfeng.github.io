// 配置
window.Config = {

  // 站点名
  SiteName: '流浪⬝𝓲三丰⬝苦行志',

  // 站点链接
  SiteUrl: '/',

  // UptimeRobot Api Keys
  // 支持 Monitor-Specific 和 Read-Only 两只 Api Key
  ApiKeys: [
    'ur1131099-37c6dc9ea8cbed2f4fe9ffb4',
  ],

  // 是否显示监测站点的链接
  ShowLink: false,

  // 日志天数
  // 虽然免费版说仅保存60天日志，但测试好像API可以获取90天的
  // 不过时间不要设置太长，容易卡，接口请求也容易失败
  CountDays: 60,

  // 导航栏菜单
  Navi: [
    {
      text: 'Home',
      url: '/'
    },
    {
      text: 'Travel Map',
      url: '/travel_map'
    },
	{
      text: 'About',
      url: '/about'
    }
  ]
};
