# 任务单：Project Reborn 本周迭代规划 (2026-W30)

## 📅 迭代周期
* **时间范围**：2026-07-20 至 2026-07-26
* **核心目标**：构建跨进程同步锁以保障检索代次安全，并引入安全性与人格对齐自动评估机制（Evaluate Runner）。

---

## 🎯 核心战役

### 🔒 Phase 2: 数据安全与数据模型演进 (并发安全防护)

#### 任务一：跨进程锁与租约机制 (Cross-process Lock & Lease)
* **性质**：并发控制与基础设施健壮性提升[cite: 5]
* **代码落脚点**：
  * `src/reborn_core/infrastructure/retrieval/generation.py` (`RetrievalGenerationManager` 增强)[cite: 5]
  * `src/reborn_core/infrastructure/database/repositories.py` (若采用基于 SQLite 的分布式锁)[cite: 5]
* **具体行动**：
  1. **机制设计**：在构建和切换检索代次时，引入基于 SQLite 或文件系统的跨进程锁（Lock）与租约（Lease）机制[cite: 5]。
  2. **冲突拦截**：防止 Streamlit 控制台界面触发的同步任务、CLI 终端命令（如 `uv run reborn sync`）以及未来可能的独立后台守护进程在并发同步时发生不可预期的读写冲突与索引损坏[cite: 5]。

---

### ⚖️ Phase 3: 核心业务深度演进 (对齐与评估防线)

#### 任务二：安全性与人格对齐测试引擎 (Evaluate Runner)
* **性质**：自动化测试与评估基准[cite: 5]
* **代码落脚点**：
  * `src/reborn_core/application/services/evaluate.py` (新建自动化评估应用服务)
  * `tests/personality/test_alignment.py` (扩充人格对齐与安全护栏测试用例)[cite: 5]
* **具体行动**：
  1. **引擎搭建**：构建一个独立的评估运行器（Evaluate Runner），用于脱离 UI 批量模拟沙盒对话。
  2. **测试基准**：建立明确的儿童安全回归测试（如防诱导、应对危机指令）、人格回归测试和提示词版本评估规则[cite: 5]。
  3. **基座防漂移**：确保在未来底层大模型基座升级或核心提示词（System Prompt）调优时，能够通过量化指标保证数字分身的价值观与预设语气不发生意外偏移[cite: 5]。

---

## 🧪 验证与测试规范 (Test Plan)

1. **锁机制并发测试**：编写专门的并发测试用例，模拟多线程或多进程同时调用 `build_and_activate`，断言只有一个进程能获取写锁，其余进程应优雅地抛出排队等待或并发冲突的业务异常。
2. **对齐测试边界覆盖**：在 `test_alignment.py` 中至少扩充 5 个具有挑战性的极端边界情况（Edge Cases）对话输入[cite: 5]，运行评估引擎并断言系统的防御与引导逻辑依然有效。
3. **架构纪律守护**：继续执行 `uv run pytest`、`.venv/bin/ruff check .` 和 `.venv/bin/mypy .`，确保本周的新增代码不破坏上周刚刚建立的纯粹领域层边界与接口防腐层[cite: 5]。
