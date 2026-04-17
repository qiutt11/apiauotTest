# 完整使用手册

本文档涵盖框架的所有功能和配置项。新手请先阅读 [quickstart.md](quickstart.md)。

---

## 目录

1. [安装与环境要求](#1-安装与环境要求)
2. [配置详解](#2-配置详解)
3. [用例编写](#3-用例编写)
4. [用例数据格式](#4-用例数据格式)
5. [断言关键字](#5-断言关键字)
6. [变量系统](#6-变量系统)
7. [接口依赖与数据传递](#7-接口依赖与数据传递)
8. [数据库操作](#8-数据库操作)
9. [Hook 扩展](#9-hook-扩展)
10. [优先级过滤](#10-优先级过滤)
11. [并行执行](#11-并行执行)
12. [重试机制](#12-重试机制)
13. [运行与命令行参数](#13-运行与命令行参数)
14. [测试报告](#14-测试报告)
15. [日志系统](#15-日志系统)
16. [邮件通知](#16-邮件通知)
17. [飞书通知](#17-飞书通知)
18. [CI/CD 集成](#18-cicd-集成)
19. [与被测系统集成](#19-与被测系统集成)
20. [常见问题](#20-常见问题)

---

## 1. 安装与环境要求

### 必须

- Python 3.10+
- pip

### 可选

- Allure CLI — 查看 Allure 报告时需要（[安装说明](https://docs.qameta.io/allure/#_installing_a_commandline)）
- MySQL — 使用数据库操作功能时需要
- Java 8+ — Allure CLI 依赖 Java 运行时

### 安装

```bash
pip install -r requirements.txt
```

依赖清单：

| 包 | 用途 |
|---|------|
| requests | HTTP 请求 |
| pytest | 测试引擎 |
| pyyaml | YAML 解析 |
| jsonpath-ng | JSONPath 数据提取 |
| openpyxl | Excel 解析 |
| allure-pytest | Allure 报告 |
| pytest-html | HTML 报告 |
| loguru | 日志 |
| pymysql | MySQL 数据库 |

---

## 2. 配置详解

配置文件在 `config/` 目录下，分为**主配置**和**环境配置**两层。

### 2.1 主配置 `config/config.yaml`

```yaml
# 当前使用的环境名（对应 config/ 目录下的 {env}.yaml 文件）
current_env: test

# HTTP 请求超时时间（秒）
timeout: 30

# 失败重试次数（0=不重试，用例级别 retry 字段可覆盖）
retry: 0

# 默认报告类型：allure / html / both
report_type: html

# 邮件通知配置
email:
  enabled: false                # 是否开启邮件通知
  smtp_host: smtp.qq.com        # SMTP 服务器地址
  smtp_port: 465                # SMTP 端口（SSL）
  sender: test@qq.com           # 发件人邮箱
  password: ""                  # SMTP 授权码（非邮箱登录密码）
  receivers:                    # 收件人列表
    - dev1@company.com
    - dev2@company.com
  send_on: fail                 # 发送时机：always=每次 / fail=失败时 / never=不发送
```

### 2.2 环境配置 `config/{env}.yaml`

每个环境一个文件，框架根据 `current_env` 或 `--env` 参数加载对应文件，**深合并**到主配置上。

```yaml
# 被测系统的接口基础地址（必填）
base_url: https://api.yourcompany.com

# 全局请求头（自动添加到所有请求，用例中的 headers 会覆盖同名 key）
global_headers:
  Content-Type: application/json
  X-App-Version: "2.0"

# 全局变量（在用例中用 ${变量名} 引用）
global_variables:
  admin_user: admin
  admin_pass: "123456"
  api_version: v1

# 数据库配置（可选，不需要数据库功能可以删掉）
database:
  host: 127.0.0.1
  port: 3306
  user: root
  password: "123456"
  database: test_db
  charset: utf8mb4
```

### 2.3 多环境管理

```
config/
├── config.yaml      # 主配置（公共部分）
├── dev.yaml         # 开发环境
├── test.yaml        # 测试环境
├── staging.yaml     # 预发环境
└── prod.yaml        # 生产环境
```

切换环境的两种方式：

```bash
# 方式1：修改 config.yaml 中的 current_env
current_env: dev

# 方式2：命令行参数（优先级更高）
python3 run.py --env dev
```

### 2.4 配置合并规则

环境配置会**深合并**到主配置上。例如：

```yaml
# config.yaml
email:
  enabled: false
  smtp_host: smtp.qq.com
  send_on: fail

# test.yaml
email:
  enabled: true
```

合并结果：`email.enabled = true`，`email.smtp_host = smtp.qq.com`，`email.send_on = fail`（保留未覆盖的字段）。

---

## 3. 用例编写

### 3.1 用例文件位置

所有用例文件放在 `testcases/` 目录下，支持任意层级的子目录：

```
testcases/
├── login/
│   └── login.yaml
├── user/
│   ├── user_crud.yaml
│   └── user_permission.yaml
└── order/
    └── order_flow.yaml
```

### 3.2 完整用例字段

```yaml
module: 模块名称                    # 显示在报告中的模块分组
testcases:
  - name: 用例名称                  # 必填
    description: 用例描述            # 可选，显示在报告详情中
    level: normal                   # 可选，优先级（影响 Allure 报告排序）
    method: POST                    # 必填，HTTP 方法
    url: /api/v1/login              # 必填，接口路径（自动拼接 base_url）
    headers:                        # 可选，请求头
      Authorization: Bearer ${token}
      X-Custom: value
    body:                           # 可选，请求体（JSON）
      username: admin
      password: "123456"
    extract:                        # 可选，从响应 body 中提取变量
      token: $.data.token
      user_id: $.data.user.id
    db_setup:                       # 可选，请求前执行的 SQL
      - sql: "INSERT INTO ..."
    db_extract:                     # 可选，请求后查询数据库提取变量
      - sql: "SELECT ..."
        extract:
          db_var: column_name
    db_teardown:                    # 可选，请求后清理 SQL
      - sql: "DELETE FROM ..."
    hook:                           # 可选，自定义处理函数
      before: function_name
      after: function_name
    validate:                       # 必填，至少一个断言
      - eq: [status_code, 200]
      - eq: [$.code, 0]
```

### 3.3 执行顺序

同一个 YAML 文件中的用例**按从上到下的顺序**执行。每个用例的内部执行流程：

```
1. 解析变量 ${xxx}
2. 执行 db_setup（如有）
3. 执行 before hook（如有）
4. 发送 HTTP 请求
5. 执行 after hook（如有）
6. 从响应中 extract 提取变量
7. 执行 db_extract 数据库查询（如有）
8. 执行 validate 断言校验
9. 执行 db_teardown 清理（如有，即使前面步骤失败也会执行）
10. 记录日志
```

### 3.4 变量作用域

- **同一个 YAML 文件内**：用例之间共享变量（前面 extract 的变量后面可以直接用）
- **不同 YAML 文件之间**：变量互相隔离（切换文件时自动清理模块变量）
- **全局变量**：在 config 中定义，所有文件都可以引用

---

## 4. 用例数据格式

### 4.1 YAML 格式（推荐）

可读性强，支持注释，是主推格式：

```yaml
module: 用户登录
testcases:
  - name: 登录成功
    method: POST
    url: /api/login
    body:
      username: ${admin_user}
      password: ${admin_pass}
    validate:
      - eq: [$.code, 0]
```

### 4.2 JSON 格式

结构与 YAML 完全一致：

```json
{
  "module": "用户登录",
  "testcases": [
    {
      "name": "登录成功",
      "method": "POST",
      "url": "/api/login",
      "body": {"username": "${admin_user}", "password": "${admin_pass}"},
      "validate": [{"eq": ["$.code", 0]}]
    }
  ]
}
```

### 4.3 Excel 格式

适合批量管理用例，业务人员更熟悉。

- **Sheet 名称**作为模块名
- **第一行**为表头
- **每行**一个用例

| name | method | url | headers | body | extract | validate |
|------|--------|-----|---------|------|---------|----------|
| 登录成功 | POST | /api/login | | {"username":"admin","password":"123456"} | {"token":"$.data.token"} | [{"eq":["$.code",0]}] |
| 密码错误 | POST | /api/login | | {"username":"admin","password":"wrong"} | | [{"neq":["$.code",0]}] |

**注意：** headers、body、extract、validate 列中需要填写**合法的 JSON 字符串**。

---

## 5. 断言关键字

| 关键字 | 说明 | 用法 | 示例 |
|--------|------|------|------|
| `eq` | 等于 | `eq: [表达式, 期望值]` | `eq: [$.code, 0]` |
| `neq` | 不等于 | `neq: [表达式, 排除值]` | `neq: [$.code, -1]` |
| `gt` | 大于 | `gt: [表达式, 下限]` | `gt: [$.data.total, 0]` |
| `lt` | 小于 | `lt: [表达式, 上限]` | `lt: [$.data.total, 100]` |
| `gte` | 大于等于 | `gte: [表达式, 下限]` | `gte: [status_code, 200]` |
| `lte` | 小于等于 | `lte: [表达式, 上限]` | `lte: [status_code, 299]` |
| `contains` | 包含子串 | `contains: [表达式, 子串]` | `contains: [$.msg, "成功"]` |
| `not_null` | 不为空 | `not_null: [表达式]` | `not_null: [$.data.token]` |
| `type` | 类型校验 | `type: [表达式, 类型]` | `type: [$.data.id, int]` |
| `length` | 长度校验 | `length: [表达式, 长度]` | `length: [$.data.list, 10]` |

**表达式类型：**
- `status_code` — HTTP 状态码
- `$.xxx` — JSONPath 表达式，从响应 body 中提取值
- `${xxx}` — 引用变量池中的变量（如数据库提取的值）

**type 支持的类型：** `int`、`float`、`str`、`list`、`dict`、`bool`

---

## 6. 变量系统

### 6.1 变量来源

| 来源 | 优先级 | 说明 |
|------|--------|------|
| 临时变量 | 最高 | 用例级别覆盖 |
| 模块变量 | 中 | `extract` 和 `db_extract` 提取的值 |
| 全局变量 | 最低 | `config/{env}.yaml` 的 `global_variables` |

### 6.2 使用方式

在用例的任何字符串字段中使用 `${变量名}`：

```yaml
url: /api/users/${user_id}                # URL 路径中
headers:
  Authorization: Bearer ${token}          # 请求头中
body:
  parent_id: ${dept_id}                   # 请求体中（保留原始类型）
validate:
  - eq: [${db_status}, "active"]          # 断言中
db_extract:
  - sql: "SELECT * FROM orders WHERE id = ${order_id}"  # SQL 中
```

### 6.3 类型保留

当 `${变量名}` 是字段的**完整值**时，保留变量的原始类型：

```yaml
body:
  user_id: ${id}    # 如果 id=42（整数），发送的是 42 而不是 "42"
  name: "User ${id}" # 嵌入在字符串中时，转为字符串 "User 42"
```

### 6.4 排错

如果变量未找到，日志中会输出警告：`Unresolved variable: ${xxx}`。常见原因：
- 变量名拼写错误
- 提取变量的上游用例失败了
- 跨文件引用（不同 YAML 文件间变量不共享）

---

## 7. 接口依赖与数据传递

### 7.1 基本模式

```yaml
# 步骤1：登录 → 提取 token
- name: 登录
  method: POST
  url: /api/login
  body: {username: admin, password: "123456"}
  extract:
    token: $.data.token
  validate:
    - eq: [$.code, 0]

# 步骤2：用 token 调用其他接口
- name: 获取我的信息
  method: GET
  url: /api/me
  headers:
    Authorization: Bearer ${token}
  validate:
    - eq: [$.code, 0]
```

### 7.2 多级依赖

```yaml
- name: 创建部门
  method: POST
  url: /api/departments
  headers: {Authorization: Bearer ${token}}
  body: {name: "测试部门"}
  extract:
    dept_id: $.data.id
  validate:
    - eq: [$.code, 0]

- name: 在该部门下创建用户
  method: POST
  url: /api/users
  headers: {Authorization: Bearer ${token}}
  body:
    name: "张三"
    department_id: ${dept_id}
  extract:
    user_id: $.data.id
  validate:
    - eq: [$.code, 0]

- name: 查询该用户
  method: GET
  url: /api/users/${user_id}
  headers: {Authorization: Bearer ${token}}
  validate:
    - eq: [$.data.name, "张三"]
    - eq: [$.data.department_id, ${dept_id}]
```

### 7.3 JSONPath 常用语法

| 表达式 | 含义 |
|--------|------|
| `$.code` | 根级 code 字段 |
| `$.data.token` | data 下的 token |
| `$.data.list[0].id` | 列表第一个元素的 id |
| `$.data.list[-1].name` | 列表最后一个元素的 name |

---

## 8. 数据库操作

需要在 `config/{env}.yaml` 中配置 `database` 字段。

### 8.1 前置数据准备

```yaml
- name: 测试删除用户
  db_setup:
    - sql: "INSERT INTO users (id, username, status) VALUES (9999, 'test_user', 1)"
    - sql: "INSERT INTO user_roles (user_id, role_id) VALUES (9999, 2)"
  method: DELETE
  url: /api/users/9999
  headers: {Authorization: Bearer ${token}}
  validate:
    - eq: [$.code, 0]
  db_teardown:
    - sql: "DELETE FROM user_roles WHERE user_id = 9999"
    - sql: "DELETE FROM users WHERE id = 9999"
```

### 8.2 数据库校验

```yaml
- name: 创建订单后验证数据库
  method: POST
  url: /api/orders
  body: {product_id: 100, quantity: 1}
  extract:
    order_id: $.data.order_id
  db_extract:
    - sql: "SELECT status, total_price FROM orders WHERE id = ${order_id}"
      extract:
        db_status: status
        db_price: total_price
  validate:
    - eq: [$.code, 0]
    - eq: [${db_status}, "pending"]
    - gt: [${db_price}, 0]
```

### 8.3 参数化 SQL（防注入）

```yaml
db_setup:
  - sql: "INSERT INTO users (id, name) VALUES (%s, %s)"
    params: [9999, "test_user"]
```

### 8.4 db_setup 中生成变量（SQL 生成数据供后续使用）

`db_setup` 中的 SQL 也可以带 `extract`，提取查询结果作为变量。后续 SQL 和接口请求都可以引用这些变量。

典型场景：自动生成手机号，后续 SQL 和接口都用这个手机号。

```yaml
- name: 注册新用户
  db_setup:
    # 第一条 SQL：生成随机手机号并提取
    - sql: "SELECT CONCAT('138', LPAD(FLOOR(RAND()*100000000), 8, '0')) AS phone"
      extract:
        phone: phone

    # 第二条 SQL：用提取的手机号插入数据
    - sql: "INSERT INTO users (phone, name, status) VALUES (%s, %s, 1)"
      params: ["${phone}", "测试用户"]

    # 第三条 SQL：关联表也用同一个手机号
    - sql: "INSERT INTO user_accounts (phone, balance) VALUES (%s, 0)"
      params: ["${phone}"]

  method: POST
  url: /api/register
  body:
    phone: ${phone}           # 接口请求也使用 db_setup 生成的变量
    code: "123456"
  validate:
    - eq: [$.code, 0]

  db_teardown:
    - sql: "DELETE FROM user_accounts WHERE phone = %s"
      params: ["${phone}"]
    - sql: "DELETE FROM users WHERE phone = %s"
      params: ["${phone}"]
```

### 8.5 注意事项

- `db_teardown` 即使用例失败也会执行（类似 finally），确保测试数据被清理
- 如果 `db_setup` 中多条 SQL 执行一半失败，已执行的 SQL 会被自动 rollback
- `db_setup` 的 `extract` 提取的变量会写入变量池，后续 SQL 的 `${xxx}` 和接口的 URL/body/headers 都可以引用
- 不需要数据库功能时，把 config 中的 `database` 配置删掉即可

---

## 9. Hook 扩展

当标准功能无法满足需求时（如请求体加密、响应解密、自定义签名），可以使用 Hook。

### 9.1 编写 Hook

在 `hooks/` 目录下创建 `.py` 文件：

```python
# hooks/custom_hooks.py
import hashlib
import json


def add_sign(request_data):
    """请求前：计算签名并添加到 body。

    参数 request_data 格式:
    {
        "method": "POST",
        "url": "https://api.example.com/api/pay",
        "headers": {"Content-Type": "application/json"},
        "body": {"order_id": "123"}
    }

    必须返回修改后的 dict。
    """
    body = request_data.get("body", {})
    sign = hashlib.md5(json.dumps(body, sort_keys=True).encode()).hexdigest()
    body["sign"] = sign
    request_data["body"] = body
    return request_data


def extract_real_data(response):
    """响应后：解密响应体。

    参数 response 格式:
    {
        "status_code": 200,
        "body": {...},
        "headers": {...},
        "elapsed_ms": 128.5,
        "error": None
    }

    必须返回修改后的 dict。
    """
    # 示例：假设 body.data 是加密的，这里解密
    if response.get("body", {}).get("encrypted_data"):
        response["body"]["data"] = decrypt(response["body"]["encrypted_data"])
    return response
```

### 9.2 在用例中使用 Hook

```yaml
- name: 需要签名的支付接口
  method: POST
  url: /api/pay
  body:
    order_id: "12345"
    amount: 99.9
  hook:
    before: add_sign              # 请求前调用
    after: extract_real_data      # 响应后调用
  validate:
    - eq: [$.code, 0]
```

### 9.3 Hook 注意事项

- Hook 函数必须接收一个 dict 参数并返回修改后的 dict
- 只有在 hooks 文件中**直接定义**的函数才会被注册（import 的第三方函数不会）
- 文件名以 `_` 开头的会被忽略（如 `_helpers.py`）
- Hook 函数如果抛出异常，用例会标记为失败并记录错误信息

---

## 10. 优先级过滤

用例可以标记优先级，运行时按优先级筛选，实现冒烟测试 / 核心回归 / 全量回归。

### 10.1 用例中标记优先级

```yaml
testcases:
  - name: 核心登录流程
    level: P0          # 最高优先级（冒烟）
    method: POST
    url: /api/login
    ...

  - name: 密码错误提示
    level: P1          # 高优先级（核心）
    ...

  - name: 用户名大小写
    level: P2          # 普通（不写 level 默认也是 P2）
    ...

  - name: 特殊字符用户名
    level: P3          # 次要
    ...
```

### 10.2 按优先级运行

```bash
# 只跑 P0 冒烟用例
python3 run.py --level P0

# 跑 P0 + P1 核心回归
python3 run.py --level P0,P1

# 也支持用英文名
python3 run.py --level blocker,critical

# 不指定 --level 则运行全部用例
python3 run.py
```

### 10.3 优先级映射表

| 简写 | 全称 | 含义 | 建议使用场景 |
|------|------|------|-------------|
| P0 | blocker | 阻塞级 | 冒烟测试，每次提交必跑 |
| P1 | critical | 核心功能 | 核心回归，提测前必跑 |
| P2 | normal | 普通（默认） | 全量回归 |
| P3 | minor | 次要 | 全量回归 |
| P4 | trivial | 边缘场景 | 全量回归 |

---

## 11. 并行执行

通过 `--workers` 参数开启多进程并行，加速测试执行。

```bash
# 4 个进程并行
python3 run.py --workers 4

# 自动按 CPU 核数
python3 run.py --workers auto

# 组合使用
python3 run.py --env test --workers 4 --level P0,P1 --report html
```

### 11.1 并行规则

| 规则 | 说明 |
|------|------|
| 同一 YAML 文件内 | 用例**按顺序执行**（保证变量依赖） |
| 不同 YAML 文件间 | **并行执行**（各自独立的变量池和数据库连接） |
| 报告和统计 | 自动聚合所有 worker 的结果 |
| 不指定 --workers | 单进程顺序执行（默认行为不变） |

### 11.2 并行示例

假设有 4 个用例文件，用 `--workers 2`：

```
Worker 0:  login.yaml（内部3个用例顺序执行）→ order.yaml（内部5个用例顺序执行）
Worker 1:  user.yaml（内部4个用例顺序执行） → product.yaml（内部2个用例顺序执行）
```

两个 Worker 同时运行，总耗时约为单线程的一半。

### 11.3 注意事项

- 并行执行要求不同 YAML 文件之间**无数据依赖**（不共享变量、不操作同一条数据库记录）
- 如果两个文件需要共享前置数据（如都需要登录 token），应各自在文件内登录
- 数据库操作要避免不同文件操作同一条记录导致冲突

---

## 12. 重试机制

失败用例自动重试，减少因网络波动或服务短暂不可用导致的误报。

### 12.1 全局配置

```yaml
# config/config.yaml
retry: 2        # 所有用例默认失败后重试 2 次（0=不重试）
```

### 12.2 用例级别覆盖

```yaml
- name: 不稳定的第三方接口
  retry: 3                     # 覆盖全局，重试 3 次
  method: GET
  url: /api/external/status
  validate:
    - eq: [status_code, 200]

- name: 稳定的内部接口
  retry: 0                     # 覆盖全局，不重试
  method: GET
  url: /api/health
  validate:
    - eq: [status_code, 200]
```

### 12.3 重试规则

| 场景 | 行为 |
|------|------|
| 请求异常（超时/连接失败） | 重试 |
| 请求成功但断言失败 | 重试（服务可能还没准备好） |
| 请求成功且断言通过 | 不重试 |
| 重试次数用尽 | 返回最后一次的失败结果 |
| 重试间隔 | 递增退避：2s → 4s → 6s → ... 最大 10s |
| db_setup / hook 失败 | 不重试（前置条件错误，重试无意义） |

---

## 13. 运行与命令行参数

### 基本语法

```bash
python3 run.py [--env ENV] [--path PATH] [--report REPORT] [--level LEVEL] [--workers N]
```

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--env` | config.yaml 中的 `current_env` | 选择环境 |
| `--path` | `testcases` | 用例路径（目录或文件） |
| `--report` | config.yaml 中的 `report_type` | 报告类型：allure / html / both |
| `--level` | 无（运行全部） | 优先级过滤：P0 / P0,P1 / blocker,critical |
| `--workers` | 无（单进程） | 并行进程数：数字或 auto |

### 常用场景

```bash
# 日常开发：只跑一个模块
python3 run.py --path testcases/login/ --report html

# 冒烟测试
python3 run.py --level P0 --report html

# 提测前：核心回归 + 并行加速
python3 run.py --level P0,P1 --workers 4 --report both

# 全量回归
python3 run.py --workers auto --report both

# 切环境
python3 run.py --env staging

# CI 中使用
python3 run.py --env test --workers auto --report allure
```

---

## 14. 测试报告

### HTML 报告

```bash
python3 run.py --report html
# 报告在 reports/report.html
```

简单轻量，用浏览器直接打开即可查看。

### Allure 报告

```bash
# 1. 运行测试（生成数据）
python3 run.py --report allure

# 2. 启动 Allure 服务查看（需要先安装 Allure CLI）
allure serve reports/allure-results

# 安装 Allure CLI:
# macOS:    brew install allure
# Linux:    sudo apt install allure 或从 GitHub 下载
# Windows:  scoop install allure
```

Allure 报告支持：
- 按模块/用例分组展示
- 用例优先级标记（level 字段）
- 请求/响应详情
- 趋势图（多次运行对比）

---

## 15. 日志系统

每次运行自动在 `logs/` 目录生成日期命名的日志文件：

```
logs/2026-04-11.log
```

日志内容示例：

```
2026-04-11 10:30:15 [INFO] ========== 用户登录 > 登录成功 ==========
2026-04-11 10:30:15 [INFO] → POST https://api.example.com/api/login
2026-04-11 10:30:15 [INFO] → Headers: {"Content-Type": "application/json"}
2026-04-11 10:30:15 [INFO] → Body: {"username": "admin", "password": "***"}
2026-04-11 10:30:15 [INFO] ← Status: 200 | Time: 128ms
2026-04-11 10:30:15 [INFO] ← Response: {"code": 0, "data": {"token": "eyJ..."}}
2026-04-11 10:30:15 [INFO] Extract: token = eyJ...
2026-04-11 10:30:15 [INFO] Validate: eq PASS
```

日志同时输出到控制台和文件，文件保留最近 7 天。

---

## 16. 邮件通知

### 配置

编辑 `config/config.yaml`：

```yaml
email:
  enabled: true                     # 开启
  smtp_host: smtp.qq.com            # SMTP 服务器
  smtp_port: 465                    # SSL 端口
  sender: your_email@qq.com         # 发件人
  password: your_smtp_auth_code     # SMTP 授权码（不是登录密码！）
  receivers:                        # 收件人
    - test_lead@company.com
    - dev@company.com
  send_on: fail                     # always=每次 / fail=仅失败 / never=不发
```

### 获取 SMTP 授权码

- **QQ 邮箱**：设置 → 帐户 → POP3/IMAP/SMTP 服务 → 开启 → 生成授权码
- **163 邮箱**：设置 → POP3/SMTP/IMAP → 开启 → 设置授权码
- **企业邮箱**：咨询公司 IT 部门获取 SMTP 配置

### 邮件内容

```
主题：[autotest] 测试报告 - test环境 - 2026-04-11 10:30

测试环境：test
执行时间：2026-04-11 10:30
────────────────────────────
总用例：58
通过：55
失败：2
跳过：1
通过率：94.8%
耗时：32s

失败用例：
  1. 用户管理 > 删除用户 - eq: $.code actual=500 expect=0
  2. 订单模块 > 创建订单 - Request error: Timeout
```

HTML 报告会作为附件一并发送。

---

## 17. 飞书通知

支持将测试结果发送到飞书群聊（通过自定义机器人 Webhook）。

### 16.1 创建飞书机器人

1. 打开飞书群 → 设置 → 群机器人 → 添加机器人 → 自定义机器人
2. 复制 Webhook 地址（格式：`https://open.feishu.cn/open-apis/bot/v2/hook/xxx`）

### 16.2 配置

编辑 `config/config.yaml`：

```yaml
feishu:
  enabled: true
  webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/你的token"
  send_on: fail           # always=每次 / fail=仅失败时 / never=不发送
  at_user_ids:            # 失败时 @ 指定用户（可选）
    - "ou_xxxx"           # 飞书用户的 open_id
    - "ou_yyyy"
```

### 16.3 通知效果

**有失败时（红色卡片）：**

```
┌─────────────────────────────────────────────┐
│  接口自动化测试报告 - test环境 - 有失败       │
├─────────────────────────────────────────────┤
│ 测试环境：test        执行时间：2026-04-17    │
│ 总用例：58            通过率：94.8%           │
│ 通过：55 | 失败：2 | 跳过：1    耗时：32s    │
├─────────────────────────────────────────────┤
│ 失败用例：                                   │
│ 1. 用户管理 > 删除用户                        │
│ 2. 订单模块 > 创建订单                        │
│ @张三 @李四                                   │
└─────────────────────────────────────────────┘
```

**全部通过时（绿色卡片）：** 只显示统计信息，不 @ 人。

### 16.4 与邮件同时使用

邮件和飞书可以同时启用，互不影响：

```yaml
email:
  enabled: true
  ...
feishu:
  enabled: true
  ...
```

### 16.5 获取用户 open_id

飞书管理后台 → 组织架构 → 点击用户 → 复制 open_id（格式：`ou_xxx`）。
也可以通过飞书开放平台 API 获取。

---

## 18. CI/CD 集成

### Jenkins

项目内置 `Jenkinsfile`，支持参数化构建：

1. 在 Jenkins 中创建 Pipeline 项目
2. Pipeline 选择 "Pipeline script from SCM"
3. 指向项目仓库，脚本路径填 `Jenkinsfile`
4. 构建时可选择：环境、用例路径、报告类型

### GitLab CI

项目内置 `.gitlab-ci.yml`：

1. 将项目推送到 GitLab
2. CI 自动触发（或手动触发）
3. 报告和日志自动归档为 Artifact（保留 7 天）

### 自定义 CI

核心命令：

```bash
pip install -r requirements.txt
python run.py --env $ENV --path testcases/ --report allure
```

退出码：`0` = 全部通过，`1` = 有失败，可直接用于 CI 判断。

---

## 19. 与被测系统集成

### 15.1 你需要知道的信息

在开始编写用例之前，你需要从开发人员或接口文档中获取以下信息：

| 信息 | 说明 | 填到哪里 |
|------|------|----------|
| 接口基础地址 | 如 `https://api.example.com` | `config/{env}.yaml` 的 `base_url` |
| 接口路径 | 如 `/api/v1/login` | 用例的 `url` 字段 |
| 请求方法 | GET / POST / PUT / DELETE | 用例的 `method` 字段 |
| 请求头 | 如 Content-Type、Authorization | 用例的 `headers` 或全局 `global_headers` |
| 请求体格式 | JSON body | 用例的 `body` 字段 |
| 响应体格式 | 如 `{"code": 0, "data": {...}}` | 用于编写 `validate` 和 `extract` |
| 鉴权方式 | Token / Cookie / API Key | 用例中提取并传递 |
| 测试账号 | 用户名、密码 | `config/{env}.yaml` 的 `global_variables` |
| 数据库信息 | 地址、账号（可选） | `config/{env}.yaml` 的 `database` |

### 15.2 典型集成步骤

```
1. 获取接口文档（Swagger/Postman/内部文档）
     ↓
2. 在 config/{env}.yaml 中配置 base_url 和账号
     ↓
3. 用 Postman 手动调一遍接口，确认请求和响应格式
     ↓
4. 按模块创建 testcases/{module}/{module}.yaml
     ↓
5. 编写用例（参照 Postman 中的请求，把参数和断言写进 YAML）
     ↓
6. 运行测试，查看日志修正 JSONPath / 断言
     ↓
7. 集成到 CI/CD
```

### 15.3 不同鉴权方式的处理

**Bearer Token（最常见）：**

```yaml
# 先登录提取 token
- name: 登录
  method: POST
  url: /api/login
  body: {username: ${admin_user}, password: ${admin_pass}}
  extract:
    token: $.data.token

# 后续接口带上 token
- name: 业务接口
  headers:
    Authorization: Bearer ${token}
```

**Cookie 鉴权：**

框架目前不自动管理 Cookie。可以通过 extract 提取 Set-Cookie，再手动设置到 headers 中。

**API Key：**

```yaml
# 在 config 的 global_variables 中配置
global_variables:
  api_key: your_api_key_here

# 用例中引用
- name: 调用接口
  headers:
    X-API-Key: ${api_key}
```

### 15.4 处理不同的响应格式

**标准 JSON 响应 `{"code": 0, "data": {...}}`：**

```yaml
validate:
  - eq: [$.code, 0]
  - not_null: [$.data.id]
```

**分页列表 `{"code": 0, "data": {"list": [...], "total": 100}}`：**

```yaml
validate:
  - eq: [$.code, 0]
  - gt: [$.data.total, 0]
  - not_null: [$.data.list[0].id]
```

**嵌套结构 `{"result": {"status": "ok", "payload": {"user": {"name": "test"}}}}`：**

```yaml
validate:
  - eq: [$.result.status, "ok"]
  - eq: [$.result.payload.user.name, "test"]
```

---

## 20. 常见问题

### Q: 如何跳过某些用例？

暂不支持用例级别的 skip。可以通过 `--path` 指定只运行部分目录/文件来实现。

### Q: 能否上传文件？

当前版本仅支持 JSON body。文件上传（multipart/form-data）需要通过 Hook 扩展实现。

### Q: 如何处理需要等待的异步接口？

目前不支持内置等待/轮询。可以通过 Hook 实现：

```python
# hooks/custom_hooks.py
import time

def wait_for_result(response):
    """轮询等待异步任务完成"""
    import requests
    task_id = response["body"]["data"]["task_id"]
    for _ in range(10):
        time.sleep(1)
        resp = requests.get(f"https://api.example.com/tasks/{task_id}")
        if resp.json()["data"]["status"] == "done":
            response["body"]["data"]["status"] = "done"
            return response
    return response
```

### Q: 支持 HTTPS 证书验证吗？

当前使用 requests 库的默认行为（验证 SSL 证书）。如果被测系统使用自签名证书，可以通过 Hook 关闭验证（不推荐在生产环境使用）。

### Q: 如何在团队中共享用例？

将整个项目提交到 Git 仓库。团队成员拉取后只需修改 `config/{env}.yaml` 中的环境配置即可运行。建议把包含真实密码的配置文件加入 `.gitignore`，通过环境变量或内部文档分发。

### Q: 用例执行顺序是怎样的？

- 同一文件内：按 YAML 中的顺序从上到下
- 不同文件间：按文件路径字母序（pytest 默认行为）
- 可以通过 `--path` 参数控制只运行特定目录或文件
