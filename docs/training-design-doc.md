# API 接口自动化测试框架 — 完整设计文档

> 培训用文档 | 版本：v2.0 | 更新日期：2026-04-24

---

## 目录

- [一、架构总览](#一架构总览)
- [二、核心执行流程](#二核心执行流程)
- [三、模块设计](#三模块设计)
- [四、Excel 驱动用例设计](#四excel-驱动用例设计)
- [五、变量池设计](#五变量池设计)
- [六、pytest 集成设计](#六pytest-集成设计)
- [七、配置系统设计](#七配置系统设计)
- [八、数据库操作设计](#八数据库操作设计)
- [九、通知系统设计](#九通知系统设计)
- [十、测试覆盖](#十测试覆盖)
- [十一、关键设计决策](#十一关键设计决策)
- [十二、文件清单与职责](#十二文件清单与职责)

---

## 一、架构总览

### 1. 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI 入口层                              │
│  run.py: 解析参数 → 构建 pytest 命令 → 执行 → 聚合 → 通知   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    pytest 集成层                              │
│  conftest.py:                                                │
│  ├── pytest_configure()   → 初始化框架组件                    │
│  ├── pytest_collect_file() → 发现 YAML/JSON/Excel 文件        │
│  ├── TestCaseFile.collect() → 解析用例，生成执行项             │
│  │   ├── 普通用例 → TestCaseItem                              │
│  │   └── Excel 驱动 → ExcelDrivenItem（每行一个）              │
│  └── pytest_runtest_makereport() → 收集统计数据               │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    核心执行层 (common/)                        │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐    │
│  │ runner.py   │→ │request_handler│→ │   HTTP 请求      │    │
│  │ 编排 10 步   │  └──────────────┘  └──────────────────┘    │
│  │ 执行流程    │                                             │
│  │             │→ extractor.py → JSONPath 提取               │
│  │             │→ validator.py → 10 个断言关键字              │
│  │             │→ db_handler.py → MySQL 操作                 │
│  │             │→ hook_manager.py → 自定义扩展               │
│  └─────────────┘                                             │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │variable_pool │  │ data_loader  │  │  config_loader   │   │
│  │三层变量管理   │  │YAML/JSON/Excel│ │ 深合并配置       │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    输出层                                     │
│  ├── logger.py → loguru 日志（控制台 + 文件，保留 7 天）       │
│  ├── notifier.py → 邮件（SMTP_SSL）+ 飞书（Webhook 卡片）    │
│  └── allure / pytest-html → 测试报告                         │
└─────────────────────────────────────────────────────────────┘
```

### 2. 数据流向

```
config.yaml + {env}.yaml
        │
        ▼
   load_config() → 深合并 → cfg 字典
        │
        ├──→ base_url, global_headers, timeout, retry
        ├──→ global_variables → pool.set_global()
        ├──→ database → DBHandler
        └──→ email / feishu → notifier

YAML / JSON / Excel 用例文件
        │
        ▼
   load_testcases() / load_excel_rows()
        │
        ▼
   TestCaseFile.collect()
        │
   ┌────┴────┐
   │         │
TestCaseItem  ExcelDrivenItem
   │         │
   ▼         ▼
run_testcase()
   │
   ├──→ pool.resolve() → 变量替换
   ├──→ db_handler.execute_setup() → 前置数据
   ├──→ hook_manager.call(before) → 请求前处理
   ├──→ send_request() → HTTP 请求
   ├──→ hook_manager.call(after) → 响应后处理
   ├──→ extract_fields() → 提取变量 → pool.set_module()
   ├──→ db_handler.execute_extract() → 数据库校验
   ├──→ validate_case() → 断言校验
   └──→ db_handler.execute_teardown() → 清理（finally）
```

---

## 二、核心执行流程

### 用例执行 10 步流程（`runner.py`）

```
┌─ run_testcase() ──────────────────────────────────────────┐
│                                                            │
│  1. case.base_url → 覆盖全局 base_url（可选）              │
│  2. pool.resolve() → 替换 ${变量名}                        │
│  3. url = base_url + resolved_url                          │
│  4. headers = global_headers + case_headers                │
│                                                            │
│  ┌─ try ────────────────────────────────────────────────┐  │
│  │                                                      │  │
│  │  5. db_setup（如有）→ execute_setup → extract → pool  │  │
│  │     → re-resolve（用新变量重新解析请求参数）            │  │
│  │                                                      │  │
│  │  6. before hook（如有）→ 修改 request_data            │  │
│  │                                                      │  │
│  │  ┌─ retry loop ───────────────────────────────────┐  │  │
│  │  │  7. send_request() → HTTP 请求                 │  │  │
│  │  │  8. after hook（如有）→ 修改 response           │  │  │
│  │  │  9. extract → pool.set_module()                │  │  │
│  │  │  10. db_extract（如有）→ pool.set_module()      │  │  │
│  │  │  11. validate → 断言校验                        │  │  │
│  │  │  → 全部通过？返回 passed                        │  │  │
│  │  │  → 失败 + 还有重试？wait → 继续循环              │  │  │
│  │  │  → 失败 + 重试耗尽？返回 failed                 │  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  │                                                      │  │
│  ├─ finally ────────────────────────────────────────────┤  │
│  │  12. db_teardown（如有）→ 即使失败也执行              │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  返回：{name, passed, response, extracts, db_vars,         │
│         validations, error}                                │
└────────────────────────────────────────────────────────────┘
```

### 重试机制

```
attempt 0（首次）→ 失败 → wait 2s
attempt 1（重试1）→ 失败 → wait 4s
attempt 2（重试2）→ 失败 → wait 6s
...
attempt N → 失败 → 返回最后一次结果
```

- 请求异常和断言失败都触发重试
- db_setup / hook 失败不触发重试
- 退避间隔：`min(attempt * 2, 10)` 秒

---

## 三、模块设计

### 3.1 `config_loader.py` — 配置加载

**职责**：加载主配置 + 环境配置，深合并。

```python
load_config(config_dir, env=None) → dict
_deep_merge(base, override) → dict  # 递归合并，保留未覆盖的嵌套键
```

**合并优先级**：`env.yaml` > `config.yaml`，`--env` 参数 > `config.yaml.current_env`

### 3.2 `data_loader.py` — 数据加载

**职责**：从 YAML/JSON/Excel 加载用例数据，统一返回 `{"module": "...", "testcases": [...]}`。

| 函数 | 用途 |
|------|------|
| `load_testcases(file_path)` | 按扩展名自动选择加载器 |
| `_load_yaml(file_path)` | YAML 加载 |
| `_load_json(file_path)` | JSON 加载 |
| `_load_excel(file_path)` | Excel 加载（每行=用例，JSON 字段自动解析） |
| `load_excel_rows(file_path)` | Excel 行数据加载（每行=数据字典，用于 Excel 驱动） |
| `scan_testcase_files(directory)` | 扫描目录下所有支持的文件 |

**`load_excel_rows` 类型处理**：

| 单元格内容 | 处理 |
|-----------|------|
| 数字 25（Excel 返回 25.0） | 转为 int 25 |
| 小数 99.5 | 保留 float |
| 字符串 `["a","b"]` | JSON 解析为 list |
| 字符串 `{"k":"v"}` | JSON 解析为 dict |
| 字符串 `"hello"` | 保留 str |
| 空单元格 | 字段不出现 |

### 3.3 `variable_pool.py` — 变量管理

**三层优先级**：

```
get(key):
  temp[key] → module[key] → global[key] → None
```

**变量解析 `resolve()`**：

- 递归处理 str / dict / list
- 完整匹配 `${var}` → 返回原始类型（int 42）
- 嵌入匹配 `"Bearer ${token}"` → 返回 str

### 3.4 `request_handler.py` — HTTP 请求

**职责**：封装 requests 库，返回标准响应字典。

```python
send_request(method, url, headers, body, timeout) → {
    "status_code": 200,
    "body": {...},
    "headers": {...},
    "elapsed_ms": 128.5,
    "error": None,        # 异常时为错误信息字符串
}
```

- 异常（Timeout/ConnectionError）不抛出，记录在 error 字段
- body 以 JSON 格式发送（`kwargs["json"] = body`）

### 3.5 `extractor.py` — JSONPath 提取

```python
extract_by_jsonpath(data, "$.data.token") → "abc123"
extract_fields(response_body, {"token": "$.data.token"}) → {"token": "abc123"}
```

基于 `jsonpath-ng` 库，匹配第一个结果，未匹配返回 None。

### 3.6 `validator.py` — 断言校验

**10 个关键字**：eq / neq / gt / lt / gte / lte / contains / not_null / type / length

**表达式解析优先级**：
1. `"status_code"` → HTTP 状态码
2. `"${var}"` → extra_vars 中查找
3. `"$.xxx"` → JSONPath 提取
4. 其他 → 原值

**返回格式**：

```python
[{"keyword": "eq", "expression": "$.code", "actual": 0, "expect": 0, "passed": True}, ...]
```

### 3.7 `runner.py` — 核心编排

**职责**：编排单个用例的 10 步执行流程。

**关键设计**：
- `base_url` 覆盖：`case.get("base_url")` → `str(pool.resolve(...))` → 覆盖参数
- db_setup 后 re-resolve：base_url + url + headers + body 全部重新解析
- 重试机制：retry loop 包裹 HTTP 请求 + 断言
- db_teardown：finally 块中执行

### 3.8 `db_handler.py` — 数据库操作

**职责**：MySQL 操作（setup / extract / teardown）。

| 方法 | 用途 |
|------|------|
| `execute_setup(sql_list)` | 前置数据 + 提取变量，失败 rollback |
| `execute_extract(extract_list)` | 请求后查询校验 |
| `execute_teardown(sql_list)` | 清理数据，失败 rollback |
| `close()` | 关闭连接（防 double-close） |

**特性**：参数化 SQL（`%s` 占位符防注入）、自动重连（`ping(reconnect=True)`）。

### 3.9 `hook_manager.py` — Hook 扩展

**职责**：动态加载 hooks/ 目录下的 Python 函数。

**安全机制**：
- 只注册 `__module__` 匹配的函数（排除 import 的第三方函数）
- `_` 开头的文件和函数被忽略
- 加载异常只记录 warning，不崩溃

### 3.10 `logger.py` — 日志

基于 loguru，按日期轮转，保留 7 天。`log_request()` 格式化记录完整请求/响应。

### 3.11 `notifier.py` — 通知

| 函数 | 用途 |
|------|------|
| `maybe_send_notification()` | 统一调度（判断 send_on → 调用对应渠道） |
| `send_email()` | SMTP_SSL 发送，HTML 报告作为附件 |
| `send_feishu()` | Webhook 卡片消息（红/绿标题 + @人） |

---

## 四、Excel 驱动用例设计

### 4.1 整体流程

```
TestCaseFile.collect()
  │
  ├── case 有 excel_source + steps?
  │     │
  │     ├── YES → load_excel_rows(excel_path)
  │     │          │
  │     │          ├── row 0 → ExcelDrivenItem("用例名[张三]")
  │     │          ├── row 1 → ExcelDrivenItem("用例名[李四]")
  │     │          └── ...
  │     │
  │     └── NO → TestCaseItem（走原有逻辑）
```

### 4.2 ExcelDrivenItem.runtest() 执行流程

```
1. pool.clear_module()（文件切换时）
2. 注入 Excel 行数据 → pool.set_module(col, val)
3. for step in steps:
   a. copy.deepcopy(step) → step_case
   b. body_from_excel? → _build_body_from_excel() → step_case["body"]
   c. validate_from_excel? → _build_excel_validations() → 追加到 step_case["validate"]
   d. run_testcase(step_case, ...) → 复用现有引擎
   e. 失败? → raise TestCaseFailure → 停止后续 step
```

### 4.3 辅助函数

| 函数 | 职责 |
|------|------|
| `_build_body_from_excel(row_data, config)` | Excel 数据 → 请求 body（支持 field_mapping） |
| `_build_excel_validations(row_data, config)` | Excel 数据 → eq 断言列表（支持 prefix + field_mapping） |
| `_flatten_excel_validations(prefix, value)` | 递归展开嵌套值为 eq 断言 |

### 4.4 递归断言展开

```
_flatten_excel_validations("$.data", {"name": "张三", "tags": ["vip"], "addr": {"city": "北京"}})

→ 递归过程：
  $.data → dict → 展开 keys
    $.data.name → "张三" → 叶子 → eq: [$.data.name, "张三"]
    $.data.tags → list → 展开 index
      $.data.tags[0] → "vip" → 叶子 → eq: [$.data.tags[0], "vip"]
    $.data.addr → dict → 展开 keys
      $.data.addr.city → "北京" → 叶子 → eq: [$.data.addr.city, "北京"]

→ 输出：3 条 eq 断言
```

---

## 五、变量池设计

```
┌──────────────────────────────────────────────┐
│              VariablePool                     │
│                                              │
│  ┌─────────┐  优先级最高                      │
│  │  _temp   │  预留，用例级覆盖                │
│  └────┬────┘                                 │
│       │ 找不到 ↓                              │
│  ┌────▼────┐  模块变量                        │
│  │ _module  │  extract / db_extract / Excel    │
│  │          │  文件切换时清空 clear_module()     │
│  └────┬────┘                                 │
│       │ 找不到 ↓                              │
│  ┌────▼────┐  全局变量                        │
│  │ _global  │  config.global_variables        │
│  └─────────┘                                 │
│                                              │
│  resolve(data):                              │
│  ├── str → "${var}" 替换                      │
│  │   ├── 完整匹配 "${id}" → 返回原始类型      │
│  │   └── 嵌入 "Bearer ${token}" → 返回 str   │
│  ├── dict → 递归 resolve 每个 value           │
│  ├── list → 递归 resolve 每个 item            │
│  └── 其他 → 原样返回                          │
└──────────────────────────────────────────────┘
```

---

## 六、pytest 集成设计

### 6.1 生命周期钩子

```
pytest 启动
  │
  ├── pytest_addoption() → 注册 --env, --path, --report, --level
  │
  ├── pytest_configure() → 初始化框架
  │   ├── load_config() → cfg
  │   ├── VariablePool() → pool
  │   ├── setup_logger() → logger
  │   ├── HookManager() → hooks
  │   ├── DBHandler() → db（可选）
  │   └── 初始化 stats 统计
  │
  ├── pytest_collect_file() → 发现 testcases/ 下的文件
  │   └── 返回 TestCaseFile
  │
  ├── TestCaseFile.collect() → 解析用例
  │   ├── --level 过滤
  │   ├── 普通用例 → TestCaseItem
  │   └── Excel 驱动 → ExcelDrivenItem × N 行
  │
  ├── TestCaseItem.runtest() / ExcelDrivenItem.runtest()
  │   └── run_testcase() → 核心执行
  │
  ├── pytest_runtest_makereport() → 收集 passed/failed/skipped
  │
  ├── pytest_sessionfinish() → 写入 .stats.json
  │
  └── pytest_unconfigure() → 关闭 DB 连接
```

### 6.2 用例收集流程

```
TestCaseFile.collect()
  │
  ├── load_testcases(yaml_path) → {"module": ..., "testcases": [...]}
  │
  ├── --level 过滤（P0 → blocker 映射）
  │
  └── for case in testcases:
      ├── 有 excel_source + steps?
      │   ├── 解析 Excel 路径（相对 → 绝对）
      │   ├── 文件不存在 → FileNotFoundError
      │   ├── load_excel_rows() → rows
      │   └── for row in rows:
      │       └── yield ExcelDrivenItem(name="用例名[第一列值]")
      │
      └── 无 → yield TestCaseItem(name=用例名)
```

---

## 七、配置系统设计

### 加载流程

```
config/
├── config.yaml     ← 主配置（公共部分）
├── test.yaml       ← 环境配置
└── dev.yaml

load_config(config_dir, env="test")
  │
  ├── 读取 config.yaml → base_dict
  ├── 读取 test.yaml → env_dict
  └── _deep_merge(base_dict, env_dict) → 最终配置
```

### 深合并规则

```python
# base: {"email": {"enabled": false, "host": "smtp.qq.com"}}
# env:  {"email": {"enabled": true}}
# 结果: {"email": {"enabled": true, "host": "smtp.qq.com"}}
#        ↑ 覆盖              ↑ 保留
```

---

## 八、数据库操作设计

### 执行流程

```
db_setup（在 HTTP 请求前）
  │
  ├── SQL 1: INSERT → 准备数据
  ├── SQL 2: SELECT + extract → 提取变量 → pool.set_module()
  ├── SQL 3: INSERT (用 ${提取的变量}) → 关联数据
  └── commit / rollback
       │
       ▼
  re-resolve（用新变量重新解析 url/body/headers/base_url）
       │
       ▼
  HTTP 请求
       │
       ▼
db_extract（在 HTTP 请求后）
  │
  ├── SELECT → 查询数据库
  └── extract → pool.set_module()
       │
       ▼
  validate（断言中可用 ${db_var} 引用）
       │
       ▼
db_teardown（finally 块，即使失败也执行）
  │
  ├── DELETE → 清理数据
  └── commit / rollback
```

---

## 九、通知系统设计

### 调度逻辑

```
maybe_send_notification(email_config, feishu_config, stats, send_on)
  │
  ├── send_on == "never" → 不发送
  ├── send_on == "always" → 发送
  ├── send_on == "fail" + stats.failed > 0 → 发送
  └── send_on == "fail" + stats.failed == 0 → 不发送
       │
       ├── email.enabled? → send_email()
       │   ├── 构建 MIMEMultipart
       │   ├── 附加 HTML 报告（如有）
       │   └── SMTP_SSL 发送
       │
       └── feishu.enabled? → send_feishu()
           ├── 构建 interactive card JSON
           ├── 红/绿标题（根据是否有失败）
           ├── 失败用例列表（最多 10 条）
           ├── @指定用户（at_user_ids）
           └── POST webhook_url
```

---

## 十、测试覆盖

### 总览

| 类别 | 数量 | 说明 |
|------|------|------|
| 单元测试 | 132 | 各模块独立测试 |
| 集成测试 | 21 | 端到端流水线 |
| 级别过滤测试 | 5 | --level 参数 |
| **总计** | **158** | |

### 单元测试分布

| 文件 | 数量 | 覆盖模块 |
|------|------|---------|
| test_config_loader.py | 6 | 配置加载、深合并、环境切换 |
| test_data_loader.py | 5 | YAML/JSON/Excel 加载、目录扫描 |
| test_excel_driven.py | 29 | load_excel_rows、断言展开、body/validate 构建 |
| test_extractor.py | 5 | JSONPath 提取 |
| test_hook_manager.py | 5 | Hook 加载、调用、缺失处理 |
| test_level_filter.py | 5 | 优先级过滤 |
| test_logger.py | 2 | 日志创建、格式化 |
| test_notifier.py | 11 | 邮件、飞书、调度逻辑 |
| test_request_handler.py | 5 | GET/POST、超时、连接错误 |
| test_runner.py | 19 | 基础执行、extract、变量、DB、Hook、重试、base_url |
| test_validator.py | 20 | 10 个断言关键字 + 边界情况 |
| test_variable_pool.py | 16 | 三层优先级、resolve、类型保留 |

### 集成测试分布

| 文件 | 数量 | 覆盖场景 |
|------|------|---------|
| test_full_pipeline.py | 14 | YAML 加载→执行、变量链式传递、变量隔离、全局 headers、Hook、失败处理、配置合并、CLI、Excel 驱动 |
| test_excel_driven_demo.py | 3 | Excel 驱动端到端、field_mapping、失败信息 |
| test_full_pipeline.py (网络) | 4 | subprocess 运行、统计写入（依赖 httpbin.org） |

---

## 十一、关键设计决策

| 决策 | 方案 | 原因 |
|------|------|------|
| 用例格式 | YAML/JSON/Excel | 业务人员友好，无需写代码 |
| 执行引擎 | pytest | 生态丰富（报告、并行、插件） |
| 变量系统 | 三层池 + `${xxx}` 语法 | 简单直观，支持跨用例传递 |
| 类型保留 | 完整 `${var}` 保留原类型 | 防止 int 变 str 导致断言失败 |
| Excel 驱动 | YAML 定义逻辑 + Excel 存数据 | 职责分离，各取所长 |
| Excel 断言展开 | 递归 flatten | 自动处理嵌套对象和数组 |
| step 拷贝 | `copy.deepcopy` | 防止多行数据共享引用导致污染 |
| base_url 覆盖 | case 级字段 + pool.resolve | 支持跨系统 + 变量 + 环境切换 |
| db_setup extract | SQL 可提取变量供后续使用 | 支持"生成随机数据→接口引用"场景 |
| db_teardown | finally 语义 | 即使失败也清理，防止脏数据 |
| Hook 安全 | `__module__` 过滤 | 防止 import 的危险函数被注册 |
| 重试退避 | `min(attempt * 2, 10)` | 递增但有上限，避免等太久 |
| 并行策略 | xdist loadfile | 同文件顺序（保证依赖），跨文件并行 |
| 通知 | 邮件 + 飞书 | 覆盖传统和 IM 两种渠道 |
| float→int | `25.0 == int(25.0)` 时转换 | openpyxl 默认行为修正 |
| 配置合并 | 递归深合并 | 保留未覆盖的嵌套键 |

---

## 十二、文件清单与职责

### 框架核心 (`common/`)

| 文件 | 行数 | 职责 |
|------|------|------|
| `config_loader.py` | 72 | 配置加载 + 深合并 |
| `data_loader.py` | 175 | YAML/JSON/Excel 数据加载 + load_excel_rows |
| `variable_pool.py` | 100 | 三层变量池 + ${xxx} 解析 |
| `runner.py` | 268 | 核心执行引擎（10 步 + 重试 + base_url 覆盖） |
| `request_handler.py` | 76 | HTTP 请求封装 |
| `extractor.py` | 54 | JSONPath 提取 |
| `validator.py` | 186 | 10 个断言关键字 |
| `db_handler.py` | 126 | MySQL 操作（setup/extract/teardown） |
| `hook_manager.py` | 86 | 动态 Hook 加载 + 安全过滤 |
| `logger.py` | 99 | loguru 日志（控制台 + 文件） |
| `notifier.py` | 251 | 邮件 + 飞书通知 |

### pytest 集成

| 文件 | 职责 |
|------|------|
| `conftest.py` | 钩子注册、框架初始化、用例收集（TestCaseItem + ExcelDrivenItem）、统计 |
| `run.py` | CLI 入口、pytest 参数构建、统计聚合、通知调度 |
| `pytest.ini` | pytest 配置（testpaths、addopts） |

### 测试

| 目录 | 文件数 | 说明 |
|------|--------|------|
| `tests/` | 12 | 单元测试 |
| `tests/integration/` | 2 | 集成测试 |
| `tests/fixtures/` | 3 | 测试数据（YAML/JSON/Excel） |

### 示例用例

| 文件 | 说明 |
|------|------|
| `testcases/login/login.yaml` | 登录示例 |
| `testcases/user/user_crud.yaml` | 用户 CRUD 示例 |
| `testcases/user/user_excel_driven.yaml` | Excel 驱动示例（3 个场景，含详细注释） |
| `testcases/user/data/user_data.xlsx` | Excel 数据（直接映射） |
| `testcases/user/data/user_data_with_mapping.xlsx` | Excel 数据（字段映射） |
