---
created: 2026-04-17 10:34
updated: 2026-04-17 10:34
status: 📥 待处理
tags:
  - Project_Reborn
aliases: []
---

# 🧬 Project Reborn (数字分身) - Master Plan & Architecture

> [!abstract] 概要
**文档使命：** 本文档是 Project Reborn 系统的终极蓝图与开发上下文记录。用于在长周期的开发中，对齐 AI 编程助手与开发者的认知，防止架构偏移，并记录演进路线。
> 
> **终极目标：** 打造一个具备视觉（对口型虚拟影像）、听觉（真实克隆音色）、认知（保留开发者习惯与价值观的 RAG 知识库）和记忆（长短期记忆与自我反思）的数字分身陪伴平台。
> 
> **硬件架构：** Mac（主控端、前端、日常服务） + Windows（强算力节点、模型推理端）。

---
## 📝 内容

## 🏗️ 第一部分：终态系统目录树设计 (Architecture Blueprint)

整个系统将采用**前后端分离 + 微服务调度**的架构，以适应未来新技术的无缝接入（例如随时替换更先进的 TTS 或唇形同步模型）。

Plaintext

```
Project_Reborn_System/
├── frontend/                  # 🖥️ 前端交互层 (Mac)
│   ├── app.py                 # Streamlit 仪表盘与管理后台 (当前)
│   ├── chat_ui.py             # 核心对话界面 (文本/语音交互)
│   ├── avatar_view.py         # 虚拟分身视频流渲染界面 (未来形态)
│   └── assets/                # 前端静态资源 (CSS, UI 图标)
│
├── backend/                   # 🧠 后端核心大脑 (Mac)
│   ├── api/                   # FastAPI 接口层 (供前端或外部调用)
│   ├── core/                  # 系统核心配置
│   │   ├── settings.py        # Pydantic 环境变量管理 (双机IP配置)
│   │   └── logger.py          # 全局日志记录
│   ├── brain/                 # 核心思考中枢
│   │   ├── llm_router.py      # 大模型路由 (调度本地/云端 LLM)
│   │   └── prompt_templates/  # 性格、价值观、回复逻辑的 Prompt 管理
│   ├── memory/                # 💾 记忆管理机制
│   │   ├── short_term.py      # 短期记忆/滑动窗口 (对话上下文)
│   │   ├── long_term.py       # 长期记忆特征提取 (存入 Qdrant)
│   │   ├── memory_manager.py  # 记忆合并与反思守护进程
│   │   └── obsidian_writer.py # 记忆落盘实体化 (写入本地 Inbox)
│   ├── rag/                   # 📚 知识检索增强
│   │   ├── vector_qdrant.py   # 向量库双路召回与管理
│   │   └── document_pipeline.py# Obsidian 数据提取与清洗流水线
│   └── clients/               # 🔌 外部/算力机服务调用客户端
│       ├── tts_client.py      # 调用 Windows 端的 GPT-SoVITS
│       └── avatar_client.py   # 调用 Windows 端的唇形视频生成服务
│
├── compute_node/              # 🚀 算力机专用脚本 (部署在 Windows)
│   ├── tts_api_wrapper.py     # GPT-SoVITS 的 API 包装启动器
│   └── avatar_service/        # 视频生成/口型对齐微服务
│
├── data/                      # 🗄️ 本地数据存储 (Mac)
│   ├── sqlite/                # 结构化数据 (指标统计、聊天记录索引)
│   ├── qdrant_db/             # 向量数据库持久化目录
│   └── cache/                 # 临时音频、视频缓存
│
├── scripts/                   # 🛠️ 自动化与运维脚本
│   ├── run_sync.py            # Obsidian 知识库同步脚本
│   └── daily_reflection.py    # 每日记忆整理定时任务
│
├── docs/                      # 📄 项目开发文档
│   └── Project_Reborn_Master_Plan.md # 本文档
│
├── .env                       # 环境变量 (IP, 路径, API Keys，不入版本库)
├── requirements.txt           # Python 依赖清单
└── README.md                  # 项目简介
```

---

## 🗺️ 第二部分：项目演进阶段计划 (Phased Roadmap)

为了避免陷入“什么都想做”的泥潭，我们将这个宏大的愿景拆解为五个可执行的阶段：

### 🟢 Phase 1: 基础设施与静态记忆底座 (Foundation) - 【当前所处阶段】

- **目标：** 让系统能够精准读取并消化你的数字遗产（笔记、音频时长等），建立统计指标与检索能力。
    
- **已完成：** SQLite 数据结构建立、Qdrant 向量库（双路召回）、Obsidian 笔记流转读取、Streamlit 数据监控看板、回写 Obsidian 统计面板。
    
- **下一步行动：** 修复双端环境依赖（NumPy/Torch 冲突），重构 `settings.py`，实现 `obsidian_writer.py` 确保系统拥有向本地生成结构化 Markdown 记忆的能力。
    

### 🟡 Phase 2: 灵魂注入与文字交互 (Personality & Text-based Chat)

- **目标：** 让分身“活”过来，具备你的说话口吻，并拥有对话上下文。
    
- **核心开发：**
    
    - 构建 `backend/brain`：设计深度 Prompt，植入你的核心价值观和语言习惯。
        
    - 构建 `backend/memory`：实现短期聊天记忆（SQLite）与长期事实记忆的提取逻辑。
        
    - 开发基于文本的前端聊天界面。
        
- **验收标准：** 可以通过纯文字与系统进行符合你人设的流畅对答，且系统能记住多轮对话的上下文，并将重要感悟写入 Obsidian。
    

### 🟠 Phase 3: 声音复刻与双机协同 (Voice Integration)

- **目标：** 让分身拥有你的声音。
    
- **核心开发：**
    
    - **Windows 端：** 部署并启动 GPT-SoVITS 的推理 API。
        
    - **Mac 端：** 编写 `tts_client.py`，实现大模型输出文本 -> 请求 Windows API -> 接收音频流 -> Mac 前端播放的完整链路。
        
- **验收标准：** 文字对话能够同步输出高拟真度的克隆语音。
    

### 🔴 Phase 4: 视觉化与动态口型 (Avatar & Lip-Sync)

- **目标：** 生成视频流，让分身具备面部表情和对口的动作。
    
- **核心开发：**
    
    - 考察并选择轻量级或开源的 2D/3D 数字人驱动框架（如 SadTalker, MuseTalk 等）。
        
    - 在 Windows 算力机上建立视频推理服务。
        
    - 前端 `avatar_view.py` 的流媒体播放对接。
        
- **验收标准：** 输入文本，系统返回带有正确口型同步的视频画面。
    

### 🟣 Phase 5: 长期陪伴与自主进化 (Autonomous Evolution)

- **目标：** 从“被动应答”走向“主动关怀”和自我成长。
    
- **核心开发：**
    
    - 记忆整理守护进程：夜间自动总结近期对话，更新 Qdrant 中的长期记忆权重。
        
    - 主动触发机制：基于时间线或特殊事件（如孩子生日），自动通过微信、邮件或前端 UI 推送关怀信息。
        

---

## 🤝 第三部分：AI 对齐协议 (Alignment Protocol)

在未来的新对话中，为了让我（AI）迅速进入状态，请按照以下格式唤醒我：

> **唤醒口令示例：**
> 
> "查阅 `Project_Reborn_Master_Plan.md`。我们目前处于 **Phase 1**，当前任务是开发 `backend/memory/obsidian_writer.py`。请帮我编写这个组件的代码，要求如下..."

---

## 🔗 相关引用
-