# 🌌 Project Reborn (数字分身核心引擎)

[![Python 3.11-3.12](https://img.shields.io/badge/python-3.11--3.12-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20DB-red)](https://qdrant.tech/)
[![LangChain](https://img.shields.io/badge/LangChain-Integration-green)](https://python.langchain.com/)

[🇨🇳 简体中文](#-简体中文) | [🇬🇧 English](#-english)

---

## 🇬🇧 English

### 📖 About The Project
**Project Reborn** is a digital companionship system aimed at providing a digital lifeform to accompany a child growing up in the event of their parents' early passing. It is designed as a highly personalized two-phase private customization product:
- **Phase 1 (Current Development):** Recording the parents' living habits, values, and language patterns through handwritten texts and AI interviews, bridging the creator's **Second Brain (Obsidian)** with a core memory architecture.
- **Phase 2 (Future Integration):** Connecting with digital human avatars and voice cloning technologies to create an interactive, autonomous digital entity.

Ultimately, it acts as an interactive **Avatar Sandbox**, aiming to provide continuous companionship, guidance, and preserving a human creator's core legacy.

### 🏗️ Core Architecture (Hierarchical Memory)
The engine utilizes a biologically inspired memory architecture:
* **ROM (Read-Only Memory) - The Core Values:** Hard-coded, immutable principles extracted via AI interviews, injected directly into the LLM's System Prompt to prevent "persona drift".
* **RAM (Random Access Memory) - The Subconscious:** A dynamic pool of past stories, experiences, and thoughts, powered by a hybrid retrieval system (Qdrant Dense Vector + BM25 Sparse Vector) and refined by Cross-Encoder Reranking.

### ✨ Key Features
1.  **Soul Interview Room (创造者引擎):** An interactive Streamlit console where the AI interviews the creator to unearth latent values and automatically synthesizes them into Markdown files within the Obsidian vault.
2.  **Seamless Knowledge Ingestion:** Automatically parses YAML frontmatter, ignores system noise, executes dual-layer chunking on Obsidian `.md` files, and sinks them into local Qdrant/BM25 databases.
3.  **Avatar Sandbox:** The testing ground for the digital twin, utilizing local RAG and DeepSeek API to simulate responses.
4.  **100% Offline Capable Infrastructure:** Designed to keep core embedding (`BGE-small-zh-v1.5`) and reranking (`BGE-reranker-base`) models fully local to resist "time erosion".

### 🚀 Getting Started

#### 1. Prerequisites
* Python 3.11 or 3.12
* Your personal Obsidian Vault

#### 2. Installation
```bash
git clone [https://github.com/yourusername/Project_Reborn_System.git](https://github.com/yourusername/Project_Reborn_System.git)
cd Project_Reborn_System
uv sync --extra llm --extra rag --extra ui --extra voice
```

#### 3. Configuration

Copy the environment template and fill in deployment-level values such as API keys and local paths:

```
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

**Project Reborn (数字生命引擎)** 的最终目标是一个数字陪伴系统，其核心愿景是在孩子幼年时若父母不幸离世，能够提供一个陪伴孩子成长的数字生命体。如果未来商业化，这将是一个双阶段的私人定制产品。项目整体分为两个阶段：

- **第一阶段（当前进行中）：** 通过手写记录以及 AI 采访等方式，深度记录父母的生活习惯、价值观、语言习惯等。将创作者的**第二大脑（Obsidian 知识库）**与底层记忆模型结合，永久封存底层逻辑与人生故事。
- **第二阶段（未来规划）：** 接入数字人、语音克隆等前端技术栈，结合动态交互的**陪伴沙盒**，最终生成一个具有真实人格厚度、能够独立思考并提供陪伴的数字实体。

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

_(若只需静默同步数据库，可直接在终端执行 `uv run reborn sync`)_

身份快照默认进入待审状态，不会自动成为当前人格。加密备份、恢复演练、身份审批与数字遗产状态可通过
`uv run reborn --help` 查看对应命令。备份默认要求配置 `BACKUP_ENCRYPTION_KEY`。

长期维护边界、数据不变量和分阶段演进计划见 [ARCHITECTURE.md](ARCHITECTURE.md)。

### 📂 项目目录结构

Plaintext

```
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

- [x] Phase 1: 工业级目录重构与底层向量库/SQLite搭建

- [x] Phase 2: 灵魂采访室落地与 Obsidian 数据闭环 (Path B)

- [ ] Phase 3: AvatarService/RAG 核心逻辑与陪伴沙盒持续打通

- [ ] Phase 4: 接入 GPT-SoVITS 本地音色克隆

- [ ] Phase 5: 数字人前端（面部/口型驱动）

### 🙏 致谢与生态整合 (Acknowledgements & Integrations)

Project Reborn 的核心在于“记忆架构”与“认知中枢”。为了让数字分身具备更完整的感官表现力，我们在后续阶段（Phase 4/5）计划无缝接入以下优秀的开源项目。

在此向这些伟大的开源团队致敬：
* **[GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS):** 强大的 Few-shot 语音克隆系统。本项目计划利用其 API 作为分身的“发声器官”。
* **[Qdrant](https://github.com/qdrant/qdrant):** 极其高效的本地向量数据库，为分身提供潜意识检索能力。
* **[LangChain](https://github.com/langchain-ai/langchain):** 提供底层文档解析与 RAG 管道支持。

> **⚠️ 声明与免责：**
> 本项目本身不包含上述第三方项目的核心源码或预训练权重文件。所有的第三方服务均以“可插拔接口”的形式存在。请用户在部署和使用上述第三方服务（特别是语音克隆功能）时，严格遵守原项目的开源协议及当地相关法律法规，**切勿用于欺骗、伪造等非法用途**。
