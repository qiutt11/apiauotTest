# Excel 驱动用例 — 设计文档

> 版本：v1.0 | 更新日期：2026-04-24

---

## 1. 背景与目标

### 1.1 业务场景

接口测试中经常遇到"保存接口 → 查看详情接口"的验证模式：

- 保存接口字段多（20+），需要逐一填入 body
- 详情接口返回同样的字段，需要逐一断言是否与保存值一致
- 同一套接口需要用多组数据测试

传统 YAML 用例在这种场景下非常冗长，且 body 和断言高度重复。

### 1.2 设计目标

- Excel 仅存储 body 字段数据（字段多、需逐一比对的部分）
- YAML 保持现有 `testcases` 结构，定义接口调用步骤和逻辑
- 现有用例、runner、validator 等核心模块**不做改动**
- 每行 Excel 数据在报告中展示为独立用例

---

## 2. 整体架构

### 2.1 执行流程

```
                YAML 文件
                    │
       ┌────────────┼────────────┐
       │            │            │
   普通用例    Excel驱动用例   普通用例
       │            │            │
  TestCaseItem      │       TestCaseItem
                    │
           load_excel_rows()
                    │
              ┌─────┴─────┐
              │            │
         第1行数据     第2行数据
              │            │
       ExcelDrivenItem  ExcelDrivenItem
              │            │
         steps循环      steps循环
              │            │
        ┌─────┤      ┌─────┤
        │     │      │     │
      step1 step2  step1 step2
        │     │      │     │
     run_testcase  run_testcase   ← 复用现有执行引擎
```

### 2.2 数据流向

```
Excel 行数据
    │
    ├──→ 变量池（pool.set_module）── step 中可通过 ${列名} 引用
    │
    ├──→ body_from_excel ──→ step_case["body"] ──→ run_testcase()
    │
    └──→ validate_from_excel ──→ _flatten ──→ step_case["validate"] ──→ run_testcase()
```

---

## 3. 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `common/data_loader.py` | 新增函数 | `load_excel_rows()` — 读取 Excel 行数据 |
| `common/runner.py` | 修改 | `run_testcase()` 支持 case 级 `base_url` 覆盖 |
| `conftest.py` | 新增类+函数 | `ExcelDrivenItem` 类、`collect()` Excel 分支、辅助函数 |
| `testcases/user/user_excel_driven.yaml` | 新增文件 | 示例用例（3 个场景） |
| `testcases/user/data/*.xlsx` | 新增文件 | 示例 Excel 数据 |
| `tests/test_excel_driven.py` | 新增文件 | 29 个单元测试 |
| `tests/integration/test_excel_driven_demo.py` | 新增文件 | 3 个端到端集成测试 |
| `tests/test_runner.py` | 追加测试 | 3 个 base_url 覆盖测试 |
| `tests/integration/test_full_pipeline.py` | 追加测试 | 4 个 Excel 驱动集成测试 |

### 未修改的文件

| 文件 | 原因 |
|------|------|
| `common/runner.py` 核心流程 | 每个 step 就是一个标准 case dict，直接走现有逻辑 |
| `common/validator.py` | 断言由框架生成标准 `{"eq": [...]}` 格式，无需修改 |
| `common/variable_pool.py` | Excel 数据通过 `set_module()` 注入，无需修改 |
| `common/request_handler.py` | body 已构建好传入，无需修改 |
| `common/extractor.py` | extract 逻辑不变 |

---

## 4. 模块设计

### 4.1 `load_excel_rows()` — 数据加载

**位置：** `common/data_loader.py`

**职责：** 读取 Excel 每行数据为 `list[dict]`，自动处理类型转换。

**设计决策：**

| 决策点 | 方案 | 原因 |
|--------|------|------|
| JSON 解析策略 | 仅 dict/list 自动转换 | 避免 `"true"` 被转为 bool、`"123"` 被转为 int |
| float→int 转换 | `25.0` → `25` | openpyxl 默认行为导致整数变浮点，影响 body 和断言 |
| 空行处理 | 静默跳过 | 空行不应生成测试项 |
| 空单元格 | 字段不出现 | 而非传 null，更贴近"未填写"语义 |

**函数签名：**

```python
def load_excel_rows(file_path: str) -> list[dict]:
    """读取 Excel 每行数据为字典列表（表头作为 key）。"""
```

### 4.2 `ExcelDrivenItem` — 用例执行器

**位置：** `conftest.py`

**职责：** 对应 Excel 中的一行数据，按 steps 顺序执行多步操作。

**类结构：**

```python
class ExcelDrivenItem(pytest.Item):
    _steps: list[dict]       # YAML 中定义的步骤列表
    _row_data: dict          # 当前 Excel 行数据 {列名: 值}
    _row_index: int          # Excel 行索引
    _module_name: str        # 所属模块名

    def runtest(self):
        # 1. 注入 Excel 行数据到变量池
        # 2. 遍历 steps:
        #    a. deepcopy(step) — 避免多行数据间干扰
        #    b. body_from_excel → 构建 body
        #    c. validate_from_excel → 生成断言
        #    d. run_testcase() — 复用现有引擎
        #    e. 失败则停止
```

**关键设计决策：**

| 决策点 | 方案 | 原因 |
|--------|------|------|
| step 拷贝方式 | `copy.deepcopy(step)` | 多行数据共享同一 steps 定义，浅拷贝会导致嵌套 dict（headers）在行间共享引用 |
| body_from_excel 处理时机 | 在 `run_testcase()` 之前 | 构建好标准 case dict 再传入，不侵入 runner |
| validate_from_excel 处理时机 | 在 `run_testcase()` 之前 | 将 Excel 断言追加到 validate 列表，runner 当普通断言处理 |
| 失败策略 | 任一 step 失败即停止 | 后续 step 依赖前面的结果（如 id），继续执行无意义 |

### 4.3 `collect()` 修改 — 用例收集

**位置：** `conftest.py` → `TestCaseFile.collect()`

**修改逻辑：**

```python
for case in testcases:
    if case.get("excel_source") and case.get("steps"):
        # Excel 驱动：加载 Excel → 每行生成一个 ExcelDrivenItem
        rows = load_excel_rows(excel_path)
        for row in rows:
            yield ExcelDrivenItem(name=f"{case_name}[{first_col_value}]", ...)
    else:
        # 普通用例：走原有逻辑
        yield TestCaseItem(...)
```

**Excel 文件路径解析：**
- 相对路径：基于 YAML 文件所在目录拼接
- 绝对路径：直接使用
- 文件不存在：抛出带路径的 `FileNotFoundError`

### 4.4 辅助函数

#### `_flatten_excel_validations(prefix, value)`

递归展开 Excel 值为 `eq` 断言列表：

```
输入：prefix="$.data", value={"name": "张三", "tags": ["vip", "new"]}

递归过程：
  $.data → dict → 展开 keys
    $.data.name → "张三" → 叶子节点 → eq: [$.data.name, "张三"]
    $.data.tags → list → 展开 index
      $.data.tags[0] → "vip" → 叶子节点 → eq: [$.data.tags[0], "vip"]
      $.data.tags[1] → "new" → 叶子节点 → eq: [$.data.tags[1], "new"]

输出：[
  {"eq": ["$.data.name", "张三"]},
  {"eq": ["$.data.tags[0]", "vip"]},
  {"eq": ["$.data.tags[1]", "new"]},
]
```

#### `_build_body_from_excel(row_data, config)`

| config 值 | 行为 |
|-----------|------|
| `True` | `dict(row_data)` 直接返回副本 |
| `{"field_mapping": {"a": "b"}}` | 遍历 row_data，按 mapping 重命名 key |

#### `_build_excel_validations(row_data, config)`

| config 值 | 行为 |
|-----------|------|
| `{"prefix": "$.data"}` | 遍历列，生成 `$.data.{col}` 前缀的断言 |
| `+ field_mapping` | 遍历列，用 mapping 后的名称作为断言路径 |

### 4.5 `base_url` 覆盖 — 跨系统支持

**位置：** `common/runner.py` → `run_testcase()`

**修改逻辑：**

```python
case_base_url = case.get("base_url")
if case_base_url:
    base_url = str(pool.resolve(case_base_url))
```

**设计决策：**

| 决策点 | 方案 | 原因 |
|--------|------|------|
| 覆盖时机 | 函数最顶部 | 确保后续所有 URL 拼接都使用新值 |
| db_setup 后重解析 | 有 | base_url 可能引用 db_setup 提取的变量 |
| 类型安全 | `str()` 包裹 | pool.resolve 可能返回非字符串 |
| 空字符串处理 | 不覆盖（falsy） | 空 base_url 无意义，视为未设置 |

---

## 5. YAML 结构设计

### 5.1 核心原则

- 保持在 `testcases` 数组中，不引入新的顶层概念
- 通过 `excel_source` + `steps` 字段标识 Excel 驱动用例
- 每个 step 的结构等同于一个普通用例（method/url/headers/body/extract/validate）
- 新增的 `body_from_excel`、`validate_from_excel`、`base_url` 都是可选字段

### 5.2 完整 YAML 结构

```yaml
module: 模块名
testcases:
  # Excel 驱动用例
  - name: 保存并验证详情
    level: P0
    excel_source: data/xxx.xlsx         # Excel 路径（相对于 YAML）
    steps:
      - name: 保存
        base_url: ${system_a_url}       # 可选：覆盖全局地址
        method: POST
        url: /api/save
        headers:
          Authorization: Bearer ${token}
        body_from_excel: true           # 或 {field_mapping: {a: b}}
        extract:
          id: $.data.id
        validate:
          - eq: [$.code, 0]

      - name: 查看详情
        base_url: ${system_b_url}       # 可选：不同系统
        method: GET
        url: /api/detail/${id}
        headers:
          Authorization: Bearer ${token}
        validate_from_excel:
          prefix: $.data                # 必填
          field_mapping:                # 可选
            excel_col: response_field
        validate:
          - eq: [$.code, 0]
```

### 5.3 `body_from_excel` 配置格式

| 写法 | 含义 |
|------|------|
| `body_from_excel: true` | 所有列直接作为 body 字段（列名=字段名） |
| `body_from_excel:` + `field_mapping:` | 列名映射，未映射的列保留原名 |

### 5.4 `validate_from_excel` 配置格式

| 字段 | 必填 | 说明 |
|------|------|------|
| `prefix` | 否（默认 `$.data`） | 响应 JSON 中数据的 JSONPath 前缀 |
| `field_mapping` | 否 | Excel 列名 → 响应字段名映射 |

---

## 6. 递归断言展开规则

`_flatten_excel_validations()` 按值类型递归生成断言：

| 值类型 | 处理方式 | 示例 |
|--------|---------|------|
| str/int/float/bool | 生成 `eq` 断言 | `"张三"` → `eq: [$.data.name, "张三"]` |
| dict | 递归展开每个 key | `{"city":"北京"}` → `eq: [$.data.addr.city, "北京"]` |
| list | 按下标递归展开 | `["a","b"]` → `eq: [$.data.tags[0], "a"]`, `eq: [$.data.tags[1], "b"]` |
| list[dict] | 继续递归 | `[{"id":1}]` → `eq: [$.data.items[0].id, 1]` |
| 空 dict/list | 不生成断言 | `{}` / `[]` → 无输出 |

---

## 7. 测试覆盖

### 7.1 单元测试（`tests/test_excel_driven.py`）— 29 个

| 分类 | 测试数 | 覆盖内容 |
|------|--------|---------|
| `TestLoadExcelRows` | 10 | 基础加载、JSON 解析（list/dict）、非 JSON 保留、空行跳过、空列头、空文件、部分空单元格、嵌套 JSON |
| `TestFlattenExcelValidations` | 9 | 简单值（str/int/bool）、平铺 dict、list、嵌套 dict、数组内对象、空 dict/list |
| `TestBuildBodyFromExcel` | 5 | true 直接映射、副本安全性、field_mapping、空 mapping |
| `TestBuildExcelValidations` | 5 | 基础 prefix、默认 prefix、field_mapping、嵌套值+mapping、复杂混合 |

### 7.2 集成测试

| 文件 | 测试数 | 覆盖内容 |
|------|--------|---------|
| `test_full_pipeline.py::TestExcelDrivenPipeline` | 4 | 保存→详情完整流程、field_mapping、断言失败、复杂嵌套值 |
| `test_excel_driven_demo.py::TestExcelDrivenDemo` | 3 | 端到端基础流程、field_mapping 端到端、失败信息展示 |
| `test_runner.py` (追加) | 3 | base_url 覆盖、变量 base_url、无覆盖时回退 |

### 7.3 测试总数

| 类别 | 变更前 | 变更后 |
|------|--------|--------|
| 单元测试 | 100 | 132 (+32) |
| 集成测试 | 17 | 24 (+7) |
| 级别过滤测试 | 5 | 5 (不变) |
| **总计** | **122** | **161** |

---

## 8. 向后兼容性

| 场景 | 行为 |
|------|------|
| 现有 YAML 用例（无 excel_source） | 走原有 `TestCaseItem` 逻辑，完全不受影响 |
| 现有 Excel 用例（直接写用例数据） | 走原有 `_load_excel()` 逻辑，完全不受影响 |
| 现有 JSON 用例 | 不受影响 |
| 不使用 base_url 的用例 | runner 行为不变 |
| `--level` 过滤 | Excel 驱动用例同样支持 level 过滤 |
| `--workers` 并行 | 同一 YAML 内的 Excel 驱动用例按顺序执行，不同文件间并行 |
| Allure 报告 | ExcelDrivenItem 正确设置 feature/story 标签 |
| 统计和通知 | ExcelDrivenItem 纳入 passed/failed/skipped 统计 |

---

## 9. 已知限制

| 限制 | 说明 | 规避方案 |
|------|------|---------|
| 不支持只运行 Excel 某一行 | pytest 收集时展开所有行 | 临时删除 Excel 中不需要的行 |
| 不支持 Excel 中写断言关键字 | validate_from_excel 只生成 `eq` | 在 YAML 的 validate 中手写其他断言 |
| 不支持跨 step 的条件分支 | steps 始终按顺序执行 | 拆分为多个 Excel 驱动用例 |
| Excel 数据变更需重跑全部行 | 无增量机制 | 按场景拆分 Excel 文件 |

---

## 10. 文件结构参考

```
testcases/
├── login/
│   └── login.yaml                      # 普通用例
├── user/
│   ├── user_crud.yaml                  # 普通用例
│   ├── user_excel_driven.yaml          # Excel 驱动用例（含 3 个场景示例）
│   └── data/
│       ├── user_data.xlsx              # 示例数据（直接映射）
│       └── user_data_with_mapping.xlsx # 示例数据（字段映射）
└── order/
    ├── order_flow.yaml                 # 可混合 Excel 驱动 + 普通用例
    └── data/
        └── order_data.xlsx
```
