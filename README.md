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

## 环境要求

- Python 3.10 或更高版本
- pip 包管理器
- (可选) Allure 命令行工具 — 查看 Allure 报告需要安装 [Allure CLI](https://docs.qameta.io/allure/#_installing_a_commandline)
- (可选) MySQL 数据库 — 仅在使用 `db_setup` / `db_extract` / `db_teardown` 时需要

## 30 秒快速体验

```bash
# 1. 克隆项目
git clone <your-repo-url> && cd autotest

# 2. 安装依赖
pip install -r requirements.txt

# 3. 修改接口地址（改成你的被测系统地址）
#    编辑 config/test.yaml 中的 base_url

# 4. 编写你的第一个用例（或先用示例用例跑一下）
python run.py --report html

# 5. 查看报告
open reports/report.html
```

更详细的上手教程见 [docs/quickstart.md](docs/quickstart.md)，完整使用手册见 [docs/usage.md](docs/usage.md)。

## 项目结构

```
autotest/
├── config/          # 环境配置 ← 需要修改（接口地址、账号、数据库）
│   ├── config.yaml  #   主配置（选择环境、超时、邮件）
│   ├── test.yaml    #   test 环境配置
│   ├── dev.yaml     #   dev 环境配置
│   ├── staging.yaml #   staging 环境配置
│   └── prod.yaml    #   prod 环境配置
├── testcases/       # 测试用例 ← 需要编写（YAML/JSON/Excel）
├── hooks/           # Hook 扩展 ← 按需编写（加密、签名等）
├── common/          # 框架核心代码（无需修改）
├── tests/           # 框架单元测试（86个，覆盖率92%）
├── reports/         # 报告输出（自动生成）
├── logs/            # 日志输出（自动生成）
├── run.py           # 运行入口
├── conftest.py      # pytest 配置
├── Jenkinsfile      # Jenkins 流水线
├── .gitlab-ci.yml   # GitLab CI
└── requirements.txt # Python 依赖
```

**日常使用只需关注 3 个目录：`config/`、`testcases/`、`hooks/`**

## 文档索引

| 文档 | 内容 |
|------|------|
| [docs/quickstart.md](docs/quickstart.md) | 新手入门教程（从零开始，手把手完成第一个用例） |
| [docs/usage.md](docs/usage.md) | 完整使用手册（所有功能、配置项、高级用法） |
| CLAUDE.md | AI 开发助手上下文（仅开发者需要） |
