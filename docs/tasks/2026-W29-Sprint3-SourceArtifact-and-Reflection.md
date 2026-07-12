# 任务单：Project Reborn 本周迭代规划 (2026-W29)

## 📅 迭代周期
* **时间范围**：2026-07-13 至 2026-07-19
* **核心目标**：实现数据源追踪建模 (SourceArtifact)，并将夜间反思机制剥离为独立用例。
cd
---

## 🎯 核心战役

### Phase 2: 数据安全与数据模型演进

#### 任务一：数据源追踪建模 (SourceArtifact)
* **性质**：数据库迁移与模型扩展
* **代码落脚点**：`src/reborn_core/application/models.py` 与 `src/reborn_core/infrastructure/database/`
* **具体行动**：
    1. 在数据库中为原始物料（音频、访谈、外源知识）增加独立的 `source_artifacts` 表，支持内容哈希校验、授权范围和敏感级别[cite: 6]。
    2. 在 `migrations.py` 中新增 `_migration_005_source_artifacts`。
    3. 创建对应的 `SQLiteSourceArtifactRepository` 适配器。

---

### Phase 3: 核心业务深度演进

#### 任务二：夜间反思独立用例拆分 (Nightly Reflection)
* **性质**：领域服务解耦
* **代码落脚点**：`src/reborn_core/application/services/identity.py` 与 `src/reborn_core/application/services/reflection.py` (新建)
* **具体行动**：
    1. 将 `run_nightly_reflection` 逻辑从现有的 `IdentityGovernanceService` 中彻底拆除[cite: 6]。
    2. 封装为独立的后台作业服务（如 `ReflectionService`）[cite: 6]。

#### 任务三：反思源与数据追踪绑定
* **性质**：业务逻辑集成
* **代码落脚点**：`ReflectionService`
* **具体行动**：
    1. 确保分析产生的反思源，强制关联到对应的 `SourceArtifact`[cite: 6]。
    2. 设定业务拦截规则：只有具备稳定价值观的快照候选，才允许进入人机审批流程（`pending_review` 状态）[cite: 6]。

---

## 🏛️ 备注
* 所有 SQLite Schema 的变更必须通过 `MigrationRunner` 进行仅向前迁移，并通过临时数据库完成测试验证[cite: 6]。
* 严格遵守 `AGENTS.md` 中的架构依赖方向，Repository 实现不可反向污染 application 层[cite: 6]。
