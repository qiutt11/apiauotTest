# API 接口自动化测试框架

基于 Python + pytest 的数据驱动接口自动化测试框架。**只需编写 YAML/JSON/Excel 数据文件即可完成接口测试，无需编写 Python 代码。**

## 特性

- **数据驱动** — 用例写在 YAML/JSON/Excel 文件中，新增用例零代码
- **多环境切换** — 支持 dev / test / staging / prod 环境一键切换
- **接口依赖** — 通过 `extract` + `${变量名}` 实现接口间数据传递
- **数据库支持** — `db_setup` 前置数据 / `db_extract` 查询校验 / `db_teardown` 清理
- **Hook 扩展** — 自定义请求前/后处理函数（加密、签名等）
- **多种报告** — Allure（美观图表）+ pytest-html（轻量纯 Python）
- **邮件通知** — 测试完成后自动发送结果邮件
- **CI/CD 集成** — 提供 Jenkinsfile 和 GitLab CI 配置

## 快速开始

### 安装

```bash
pip install -r requirements.txt
```

### 配置环境

编辑 `config/config.yaml`：

```yaml
current_env: test    # 选择环境
```

编辑 `config/test.yaml`：

```yaml
base_url: https://your-api.example.com
global_variables:
  admin_user: your_username
  admin_pass: your_password
```

### 编写用例

在 `testcases/` 下创建 YAML 文件：

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
      - not_null: [$.data.token]

  - name: 密码错误
    method: POST
    url: /api/login
    body:
      username: ${admin_user}
      password: wrong
    validate:
      - eq: [$.code, 1001]
      - contains: [$.msg, "密码错误"]
```

### 运行

```bash
python run.py                                    # 运行全部用例
python run.py --env dev                          # 指定环境
python run.py --path testcases/login/            # 指定用例路径
python run.py --report both                      # 同时生成 Allure + HTML 报告
python run.py --env staging --report allure      # 组合使用
```

## 用例格式

### 断言关键字

| 关键字 | 说明 | 示例 |
|--------|------|------|
| `eq` | 等于 | `eq: [$.code, 0]` |
| `neq` | 不等于 | `neq: [$.code, -1]` |
| `gt` / `lt` | 大于 / 小于 | `gt: [$.data.total, 0]` |
| `gte` / `lte` | 大于等于 / 小于等于 | `gte: [status_code, 200]` |
| `contains` | 包含 | `contains: [$.msg, "成功"]` |
| `not_null` | 不为空 | `not_null: [$.data.token]` |
| `type` | 类型校验 | `type: [$.data.id, int]` |
| `length` | 长度校验 | `length: [$.data.list, 10]` |

### 接口依赖

```yaml
- name: 登录
  method: POST
  url: /api/login
  body: {username: admin, password: "123456"}
  extract:
    token: $.data.token       # 提取 token

- name: 查询用户
  method: GET
  url: /api/users
  headers:
    Authorization: Bearer ${token}   # 引用 token
```

### 数据库操作

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

### Hook 扩展

```python
# hooks/custom_hooks.py
def encrypt_body(request_data):
    request_data["body"]["sign"] = calculate_sign(request_data["body"])
    return request_data
```

```yaml
- name: 需要签名的接口
  method: POST
  url: /api/pay
  body: {order_id: "123"}
  hook:
    before: encrypt_body
```

### Excel 格式

Sheet 名作为模块名，第一行为表头：

| name | method | url | headers | body | extract | validate |
|------|--------|-----|---------|------|---------|----------|
| 登录成功 | POST | /api/login | | {"username":"admin"} | {"token":"$.data.token"} | [{"eq":["$.code",0]}] |

## 报告

```bash
# Allure 报告
python run.py --report allure
allure serve reports/allure-results

# HTML 报告
python run.py --report html
# 查看 reports/report.html
```

## 邮件通知

在 `config/config.yaml` 中配置：

```yaml
email:
  enabled: true
  smtp_host: smtp.qq.com
  smtp_port: 465
  sender: your@qq.com
  password: your_smtp_password
  receivers:
    - dev@company.com
  send_on: fail    # always / fail / never
```

## 项目结构

```
autotest/
├── config/          # 环境配置 ← 需要修改
├── testcases/       # 测试用例 ← 需要编写
├── hooks/           # Hook 扩展 ← 按需编写
├── common/          # 框架核心（无需修改）
├── tests/           # 单元测试（79个，覆盖率96%）
├── reports/         # 报告输出（自动生成）
├── logs/            # 日志输出（自动生成）
├── run.py           # 运行入口
├── conftest.py      # pytest 配置
├── Jenkinsfile      # Jenkins 流水线
├── .gitlab-ci.yml   # GitLab CI
└── requirements.txt # 依赖
```

## CI/CD

### Jenkins

内置 `Jenkinsfile`，支持参数化构建（环境 / 用例路径 / 报告类型）。

### GitLab CI

内置 `.gitlab-ci.yml`，自动执行测试并归档报告（7天过期）。

## 详细文档

完整使用指南见 [docs/usage.md](docs/usage.md)。
