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

---

## 实施与验收记录（2026-08-04）

### 已完成

- SQLite migration v6 新增 `source_artifacts`，记录 `audio_dataset` 文件路径、大小、SHA-256、授权用途、目标音色模型、高敏级别和朗读脚本元数据。
- 新增 `VoiceArchiveService`、Repository/存储端口及本地原子 WAV 存储；数据库写入失败会清理本次新建文件。
- Streamlit 新增“声音档案”页面和六类朗读脚本，使用原生 `st.audio_input` 的 48 kHz 录音；语音速记使用 16 kHz，并移除 `audio-recorder-streamlit`。
- 后台运行时拆分为无执行资源的 `TaskQueue` 和独立 `BackgroundTaskWorker`；Streamlit 只入队，`uv run reborn worker` 独占 SQLite 轮询和受控线程池。
- Worker 启动时保留 queued 任务并将遗留 running 任务标记失败；同类型任务默认保持单例，可通过显式 `allow_parallel=True` 并发提交。
- `reborn sync`、`reborn backup` 与 `scripts/run_sync.py` 保持一次性同步命令语义；README 和架构文档已更新双进程运行方式。

### 验收

- targeted tests：40 passed，覆盖 v6 迁移、语音归档合规/补偿、10 个同类型任务、真实 Worker 子进程、生命周期隔离、Streamlit 和架构边界。
- 完整测试：158 passed，1 个第三方 `pkg_resources` 弃用警告。
- 静态检查：`ruff check .` 全通过；`mypy .` 对 103 个源码文件零问题。
- 构建：`uv build` 成功生成 sdist 与 wheel。
- 环境备注：pytest 汇总和退出码均为 0；退出阶段 Windows 原生 pyarrow/sklearn 依赖链仍打印一次 access violation 堆栈，与上一迭代记录的环境现象一致，未造成测试失败。

### 边界

- 未实现音色训练、语音克隆、音频切片、降噪或 running 任务自动重试。
- 未修改现有用户音频、SQLite 数据、向量索引、备份或 Obsidian 源文件。
- **具体行动**：
  1. **UI 与计算彻底物理隔离**：剥离原本依附于 Streamlit Web 进程的 `BackgroundTaskRunner`。未来，Streamlit 仅向 SQLite 的 `background_tasks` 表写入状态（Queued）[cite: 11]。
  2. **独立 Worker 守护进程**：在 CLI 入口中新增 `uv run reborn worker` 命令。该进程将持续轮询数据库，拾取未完成的任务（如大模型访谈提炼、全量知识库向量同步），并在完成或异常时更新状态。
  3. **崩溃恢复 (Crash Recovery) 升级**：优化任务分配逻辑，支持独立 Worker 意外宕机重启后，能够安全接管并继续处理残留的排队任务[cite: 11]。

---

## 🧪 验证与测试规范 (Test Plan)

1. **语料合规性断言**：编写集成测试，模拟音频上传流程，断言文件不仅落盘成功，且在 SQLite 的 `source_artifacts` 表中生成了校验哈希值与正确的 `audio_dataset` 类型标签。
2. **Worker 拾取与隔离测试**：通过 Python 的 `subprocess` 启动独立的 `reborn worker` 进程，同时在主进程中快速并发提交 10 个测试耗时任务，断言所有任务能跨进程被正确拾取、执行并变更状态。
3. **架构纪律扫描**：运行 `uv run ruff check .` 与 `uv run mypy .`，确保新增的 `voice_archive` 服务严格遵从 DDD 依赖倒置原则。
