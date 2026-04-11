# API 接口自动化测试框架设计文档

日期：2026-04-11

## 概述

基于 Python + pytest 的数据驱动接口自动化测试框架。用户只需编写 YAML/JSON/Excel 数据文件即可完成接口测试，无需编写 Python 代码。支持多环境切换、接口间数据依赖（接口调用传递 + 数据库直接插入）、多种报告格式、邮件通知和 CI/CD 集成。

## 技术选型

- Python 3.10+
- pytest：测试执行引擎
- requests：HTTP 请求
- PyYAML：YAML 解析
- openpyxl：Excel 解析
- jsonpath-ng：JSONPath 数据提取
- allure-pytest：Allure 报告
- pytest-html：HTML 报告
- loguru：日志记录
- PyMySQL：MySQL 数据库操作
- psycopg2-binary：PostgreSQL 数据库操作（可选）

## 项目结构

```
autotest/
├── config/                     # 环境配置
│   ├── config.yaml             # 主配置（当前环境、公共参数）
│   ├── dev.yaml                # dev 环境
│   ├── test.yaml               # test 环境
│   ├── staging.yaml            # staging 环境
│   └── prod.yaml               # prod 环境
├── testcases/                  # 测试用例（数据文件）
│   ├── login/
│   │   ├── login.yaml
│   │   ├── login.json
│   │   └── login.xlsx
│   └── user/
│       └── user_crud.yaml
├── hooks/                      # 自定义 hook 函数
│   └── custom_hooks.py
├── common/                     # 框架核心代码
│   ├── request_handler.py      # 请求发送（封装 requests）
│   ├── data_loader.py          # 数据加载（YAML/JSON/Excel）
│   ├── extractor.py            # 响应数据提取（JSONPath）
│   ├── validator.py            # 断言校验
│   ├── variable_pool.py        # 变量池（接口间数据传递）
│   ├── db_handler.py           # 数据库操作（增删改查）
│   ├── hook_manager.py         # hook 管理
│   ├── logger.py               # 日志模块
│   └── notifier.py             # 邮件通知
├── reports/                    # 测试报告输出目录
├── logs/                       # 日志输出目录
├── conftest.py                 # pytest 入口，自动发现并执行用例
├── pytest.ini                  # pytest 配置
├── requirements.txt            # 依赖
├── Jenkinsfile                 # Jenkins 流水线
├── .gitlab-ci.yml              # GitLab CI 配置
└── run.py                      # 命令行入口（一键运行）
```

## 用例数据格式

### YAML 格式（主推）

```yaml
module: 用户登录
testcases:
  - name: 登录成功
    description: 使用正确账号密码登录
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

列定义：name | method | url | headers | body | extract | validate

headers/body/extract/validate 列中使用 JSON 字符串。

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

```yaml
- name: 测试删除用户
  description: 先通过数据库插入一个测试用户，再调接口删除
  db_setup:                          # 用例执行前：数据库操作
    - sql: "INSERT INTO users (id, username, status) VALUES (9999, 'test_user', 1)"
    - sql: "INSERT INTO user_roles (user_id, role_id) VALUES (9999, 2)"
  method: DELETE
  url: /api/users/9999
  headers:
    Authorization: Bearer ${token}
  validate:
    - eq: [status_code, 200]
    - eq: [$.code, 0]
  db_teardown:                       # 用例执行后：清理数据
    - sql: "DELETE FROM user_roles WHERE user_id = 9999"
    - sql: "DELETE FROM users WHERE id = 9999"

- name: 验证订单状态
  description: 调接口创建订单后，查数据库验证状态
  method: POST
  url: /api/orders
  body:
    product_id: 100
    quantity: 1
  extract:
    order_id: $.data.order_id
  db_extract:                        # 从数据库查询提取变量
    - sql: "SELECT status, total_price FROM orders WHERE id = ${order_id}"
      extract:
        db_status: status
        db_price: total_price
  validate:
    - eq: [$.code, 0]
    - eq: [${db_status}, "pending"]  # 断言数据库中的值
    - gt: [${db_price}, 0]
```

**两种数据依赖方式对比：**

| | 接口依赖（extract） | 数据库依赖（db_setup/db_extract） |
|---|---|---|
| 适用场景 | 上游接口返回数据作为下游入参 | 需要预置/校验数据库数据 |
| 示例 | 登录拿 token → 后续接口带 token | 插入测试用户 → 测试删除接口 |
| 用法 | `extract` + `${var}` | `db_setup` / `db_extract` + `${var}` |
| 可混合使用 | 是，变量池统一管理 | 是，变量池统一管理 |

### 用例优先级标记

```yaml
- name: 核心支付接口
  level: critical    # blocker / critical / normal / minor / trivial
```

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

## Hook 扩展机制

用例中通过 `hook.before` 和 `hook.after` 指定自定义函数名，框架自动从 `hooks/` 目录加载并调用。

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
    """请求前处理，接收 request_data dict，返回处理后的 dict"""
    request_data["body"]["sign"] = md5(request_data["body"])
    return request_data

def decrypt_response(response):
    """响应后处理，接收 response dict，返回处理后的 dict"""
    response["body"] = decrypt(response["body"])
    return response
```

## 环境配置

### 主配置 config/config.yaml

```yaml
current_env: test
timeout: 30
retry: 0
report_type: allure          # allure / html / both

email:
  enabled: true
  smtp_host: smtp.qq.com
  smtp_port: 465
  sender: test@qq.com
  password: xxxxxx
  receivers:
    - dev1@company.com
    - dev2@company.com
  send_on: fail              # always / fail / never
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

## 变量池机制

三层优先级，从高到低：

1. **临时变量** - 用例级别覆盖
2. **模块变量** - 同一 YAML 文件内 extract 提取的
3. **全局变量** - config 中定义的 global_variables

遇到 `${xxx}` 时按优先级从高到低查找，找到即替换。

## 执行流程

```
run.py / pytest 启动
    ↓
加载 config.yaml → 确定环境 → 加载对应环境配置
    ↓
扫描 testcases/ 目录 → data_loader 解析所有用例文件
    ↓
按文件 → 按用例顺序执行：
    1. 替换变量 ${xxx}
    2. 执行 db_setup 数据库前置操作（如有）
    3. 执行 before hook（如有）
    4. 发送 HTTP 请求
    5. 执行 after hook（如有）
    6. extract 提取接口响应变量存入变量池
    7. 执行 db_extract 数据库查询提取变量（如有）
    8. validate 断言校验（支持接口变量和数据库变量）
    9. 执行 db_teardown 数据库清理（如有）
    10. 记录日志
    ↓
全部执行完毕 → 生成报告 → 发送邮件通知（如配置）
```

## 日志记录

使用 loguru，每次请求完整记录：

```
2026-04-11 10:30:15 [INFO] ========== 用户登录 > 登录成功 ==========
2026-04-11 10:30:15 [INFO] → POST https://test-api.example.com/api/login
2026-04-11 10:30:15 [INFO] → Headers: {"Content-Type": "application/json"}
2026-04-11 10:30:15 [INFO] → Body: {"username": "admin", "password": "***"}
2026-04-11 10:30:15 [INFO] ← Status: 200 | Time: 128ms
2026-04-11 10:30:15 [INFO] ← Response: {"code": 0, "data": {"token": "eyJ..."}}
2026-04-11 10:30:15 [INFO] ✓ Extract: token = eyJ...
2026-04-11 10:30:15 [INFO] ✓ Validate: $.code == 0 PASS
```

日志同时输出到控制台和 `logs/` 目录下的日期文件。

## 邮件通知

测试完成后根据 `send_on` 配置决定是否发送邮件。邮件包含：

- 测试环境、执行时间
- 用例统计（总数/通过/失败/跳过/通过率/耗时）
- 失败用例摘要
- HTML 报告作为附件

## 命令行入口

```bash
python run.py                                          # 运行全部用例
python run.py --env dev                                # 指定环境
python run.py --path testcases/login/                  # 指定用例路径
python run.py --report both                            # 指定报告类型
python run.py --env staging --path testcases/user/ --report allure  # 组合
```

## CI/CD 集成

### Jenkins

通过 Jenkinsfile 配置，支持参数化构建（选择环境、用例路径），自动归档报告和日志。

### GitLab CI

通过 .gitlab-ci.yml 配置，自动安装依赖、执行测试、归档产物（7天过期）。

## 依赖清单

```
requests>=2.28.0
pytest>=7.0.0
pyyaml>=6.0
jsonpath-ng>=1.5.0
openpyxl>=3.0.0
allure-pytest>=2.12.0
pytest-html>=3.2.0
loguru>=0.7.0
pymysql>=1.1.0
```
