+++
date = '2026-02-19T21:41:58+08:00'
draft = false
title = 'poi'
+++

### 1）一个文件 Excel 对应 POI 的哪些抽象类？

一个 Excel 文件（`.xlsx/.xls`）的结构大致是：

- **Workbook（工作簿）**：一个文件
  - **Sheet（工作表）**：一个 tab（例如 `原始数据`、`过程线`）
    - **Row（行）**
      - **Cell（单元格）**

### 2）POI 中对应的核心类是什么？

**抽象接口**

- `org.apache.poi.ss.usermodel.Workbook`  -> 工作簿（一个 Excel 文件）
- `org.apache.poi.ss.usermodel.Sheet`     -> 工作表（一个表）
- `org.apache.poi.ss.usermodel.Row`       -> 行
- `org.apache.poi.ss.usermodel.Cell`      -> 单元格
- `org.apache.poi.ss.usermodel.CellStyle` -> 单元格样式
- `org.apache.poi.ss.usermodel.DataFormat`-> 数据格式（日期、数字格式等）
- `org.apache.poi.ss.usermodel.FormulaEvaluator` -> 公式计算器（需要时）

**具体实现**

- `.xlsx`：`org.apache.poi.xssf.usermodel.XSSFWorkbook`
- `.xls` ：`org.apache.poi.hssf.usermodel.HSSFWorkbook`

### 3）Java POI 如何操作一个文件中的多个 Sheet？

#### 3.1 读取一个 Excel，遍历所有 Sheet

```java
try (InputStream is = new FileInputStream("template.xlsx");
     Workbook wb = WorkbookFactory.create(is)) {

    int sheetCount = wb.getNumberOfSheets();
    for (int i = 0; i < sheetCount; i++) {
        Sheet sheet = wb.getSheetAt(i);
        System.out.println(i + " -> " + sheet.getSheetName());
    }
}
```

#### 3.2 按名字获取某个 Sheet

```java
Sheet raw = wb.getSheet("原始数据");
Sheet chart = wb.getSheet("过程线");
```

#### 3.3 新增 / 删除 / 重命名 Sheet

```java
Sheet s = wb.createSheet("新表");

int idx = wb.getSheetIndex("原始数据");
wb.setSheetName(idx, "原始数据_备份");

// 删除
wb.removeSheetAt(idx);
```

### 4）行、单元格怎么操作？

#### 4.1 取某个单元格

```java
Row row = sheet.getRow(1);          // 第2行（0-based）
Cell cell = row != null ? row.getCell(2) : null;  // 第3列（C列）
```

#### 4.2 写入单元格

```java
Row row = sheet.getRow(1);
if (row == null) row = sheet.createRow(1);

Cell c = row.getCell(2);
if (c == null) c = row.createCell(2);

c.setCellValue(123.45); // 数字
```

#### 4.3 读取单元格值

因为 Excel 里同一格可能是数值/日期/字符串/公式，你直接 getStringCellValue 很容易报错。

```java
DataFormatter fmt = new DataFormatter();
String text = fmt.formatCellValue(cell); // 统一转成显示文本
```

如果要处理公式结果：

```java
FormulaEvaluator evaluator = wb.getCreationHelper().createFormulaEvaluator();
String text = fmt.formatCellValue(cell, evaluator);
```

### 5）列在 POI 里是什么？

POI **没有 Column 这个对象类**，列主要用：

- **列索引 int** 表示（A=0, B=1, C=2…）
- 列宽、隐藏等通过 `Sheet` API 操作：

```java
sheet.setColumnWidth(2, 20 * 256); // 第3列宽度
sheet.setColumnHidden(2, true);
```

数据结构对应关系总结表

| Excel 概念                | POI 对应类/表示                                      |
| ------------------------- | ---------------------------------------------------- |
| 文件（工作簿）            | `Workbook`（`XSSFWorkbook` / `HSSFWorkbook`）        |
| 工作表（一个表）          | `Sheet`                                              |
| 行                        | `Row`                                                |
| 单元格                    | `Cell`                                               |
| 列                        | 没有 Column 类，用 `int colIndex` 表示               |
| 单元格样式                | `CellStyle`                                          |
| 数据格式（日期/数字格式） | `DataFormat`                                         |
| 公式                      | `Cell.getCellType() == FORMULA` + `FormulaEvaluator` |
| 图表/图片等对象           | `.xlsx` 里属于 drawing（POI 可保留，改动较复杂）     |

> 我感觉这套 API 非常形象
