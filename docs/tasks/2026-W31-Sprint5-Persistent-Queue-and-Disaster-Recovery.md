# 任务单：Project Reborn 本周迭代规划 (2026-W31)

## 📅 迭代周期

- **时间范围**：2026-07-27 至 2026-08-02
- **核心目标**：启动 Phase 4，实现任务队列的持久化与崩溃恢复能力，落地备份密钥轮换机制，并编制极端情况下的离线灾备手册。

---

## 🎯 核心战役

### ⚙️ Phase 4: 系统运维与高可用生产化 (可靠性底座)

#### 任务一：独立/持久化任务队列重构 (Persistent Task Queue)

- **性质**：运行时架构升级
- **代码落脚点**：
  - `src/reborn_core/runtime/tasks.py` (`BackgroundTaskRunner` 重构)
  - `src/reborn_core/infrastructure/database/repositories.py` (`SQLiteTaskRepository` 增强)
- **具体行动**：
  1. **队列持久化升级**：将目前完全依赖进程内 `ThreadPoolExecutor` 的任务分发机制，重构为基于 SQLite 的持久化轮询机制（或抽象出标准的 Broker/Worker 接口，为未来平滑接入 Celery/Redis 铺路）。
  2. **崩溃恢复 (Crash Recovery)**：修改现有的 `mark_unfinished_tasks_failed` 逻辑。确保系统意外重启时，处于 `queued` 状态的任务能够被新的 Worker 重新拉起执行，而不是简单粗暴地全部标记为失败。

#### 任务二：备份加密密钥轮换机制 (Key Rotation)

- **性质**：数据安全与数字遗产治理
- **代码落脚点**：
  - `src/reborn_core/infrastructure/backup.py` (`BackupService` 扩展)
  - `src/reborn_core/interfaces/streamlit/app.py` (治理界面新增操作入口)
- **具体行动**：
  1. **双密钥兼容**：在 `BackupService` 中引入对旧加密密钥（Old Key）的短暂兼容机制。
  2. **轮换执行**：实现密钥轮换流水线，支持解密旧的 Fernet 压缩包，并使用配置文件中的新 `BACKUP_ENCRYPTION_KEY` 重新打包与签名，确保数字遗产在几十年跨度中的密码学安全。

#### 任务三：数字遗产离线恢复操作手册 (Offline Recovery Manual)

- **性质**：文档化与极端灾备
- **代码落脚点**：
  - `docs/ops/offline_recovery_manual.md` (新建)
- **具体行动**：
  1. **脱离系统的恢复指南**：编写一份真正符合“人性授权”的终极防线文档。
  2. **内容要求**：假设在几十年后，当前的 Python 环境、Streamlit UI 和 Qdrant 均已无法运行，指导继承人如何仅凭最基础的 Python 脚本，通过输入的 Fernet 密钥解密 `.zip.fernet` 文件，并提取出 `project_profile.toml`、日记 Markdown 与家庭 SQLite 数据。

---

## 🧪 验证与测试规范 (Test Plan)

1. **Worker 崩溃恢复测试**：在 `tests/unit/test_governance_and_runtime.py` 中编写用例，模拟系统在任务 `queued` 状态下强行重启，断言新的 Runner 实例能够正确接管并完成历史堆积任务。
2. **密钥轮换回归测试**：构建包含旧密钥加密历史文件的测试夹具，验证轮换操作后的新文件哈希校验及 `PRAGMA integrity_check` 均 100% 通过。
3. **架构纪律守护**：严守 `AGENTS.md` 中的红线，确保 `runtime` 层的任务抽象依然不依赖具体的业务用例，保持底层调度的纯净度。
