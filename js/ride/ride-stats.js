// 骑行年度统计图表：每年总里程（柱）+ 骑行次数（折线），双指标、带 tooltip。
// 数据由 a_ride-stats.html 的 Liquid 聚合注入到 window.__rideYearData。
(function () {
  "use strict";

  var canvas = document.getElementById("ride-stats-canvas");
  if (!canvas) return;

  var data = window.__rideYearData || [];

  function fail(msg) {
    canvas.innerHTML = '<p style="padding:24px;color:#b00">' + msg + '</p>';
  }

  if (typeof am5 === "undefined" || typeof am5xy === "undefined" ||
      typeof am5themes_Animated === "undefined") {
    fail("amCharts 5 资源未加载，请检查 /js/amcharts/5/*.js 是否 200");
    return;
  }

  if (!data.length) {
    canvas.innerHTML = '<p style="padding:24px;opacity:.65">暂无骑行数据。给文章 front-matter 加上 <code>ride:</code> 块后即可自动统计。</p>';
    return;
  }

  try {
    // 按年份升序展示
    data.sort(function (a, b) { return a.year < b.year ? -1 : 1; });

    var root = am5.Root.new("ride-stats-canvas");
    root.setThemes([am5themes_Animated.new(root)]);

    var chart = root.container.children.push(am5xy.XYChart.new(root, {
      panX: false, panY: false, wheelX: "none", wheelY: "none",
      layout: root.verticalLayout
    }));

    var xAxis = chart.xAxes.push(am5xy.CategoryAxis.new(root, {
      categoryField: "year",
      renderer: am5xy.AxisRendererX.new(root, { minGridDistance: 20 })
    }));
    xAxis.data.setAll(data);

    var yKm = chart.yAxes.push(am5xy.ValueAxis.new(root, {
      renderer: am5xy.AxisRendererY.new(root, {})
    }));
    // amCharts 5 轴标题需用 Label 手动加（Axis 无 title 属性，v4 的 axis.title.setAll 在 v5 会崩）
    yKm.children.push(am5.Label.new(root, {
      text: "总里程 (km)",
      fontSize: 12, fontWeight: "500",
      rotation: -90, y: am5.percent(50), centerX: am5.percent(50)
    }));

    var yRides = chart.yAxes.push(am5xy.ValueAxis.new(root, {
      renderer: am5xy.AxisRendererY.new(root, { opposite: true })
    }));
    yRides.children.push(am5.Label.new(root, {
      text: "骑行次数",
      fontSize: 12, fontWeight: "500",
      rotation: -90, y: am5.percent(50), centerX: am5.percent(50)
    }));

    var colSeries = chart.series.push(am5xy.ColumnSeries.new(root, {
      name: "总里程", xAxis: xAxis, yAxis: yKm,
      valueYField: "km", categoryXField: "year",
      tooltip: am5.Tooltip.new(root, { labelText: "{name}: {valueY} km" })
    }));
    colSeries.columns.template.setAll({ fill: am5.color(0x00853a), stroke: am5.color(0x00853a) });
    colSeries.data.setAll(data);

    var lineSeries = chart.series.push(am5xy.LineSeries.new(root, {
      name: "骑行次数", xAxis: xAxis, yAxis: yRides,
      valueYField: "rides", categoryXField: "year",
      tooltip: am5.Tooltip.new(root, { labelText: "{name}: {valueY}" })
    }));
    lineSeries.strokes.template.setAll({ stroke: am5.color(0xe74c3c), strokeWidth: 2 });
    lineSeries.data.setAll(data);

    var legend = chart.children.push(am5.Legend.new(root, {
      centerX: am5.p50, x: am5.p50, paddingTop: 12
    }));
    // amCharts 5 图例不会自动收集 series，必须显式塞入，否则图例空白
    legend.data.setAll([colSeries, lineSeries]);

    chart.appear(1000, 100);
  } catch (e) {
    fail("图表渲染失败：" + (e && e.message ? e.message : e));
    if (window.console) console.error(e);
  }
})();
