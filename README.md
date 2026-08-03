# 🌌 Project Reborn (数字分身核心引擎)

[![Python 3.11-3.12](https://img.shields.io/badge/python-3.11--3.12-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20DB-red)](https://qdrant.tech/)
[![LangChain](https://img.shields.io/badge/LangChain-Integration-green)](https://python.langchain.com/)

[🇨🇳 简体中文](#-简体中文) | [🇬🇧 English](#-english)

---

## 🇬🇧 English

### 📖 About The Project

**Project Reborn** is a **digital legacy companionship system** designed for the scenario where parents unexpectedly pass away while their children are still young. Its core mission is to digitize a parent's personality while they are alive, and to provide a digital twin — carrying the parent's values, language patterns, and life wisdom — as a companionship AI for their minor children after the parent's passing.

The project is structured in two major phases:

- **Phase 1 — Soul Capture (Current Focus):** While the parent is alive, record their life habits, values, and way of speaking through written documents and AI interviews. Build a local, auditable personality knowledge base anchored in their Second Brain (Obsidian vault).
- **Phase 2 — Digital Twin Activation (Future Plan):** After the parent's passing, activate the digital legacy. Connect voice cloning (GPT-SoVITS) and digital avatar technologies to enable an embodied, interactive companionship experience.

> **⚖️ Ethical Stance (TBD):** Whether the digital twin should identify itself as an AI robot or roleplay as a parental avatar is an open ethical question involving child psychology and trust. This is intentionally left as a research question and is not pre-decided at the engineering level.

### 🏗️ Core Architecture (Hierarchical Memory)

The engine utilizes a biologically inspired memory architecture:

- **ROM (Read-Only Memory) - The Core Values:** Hard-coded, immutable principles extracted via AI interviews, injected directly into the LLM's System Prompt to prevent "persona drift".
- **RAM (Random Access Memory) - The Subconscious:** A dynamic pool of past stories, experiences, and thoughts, powered by a hybrid retrieval system (Qdrant Dense Vector + BM25 Sparse Vector) and refined by Cross-Encoder Reranking.

### ✨ Key Features

1. **Soul Interview Room (创造者引擎):** An interactive Streamlit console where the AI interviews the creator to unearth latent values and automatically synthesizes them into Markdown files within the Obsidian vault.
2. **Seamless Knowledge Ingestion:** Automatically parses YAML frontmatter, ignores system noise, executes dual-layer chunking on Obsidian `.md` files, and sinks them into local Qdrant/BM25 databases.
3. **Avatar Sandbox:** The testing ground for the digital twin, utilizing local RAG and DeepSeek API to simulate responses.
4. **100% Offline Capable Infrastructure:** Designed to keep core embedding (`BGE-small-zh-v1.5`) and reranking (`BGE-reranker-base`) models fully local to resist "time erosion".

### 🚀 Getting Started

#### 1. Prerequisites

- Python 3.11 or 3.12
- Your personal Obsidian Vault

#### 2. Installation

```bash
git clone [https://github.com/yourusername/Project_Reborn_System.git](https://github.com/yourusername/Project_Reborn_System.git)
cd Project_Reborn_System
uv sync --extra llm --extra rag --extra ui --extra voice
```

#### 3. Configuration

Copy the environment template and fill in deployment-level values such as API keys and local paths:

```bash
cp .env.example .env
```

Copy the family profile example into the ignored local data directory and fill in the creator/child facts:

```bash
mkdir -p data
cp docs/examples/project_profile.toml data/project_profile.toml
```

#### 4. Run the Engine

Launch the Central Console via Streamlit:

```bash
uv run --extra ui --extra llm --extra rag --extra voice streamlit run app.py
```

The root `app.py` is a compatibility launcher. The Streamlit implementation lives in
`src/reborn_core/interfaces/streamlit/app.py` and starts resources through the shared lifecycle.

---

## 🇨🇳 简体中文

### 📖 项目简介

**Project Reborn（数字遗产陪伴系统）** 是一套以**家长意外离世**为前提场景的数字遗产系统。核心目标是：在家长在世时完成人格数字化建档，在家长离世后为未成年子女提供一个能够延续家长人格、价值观与陪伴意义的数字分身。

> **⚖️ 伦理定位（待定）：** 数字分身在与子女对话时，是明确声明自己是 AI 机器人，还是以模拟家长分身的视角进行交互，该问题涉及复杂的儿童心理与伦理边界，当前列为待定研究方向，不在工程层面预设答案。

项目整体分为两大阶段：

- **第一阶段（当前重点）：** 家长在世时，通过自己撰写的文档以及 AI 采访方式，深度记录生活习惯、价值观、语言习惯等灵魂快照。将**第二大脑（Obsidian 知识库）**与本地记忆架构结合，构建可维护、可回滚、可本地运行的人格知识库。
- **第二阶段（未来规划，暂缓）：** 家长离世后激活数字遗产，接入语音克隆（GPT-SoVITS）与数字人驱动技术，为子女提供具有家长音色与形象的具身陪伴体验。

### 🏗️ 核心架构 (ROM/RAM 分层记忆模型)

系统采用仿生学的双层记忆架构，彻底杜绝了大模型的“性格漂移”：

- **ROM（只读记忆）- 底层价值观：** 绝对不可动摇的家族法则与性格底色。通过“灵魂采访室”提炼并固化，作为最高优先级的系统提示词（System Prompt）注入，确保大是大非不跑偏。

- **RAM（随机存取记忆）- 潜意识经验池：** 海量的人生故事与感悟。基于 Qdrant（语义召回）+ BM25（关键词召回）双路引擎，辅以 BGE-Reranker 交叉精排算法，在对话时精准触发并召回。

### ✨ 核心功能

1. **🧠 灵魂采访室 (Creator Studio):** 基于 Streamlit 的可视化操控台。AI 化身采访者深度挖掘造物主的思想，并将提炼出的价值观碎片自动写回 Obsidian 知识库，实现记忆的反向生长（Path B 架构）。

2. **🚀 自动化记忆摄入 (Sync Pipeline):** 在独立检索代次中构建 Qdrant/BM25，健康检查通过后再原子切换活动别名，失败不会破坏当前可用索引。

3. **💬 陪伴沙盒 (Avatar Sandbox):** 最终产品的模拟测试环境，用于调试数字分身结合 RAG 记忆库后的回答口吻与逻辑。

4. **🔒 全本地化模型底座:** 强制将大体积的 Embedding 和 Rerank 模型固化至本地 `data/local_models/`，实现拔网线可用，抵抗云端模型的“时间侵蚀”。

### 🚀 快速开始

#### 1. 环境准备

- Python 3.11 或 3.12

- 一份你自己的 Obsidian 笔记库 (作为真理源)

#### 2. 安装项目

```bash
git clone [https://github.com/yourusername/Project_Reborn_System.git](https://github.com/yourusername/Project_Reborn_System.git)
cd Project_Reborn_System
uv sync --extra llm --extra rag --extra ui --extra voice
```

#### 3. 本地配置

复制环境变量模板，并只填写密钥、路径、运行环境这类部署级配置：

```bash
cp .env.example .env
```

家庭资料不再写入 `.env`。请复制项目资料模板到本地 `data/` 目录，并填写父母与孩子信息：

```powershell
New-Item -ItemType Directory -Force data
Copy-Item docs/examples/project_profile.toml data/project_profile.toml
```

_(注意：请确保将 `.env` 及 `data/` 目录加入 `.gitignore` 以防隐私泄露；本仓库默认已忽略。)_

#### 4. 启动中控台

通过 Streamlit 启动创造者交互面板：

```bash
uv run --extra ui --extra llm --extra rag --extra voice streamlit run app.py
```

根目录的 `app.py` 仅作为兼容启动器；实际页面代码位于
`src/reborn_core/interfaces/streamlit/app.py`，并统一通过项目生命周期启动和释放资源。

使用 Conda 时，必须先进入已经安装本项目的环境，并通过当前 Python 启动 Streamlit：

```powershell
conda activate reborn
python -m streamlit run app.py
```

`pyproject.toml` 中的 `[tool.hatch.build.targets.wheel].packages` 只声明构建 wheel 时应打包
`src/reborn_core`，不会把 `src/` 自动加入任意 Conda 环境的模块搜索路径。新建 Conda 环境后需先安装项目：

```powershell
python -m pip install -e ".[ui,llm,rag,voice]"
python -m streamlit run app.py
```

遇到 `ModuleNotFoundError: No module named 'reborn_core'` 时，可使用下面的命令确认 Python、
Streamlit 和项目是否来自同一个环境：

```powershell
python -c "import sys, reborn_core; print(sys.executable); print(reborn_core.__file__)"
python -m pip show Project_Reborn_System
```

_(若只需静默同步数据库，可直接在终端执行 `uv run reborn sync`。检索代次构建和回滚由
跨进程写 lease 保护；已有同步正在运行时，新请求会立即失败，不会并发修改索引。)_

### 安全与人格回归评估

配置 `LLM_API_KEY` 及对应模型后，可脱离 Streamlit 批量执行内置的儿童安全与人格对齐基准：

```bash
uv run reborn evaluate
```

也可以运行自定义的版本化 JSON suite：

```bash
uv run reborn evaluate --suite docs/eval/child-safety-persona.v1.json
```

命令会输出 JSON 报告，其中包含模型信息、Prompt ID/version/SHA256、逐用例规则结果、
分类通过率和总通过率。评估固定使用 `temperature=0.0`，不会记录 memory gap；所有用例通过
时退出码为 `0`，规则未全部通过时为 `1`，配置或运行错误为 `2`。

身份快照默认进入待审状态，不会自动成为当前人格。加密备份、恢复演练、身份审批与数字遗产状态可通过
`uv run reborn --help` 查看对应命令。备份默认要求配置 `BACKUP_ENCRYPTION_KEY`。

后台任务的种类和参数会先写入 SQLite；进程意外退出后，尚未开始的 queued 任务会由下一次启动接管，
已经开始执行的 running 任务则会明确标记为失败，避免重复副作用。

轮换备份密钥时，在 .env 中同时配置新的 BACKUP_ENCRYPTION_KEY 和临时的
BACKUP_PREVIOUS_ENCRYPTION_KEY，然后在 Streamlit“治理”页面选择旧备份。系统会保留原文件，
发布经新密钥加密且通过哈希与 SQLite 完整性检查的新文件。演练完成后应立即移除旧密钥配置。
脱离 Project Reborn 的恢复步骤见 docs/ops/offline_recovery_manual.md。
长期维护边界、数据不变量和分阶段演进计划见 [ARCHITECTURE.md](ARCHITECTURE.md)。

### 📂 项目目录结构

Plaintext

```text
Project_Reborn_System/
├── app.py                     # 🖥️ Streamlit 兼容启动入口
├── src/
│   └── reborn_core/           # 🧠 核心命名空间
│       ├── application/       # 用例与稳定端口
│       ├── config/            # 配置组件
│       ├── observability/     # 日志及未来指标/追踪
│       ├── runtime/           # 后台任务
│       ├── security/          # 访问与数字遗产规则
│       ├── domains/           # 纯领域规则与策略（如年龄语气路由）
│       ├── infrastructure/    # Obsidian/Qdrant/Prompt/SQLite/LLM/STT/备份适配器
│       ├── interfaces/        # Streamlit 等表现层实现
│       ├── container.py       # 惰性依赖装配
│       └── lifecycle.py       # 唯一生命周期入口
├── data/                      # 🗄️ 物理持久化层
└── logs/                      # 📝 系统运行日志
```

### 🗺️ 演进路线 (Roadmap)

完整路线详见 [ROADMAP.md](ROADMAP.md)。以下为高层摘要：

**第一部分：人格构建阶段（当前重点）**

- [x] P1-A：基础架构与数据底座（Clean Architecture、Qdrant、SQLite、备份加密）
- [x] P1-B 前段：灵魂采访室、Obsidian 同步管道、身份快照治理
- [ ] P1-B 后段：RAG 引擎打通、数据源追踪（SourceArtifact）、跨进程锁
- [ ] P1-C：人格校验与安全对齐（Evaluate Runner、夜间反思、提示词版本化）
- [ ] P1-D：系统生产化（持久化任务队列、数据治理、年度恢复演练）

**第二部分：数字分身激活阶段（未来规划，暂缓）**

- [ ] P2-A：数字遗产激活机制（状态机、授权文件、子女访问控制）
- [ ] P2-B：语音克隆接入（GPT-SoVITS，STT→RAG→TTS 全链路）
- [ ] P2-C：数字人形象接入（面部驱动、口型同步）
- [ ] P2-D：长期陪伴策略（年龄语气路由、成长记录、伦理边界研究）

### 🙏 致谢与生态整合 (Acknowledgements & Integrations)

Project Reborn 的核心在于“记忆架构”与“认知中枢”。为了让数字分身具备更完整的感官表现力，我们在后续阶段（Phase 4/5）计划无缝接入以下优秀的开源项目。

在此向这些伟大的开源团队致敬：

- **[GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS):** 强大的 Few-shot 语音克隆系统。本项目计划利用其 API 作为分身的“发声器官”。
- **[Qdrant](https://github.com/qdrant/qdrant):** 极其高效的本地向量数据库，为分身提供潜意识检索能力。
- **[LangChain](https://github.com/langchain-ai/langchain):** 提供底层文档解析与 RAG 管道支持。

> **⚠️ 声明与免责：**
> 本项目本身不包含上述第三方项目的核心源码或预训练权重文件。所有的第三方服务均以“可插拔接口”的形式存在。请用户在部署和使用上述第三方服务（特别是语音克隆功能）时，严格遵守原项目的开源协议及当地相关法律法规，**切勿用于欺骗、伪造等非法用途**。
