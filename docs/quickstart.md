# 新手入门教程

本教程从零开始，手把手教你完成第一个接口自动化测试。

## 前置条件

确认你的电脑已安装 Python 3.10+：

```bash
python3 --version
# 输出类似：Python 3.10.x 或更高
```

## 第一步：安装

```bash
# 进入项目目录
cd autotest

# 安装依赖（一次即可）
pip install -r requirements.txt
```

如果安装失败提示 SSL 错误，尝试：

```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
```

验证安装成功：

```bash
python3 run.py --help
```

应输出：

```
usage: run.py [-h] [--env ENV] [--path PATH] [--report REPORT]

API Autotest Framework

options:
  -h, --help       show this help message and exit
  --env ENV        Test environment (dev/test/staging/prod)
  --path PATH      Test case path (directory or file)
  --report REPORT  Report type: allure / html / both
```

## 第二步：配置被测系统

假设你要测试的系统接口地址是 `https://api.yourcompany.com`。

### 2.1 修改主配置

编辑 `config/config.yaml`：

```yaml
# 选择当前使用的环境（对应 config/ 目录下的同名文件）
current_env: test

# 全局超时时间（秒）
timeout: 30

# 报告类型：allure / html / both
report_type: html

# 邮件通知（暂时关闭，后面再配）
email:
  enabled: false
  smtp_host: smtp.qq.com
  smtp_port: 465
  sender: ""
  password: ""
  receivers: []
  send_on: fail
```

### 2.2 修改环境配置

编辑 `config/test.yaml`：

```yaml
# !! 改成你的真实接口地址 !!
base_url: https://api.yourcompany.com

# 全局请求头（所有接口自动携带）
global_headers:
  Content-Type: application/json

# 全局变量（在用例中用 ${变量名} 引用）
global_variables:
  admin_user: your_real_username
  admin_pass: your_real_password

# 数据库配置（可选，不用数据库功能就删掉这段）
# database:
#   host: 127.0.0.1
#   port: 3306
#   user: root
#   password: "123456"
#   database: your_db
#   charset: utf8mb4
```

**关键：`base_url` 必须改成你被测系统的真实地址！**

## 第三步：编写第一个用例

假设你的系统有一个登录接口：

- 地址：`POST /api/v1/login`
- 请求体：`{"username": "admin", "password": "123456"}`
- 成功响应：`{"code": 0, "msg": "success", "data": {"token": "xxx"}}`

### 3.1 创建用例文件

在 `testcases/` 下创建目录和文件 `testcases/login/login.yaml`：

```yaml
module: 用户登录
testcases:
  # 用例1：正常登录
  - name: 登录成功
    description: 使用正确的用户名密码登录
    method: POST
    url: /api/v1/login
    body:
      username: ${admin_user}
      password: ${admin_pass}
    extract:
      token: $.data.token
    validate:
      - eq: [status_code, 200]
      - eq: [$.code, 0]
      - not_null: [$.data.token]

  # 用例2：密码错误
  - name: 密码错误
    description: 密码输入错误应返回错误
    method: POST
    url: /api/v1/login
    body:
      username: ${admin_user}
      password: wrong_password
    validate:
      - eq: [status_code, 200]
      - neq: [$.code, 0]
```

### 3.2 字段说明

```yaml
- name: 用例名称               # 必填，显示在报告中
  description: 用例描述          # 可选
  level: normal                 # 可选，优先级 blocker/critical/normal/minor/trivial
  method: POST                  # 必填，HTTP 方法
  url: /api/v1/login            # 必填，接口路径（自动拼接 base_url）
  headers:                      # 可选，请求头
    Authorization: Bearer ${token}
  body:                         # 可选，请求体
    username: admin
  extract:                      # 可选，从响应中提取变量
    token: $.data.token         #   变量名: JSONPath表达式
  validate:                     # 必填，至少一个断言
    - eq: [$.code, 0]
```

## 第四步：运行测试

```bash
# 运行全部用例，生成 HTML 报告
python3 run.py --report html
```

看到类似输出说明运行成功：

```
============================= test session starts =============================
testcases/login/login.yaml::登录成功 PASSED
testcases/login/login.yaml::密码错误 PASSED
============================== 2 passed in 1.23s ==============================
```

### 查看报告

```bash
# 方式1：HTML 报告（推荐新手）
open reports/report.html      # macOS
# 或者用浏览器打开 reports/report.html

# 方式2：Allure 报告（更美观，需要先安装 Allure CLI）
python3 run.py --report allure
allure serve reports/allure-results
```

### 查看日志

每次运行的详细日志在 `logs/` 目录下，按日期命名：

```
logs/2026-04-11.log
```

日志包含每个请求的完整信息：请求方法、URL、请求头、请求体、响应状态码、响应体、提取结果、断言结果。

## 第五步：添加更多用例

### 5.1 有接口依赖的用例

很多接口需要先登录拿 token。在同一个 YAML 文件中，上面的用例提取的变量，下面的用例可以直接引用：

```yaml
module: 用户管理
testcases:
  # 第一步：登录拿 token
  - name: 登录获取token
    method: POST
    url: /api/v1/login
    body:
      username: ${admin_user}
      password: ${admin_pass}
    extract:
      token: $.data.token          # 提取 token 存入变量池
    validate:
      - eq: [$.code, 0]

  # 第二步：用 token 调用需要鉴权的接口
  - name: 获取用户列表
    method: GET
    url: /api/v1/users
    headers:
      Authorization: Bearer ${token}  # 引用上一步的 token
    validate:
      - eq: [status_code, 200]
      - eq: [$.code, 0]
      - gt: [$.data.total, 0]

  # 第三步：创建用户
  - name: 创建用户
    method: POST
    url: /api/v1/users
    headers:
      Authorization: Bearer ${token}
    body:
      username: new_user
      email: new@test.com
    extract:
      new_user_id: $.data.id       # 提取新用户ID
    validate:
      - eq: [$.code, 0]

  # 第四步：查询刚创建的用户
  - name: 查询新用户
    method: GET
    url: /api/v1/users/${new_user_id}   # 在 URL 中使用变量
    headers:
      Authorization: Bearer ${token}
    validate:
      - eq: [$.code, 0]
      - eq: [$.data.username, "new_user"]
```

**注意：同一个 YAML 文件内的用例按顺序执行，变量在文件内共享。不同文件之间的变量互相隔离。**

### 5.2 用例文件组织建议

```
testcases/
├── login/
│   └── login.yaml         # 登录相关用例
├── user/
│   └── user_crud.yaml     # 用户增删改查
├── order/
│   └── order_flow.yaml    # 订单流程
└── product/
    └── product_query.yaml # 商品查询
```

建议按业务模块分目录，每个 YAML 文件是一个独立的测试场景。

## 常用运行命令

```bash
# 运行全部用例
python3 run.py

# 只运行某个目录下的用例
python3 run.py --path testcases/login/

# 只运行某个文件
python3 run.py --path testcases/login/login.yaml

# 切换环境
python3 run.py --env dev
python3 run.py --env staging

# 按优先级运行（只跑 P0 冒烟用例）
python3 run.py --level P0

# 跑 P0 + P1 核心回归
python3 run.py --level P0,P1

# 并行执行（4个进程）
python3 run.py --workers 4

# 自动按CPU核数并行
python3 run.py --workers auto

# 指定报告格式
python3 run.py --report html      # 生成 HTML 报告
python3 run.py --report allure    # 生成 Allure 数据
python3 run.py --report both      # 同时生成两种

# 组合使用
python3 run.py --env dev --path testcases/login/ --level P0,P1 --workers 4 --report html
```

## 遇到问题？

### 问题1：运行报错 `ModuleNotFoundError`

依赖未安装，重新执行：`pip install -r requirements.txt`

### 问题2：所有用例都失败，报 `ConnectionError`

`config/test.yaml` 中的 `base_url` 不正确，或被测系统未启动。检查接口地址是否可以在浏览器/Postman 中访问。

### 问题3：登录成功但后续接口报 401

检查 token 提取的 JSONPath 是否正确。可以先在日志中看登录接口的完整响应，确认 token 的路径。例如响应是 `{"data": {"access_token": "xxx"}}` 则 extract 应该写 `$.data.access_token`。

### 问题4：日志中看到 `Unresolved variable: ${xxx}`

变量名拼写错误，或者提取变量的用例执行失败导致变量未写入。检查日志确认上游用例是否成功。

### 问题5：Database connection failed

没有安装 MySQL 或数据库地址配置错误。如果不需要数据库功能，把 `config/test.yaml` 中的 `database:` 整段删掉或注释即可，框架会自动跳过。

## 下一步

- 阅读 [完整使用手册](usage.md) 了解全部功能（优先级过滤、并行执行、数据库操作、Hook 扩展、飞书通知等）
- 参考 `testcases/` 下的示例用例
- 对接 CI/CD：项目自带 `Jenkinsfile` 和 `.gitlab-ci.yml`
