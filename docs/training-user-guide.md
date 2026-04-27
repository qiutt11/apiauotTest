# API 接口自动化测试框架 — 完整使用手册

> 培训用文档 | 版本：v2.0 | 更新日期：2026-04-24

---

## 目录

- [一、框架简介](#一框架简介)
- [二、环境搭建](#二环境搭建)
- [三、配置管理](#三配置管理)
- [四、编写普通用例](#四编写普通用例)
- [五、用例数据格式](#五用例数据格式)
- [六、断言关键字](#六断言关键字)
- [七、变量系统](#七变量系统)
- [八、接口依赖与数据传递](#八接口依赖与数据传递)
- [九、数据库操作](#九数据库操作)
- [十、Hook 扩展](#十hook-扩展)
- [十一、Excel 驱动用例](#十一excel-驱动用例)
- [十二、跨系统场景（base_url 覆盖）](#十二跨系统场景base_url-覆盖)
- [十三、优先级过滤](#十三优先级过滤)
- [十四、并行执行](#十四并行执行)
- [十五、重试机制](#十五重试机制)
- [十六、运行与命令行参数](#十六运行与命令行参数)
- [十七、测试报告](#十七测试报告)
- [十八、日志系统](#十八日志系统)
- [十九、通知（邮件 + 飞书）](#十九通知邮件--飞书)
- [二十、CI/CD 集成](#二十cicd-集成)
- [附录A：JSONPath 速查](#附录ajsonpath-速查)
- [附录B：常见问题 FAQ](#附录b常见问题-faq)

---

## 一、框架简介

### 1. 定位

基于 Python + pytest 的**数据驱动**接口自动化测试框架。**只需编写 YAML/JSON/Excel 数据文件即可完成接口测试，无需编写 Python 代码。**

### 2. 核心特性

| 特性 | 说明 |
|------|------|
| 数据驱动 | 用例写在 YAML/JSON/Excel 中，新增用例零代码 |
| Excel 驱动 | 支持「保存→详情」批量验证模式，Excel 管理字段数据 |
| 多环境切换 | dev / test / staging / prod 一键切换，支持跨系统 base_url |
| 接口依赖 | 通过 `extract` + `${变量名}` 实现接口间数据传递 |
| 数据库支持 | `db_setup`（含变量提取）/ `db_extract` / `db_teardown` |
| 优先级过滤 | P0~P4 分级，按需运行冒烟/核心/全量 |
| 并行执行 | `--workers` 多进程，同文件顺序、跨文件并行 |
| 失败重试 | 全局/用例级配置，递增退避 |
| Hook 扩展 | 请求前/后自定义处理（加密、签名等） |
| 多种报告 | Allure + pytest-html |
| 多渠道通知 | 邮件（SMTP_SSL + 附件）+ 飞书（卡片 + @人） |
| CI/CD 集成 | Jenkinsfile + GitLab CI |

### 3. 项目结构

```
autotest/
├── config/          # 环境配置（需修改：接口地址、账号、数据库）
│   ├── config.yaml  #   主配置（环境选择、超时、报告、邮件、飞书）
│   ├── test.yaml    #   test 环境
│   ├── dev.yaml     #   dev 环境
│   └── prod.yaml    #   prod 环境
├── testcases/       # 测试用例（需编写）
│   ├── login/
│   │   └── login.yaml
│   └── user/
│       ├── user_crud.yaml
│       ├── user_save_detail.yaml     # YAML 数据驱动用例示例
│       └── data/
│           └── user_datasets.yaml    # 数据驱动测试数据
├── hooks/           # Hook 扩展（按需编写）
├── common/          # 框架核心（无需修改）
├── tests/           # 框架单元测试（154个）
├── reports/         # 报告输出（自动生成）
├── logs/            # 日志输出（自动生成）
├── run.py           # 运行入口
├── conftest.py      # pytest 配置
└── requirements.txt # Python 依赖
```

**日常使用只需关注 3 个目录：`config/`、`testcases/`、`hooks/`**

### 4. 技术栈

| 组件 | 用途 |
|------|------|
| Python 3.10+ | 运行环境 |
| pytest | 测试引擎 |
| requests | HTTP 请求 |
| PyYAML / openpyxl | 数据解析（YAML / Excel） |
| jsonpath-ng | 响应数据提取 |
| allure-pytest / pytest-html | 测试报告 |
| loguru | 日志 |
| PyMySQL | 数据库操作 |
| pytest-xdist | 并行执行 |

---

## 二、环境搭建

### 1. 安装 Python

确保 Python 3.10+：

```bash
python3 --version
# 输出：Python 3.10.x 或更高
```

### 2. 安装依赖

```bash
cd autotest
pip install -r requirements.txt
```

### 3. 验证安装

```bash
python3 run.py --help
```

输出：

```
usage: run.py [-h] [--env ENV] [--path PATH] [--report REPORT]
              [--level LEVEL] [--workers WORKERS]

API Autotest Framework

options:
  --env ENV          Test environment (dev/test/staging/prod)
  --path PATH        Test case path (directory or file)
  --report REPORT    Report type: allure / html / both
  --level LEVEL      Filter by priority: P0,P1 or blocker,critical
  --workers WORKERS  Parallel workers: number or 'auto'
```

### 4. 可选组件

| 组件 | 何时需要 | 安装方式 |
|------|---------|---------|
| Allure CLI | 查看 Allure 报告 | `brew install allure`（macOS） |
| MySQL | 使用数据库功能 | 正常安装 MySQL |
| Java 8+ | Allure CLI 依赖 | `brew install java` |

---

## 三、配置管理

### 1. 主配置 `config/config.yaml`

```yaml
# 当前环境（对应 config/ 下的同名文件）
current_env: test

# HTTP 超时时间（秒）
timeout: 30

# 失败重试次数（0=不重试）
retry: 0

# 默认报告类型
report_type: html

# 邮件通知
email:
  enabled: false
  smtp_host: smtp.qq.com
  smtp_port: 465
  sender: ""
  password: ""
  receivers: []
  send_on: fail          # always / fail / never

# 飞书通知
feishu:
  enabled: false
  webhook_url: ""
  send_on: fail
  at_user_ids: []        # 失败时 @指定用户
```

### 2. 环境配置 `config/{env}.yaml`

```yaml
# 被测系统地址（必填）
base_url: https://api.yourcompany.com

# 全局请求头（自动添加到所有请求）
global_headers:
  Content-Type: application/json

# 全局变量（用例中用 ${变量名} 引用）
global_variables:
  admin_user: admin
  admin_pass: "123456"

# 数据库配置（可选）
database:
  host: 127.0.0.1
  port: 3306
  user: root
  password: "123456"
  database: test_db
  charset: utf8mb4
```

### 3. 多环境管理

```bash
# 方式1：修改 config.yaml 中的 current_env
# 方式2：命令行参数（优先级更高）
python3 run.py --env dev
python3 run.py --env staging
python3 run.py --env prod
```

### 4. 配置合并规则

环境配置**深合并**到主配置：

```yaml
# config.yaml                  # test.yaml
email:                          email:
  enabled: false                  enabled: true
  smtp_host: smtp.qq.com

# 合并结果：email.enabled=true, email.smtp_host=smtp.qq.com（保留）
```

---

## 四、编写普通用例

### 1. 完整字段说明

```yaml
module: 模块名称                    # 报告中的模块分组
testcases:
  - name: 用例名称                  # 必填，报告中显示
    description: 用例描述            # 可选
    level: P0                      # 可选，P0/P1/P2/P3/P4
    base_url: https://other.com    # 可选，覆盖全局 base_url
    method: POST                    # 必填，GET/POST/PUT/DELETE/PATCH
    url: /api/v1/login              # 必填，接口路径（拼接 base_url）
    headers:                        # 可选
      Authorization: Bearer ${token}
    body:                           # 可选，JSON 请求体
      username: admin
    extract:                        # 可选，从响应中提取变量
      token: $.data.token           #   简写（module 作用域）
      # 或完整写法：
      # token:
      #   jsonpath: $.data.token
      #   scope: global             #   global=跨文件可用
    db_setup:                       # 可选，请求前执行 SQL
      - sql: "INSERT INTO ..."
    db_extract:                     # 可选，请求后查询数据库
      - sql: "SELECT ..."
        extract: {db_var: column}
    db_teardown:                    # 可选，请求后清理
      - sql: "DELETE FROM ..."
    hook:                           # 可选
      before: function_name
      after: function_name
    retry: 2                        # 可选，覆盖全局重试
    validate:                       # 必填，至少一个断言
      - eq: [$.code, 0]
```

### 2. 最简用例

```yaml
module: 健康检查
testcases:
  - name: 检查服务是否存活
    method: GET
    url: /api/health
    validate:
      - eq: [status_code, 200]
```

### 3. 用例执行流程

每个用例内部的执行顺序（10 步）：

```
1. 解析变量 ${xxx}
2. 执行 db_setup（如有，支持 extract 提取变量）
3. 用 db_setup 提取的变量重新解析请求参数
4. 执行 before hook（如有）
5. 发送 HTTP 请求
6. 执行 after hook（如有）
7. 从响应中 extract 提取变量
8. 执行 db_extract 数据库查询（如有）
9. 执行 validate 断言校验
10. 执行 db_teardown 清理（如有，即使前面失败也执行）
```

### 4. 变量作用域

- **同一 YAML 文件内**：用例间共享变量（前面 extract 的后面可用）
- **不同 YAML 文件间**：默认隔离（切换文件时自动清理模块变量）
- **全局变量**：config 中定义，或 `extract` 指定 `scope: global`，所有文件都可用

---

## 五、用例数据格式

### 1. YAML 格式（推荐）

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

### 2. JSON 格式

```json
{
  "module": "用户登录",
  "testcases": [{
    "name": "登录成功",
    "method": "POST",
    "url": "/api/login",
    "body": {"username": "${admin_user}", "password": "${admin_pass}"},
    "validate": [{"eq": ["$.code", 0]}]
  }]
}
```

### 3. Excel 格式（直接写用例）

Sheet 名 = 模块名，表头 = 字段名，每行 = 一个用例。

| name | method | url | body | validate |
|------|--------|-----|------|----------|
| 登录成功 | POST | /api/login | {"username":"admin"} | [{"eq":["$.code",0]}] |

> **注意**：headers/body/extract/validate 列需填合法 JSON 字符串。

---

## 六、断言关键字

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
- `status_code` → HTTP 状态码
- `$.xxx` → JSONPath，从响应 body 提取
- `${xxx}` → 引用变量池中的变量

**type 支持的类型：** `int`、`float`、`str`、`list`、`dict`、`bool`

---

## 七、变量系统

### 1. 三层优先级

| 来源 | 优先级 | 说明 |
|------|--------|------|
| 临时变量 | 最高 | 用例级别覆盖（预留） |
| 模块变量 | 中 | `extract`、`db_extract` 提取的值、Excel 行数据 |
| 全局变量 | 最低 | `config/{env}.yaml` 的 `global_variables` |

### 2. 使用方式

在用例的任何字符串字段中使用 `${变量名}`：

```yaml
url: /api/users/${user_id}
headers:
  Authorization: Bearer ${token}
body:
  parent_id: ${dept_id}
```

### 3. 类型保留

```yaml
body:
  user_id: ${id}        # id=42 → 发送 42（int），不是 "42"
  name: "User ${id}"    # 嵌入字符串 → "User 42"（str）
```

### 4. extract scope（跨文件共享变量）

默认 extract 的变量只在当前文件内可用。加 `scope: global` 可跨文件共享（典型场景：登录 token）：

```yaml
# testcases/common/login.yaml
extract:
  token:
    jsonpath: $.data.token
    scope: global              # 存全局，跨文件可用

# testcases/user/user_crud.yaml（无需重复登录）
headers:
  Authorization: Bearer ${token}    # 直接引用
```

| 写法 | 作用域 | 跨文件 |
|------|--------|--------|
| `token: $.data.token` | module（默认） | 否 |
| `token: {jsonpath: $.data.token, scope: global}` | global | 是 |

---

## 八、接口依赖与数据传递

### 1. 基本模式

```yaml
testcases:
  - name: 登录
    method: POST
    url: /api/login
    body: {username: admin, password: "123456"}
    extract:
      token: $.data.token          # 提取 token
    validate:
      - eq: [$.code, 0]

  - name: 获取我的信息
    method: GET
    url: /api/me
    headers:
      Authorization: Bearer ${token}  # 引用 token
    validate:
      - eq: [$.code, 0]
```

### 2. 多级依赖

```yaml
  - name: 创建部门
    extract: {dept_id: $.data.id}

  - name: 在部门下创建用户
    body: {department_id: ${dept_id}}
    extract: {user_id: $.data.id}

  - name: 查询用户
    url: /api/users/${user_id}
    validate:
      - eq: [$.data.department_id, ${dept_id}]
```

---

## 九、数据库操作

> 需在 `config/{env}.yaml` 中配置 `database` 字段。不需要数据库功能则无需配置。

### 1. 前置数据准备（db_setup）

```yaml
- name: 测试删除用户
  db_setup:
    - sql: "INSERT INTO users (id, name) VALUES (9999, 'test')"
  method: DELETE
  url: /api/users/9999
  validate:
    - eq: [$.code, 0]
  db_teardown:
    - sql: "DELETE FROM users WHERE id = 9999"
```

### 2. db_setup 提取变量

```yaml
- name: 注册新用户
  db_setup:
    - sql: "SELECT CONCAT('138', LPAD(FLOOR(RAND()*1e8), 8, '0')) AS phone"
      extract: {phone: phone}
    - sql: "INSERT INTO users (phone) VALUES (%s)"
      params: ["${phone}"]
  method: POST
  url: /api/register
  body: {phone: ${phone}}
```

### 3. 请求后数据库校验（db_extract）

```yaml
  extract: {order_id: $.data.order_id}
  db_extract:
    - sql: "SELECT status FROM orders WHERE id = ${order_id}"
      extract: {db_status: status}
  validate:
    - eq: [${db_status}, "pending"]
```

### 4. 参数化 SQL（防注入）

```yaml
db_setup:
  - sql: "INSERT INTO users (id, name) VALUES (%s, %s)"
    params: [9999, "test_user"]
```

### 5. 注意事项

- `db_teardown` 即使用例失败也会执行（finally 语义）
- `db_setup` 执行失败自动 rollback
- 不配置 `database` 时框架自动跳过所有数据库操作

---

## 十、Hook 扩展

### 1. 编写 Hook

在 `hooks/` 目录下创建 `.py` 文件：

```python
# hooks/custom_hooks.py
import hashlib, json

def add_sign(request_data):
    """请求前：计算签名添加到 body。"""
    body = request_data.get("body", {})
    sign = hashlib.md5(json.dumps(body, sort_keys=True).encode()).hexdigest()
    body["sign"] = sign
    request_data["body"] = body
    return request_data

def decrypt_response(response):
    """响应后：解密响应体。"""
    if response.get("body", {}).get("encrypted"):
        response["body"]["data"] = decrypt(response["body"]["encrypted"])
    return response
```

### 2. 在用例中使用

```yaml
- name: 需要签名的接口
  method: POST
  url: /api/pay
  body: {order_id: "123"}
  hook:
    before: add_sign
    after: decrypt_response
  validate:
    - eq: [$.code, 0]
```

### 3. 安全机制

- 只注册 hook 文件中**直接定义**的函数（import 的第三方函数不会被注册）
- 以 `_` 开头的文件和函数会被忽略
- Hook 异常不会崩溃框架，用例标记为失败并记录错误

---

## 十一、YAML 数据驱动用例（保存+详情对比）

### 1. 适用场景

- 保存接口字段多（20+）、层层嵌套
- 详情接口需要**逐字段比对**，且入参和反参**字段名不同**
- 多组测试数据，不同数据组字段可以不同

### 2. 工作原理

```
数据文件（YAML，支持嵌套）          用例文件（映射定义一次）
┌─────────────────────┐          ┌──────────────────────────┐
│ - label: 张三        │          │ steps:                    │
│   userInfo:          │          │   - body_from_yaml: true  │
│     name: 张三       │    ×     │   - validate_from_yaml:   │
│     age: 25          │          │       userInfo.name:      │
│ - label: 李四        │          │         $.data.userName   │
│   userInfo:          │          └──────────────────────────┘
│     name: 李四       │
└─────────────────────┘
        ↓
  创建用户并验证详情[张三]  → save(body=张三嵌套数据) → detail(按映射断言)
  创建用户并验证详情[李四]  → save(body=李四嵌套数据) → detail(按映射断言)
```

### 3. 数据文件

放在 `testcases/模块/data/` 下，YAML 列表格式：

```yaml
# testcases/user/data/user_datasets.yaml
- label: 张三-完整信息
  userInfo:
    name: 张三
    age: 25
    contacts:
      - type: phone
        value: "138xxx"
  tags: [vip, new]
  status: 1

- label: 李四-只有手机号
  userInfo:
    name: 李四
    age: 30
    contacts:
      - type: phone
        value: "139xxx"
  tags: [normal]
  status: 1
  remark: "VIP转介绍"       # 李四多了 remark，张三没有 → 自动适应
```

### 4. 用例文件

```yaml
- name: 创建用户并验证详情
  yaml_source: data/user_datasets.yaml
  steps:
    - name: 保存
      method: POST
      url: /api/user/save
      headers: {Authorization: Bearer ${token}}
      body_from_yaml: true           # dataset 去掉 label 作为 body
      extract: {id: $.data.id}
      validate: [{eq: [$.code, 0]}]

    - name: 验证详情
      method: GET
      url: /api/user/detail/${id}
      headers: {Authorization: Bearer ${token}}
      validate_from_yaml:            # 路径映射（入参路径 → 反参路径）
        userInfo.name: $.data.basicInfo.userName
        userInfo.age: $.data.basicInfo.userAge
        userInfo.contacts[].type: $.data.contactList[].contactType
        userInfo.contacts[].value: $.data.contactList[].contactValue
        tags[]: $.data.tagNames[]
        status: $.data.userStatus
        remark: $.data.remark
      validate: [{eq: [$.code, 0]}]
```

### 5. 映射语法

| 语法 | 含义 |
|------|------|
| `status` | 顶层字段 |
| `userInfo.name` | 嵌套取值 |
| `tags[]` | 数组每个元素 |
| `contacts[].type` | 数组内每个元素的字段 |

路径不存在时自动跳过（不报错）。

### 6. 注意事项

- 数据文件放在 `data/` 子目录，框架自动跳过不当用例收集
- 普通用例和数据驱动用例可混合在同一 YAML 中
- 任一 step 失败则整体失败，后续 step 不执行
- 支持 `--level` 过滤和 `base_url` 跨系统覆盖

---

## 十二、跨系统场景（base_url 覆盖）

当不同接口在不同系统时，在用例或 step 中用 `base_url` 覆盖全局地址：

### 1. 直接写地址

```yaml
steps:
  - name: A系统保存
    base_url: https://api-a.example.com
    method: POST
    url: /api/save
    ...

  - name: B系统查询
    base_url: https://api-b.example.com
    method: GET
    url: /api/detail/${id}
    ...
```

### 2. 使用变量（推荐）

```yaml
# config/test.yaml
global_variables:
  system_a_url: https://api-a.test.com
  system_b_url: https://api-b.test.com
```

```yaml
# 用例中
- name: A系统保存
  base_url: ${system_a_url}
  ...
```

### 3. 适用范围

`base_url` 对**普通用例和 Excel 驱动 step** 都适用。不写则用全局配置。

---

## 十三、优先级过滤

### 1. 标记优先级

```yaml
testcases:
  - name: 核心登录
    level: P0              # 冒烟
  - name: 密码错误
    level: P1              # 核心
  - name: 大小写测试
    level: P2              # 普通（默认）
```

### 2. 按优先级运行

```bash
python3 run.py --level P0            # 只跑冒烟
python3 run.py --level P0,P1         # 冒烟 + 核心
python3 run.py                       # 全部
```

### 3. 映射表

| 简写 | 全称 | 建议 |
|------|------|------|
| P0 | blocker | 每次提交必跑 |
| P1 | critical | 提测前必跑 |
| P2 | normal | 全量回归（默认） |
| P3 | minor | 全量回归 |
| P4 | trivial | 全量回归 |

---

## 十四、并行执行

```bash
python3 run.py --workers 4           # 4 进程
python3 run.py --workers auto        # 按 CPU 核数
```

**规则：**
- 同一 YAML 文件内 → 按顺序执行（保证变量依赖）
- 不同 YAML 文件间 → 并行执行
- 要求不同文件间**无数据依赖**

---

## 十五、重试机制

### 1. 全局配置

```yaml
# config/config.yaml
retry: 2      # 所有用例默认重试 2 次
```

### 2. 用例级覆盖

```yaml
- name: 不稳定接口
  retry: 3                  # 重试 3 次
- name: 稳定接口
  retry: 0                  # 不重试
```

### 3. 重试规则

| 场景 | 行为 |
|------|------|
| 请求异常（超时/连接失败） | 重试 |
| 请求成功但断言失败 | 重试 |
| 请求成功且断言通过 | 不重试 |
| 重试间隔 | 递增退避：2s → 4s → 6s → ... 最大 10s |
| db_setup / hook 失败 | 不重试 |

---

## 十六、运行与命令行参数

```bash
python3 run.py [--env ENV] [--path PATH] [--report REPORT] [--level LEVEL] [--workers N]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--env` | config.yaml 中的 `current_env` | 选择环境 |
| `--path` | `testcases` | 用例路径（目录或文件） |
| `--report` | `html` | allure / html / both |
| `--level` | 无（全部） | P0 / P0,P1 / blocker,critical |
| `--workers` | 无（单进程） | 数字或 auto |

### 常用场景

```bash
# 日常开发
python3 run.py --path testcases/login/ --report html

# 冒烟测试
python3 run.py --level P0

# 提测前回归
python3 run.py --level P0,P1 --workers 4 --report both

# 全量回归
python3 run.py --workers auto --report both
```

---

## 十七、测试报告

### HTML 报告

```bash
python3 run.py --report html
open reports/report.html
```

### Allure 报告

```bash
python3 run.py --report allure
allure serve reports/allure-results
```

Allure 支持：按模块分组、优先级标记、请求/响应详情、趋势图。

---

## 十八、日志系统

每次运行在 `logs/` 下生成日期命名的日志文件：

```
logs/2026-04-24.log
```

日志内容示例：

```
========== 用户登录 > 登录成功 ==========
→ POST https://api.example.com/api/login
→ Headers: {"Content-Type": "application/json"}
→ Body: {"username": "admin", "password": "***"}
← Status: 200 | Time: 128ms
← Response: {"code": 0, "data": {"token": "eyJ..."}}
✓ Extract: token = eyJ...
✓ Validate: eq PASS
```

日志同时输出到控制台和文件，文件保留 7 天。

---

## 十九、通知（邮件 + 飞书）

### 1. 邮件通知

```yaml
# config/config.yaml
email:
  enabled: true
  smtp_host: smtp.qq.com
  smtp_port: 465
  sender: your@qq.com
  password: your_smtp_auth_code    # SMTP 授权码，非登录密码
  receivers: [dev@company.com]
  send_on: fail                    # always / fail / never
```

邮件内容包含：环境、统计数据、失败用例列表，HTML 报告作为附件。

### 2. 飞书通知

```yaml
# config/config.yaml
feishu:
  enabled: true
  webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
  send_on: fail
  at_user_ids:
    - "ou_xxxx"                    # 失败时 @指定用户
```

效果：失败时红色卡片 + @人，全部通过时绿色卡片。

### 3. 同时启用

邮件和飞书互不影响，可同时开启。

---

## 二十、CI/CD 集成

### Jenkins

项目内置 `Jenkinsfile`：
1. 创建 Pipeline 项目
2. Pipeline 选择 "Pipeline script from SCM"
3. 指向项目仓库，脚本路径 `Jenkinsfile`

### GitLab CI

项目内置 `.gitlab-ci.yml`，推送到 GitLab 即自动触发。

### 核心命令

```bash
pip install -r requirements.txt
python run.py --env $ENV --path testcases/ --report allure
# 退出码：0=全部通过，1=有失败
```

---

## 附录A：JSONPath 速查

| 表达式 | 含义 |
|--------|------|
| `$.code` | 根级 code 字段 |
| `$.data.token` | data 下的 token |
| `$.data.list[0].id` | 列表第一个元素的 id |
| `$.data.list[-1].name` | 列表最后一个元素的 name |
| `status_code` | HTTP 状态码（特殊关键字） |

---

## 附录B：常见问题 FAQ

| 问题 | 解决方案 |
|------|---------|
| `ModuleNotFoundError` | `pip install -r requirements.txt` |
| 所有用例 `ConnectionError` | 检查 `config/{env}.yaml` 的 `base_url` |
| 登录成功但后续 401 | 检查 token 的 JSONPath 是否正确（看日志中的完整响应） |
| `Unresolved variable: ${xxx}` | 变量名拼写错误，或上游用例失败 |
| `Database connection failed` | 不需要数据库功能则删掉 `database:` 配置 |
| Excel 数字变成 25.0 | 框架已自动处理，整数会转为 int |
| YAML 数据文件不存在 | 检查 `yaml_source` 路径（相对于 YAML 文件），确认 data/ 目录存在 |
| 如何跳过某些用例 | 用 `--path` 指定目录/文件，或 `--level` 过滤 |
| 如何上传文件 | 通过 Hook 扩展实现 multipart/form-data |
| 用例执行顺序 | 同文件按 YAML 顺序，不同文件按路径字母序 |
