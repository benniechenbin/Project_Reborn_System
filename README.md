# 🌌 Project Reborn (数字分身核心引擎)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20DB-red)](https://qdrant.tech/)
[![LangChain](https://img.shields.io/badge/LangChain-Integration-green)](https://python.langchain.com/)

[🇨🇳 简体中文](#-简体中文) | [🇬🇧 English](#-english)

---

## 🇬🇧 English

### 📖 About The Project
**Project Reborn** is a highly personalized "Digital Twin" engine. Unlike standard knowledge base systems or enterprise RAG bots, this system is designed to capture, digest, and preserve a human creator's core values, memories, and cognitive patterns, ultimately generating an autonomous digital entity.

It acts as a bridge between a creator's **Second Brain (Obsidian)** and an interactive **Avatar Sandbox**, aiming to provide continuous companionship and guidance for the creator's child or family members.

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
* Python 3.10+
* Your personal Obsidian Vault

#### 2. Installation
```bash
git clone [https://github.com/yourusername/Project_Reborn_System.git](https://github.com/yourusername/Project_Reborn_System.git)
cd Project_Reborn_System
pip install -r requirements.txt
```

#### 3. Configuration

Copy the environment template and fill in your keys and absolute paths:

```
cp .env.example .env
```

#### 4. Run the Engine

Launch the Central Console via Streamlit:


```bash
streamlit run frontend/app.py
```

---

## 🇨🇳 简体中文

### 📖 项目简介

**Project Reborn (数字生命引擎)** 是一个高度个性化的“数字分身”构建系统。与传统的企业级知识库或普通聊天机器人不同，本系统旨在捕获、消化和永久封存创造者的底层逻辑、核心价值观与人生故事。

它将创作者的**第二大脑（Obsidian 知识库）**与动态交互的**陪伴沙盒**完美桥接，最终目标是为创作者的子孙后代提供一个具有真实人格厚度、能够独立思考并陪伴成长的数字实体。

### 🏗️ 核心架构 (ROM/RAM 分层记忆模型)

系统采用仿生学的双层记忆架构，彻底杜绝了大模型的“性格漂移”：

- **ROM（只读记忆）- 底层价值观：** 绝对不可动摇的家族法则与性格底色。通过“灵魂采访室”提炼并固化，作为最高优先级的系统提示词（System Prompt）注入，确保大是大非不跑偏。
    
- **RAM（随机存取记忆）- 潜意识经验池：** 海量的人生故事与感悟。基于 Qdrant（语义召回）+ BM25（关键词召回）双路引擎，辅以 BGE-Reranker 交叉精排算法，在对话时精准触发并召回。
    

### ✨ 核心功能

1. **🧠 灵魂采访室 (Creator Studio):** 基于 Streamlit 的可视化操控台。AI 化身采访者深度挖掘造物主的思想，并将提炼出的价值观碎片自动写回 Obsidian 知识库，实现记忆的反向生长（Path B 架构）。
    
2. **🚀 自动化记忆摄入 (Sync Pipeline):** 一键扫描指定 Obsidian 目录，自动清洗 YAML 乱码，执行文档深度切片，并双写至向量库与稀疏索引库。
    
3. **💬 陪伴沙盒 (Avatar Sandbox):** 最终产品的模拟测试环境，用于调试数字分身结合 RAG 记忆库后的回答口吻与逻辑。
    
4. **🔒 全本地化模型底座:** 强制将大体积的 Embedding 和 Rerank 模型固化至本地 `data/local_models/`，实现拔网线可用，抵抗云端模型的“时间侵蚀”。
    

### 🚀 快速开始

#### 1. 环境准备

- Python 3.10 或更高版本
    
- 一份你自己的 Obsidian 笔记库 (作为真理源)
    

#### 2. 安装项目


```bash
git clone [https://github.com/yourusername/Project_Reborn_System.git](https://github.com/yourusername/Project_Reborn_System.git)
cd Project_Reborn_System
pip install -r requirements.txt
```

#### 3. 环境变量配置

复制配置模板并填写你的大模型 API 密钥以及电脑上的绝对路径：


```bash
cp .env.example .env
```

_(注意：请确保将 `.env` 及 `data/` 目录加入 `.gitignore` 以防隐私泄露)_

#### 4. 启动中控台

通过 Streamlit 启动创造者交互面板：


```bash
streamlit run frontend/app.py
```

_(若只需静默同步数据库，可直接在终端执行 `python scripts/run_sync.py`)_

### 📂 项目目录结构

Plaintext

```
Project_Reborn_System/
├── frontend/             # 🖥️ Streamlit 交互式中控台
├── backend/              # 🧠 核心大脑层
│   ├── brain/            # LLM 路由调度与 System Prompts
│   ├── memory/           # 向量库(Qdrant/BM25)与 SQLite 控制器
│   ├── knowledge_base/   # Obsidian 深度解析与清洗管道
│   └── core/             # 全局配置(Settings)与日志(Logger)
├── data/                 # 🗄️ 物理持久化层 (数据库与本地大模型保险箱)
└── scripts/              # 🛠️ 独立执行的自动化运维脚本
```

### 🗺️ 演进路线 (Roadmap)

- [x] Phase 1: 工业级目录重构与底层向量库/SQLite搭建
    
- [x] Phase 2: 灵魂采访室落地与 Obsidian 数据闭环 (Path B)
    
- [ ] Phase 3: RAG 引擎核心逻辑 (rag_engine.py) 与沙盒打通
    
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