+++
date = '2025-11-28T21:41:21+08:00'
draft = false
title = '后端如何配合前端使用 ECharts 显示数据'
+++

ECharts 的图表配置在前端完成，但数据结构需要后端配合。后端不应该直接返回一大段 ECharts option，让前端只能照着渲染；也不应该只返回数据库原始行，让前端猜字段含义。

比较好的方式是：**后端返回稳定、清晰、接近图表语义的数据，前端负责把数据组装成 option**。

## 简单柱状图

假设前端要展示每个章节的学习人数，后端可以返回 x 轴和数据序列。

```java
@RestController
@RequestMapping("/analysis")
public class AnalysisController {

    @GetMapping("/study-stat")
    public ChartResponse<Integer> getStudyStat() {
        List<String> categories = List.of("第一章", "第二章", "第三章", "第四章", "第五章");
        List<Integer> values = List.of(120, 200, 150, 80, 70);

        return new ChartResponse<>(
                categories,
                List.of(new Series<>("学习人数", values))
        );
    }
}
```

响应结构：

```json
{
  "categories": ["第一章", "第二章", "第三章", "第四章", "第五章"],
  "series": [
    {
      "name": "学习人数",
      "data": [120, 200, 150, 80, 70]
    }
  ]
}
```

DTO 可以这样定义：

```java
public record ChartResponse<T>(
        List<String> categories,
        List<Series<T>> series
) {
}

public record Series<T>(
        String name,
        List<T> data
) {
}
```

前端拿到后再组装 ECharts option：

```javascript
const option = {
  tooltip: { trigger: "axis" },
  xAxis: { type: "category", data: response.categories },
  yAxis: { type: "value" },
  series: response.series.map(item => ({
    name: item.name,
    type: "bar",
    data: item.data
  }))
};
```

这样后端不需要知道前端用柱状图、折线图还是混合图，只需要保证数据语义稳定。

## 多序列图表

如果要同时展示学习人数和完成人数：

```json
{
  "categories": ["第一章", "第二章", "第三章"],
  "series": [
    {
      "name": "学习人数",
      "data": [120, 200, 150]
    },
    {
      "name": "完成人数",
      "data": [80, 160, 100]
    }
  ]
}
```

这种结构比 `xAxis`、`data1`、`data2` 更容易扩展。后面新增一条线，只需要多一个 series。

## 饼图数据

饼图通常不需要 x 轴，而是 name-value 结构：

```json
{
  "items": [
    { "name": "Java", "value": 120 },
    { "name": "MySQL", "value": 80 },
    { "name": "Redis", "value": 60 }
  ]
}
```

DTO：

```java
public record PieChartResponse<T>(
        List<PieItem<T>> items
) {
}

public record PieItem<T>(
        String name,
        T value
) {
}
```

前端：

```javascript
const option = {
  tooltip: { trigger: "item" },
  series: [
    {
      type: "pie",
      data: response.items
    }
  ]
};
```

## 后端应该负责什么

后端应负责：

- 聚合数据库数据。
- 补齐缺失时间点。
- 排序。
- 单位换算。
- 权限过滤。
- 控制返回字段。
- 保证接口结构稳定。

例如按日期统计时，如果某天没有数据，后端最好补 `0`：

```json
{
  "categories": ["2026-02-01", "2026-02-02", "2026-02-03"],
  "series": [
    {
      "name": "访问量",
      "data": [32, 0, 45]
    }
  ]
}
```

否则前端图表会断开，或者需要写一堆补齐逻辑。能在数据层一次性处理清楚，就别让每个页面重复猜。

## 接口设计建议

图表接口建议注意：

- 时间范围由前端传入，例如 `startTime`、`endTime`。
- 粒度可配置，例如 day、week、month。
- 返回结果保持有序。
- 数值字段使用数字类型，不要返回字符串。
- 空数据返回空数组或补零，不要返回 `null`。
- 后端不要把 ECharts 私有配置和业务数据绑定过死。

示例请求：

```http
GET /analysis/study-stat?startDate=2026-02-01&endDate=2026-02-07&granularity=day
```

## 小结

后端配合 ECharts 的重点不是“把 option 拼好返回”，而是提供稳定、清楚、可扩展的数据结构。前端控制展示，后端控制数据语义。边界清楚，图表需求变动时才不会互相拖着下水。
