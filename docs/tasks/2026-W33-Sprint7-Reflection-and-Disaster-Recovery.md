# 任务单：Project Reborn 本周迭代规划 (2026-W33)

## 📅 迭代周期

- **时间范围**：2026-08-10 至 2026-08-16
- **核心目标**：完成第一阶段终极收官，彻底剥离夜间反思机制，并编制跨越时间周期的离线灾备操作手册。

---

## 🎯 核心战役

### 实施契约与现状修正（2026-08-10）

- Sprint 5 已交付 `scripts/offline_restore.py` 和
  `docs/ops/offline_recovery_manual.md`；本期对其做契约补强、隔离黑盒演练和验收，
  不重复新建同名交付物。
- “稳定价值观快照”统一指当前 `active=True` 且状态为 `approved` 的
  `IdentitySnapshot`。夜间反思在来源归档与 Worker 执行两个时点都必须满足该条件。
- CLI 仅在操作者显式传入 `--confirm-authorized` 时自动归档聊天记录；
  该确认表示操作者已获得将记录用于身份反思的授权。
- `nightly_reflection` 队列载荷只保存 `SourceArtifact` ID，不携带高敏感聊天正文。
  来源物必须通过类型、授权用途、授权目标、路径、字节数和 SHA-256 校验后
  才可用于生成 `pending_review` 快照。
- 本期不新增定时调度器或 Streamlit 入口；仅交付可由人工 CLI 或外部计划任务
  触发的持久化后台作业。

### 🧠 Phase 3: 核心业务深度演进 (独立认知解耦)

#### 任务一：夜间反思独立用例拆分与溯源绑定 (Nightly Reflection Service)

- **性质**：领域服务解耦与后台异步化[cite: 13]
- **代码落脚点**：
  - `src/reborn_core/application/services/identity.py` (移除遗留的反思逻辑)
  - `src/reborn_core/application/services/reflection.py` (新建业务用例服务)
  - `src/reborn_core/container.py` (注册服务与队列 Handler)
- **具体行动**：
  1. **服务剥离**：将 `IdentityGovernanceService` 中臃肿的反思调度逻辑彻底拆出，封装为独立的后台作业[cite: 13]。
  2. **Worker 接入**：将其注册为可通过 `BackgroundTaskWorker` 轮询处理的异步任务（例如 `kind: "nightly_reflection"`）。
  3. **强溯源绑定**：分析产生的反思源必须强制关联至对应的 `SourceArtifact`[cite: 13]，只有具备合规来源且系统存在稳定价值观快照时，才允许将结果送入 `pending_review` 审批隔离区。

---

### 🛡️ Phase 4: 系统运维与生产化交付 (长期主义底座)

#### 任务二：数字遗产离线恢复操作手册 (Offline Recovery Manual)

- **性质**：极端灾备与文档化[cite: 13]
- **代码落脚点**：
  - `docs/ops/offline_recovery_manual.md` (新建指南文档)
- **具体行动**：
  1. **降维说明**：编写真正符合人性授权、用于极端灾备情况下的离线恢复操作手册[cite: 13]。假定在几十年后，继承人面对毫无运行环境的机器，如何利用标准 Python 和依赖执行 `offline_restore.py`。
  2. **流程规范**：详细记录如何使用 `BACKUP_ENCRYPTION_KEY` 解密 `.zip.fernet`，并提取出 `project_profile.toml` 家庭档案、核心 SQLite 记忆库及 Obsidian 文本。

---

## 🧪 验证与测试规范 (Test Plan)

1. **后台反思流测试**：通过 CLI 触发一个 `nightly_reflection` 模拟任务，断言其能被 `Worker` 进程拾取，并正确生成包含 `SourceArtifact` 的待审快照。
2. **依赖边界核查**：运行静态检查工具（`ruff` 和 `mypy`），确保 `ReflectionService` 的拆分没有引入新的循环依赖或架构越权。
3. **灾备演练复盘**：依照编写完成的 `offline_recovery_manual.md`，在完全断网且不加载项目原始依赖的沙盒容器中，仅通过单一脚本进行一次黑盒解密演练，验证手册的可用性。

## 实施与验收记录（2026-08-10）

### 已完成

- 夜间反思已从 `IdentityGovernanceService` 拆至独立 `ReflectionService`，治理服务只保留人工审批职责。
- CLI 会在显式授权确认后，把规范化聊天 JSON 原子归档为高敏感 SourceArtifact；队列只保存 Artifact ID。
- Worker 在调用 LLM 前复核来源类型、授权、相对路径、大小、SHA-256 和归档时绑定的激活批准快照。
- 新候选固定进入 `pending_review`，使用真实 Artifact ID 作为来源，并记录批准父快照。
- 离线恢复脚本优先读取 `BACKUP_ENCRYPTION_KEY`，手册补充了离线 wheel、校验值和隔离黑盒演练流程。
- 未增加 SQLite migration、定时调度器、Streamlit 入口、运行时依赖，也未修改任何真实用户数据。

### 验收

- targeted tests：44 passed，覆盖反思准入/篡改/路径越界/父快照过期、CLI + 独立 Worker 子进程和隔离恢复。
- 完整测试：180 passed，1 个第三方 `pkg_resources` 弃用警告。
- 静态检查：`uv run ruff check .` 通过；`uv run mypy .` 对 108 个源文件零问题。
- 环境备注：pytest 退出码为 0；测试汇总完成后，Windows 原生 pyarrow/sklearn 依赖链仍打印一次既有
  access violation 堆栈，未造成测试失败。
