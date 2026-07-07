# 任务单：Project Reborn 本周迭代规划 (2026-W28)

## 📅 迭代周期
* **时间范围**：2026-07-06 至 2026-07-12
* **核心目标**：完成 RAG 沙盒对线与感官调优，启动模块化架构重构。

---

## 🎯 核心战役

### Phase 1: 灵魂与感官调优 (Sprint 2 收尾)

#### 任务一：沙盒“灵魂对线”实测
* **性质**：功能验证 / 数据采集
* **代码落脚点**：`app.py` (Streamlit 控制台)
* **具体行动**：
    1. 启动陪伴沙盒环境。
    2. 针对 16 篇核心记忆内容，发起多角度模拟对话。
    3. **关键指标记录**：紧盯后台终端日志，记录 `BGE-Reranker` 对真实日记片段的 `rerank_score` 打分区间。

#### 任务二：相似度硬拦截与 Prompt 元编程
* **性质**：算法调优 / 提示词工程
* **代码落脚点**：`src/reborn_core/domains/brain/rag_engine.py` 与 `src/reborn_core/domains/brain/prompts/`
* **具体行动**：
    1. 根据任务一的日志分数，标定 `rag_engine.py` 中的相似度拦截阈值。
    2. 若发现回答有“机器味”，在 `AVATAR_RAG_FRAMEWORK` 中添加强制的口语化约束锚点。

---

### Phase 2: 纯正六边形架构重构 (Phase 1 启动)

#### 任务三：表现层彻底解耦 (UI 分离)
* **性质**：架构重构
* **代码落脚点**：`app.py` -> `src/reborn_core/interfaces/streamlit/`
* **具体行动**：
    1. 将表现层代码从根目录迁移至 `interfaces/streamlit/` 目录。
    2. 确保 `lifecycle` 入口可正确加载分离后的 UI 组件。

#### 任务四：拆分单体 DBManager (仓储隔离)
* **性质**：架构重构
* **代码落脚点**：`src/reborn_core/domains/memory/relational/db_manager.py`
* **具体行动**：
    1. 将 `DBManager` 拆分为独立 Repository 接口（身份快照、后台任务、同步历史等）。
    2. 引入独立的版本化迁移运行器。

---

## 🏛️ 备注 (ADR 关联)
* 本次重构涉及架构边界变更，相关决策已归档至 `docs/rfc/` 或 `docs/adr/`。
* 严禁在任务执行过程中过度设计，保持系统的本地运行简洁性。
