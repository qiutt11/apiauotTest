# API 接口自动化测试框架

基于 Python + pytest 的数据驱动接口自动化测试框架。**只需编写 YAML/JSON/Excel 数据文件即可完成接口测试，无需编写 Python 代码。**

## 特性

- **数据驱动** — 用例写在 YAML/JSON/Excel 文件中，新增用例零代码，支持 YAML 数据驱动的保存+详情对比验证
- **多环境切换** — 支持 dev / test / staging / prod 环境一键切换，用例级 `base_url` 覆盖支持跨系统调用
- **接口依赖** — 通过 `extract` + `${变量名}` 实现接口间数据传递
- **数据库支持** — `db_setup` 前置数据（支持 SQL 生成变量）/ `db_extract` 查询校验 / `db_teardown` 清理
- **优先级过滤** — 用例标记 P0~P4 优先级，按需运行冒烟/核心/全量测试
- **并行执行** — `--workers` 多进程并行，同文件用例保持顺序，不同文件并行加速
- **失败重试** — 全局/用例级重试配置，递增退避，减少网络波动误报
- **Hook 扩展** — 自定义请求前/后处理函数（加密、签名等）
- **多种报告** — Allure（美观图表）+ pytest-html（轻量纯 Python）
- **多渠道通知** — 邮件 + 飞书机器人，失败自动告警并 @相关人
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
├── tests/           # 框架测试（154个：128单元+21集成+5过滤）
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
| **[docs/training-user-guide.md](docs/training-user-guide.md)** | **培训用完整使用手册（覆盖全部功能，适合培训讲解）** |
| **[docs/training-design-doc.md](docs/training-design-doc.md)** | **培训用完整设计文档（架构、模块、流程图，适合技术分享）** |
| CLAUDE.md | AI 开发助手上下文（仅开发者需要） |
