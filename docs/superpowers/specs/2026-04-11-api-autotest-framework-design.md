# API 接口自动化测试框架设计文档

日期：2026-04-11（最后更新：2026-04-17）

## 概述

基于 Python + pytest 的数据驱动接口自动化测试框架。用户只需编写 YAML/JSON/Excel 数据文件即可完成接口测试，无需编写 Python 代码。支持多环境切换、接口间数据依赖（接口调用传递 + 数据库直接插入与提取）、优先级过滤、多进程并行执行、多种报告格式、邮件 + 飞书通知和 CI/CD 集成。

## 技术选型

- Python 3.10+
- pytest：测试执行引擎
- pytest-xdist：多进程并行执行
- requests：HTTP 请求
- PyYAML：YAML 解析
- openpyxl：Excel 解析
- jsonpath-ng：JSONPath 数据提取
- allure-pytest：Allure 报告
- pytest-html：HTML 报告
- loguru：日志记录
- PyMySQL：MySQL 数据库操作
- responses：HTTP 模拟（测试用）

## 项目结构

```
autotest/
├── config/                     # 环境配置
│   ├── config.yaml             # 主配置（环境、超时、邮件、飞书）
│   ├── dev.yaml                # dev 环境
│   ├── test.yaml               # test 环境
│   ├── staging.yaml            # staging 环境
│   └── prod.yaml               # prod 环境
├── testcases/                  # 测试用例（数据文件）
│   ├── login/
│   │   └── login.yaml
│   └── user/
│       └── user_crud.yaml
├── hooks/                      # 自定义 hook 函数
│   └── custom_hooks.py
├── common/                     # 框架核心代码
│   ├── request_handler.py      # 请求发送（封装 requests）
│   ├── data_loader.py          # 数据加载（YAML/JSON/Excel）
│   ├── extractor.py            # 响应数据提取（JSONPath）
│   ├── validator.py            # 断言校验（10个关键字）
│   ├── variable_pool.py        # 变量池（三层优先级 + 类型保留）
│   ├── db_handler.py           # 数据库操作（参数化查询 + rollback）
│   ├── hook_manager.py         # hook 管理（__module__ 安全过滤）
│   ├── config_loader.py        # 配置加载（深合并）
│   ├── runner.py               # 核心执行引擎
│   ├── logger.py               # 日志模块
│   └── notifier.py             # 邮件 + 飞书通知
├── tests/                      # 框架测试
│   ├── test_*.py               # 单元测试（95个）
│   ├── integration/            # 集成测试（17个）
│   └── test_level_filter.py    # 优先级过滤测试（5个）
├── reports/                    # 测试报告输出目录
├── logs/                       # 日志输出目录
├── conftest.py                 # pytest 入口（收集、执行、统计、优先级过滤）
├── pytest.ini                  # pytest 配置
├── requirements.txt            # 依赖
├── Jenkinsfile                 # Jenkins 流水线
├── .gitlab-ci.yml              # GitLab CI 配置
└── run.py                      # 命令行入口（--env, --path, --report, --level, --workers）
```

## 用例数据格式

### YAML 格式（主推）

```yaml
module: 用户登录
testcases:
  - name: 登录成功
    description: 使用正确账号密码登录
    level: P0                    # 优先级：P0/P1/P2/P3/P4
    method: POST
    url: /api/login
    headers:
      Content-Type: application/json
    body:
      username: admin
      password: "123456"
    extract:
      token: $.data.token
      user_id: $.data.user_id
    validate:
      - eq: [status_code, 200]
      - eq: [$.code, 0]
      - not_null: [$.data.token]

  - name: 密码错误
    description: 密码输入错误
    level: P1
    method: POST
    url: /api/login
    body:
      username: admin
      password: wrong
    validate:
      - eq: [$.code, 1001]
      - contains: [$.msg, "密码错误"]
```

### JSON 格式

与 YAML 结构完全一致，仅文件格式不同。

### Excel 格式

列定义：name | method | url | headers | body | extract | validate | level

headers/body/extract/validate 列中使用 JSON 字符串。空列头自动跳过。

### 接口间依赖（变量引用）

通过 `extract` 提取响应数据存入变量池，通过 `${变量名}` 在后续用例中引用：

```yaml
- name: 登录获取token
  method: POST
  url: /api/login
  body: {username: admin, password: "123456"}
  extract:
    token: $.data.token

- name: 查询用户列表
  method: GET
  url: /api/users
  headers:
    Authorization: Bearer ${token}
  validate:
    - eq: [status_code, 200]
```

### 数据库数据准备

通过 `db_setup` 在用例执行前向数据库插入/更新数据，通过 `db_teardown` 在用例执行后清理数据，通过 `db_extract` 从数据库查询结果提取变量。三者可独立使用，也可组合使用。

支持参数化 SQL 防注入（`params` 字段）和 `db_setup` 内 SQL 生成变量（`extract` 字段）。

```yaml
- name: 测试删除用户
  description: 先通过数据库插入一个测试用户，再调接口删除
  db_setup:
    - sql: "INSERT INTO users (id, username, status) VALUES (%s, %s, 1)"
      params: [9999, "test_user"]
    - sql: "INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)"
      params: [9999, 2]
  method: DELETE
  url: /api/users/9999
  headers:
    Authorization: Bearer ${token}
  validate:
    - eq: [status_code, 200]
    - eq: [$.code, 0]
  db_teardown:
    - sql: "DELETE FROM user_roles WHERE user_id = %s"
      params: [9999]
    - sql: "DELETE FROM users WHERE id = %s"
      params: [9999]
```

### db_setup 内生成变量

`db_setup` 中的 SQL 可以带 `extract` 提取查询结果作为变量，供后续 SQL 和接口请求使用：

```yaml
- name: 注册新用户
  db_setup:
    - sql: "SELECT CONCAT('138', LPAD(FLOOR(RAND()*100000000), 8, '0')) AS phone"
      extract:
        phone: phone
    - sql: "INSERT INTO users (phone, name, status) VALUES (%s, %s, 1)"
      params: ["${phone}", "测试用户"]
  method: POST
  url: /api/register
  body:
    phone: ${phone}
    code: "123456"
  validate:
    - eq: [$.code, 0]
  db_teardown:
    - sql: "DELETE FROM users WHERE phone = %s"
      params: ["${phone}"]
```

### 数据库校验（db_extract）

```yaml
- name: 验证订单状态
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

**三种数据依赖方式对比：**

| | 接口依赖（extract） | db_setup extract | db_extract |
|---|---|---|---|
| 时机 | 请求后 | 请求前 | 请求后 |
| 适用场景 | 上游接口返回数据 | SQL 生成测试数据 | 校验数据库状态 |
| 示例 | 登录拿 token | 生成随机手机号 | 校验订单状态 |
| 用法 | `extract` + `${var}` | `db_setup.extract` + `${var}` | `db_extract` + `${var}` |
| 变量池 | 统一管理 | 统一管理 | 统一管理 |

### 用例优先级标记

```yaml
- name: 核心支付接口
  level: P0          # P0=blocker / P1=critical / P2=normal / P3=minor / P4=trivial
```

不写 level 默认为 P2 (normal)。

## 优先级过滤

通过 `--level` 参数按优先级筛选用例执行：

```bash
python run.py --level P0              # 冒烟测试
python run.py --level P0,P1           # 核心回归
python run.py --level blocker,critical # 等价写法
```

| 简写 | 全称 | 含义 |
|------|------|------|
| P0 | blocker | 阻塞级，冒烟必跑 |
| P1 | critical | 核心功能 |
| P2 | normal | 普通（默认） |
| P3 | minor | 次要 |
| P4 | trivial | 边缘场景 |

## 并行执行

通过 `--workers` 参数开启多进程并行（基于 pytest-xdist）：

```bash
python run.py --workers 4             # 4 个进程
python run.py --workers auto          # 按 CPU 核数
```

并行规则：
- **同一 YAML 文件内**：用例按顺序执行（保证变量依赖，`--dist loadfile` 模式）
- **不同 YAML 文件间**：并行执行（各自独立的变量池和数据库连接）
- 统计结果自动聚合所有 worker

## 断言关键字

| 关键字 | 说明 | 示例 |
|--------|------|------|
| `eq` | 等于 | `eq: [$.code, 0]` |
| `neq` | 不等于 | `neq: [$.code, -1]` |
| `gt` | 大于 | `gt: [$.data.total, 0]` |
| `lt` | 小于 | `lt: [$.data.total, 100]` |
| `gte` | 大于等于 | `gte: [status_code, 200]` |
| `lte` | 小于等于 | `lte: [status_code, 299]` |
| `contains` | 包含 | `contains: [$.msg, "成功"]` |
| `not_null` | 不为空 | `not_null: [$.data.token]` |
| `type` | 类型校验 | `type: [$.data.id, int]` |
| `length` | 长度校验 | `length: [$.data.list, 10]` |

类型安全：`gt/lt/gte/lte` 在值为 None 时返回 FAIL（不崩溃）。`length` 在非可迭代类型时返回 FAIL。

## Hook 扩展机制

用例中通过 `hook.before` 和 `hook.after` 指定自定义函数名，框架自动从 `hooks/` 目录加载并调用。

安全机制：只注册 hook 文件中**直接定义**的函数（通过 `__module__` 过滤），import 的第三方函数不会被注册。加载异常不会崩溃框架。

```yaml
- name: 需要加密的接口
  method: POST
  url: /api/pay
  body: {order_id: "12345"}
  hook:
    before: encrypt_body
    after: decrypt_response
```

```python
# hooks/custom_hooks.py
def encrypt_body(request_data):
    """请求前处理，接收并返回 dict: {method, url, headers, body}"""
    request_data["body"]["sign"] = md5(request_data["body"])
    return request_data

def decrypt_response(response):
    """响应后处理，接收并返回 dict: {status_code, body, headers, elapsed_ms, error}"""
    response["body"] = decrypt(response["body"])
    return response
```

## 环境配置

### 主配置 config/config.yaml

```yaml
current_env: test
timeout: 30
retry: 0                       # 失败重试次数（0=不重试，用例级 retry 可覆盖）
report_type: html              # allure / html / both

email:
  enabled: false
  smtp_host: smtp.qq.com
  smtp_port: 465
  sender: test@qq.com
  password: ""
  receivers: []
  send_on: fail                # always / fail / never

feishu:
  enabled: false
  webhook_url: ""              # 飞书自定义机器人 Webhook
  send_on: fail                # always / fail / never
  at_user_ids: []              # 失败时 @ 的用户 open_id
```

### 环境配置 config/{env}.yaml

```yaml
base_url: https://test-api.example.com
global_headers:
  Content-Type: application/json
  X-App-Version: "1.0"
global_variables:
  admin_user: admin
  admin_pass: "123456"

database:
  host: 127.0.0.1
  port: 3306
  user: root
  password: "123456"
  database: test_db
  charset: utf8mb4
```

环境配置通过**深合并**覆盖主配置（嵌套字段不会丢失）。

## 变量池机制

三层优先级，从高到低：

1. **临时变量** - 用例级别覆盖
2. **模块变量** - 同一 YAML 文件内 extract / db_setup extract / db_extract 提取的
3. **全局变量** - config 中定义的 global_variables

遇到 `${xxx}` 时按优先级从高到低查找，找到即替换。

**类型保留：** 当 `${var}` 是字段的完整值时，保留原始类型（int、bool 等）。嵌入在字符串中时（如 `"Bearer ${token}"`）转为字符串。

**变量隔离：** 不同 YAML 文件之间的模块变量互相隔离（切换文件时自动清理）。全局变量始终可用。

**排错：** 未解析的 `${xxx}` 会在日志中输出 warning，便于发现拼写错误。

## 执行流程

```
run.py 启动
    ↓
解析命令行参数（--env, --path, --report, --level, --workers）
    ↓
加载 config.yaml → 深合并环境配置
    ↓
pytest 启动（可选多进程 xdist loadfile 模式）
    ↓
conftest.py 收集 testcases/ 下的 YAML/JSON/Excel 文件
    ↓
按 --level 过滤用例（如有）
    ↓
按文件 → 按用例顺序执行（文件切换时清理模块变量）：
    1. 替换变量 ${xxx}
    2. 执行 db_setup 数据库前置操作（支持 extract 提取变量）
    3. 用 db_setup 提取的变量重新解析请求参数
    4. 合并 global_headers + 用例 headers
    5. 执行 before hook（如有）
    6. 发送 HTTP 请求
    7. 执行 after hook（如有）
    8. extract 提取接口响应变量存入变量池
    9. 执行 db_extract 数据库查询提取变量（如有）
    10. validate 断言校验（支持接口变量和数据库变量）
    11. 执行 db_teardown 数据库清理（如有，始终执行 — finally 语义）
    12. 记录日志
    ↓
全部执行完毕 → 聚合统计结果 → 生成报告 → 发送通知（邮件 + 飞书）
```

重试机制：
- 请求异常或断言失败时，根据 `retry` 配置自动重试（全局配置 + 用例级覆盖）
- 重试间隔递增退避：2s → 4s → 6s → ... 最大 10s
- db_setup / hook 失败不触发重试（前置条件错误，重试无意义）
- 用例级 `retry` 字段优先级高于全局 `retry` 配置

异常处理：
- `db_setup` 失败：已执行的 SQL 自动 rollback，用例标记失败，teardown 仍执行
- `hook` 异常：用例标记失败，记录错误信息，teardown 仍执行
- 请求超时/连接失败：触发重试机制，全部失败后标记失败
- `db_teardown` 异常：记录错误日志，不影响用例结果

## 日志记录

使用 loguru，每次请求完整记录：

```
2026-04-11 10:30:15 [INFO] ========== 用户登录 > 登录成功 ==========
2026-04-11 10:30:15 [INFO] → POST https://test-api.example.com/api/login
2026-04-11 10:30:15 [INFO] → Headers: {"Content-Type": "application/json"}
2026-04-11 10:30:15 [INFO] → Body: {"username": "admin", "password": "***"}
2026-04-11 10:30:15 [INFO] ← Status: 200 | Time: 128ms
2026-04-11 10:30:15 [INFO] ← Response: {"code": 0, "data": {"token": "eyJ..."}}
2026-04-11 10:30:15 [INFO] Extract: token = eyJ...
2026-04-11 10:30:15 [INFO] Validate: eq PASS
```

日志同时输出到控制台和 `logs/` 目录下的日期文件。

## 通知

### 邮件通知

测试完成后根据 `send_on` 配置决定是否发送邮件。邮件包含：
- 测试环境、执行时间
- 用例统计（总数/通过/失败/跳过/通过率/耗时）
- 失败用例摘要
- HTML 报告作为附件

### 飞书通知

通过飞书自定义机器人 Webhook 发送富文本卡片消息：
- 失败时红色卡片，全部通过绿色卡片
- 显示统计数据和失败用例列表
- 支持 @指定用户（通过 `at_user_ids` 配置）
- 邮件和飞书可同时启用

## 命令行入口

```bash
python run.py                                             # 运行全部用例
python run.py --env dev                                   # 指定环境
python run.py --path testcases/login/                     # 指定用例路径
python run.py --report both                               # 指定报告类型
python run.py --level P0,P1                               # 按优先级过滤
python run.py --workers 4                                 # 4 进程并行
python run.py --workers auto                              # 按 CPU 核数并行
python run.py --env test --level P0 --workers 4 --report html  # 组合
```

## CI/CD 集成

### Jenkins

通过 Jenkinsfile 配置，支持参数化构建（选择环境、用例路径），自动归档报告和日志。

### GitLab CI

通过 .gitlab-ci.yml 配置，自动安装依赖、执行测试、归档产物（7天过期）。

## 测试覆盖

- 单元测试：95 个，覆盖所有 11 个核心模块，覆盖率 91%
- 集成测试：17 个，覆盖端到端流水线、变量传递、变量隔离、hook 集成、全局头、失败处理、conftest 管道、CLI
- 优先级过滤测试：5 个，验证 --level 参数的收集过滤逻辑
- 总计：117 个测试
- 经过 4 轮交叉 Code Review，累计修复 34 个问题

## 安全设计

- **SQL 注入防护**：所有 SQL 执行支持参数化查询（`params` 字段）
- **Hook 安全**：只注册 hook 文件中直接定义的函数（`__module__` 过滤），不注册 import 的第三方函数
- **事务安全**：`db_setup` / `db_teardown` 失败时自动 rollback，防止脏数据
- **连接安全**：数据库自动重连（`ping(reconnect=True)`），close 后防止 double-close
- **配置安全**：`yaml.safe_load` 防止 YAML 反序列化攻击
- **SMTP 安全**：发送异常捕获，不影响测试主流程

## 依赖清单

```
requests>=2.28.0
pytest>=7.0.0
pytest-xdist>=3.0.0
pyyaml>=6.0
jsonpath-ng>=1.5.0
openpyxl>=3.0.0
allure-pytest>=2.12.0
pytest-html>=3.2.0
loguru>=0.7.0
pymysql>=1.1.0
responses>=0.23.0
```
