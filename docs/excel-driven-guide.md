# Excel 驱动用例使用手册

本文档详细介绍 Excel 驱动用例功能的使用方法，面向**编写和维护测试用例的测试人员**。

---

## 目录

1. [功能简介](#1-功能简介)
2. [快速上手](#2-快速上手)
3. [Excel 文件规范](#3-excel-文件规范)
4. [YAML 配置详解](#4-yaml-配置详解)
5. [body_from_excel 用法](#5-body_from_excel-用法)
6. [validate_from_excel 用法](#6-validate_from_excel-用法)
7. [跨系统场景（base_url 覆盖）](#7-跨系统场景base_url-覆盖)
8. [变量传递机制](#8-变量传递机制)
9. [完整示例](#9-完整示例)
10. [常见问题](#10-常见问题)

---

## 1. 功能简介

### 1.1 解决什么问题

当你遇到以下场景时，传统 YAML 用例写起来非常繁琐：

- 保存接口有 **20+ 个字段**，每个都要填入 body
- 查看详情接口需要**逐个字段**比对是否与保存一致
- 同一组接口需要用**多组数据**测试（张三、李四、王五...）

Excel 驱动用例让你：

- **Excel 管理数据**：字段多时在 Excel 中填写更直观，支持业务人员维护
- **YAML 管理逻辑**：接口调用步骤、URL、headers 等仍在 YAML 中定义
- **自动展开**：Excel 每行数据自动生成一个独立用例，报告中分别展示

### 1.2 工作原理

```
YAML 定义步骤               Excel 存储数据
┌──────────────┐          ┌──────────────────┐
│ step1: 保存   │          │ 张三 | 25 | 138.. │
│ step2: 详情   │    ×     │ 李四 | 30 | 139.. │
└──────────────┘          └──────────────────┘
        ↓                          ↓
  自动组合生成 2 个独立用例：
  ├── 保存并验证[张三] → step1(body=张三数据) → step2(断言=张三数据)
  └── 保存并验证[李四] → step1(body=李四数据) → step2(断言=李四数据)
```

---

## 2. 快速上手

### 第一步：准备 Excel 数据文件

在 `testcases/` 对应模块目录下创建 `data/` 子目录，放入 Excel 文件：

```
testcases/user/
├── user_crud.yaml              # 原有用例（不受影响）
├── user_excel_driven.yaml      # 新增：Excel 驱动用例
└── data/
    └── user_data.xlsx          # 新增：Excel 数据文件
```

Excel 内容示例：

| name | age | phone       |
|------|-----|-------------|
| 张三 | 25  | 13800001111 |
| 李四 | 30  | 13900002222 |

### 第二步：编写 YAML 用例

```yaml
module: 用户管理
testcases:
  - name: 登录获取token
    method: POST
    url: /api/login
    body:
      username: ${admin_user}
      password: ${admin_pass}
    extract:
      token: $.data.token
    validate:
      - eq: [$.code, 0]

  - name: 保存并验证用户
    excel_source: data/user_data.xlsx       # 指向 Excel 文件
    steps:
      - name: 保存
        method: POST
        url: /api/user/save
        headers:
          Authorization: Bearer ${token}
        body_from_excel: true               # Excel 数据作为 body
        extract:
          id: $.data.id
        validate:
          - eq: [$.code, 0]

      - name: 查看详情
        method: GET
        url: /api/user/detail/${id}
        headers:
          Authorization: Bearer ${token}
        validate_from_excel:                # Excel 数据作为断言
          prefix: $.data
        validate:
          - eq: [$.code, 0]
```

### 第三步：运行

```bash
# 查看收集到的用例
python3 run.py --path testcases/user/user_excel_driven.yaml --report html

# 报告中会看到：
#   登录获取token          PASSED
#   保存并验证用户[张三]     PASSED
#   保存并验证用户[李四]     PASSED
```

---

## 3. Excel 文件规范

### 3.1 基本规则

| 规则 | 说明 |
|------|------|
| 第一行 | 表头（列名），作为字段名或映射的 key |
| 第二行起 | 每行一组测试数据 |
| 空行 | 自动跳过（所有单元格为空的行） |
| 空列头 | 该列被忽略 |
| 空单元格 | 该字段不出现在数据中（不会传 null） |

### 3.2 数据类型

| Excel 单元格内容 | 框架解析结果 | 类型 |
|-----------------|-------------|------|
| `张三` | `"张三"` | str |
| `25`（数字格式） | `25` | int |
| `99.5`（小数） | `99.5` | float |
| `13800001111`（文本格式） | `"13800001111"` | str |
| `["vip","new"]` | `["vip", "new"]` | list |
| `{"city":"北京"}` | `{"city": "北京"}` | dict |
| `[{"id":1},{"id":2}]` | `[{"id": 1}, {"id": 2}]` | list[dict] |

**关键点：**

- 整数单元格（如 `25`）自动转为 Python `int`，不会出现 `25.0`
- JSON 字符串只有解析为 `dict` 或 `list` 时才转换，普通字符串不会被意外转换
- 如果手机号等数字想保持字符串格式，在 Excel 中将单元格设为「文本」格式

### 3.3 复杂值写法

在单元格中直接写 JSON 字符串即可：

| 场景 | 单元格内容 | 解析结果 |
|------|-----------|---------|
| 标签数组 | `["vip","new"]` | Python list |
| 地址对象 | `{"city":"北京","street":"xx路"}` | Python dict |
| 嵌套数组 | `[{"id":1,"name":"A"},{"id":2,"name":"B"}]` | list of dicts |

---

## 4. YAML 配置详解

### 4.1 Excel 驱动用例结构

```yaml
- name: 用例名称                    # 报告中显示为"用例名称[第一列值]"
  level: P0                        # 可选，优先级（支持 --level 过滤）
  excel_source: data/xxx.xlsx      # Excel 文件路径（相对于本 YAML 文件）
  steps:                           # 步骤列表，按顺序执行
    - name: 步骤1
      method: POST
      url: /api/save
      body_from_excel: true        # 用 Excel 数据构建 body
      extract:
        id: $.data.id
      validate:
        - eq: [$.code, 0]

    - name: 步骤2
      method: GET
      url: /api/detail/${id}
      validate_from_excel:         # 用 Excel 数据生成断言
        prefix: $.data
      validate:
        - eq: [$.code, 0]
```

### 4.2 关键字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `excel_source` | 是 | Excel 文件路径，相对于 YAML 文件目录，也支持绝对路径 |
| `steps` | 是 | 步骤列表，每个 step 等同于一个普通用例的结构 |
| `body_from_excel` | 否 | 放在 step 中，将 Excel 行数据转为请求 body |
| `validate_from_excel` | 否 | 放在 step 中，将 Excel 行数据转为 eq 断言 |
| `base_url` | 否 | 放在 step 中，覆盖全局接口地址（跨系统场景） |

### 4.3 与普通用例混合

Excel 驱动用例和普通用例可以写在同一个 YAML 文件中，互不影响：

```yaml
testcases:
  - name: 登录                    # 普通用例
    method: POST
    url: /api/login
    ...

  - name: Excel驱动用例           # Excel 驱动用例
    excel_source: data/xxx.xlsx
    steps: [...]

  - name: 其他普通用例             # 普通用例
    method: GET
    url: /api/other
    ...
```

---

## 5. body_from_excel 用法

### 5.1 直接映射（最简场景）

当 **Excel 列名 = 接口字段名** 时：

```yaml
body_from_excel: true
```

| Excel | → | 请求 body |
|-------|---|-----------|
| name=张三, age=25, phone=138xxx | → | `{"name":"张三","age":25,"phone":"138xxx"}` |

### 5.2 字段名映射

当 **Excel 列名 ≠ 接口字段名** 时（如 Excel 用中文，接口用英文）：

```yaml
body_from_excel:
  field_mapping:
    姓名: name              # Excel 的「姓名」列 → body 的 name 字段
    年龄: age
    手机号: phone
```

| Excel | → | 请求 body |
|-------|---|-----------|
| 姓名=张三, 年龄=25, 手机号=138xxx | → | `{"name":"张三","age":25,"phone":"138xxx"}` |

**规则：** 未在 `field_mapping` 中列出的列，仍使用原列名。

### 5.3 注意事项

- `body_from_excel` 会**替换** step 中的 `body` 字段（如果同时存在）
- Excel 中的复杂值（数组、对象）会作为嵌套结构写入 body，不是字符串

---

## 6. validate_from_excel 用法

### 6.1 基本用法

```yaml
validate_from_excel:
  prefix: $.data               # 响应 JSON 中数据的前缀路径
```

框架自动将 Excel 每列数据生成 `eq` 断言：

| Excel 列 | 生成的断言 |
|----------|-----------|
| name=张三 | `eq: [$.data.name, "张三"]` |
| age=25 | `eq: [$.data.age, 25]` |

### 6.2 字段名映射

当 **Excel 列名 ≠ 响应字段名** 时：

```yaml
validate_from_excel:
  prefix: $.data
  field_mapping:
    姓名: user_name           # Excel 的「姓名」→ 响应的 $.data.user_name
    年龄: user_age
```

### 6.3 嵌套值自动递归展开

Excel 中的复杂值会被递归展开为多条断言：

| Excel 值 | 自动生成的断言 |
|----------|--------------|
| `tags=["vip","new"]` | `eq: [$.data.tags[0], "vip"]`<br>`eq: [$.data.tags[1], "new"]` |
| `address={"city":"北京","street":"xx路"}` | `eq: [$.data.address.city, "北京"]`<br>`eq: [$.data.address.street, "xx路"]` |
| `items=[{"id":1,"name":"A"}]` | `eq: [$.data.items[0].id, 1]`<br>`eq: [$.data.items[0].name, "A"]` |

### 6.4 与手写 validate 并存

`validate_from_excel` 生成的断言**追加**在手写 `validate` 后面：

```yaml
validate_from_excel:
  prefix: $.data
validate:
  - eq: [$.code, 0]           # 手写断言（先执行）
  # Excel 生成的断言自动追加在这里
```

---

## 7. 跨系统场景（base_url 覆盖）

当不同 step 需要调用**不同系统**的接口时，在 step 中使用 `base_url` 覆盖全局地址。

### 7.1 直接写地址

```yaml
steps:
  - name: A系统保存
    base_url: https://api-a.example.com
    method: POST
    url: /api/save
    body_from_excel: true
    ...

  - name: B系统查询
    base_url: https://api-b.example.com
    method: GET
    url: /api/detail/${id}
    validate_from_excel:
      prefix: $.data
    ...
```

### 7.2 使用变量（推荐）

在环境配置中定义各系统地址，用例中引用变量，方便环境切换：

```yaml
# config/test.yaml
global_variables:
  system_a_url: https://api-a.test.com
  system_b_url: https://api-b.test.com

# config/prod.yaml
global_variables:
  system_a_url: https://api-a.prod.com
  system_b_url: https://api-b.prod.com
```

```yaml
# 用例中
steps:
  - name: A系统保存
    base_url: ${system_a_url}
    ...
  - name: B系统查询
    base_url: ${system_b_url}
    ...
```

### 7.3 适用范围

`base_url` 不仅限于 Excel 驱动用例，**普通用例也支持**：

```yaml
testcases:
  - name: 调用外部系统
    base_url: ${external_api_url}      # 覆盖全局 base_url
    method: GET
    url: /api/external/data
    validate:
      - eq: [status_code, 200]
```

不写 `base_url` 则使用全局配置，完全向后兼容。

---

## 8. 变量传递机制

### 8.1 Excel 数据自动注入变量池

Excel 每行数据在执行前自动写入变量池，可在 step 的任意字段中通过 `${列名}` 引用：

```yaml
steps:
  - name: 保存
    url: /api/user/save
    body_from_excel: true
    extract:
      id: $.data.id              # 从响应中提取 id

  - name: 查详情
    url: /api/user/detail/${id}  # 使用上一步提取的 id
    validate_from_excel:
      prefix: $.data
```

### 8.2 step 间变量传递

前一个 step 的 `extract` 提取的变量在后续 step 中可直接使用（与普通用例规则一致）。

### 8.3 变量优先级

```
临时变量 > 模块变量（extract + Excel 行数据）> 全局变量（config）
```

Excel 行数据以**模块变量**身份注入，会被同名的 extract 结果覆盖。

---

## 9. 完整示例

### 示例文件参考

项目中已提供完整的示例文件：

```
testcases/user/
├── user_excel_driven.yaml              # 3 个场景的 YAML 定义（含详细注释）
└── data/
    ├── user_data.xlsx                  # 示例1：直接映射（2行数据，含嵌套 JSON）
    └── user_data_with_mapping.xlsx     # 示例2：中文列名映射（1行数据）
```

### 场景汇总

| 场景 | body_from_excel | validate_from_excel | base_url | 示例文件 |
|------|----------------|--------------------|---------|---------|
| 列名=字段名 | `true` | `prefix: $.data` | 不需要 | `user_data.xlsx` |
| 列名≠字段名 | `field_mapping: {...}` | `field_mapping: {...}` | 不需要 | `user_data_with_mapping.xlsx` |
| 跨系统调用 | `true` 或 mapping | `prefix: $.data` | `${system_x_url}` | YAML 注释示例 |

---

## 10. 常见问题

### Q: Excel 文件放在哪里？

推荐放在 YAML 同目录的 `data/` 子目录下。`excel_source` 的路径相对于 YAML 文件所在目录，也支持绝对路径。

### Q: Excel 文件不存在会怎样？

收集阶段会报明确错误：`Excel data file not found: /path/to/file.xlsx (referenced by excel_source in /path/to/yaml)`。

### Q: Excel 只有表头没有数据行会怎样？

不会报错，但该 Excel 驱动用例不会生成任何测试项（相当于 0 行数据）。

### Q: 某个 step 失败了会怎样？

任一 step 失败，整个用例立即标记为失败，后续 step **不再执行**。失败信息中会注明是哪个 step 失败的。

### Q: Excel 中的数字变成了小数（25.0）怎么办？

框架已自动处理：整数值（如 25.0）会转为 `int` 类型（25）。无需手动处理。

### Q: 能否只用 validate_from_excel 不用 body_from_excel？

可以。两者完全独立，可以单独使用。例如手动写 body，只用 Excel 数据做详情校验。

### Q: 能否只用 body_from_excel 不用 validate_from_excel？

可以。例如只需要批量提交数据，不需要逐字段校验详情。

### Q: 普通用例能用 base_url 吗？

可以。`base_url` 是 runner 层面的通用功能，所有用例（普通用例和 Excel 驱动 step）都支持。

### Q: 同一个 YAML 中能混合普通用例和 Excel 用例吗？

可以。框架通过 `excel_source` + `steps` 字段判断是否为 Excel 驱动用例，没有这两个字段的用例走原有逻辑。

### Q: Excel 驱动用例支持 --level 过滤吗？

支持。在 YAML 中给 Excel 驱动用例设置 `level` 即可，与普通用例一样。

### Q: 如何调试某一行数据？

暂不支持只运行 Excel 中的某一行。可以临时删除其他行，或在 Excel 中只保留要调试的行。
