# 任务单：Project Reborn 本周迭代规划 (2026-W33)

## 📅 迭代周期

- **时间范围**：2026-08-10 至 2026-08-16
- **核心目标**：完成第一阶段终极收官，彻底剥离夜间反思机制，并编制跨越时间周期的离线灾备操作手册。

---

## 🎯 核心战役

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
