# API 接口自动化测试框架 - 使用文档

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境

编辑 `config/config.yaml` 设置当前环境：

```yaml
current_env: test    # 修改为你的环境：dev / test / staging / prod
```

编辑对应环境文件（如 `config/test.yaml`）：

```yaml
base_url: https://your-api.example.com   # 你的接口地址
global_headers:
  Content-Type: application/json
global_variables:
  admin_user: your_username
  admin_pass: your_password

database:                                  # 数据库配置（可选）
  host: 127.0.0.1
  port: 3306
  user: root
  password: "123456"
  database: your_db
  charset: utf8mb4
```

### 3. 编写用例

在 `testcases/` 目录下创建 YAML 文件：

```yaml
module: 用户登录
testcases:
  - name: 登录成功
    method: POST
    url: /api/login
    body:
      username: ${admin_user}
      password: ${admin_pass}
    extract:
      token: $.data.token
    validate:
      - eq: [status_code, 200]
      - eq: [$.code, 0]
```

### 4. 运行测试

```bash
python run.py                           # 运行全部用例
python run.py --env dev                 # 指定环境
python run.py --path testcases/login/   # 指定用例路径
python run.py --report both             # 指定报告类型
```

---

## 用例编写指南

### 基础结构

```yaml
module: 模块名称
testcases:
  - name: 用例名称
    description: 用例描述（可选）
    level: normal          # 优先级：blocker/critical/normal/minor/trivial（可选）
    method: POST           # 请求方法：GET/POST/PUT/DELETE/PATCH
    url: /api/path         # 接口路径（会自动拼接 base_url）
    headers:               # 请求头（可选）
      Authorization: Bearer ${token}
    body:                  # 请求体（可选）
      key: value
    extract:               # 提取响应数据（可选）
      变量名: JSONPath表达式
    validate:              # 断言（至少一个）
      - eq: [表达式, 期望值]
```

### 断言关键字

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

### 变量引用

使用 `${变量名}` 引用变量。变量来源：

1. **全局变量**：`config/{env}.yaml` 中的 `global_variables`
2. **接口提取**：`extract` 从响应中提取的值
3. **数据库提取**：`db_extract` 从数据库查询的值

```yaml
- name: 登录
  method: POST
  url: /api/login
  body:
    username: ${admin_user}      # 引用全局变量
  extract:
    token: $.data.token          # 提取到变量池

- name: 查询用户
  method: GET
  url: /api/users
  headers:
    Authorization: Bearer ${token}  # 引用上一步提取的变量
```

### 数据库操作

#### 前置数据准备（db_setup）

```yaml
- name: 测试删除用户
  db_setup:
    - sql: "INSERT INTO users (id, name) VALUES (9999, 'test_user')"
  method: DELETE
  url: /api/users/9999
  validate:
    - eq: [$.code, 0]
  db_teardown:
    - sql: "DELETE FROM users WHERE id = 9999"
```

#### 数据库校验（db_extract）

```yaml
- name: 创建订单后验证数据库
  method: POST
  url: /api/orders
  body:
    product_id: 100
  extract:
    order_id: $.data.order_id
  db_extract:
    - sql: "SELECT status FROM orders WHERE id = ${order_id}"
      extract:
        db_status: status
  validate:
    - eq: [$.code, 0]
    - eq: [${db_status}, "pending"]
```

### Hook 扩展

在 `hooks/custom_hooks.py` 中定义函数，用例中通过 `hook` 字段调用：

```python
# hooks/custom_hooks.py
def encrypt_body(request_data):
    # request_data = {"method": ..., "url": ..., "headers": ..., "body": ...}
    request_data["body"]["sign"] = calculate_sign(request_data["body"])
    return request_data
```

```yaml
- name: 需要签名的接口
  method: POST
  url: /api/pay
  body:
    order_id: "12345"
  hook:
    before: encrypt_body     # 请求前调用
    after: decrypt_response  # 响应后调用（可选）
  validate:
    - eq: [$.code, 0]
```

### Excel 格式用例

Excel 文件的 Sheet 名称作为模块名，第一行为表头：

| name | method | url | headers | body | extract | validate |
|------|--------|-----|---------|------|---------|----------|
| 登录成功 | POST | /api/login | | {"username":"admin"} | {"token":"$.data.token"} | [{"eq":["$.code",0]}] |

headers/body/extract/validate 列使用 JSON 字符串。

---

## 报告

### Allure 报告

```bash
python run.py --report allure
# 查看报告：
allure serve reports/allure-results
```

### HTML 报告

```bash
python run.py --report html
# 报告生成在 reports/report.html
```

---

## 邮件通知

在 `config/config.yaml` 中配置：

```yaml
email:
  enabled: true
  smtp_host: smtp.qq.com
  smtp_port: 465
  sender: your_email@qq.com
  password: your_smtp_password
  receivers:
    - receiver1@company.com
    - receiver2@company.com
  send_on: fail    # always=每次发送 / fail=失败时发送 / never=不发送
```

---

## 目录说明

```
autotest/
├── config/          # 环境配置（需要修改）
├── testcases/       # 测试用例（需要编写）
├── hooks/           # 自定义扩展函数（按需编写）
├── common/          # 框架核心代码（无需修改）
├── reports/         # 报告输出（自动生成）
├── logs/            # 日志输出（自动生成）
├── run.py           # 运行入口
└── conftest.py      # pytest 配置
```

日常使用只需关注 `config/`、`testcases/`、`hooks/` 三个目录。
