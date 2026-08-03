# 任务单：Project Reborn 本周迭代规划 (2026-W32)

## 📅 迭代周期

- **时间范围**：2026-08-03 至 2026-08-09
- **核心目标**：构建家长语音语料库采集防线，并将后台任务处理器彻底拆分为独立守护进程（Standalone Worker）。

---

## 🎯 核心战役

### 🎙️ 前置战役: 语音素材语料库构建 (Voice Dataset Collection)

- **性质**：领域资产积累与表现层功能扩展[cite: 11]
- **代码落脚点**：
  - `src/reborn_core/interfaces/streamlit/app.py` (新增“声音档案”录制界面)
  - `src/reborn_core/application/services/voice_archive.py` (新建录音归档用例)
- **具体行动**：
  1. **前端录制面板**：在 Streamlit 控制台中新增一个专属的录音模块，提供预设的文本朗读脚本（涵盖多情绪、多语境），供家长在线录制[cite: 11]。
  2. **资产合规追踪**：将录制的长音频文件持久化至本地存储，并将其强制纳入 `SourceArtifact` 管理体系[cite: 11]。为这些音频打上明确的授权标签与敏感级别，确保它们在未来仅被授权用于训练指定的音色模型。

---

### ⚙️ Phase 1-D: 系统生产化与运维 (分布式运行时)

- **性质**：运行时架构升级[cite: 11]
- **代码落脚点**：
  - `src/reborn_core/__main__.py` (新增 `worker` CLI 命令)[cite: 11]
  - `src/reborn_core/runtime/tasks.py` (彻底重构现有的线程池逻辑)[cite: 11]
- **具体行动**：
  1. **UI 与计算彻底物理隔离**：剥离原本依附于 Streamlit Web 进程的 `BackgroundTaskRunner`。未来，Streamlit 仅向 SQLite 的 `background_tasks` 表写入状态（Queued）[cite: 11]。
  2. **独立 Worker 守护进程**：在 CLI 入口中新增 `uv run reborn worker` 命令。该进程将持续轮询数据库，拾取未完成的任务（如大模型访谈提炼、全量知识库向量同步），并在完成或异常时更新状态。
  3. **崩溃恢复 (Crash Recovery) 升级**：优化任务分配逻辑，支持独立 Worker 意外宕机重启后，能够安全接管并继续处理残留的排队任务[cite: 11]。

---

## 🧪 验证与测试规范 (Test Plan)

1. **语料合规性断言**：编写集成测试，模拟音频上传流程，断言文件不仅落盘成功，且在 SQLite 的 `source_artifacts` 表中生成了校验哈希值与正确的 `audio_dataset` 类型标签。
2. **Worker 拾取与隔离测试**：通过 Python 的 `subprocess` 启动独立的 `reborn worker` 进程，同时在主进程中快速并发提交 10 个测试耗时任务，断言所有任务能跨进程被正确拾取、执行并变更状态。
3. **架构纪律扫描**：运行 `uv run ruff check .` 与 `uv run mypy .`，确保新增的 `voice_archive` 服务严格遵从 DDD 依赖倒置原则。
