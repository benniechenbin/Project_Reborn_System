# 任务单：Project Reborn 本周迭代规划 (2026-W32)

## 📅 迭代周期

- **时间范围**：2026-08-03 至 2026-08-09
- **核心目标**：实现多模态语音接入（GPT-SoVITS），并将后台任务处理器拆分为独立守护进程（Standalone Worker）。

---

## 🎯 核心战役

### 🗣️ Phase 4/5: 多模态接入 (语音克隆引擎)

#### 任务一：TTS 端口定义与基础设施适配 (GPT-SoVITS Adapter)

- **性质**：领域模型扩展与基础设施接入[cite: 7]
- **代码落脚点**：
  - `src/reborn_core/application/ports.py` (新增 `TextToSpeechPort` 接口定义)[cite: 7]
  - `src/reborn_core/infrastructure/voice/sovits_engine.py` (新建 GPT-SoVITS 适配器实现)
  - `src/reborn_core/config/settings.py` (新增 TTS 相关的 API Endpoint 配置)[cite: 7]
- **具体行动**：
  1. **定义契约**：在 `ports.py` 中声明 TTS 接口，确保应用层只依赖标准字节流输出，不耦合任何具体语音模型[cite: 7]。
  2. **实现适配器**：编写封装 GPT-SoVITS 本地推理 API 的客户端。该组件仅负责将沙盒生成的文本，转换为带有个人真实音色特征的音频流。
  3. **容器装配**：在 `container.py` 中将 TTS 引擎作为基础设施资源进行惰性加载，并通过配置开关控制其启用状态[cite: 7]。

#### 任务二：沙盒多模态交互升级 (Sandbox Voice Feedback)

- **性质**：表现层与应用层集成[cite: 7]
- **代码落脚点**：
  - `src/reborn_core/application/services/avatar.py` (增强回复能力)[cite: 7]
  - `src/reborn_core/interfaces/streamlit/app.py` (沙盒界面支持音频播放)[cite: 7]
- **具体行动**：
  1. 升级 `AvatarService` 的调用逻辑，当开启语音模式时，同步触发 TTS 引擎生成伴随语音。
  2. 在 Streamlit 的 `render_sandbox` 界面中，当接收到大模型的文本回复后，自动渲染对应的 `<audio>` 播放组件，实现宁宁与分身的“看、听、聊”三位一体交互[cite: 7]。

---

### ⚙️ Phase 4: 高可用生产化 (分布式运行时)

#### 任务三：独立任务守护进程 (Standalone Worker)

- **性质**：运行时架构升级[cite: 7]
- **代码落脚点**：
  - `src/reborn_core/__main__.py` (新增 `worker` CLI 命令)[cite: 7]
  - `src/reborn_core/runtime/tasks.py` (解耦现有的线程池逻辑)[cite: 7]
- **具体行动**：
  1. **剥离 UI 线程**：将原本依附于 Streamlit 进程的 `BackgroundTaskRunner` 升级为可独立运行的实体[cite: 7]。
  2. **CLI 守护进程**：在 CLI 入口中新增 `uv run reborn worker` 命令。系统在生产模式下，UI 仅负责向 SQLite 写入任务状态（Queued），而真正的记忆切片、大模型总结由背后持续轮询的独立 Worker 进程拾取并执行[cite: 7]。

---

## 🧪 验证与测试规范 (Test Plan)

1. **TTS 适配器隔离测试**：编写单元测试拦截 GPT-SoVITS 的网络请求，验证配置缺失或模型掉线时，系统能优雅降级回纯文本模式，不引发全局崩溃。
2. **Worker 拾取基准测试**：启动独立的 `reborn worker` 进程，并通过 CLI 推送 10 个模拟的 `memory_sync` 任务，断言所有任务都能被正确轮询、执行、并更新 SQLite 状态[cite: 7]。
3. **架构边界扫描**：运行 `uv run ruff check .` 与 `uv run mypy .`，确保新增的 `voice` 模块完全符合单向依赖规则，未对核心的 `domains` 层产生任何污染[cite: 7]。
