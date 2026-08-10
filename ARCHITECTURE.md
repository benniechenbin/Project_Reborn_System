# Project Reborn Architecture Baseline

## 1. 系统定位

**Project Reborn** 是一套以**家长意外离世**为前提场景的数字遗产陪伴系统，整体分为两大部分：

**第一部分（人格构建，当前重点）：** 在家长在世时，通过 AI 采访、手写文档等方式持续采集家长的生活习惯、价值观与语言习惯，建立可本地运行的人格知识库，作为数字分身的底层基座。

**第二部分（数字分身激活，未来规划，暂缓）：** 在家长离世后激活数字遗产，接入语音克隆与数字人技术，为未成年子女提供具有家长人格特征的陪伴型数字分身。

Project Reborn 首先是需要跨越多年保存、验证和迁移的数字遗产系统，其次才是对话产品。

必须长期保持的不变量：

1. 原始资料与 AI 派生内容严格区分，生成内容不能静默成为“事实”。
2. 身份快照、检索索引和对话能力都可替换、可追溯、可回滚。
3. **伦理定位（待定）：** 孩子是否始终明确知道自己在与 AI 数字分身交互，而非现实中的真人——这一问题当前列为待定研究方向，工程层面不预设答案，但系统保留明确 AI 身份声明的能力开关。
4. 未安装某个可选能力时，核心生命周期、治理和其他能力仍可启动。
5. 敏感操作必须经过访问策略，并留下审计记录。

## 2. 当前依赖方向

```text
Streamlit / CLI / future API
             |
             v
application services + ports
             |
             v
domain rules / governance policies
             ^
             |
infrastructure adapters
SQLite / Obsidian / Qdrant / LLM / STT / backup
```

### 正式边界

- `reborn_core.config`：配置组件入口，配置实现统一放在该包内。
- `reborn_core.observability`：日志及未来指标、追踪入口。
- `reborn_core.lifecycle`：唯一拥有启动与关闭副作用的入口。
- `reborn_core.container.Container`：惰性依赖装配，不在构造时加载模型。
- `reborn_core.application`：访谈、同步、身份审批和 Avatar/RAG 用例；只依赖端口、DTO 与纯领域规则，不直接依赖配置实现或基础设施。
- `reborn_core.domains`：纯领域模型、规则和策略，例如家庭资料模型与年龄语气路由；不得包含文件系统、模型加载、Qdrant、Prompt 文件读取或日志等适配器行为。
- `reborn_core.infrastructure`：SQLite、Obsidian、Qdrant/BM25、LLM、STT、Prompt 文件加载、备份等外部资源适配器。
- `reborn_core.runtime`：后台任务运行器与持久化任务状态。
- `reborn_core.security`：访问策略和数字遗产激活规则。

所有入口必须使用 `build_app().start()` 或 `lifespan()`。生命周期副作用只能由
`reborn_core.lifecycle` 管理，项目不再保留第二套启动入口。

父母姓名、孩子姓名、性别和生日等家庭资料属于业务数据，不属于环境变量。真实资料默认存放在
`data/project_profile.toml`，由 `reborn_core.infrastructure.profile` 读取并构造领域层
`FamilyProfile`；`.env` 只保存密钥、路径、运行环境等部署级配置。

### 目录与命名空间结构规范 (Directory & Namespace Layout Rules)

为了保持系统各层级在业务概念上的高度内聚与对齐（认知对齐，避免跨子域的技术组件耦合），本项目遵循以下布局原则：

1. **子域 1:1 镜像关系**：在 `infrastructure/` 层级中，其内部子目录应尽量与领域业务子域对齐（例如：脑部域的纯领域策略位于 `domains/brain/`，其具体 Prompt、LLM 或记忆上下文适配器位于 `infrastructure/prompting/`、`infrastructure/brain/` 或 `infrastructure/memory/`）。
2. **便于垂直切片（Vertical Slice）**：这有助于降低心智检索负担，并在未来需要将系统模块化或微服务化拆分时，能以业务子域为边界进行干净的解耦。
3. **通用基础设施扁平化**：对于跨多个子域的、扁平的通用基础设施（如 `backup.py` 或公共数据库管理），可以直接放置在 `infrastructure/` 的根部。

## 3. 已落地的关键流程

### 生命周期

`RebornApp.start()` 负责日志、目录、版本化 SQLite migration、检索代次�

## 5. 演进路线（架构层面）

完整产品路线见 [ROADMAP.md](ROADMAP.md)。以下为架构层面的分阶段说明。

---

### 第一部分：人格构建阶段（当前重点）

#### P1-A / P1-B 已落地

- **已完成：将 Streamlit 页面拆分**：页面实现已移至 `src/reborn_core/interfaces/streamlit/`；根 `app.py` 仅保留兼容启动职责，资源仍由统一生命周期管理。
- **已完成：规范检索代次注入**：Avatar/RAG 用例由 `Container` 显式注入活动检索代次适配器；Qdrant/BM25、Prompt 文件加载、Obsidian 读写和记忆盲区 JSON 写入均位于 `infrastructure/`。
- **已完成：拆分单体 DBManager**：身份快照、后台任务、同步历史、备份与审计已使用独立 Repository adapter，并由独立 `MigrationRunner` 管理版本化迁移。
- **已完成：SQLite 持久化队列底座**：全部生产后台任务具有可重放载荷，queued 任务可在重启后接管，running 任务不会被盲目重试。
- **已完成：备份密钥轮换与离线恢复**：支持新旧密钥短期并存、原子发布轮换备份，并提供独立恢复脚本与人性授权手册。

#### P1-B 后段 / P1-C：核心业务深度演进（进行中，高优先级）

- **已完成：SourceArtifact 与声音档案**：SQLite v6 记录音频资产哈希、授权目标和高敏级别；原生 Streamlit 录音以原子文件写入纳入审计。
- **跨进程锁与租约**：在构建和切换检索代次时，引入基于文件系统或数据库的跨进程锁（Lock）与租约（Lease）机制，防止 Streamlit、CLI 和未来独立守护进程并发同步时发生冲突。
- **待后续：新增稳定 API 接口层**：在存在明确客户端需求后再评估 API 技术选型，不在当前重构中引入 Web 框架。
- **已完成：夜间反思独立用例**：`ReflectionService` 负责授权来源归档和候选生成；队列仅保存 `SourceArtifact` ID，Worker 执行前复核文件完整性及其绑定的当前批准快照。
- **安全性与人格对齐测试**：引入自动评估机制（Evaluate Runner），包含儿童安全回归测试、人格回归测试和提示词版本评估，确保大模型基座或提示词变更时，数字分身的价值观不发生偏移。

#### P1-D：系统生产化（中低优先级）

- **已完成：独立 SQLite Worker**：`TaskQueue` 只负责入队和查状态，`uv run reborn worker` 独占轮询与受控线程池；queued 可接管，running 失败后人工重试。
- **数据治理与人工操作手册**：增加开放标准的导出格式、支持备份加密密钥轮换，并编写真正符合人性授权、用于极端灾备情况下的离线恢复操作手册。

---

### 第二部分：数字分身激活阶段（未来规划，暂缓）

当前以**可插拔适配器**方式预留接入点，核心领域层不引入语音克隆、数字人驱动等具体实现依赖。待第一部分核心能力稳定后，依次推进：

- **P2-A：数字遗产激活机制** — 状态机（`owner_only` → `activation_file` → `activated`）、授权文件规范、子女访问控制适配器。
- **P2-B：语音克隆接入** — 接入 GPT-SoVITS 训练个性化音色模型，实现 STT → RAG → TTS 完整语音对话链路。语音素材纳入 SourceArtifact 管理。
- **P2-C：数字人形象接入** — 面部驱动（SadTalker / MuseTalk 等）、口型同步，集成到陪伴沙盒前端。
- **P2-D：长期陪伴策略** — 年龄语气路由动态调整、子女成长记录、伦理边界研究（子女成年后的陪伴策略设计）。
�

只有 `IdentityGovernanceService.approve()` 可将快照晋升为当前身份。Streamlit 提供差异查看、
批准和拒绝流程；CLI 也提供审批命令。

### 安全、备份与数字遗产

- 当前使用 `LocalOwnerAccessPolicy`，并通过 `AuditedAccessPolicy` 记录敏感操作。
- 登录界面尚未启用；未来认证系统只需替换访问策略适配器。
- 备份默认要求 `BACKUP_ENCRYPTION_KEY`，使用 Fernet 加密。
- 备份包含 SQLite 一致性快照、Obsidian 资料、家庭资料 TOML 和数字遗产激活文件；可重建的模型与检索索引不纳入。
- 恢复演练会解密、校验每个文件哈希、在隔离临时目录解包，并执行 SQLite integrity check。
- 密钥轮换使用临时 BACKUP_PREVIOUS_ENCRYPTION_KEY 解密旧归档，以当前密钥重新加密；原文件不会被覆盖或删除。
- scripts/offline_restore.py 可在没有项目运行环境、Streamlit 和 Qdrant 时恢复开放格式资产，操作规范见离线恢复手册。
- 数字遗产激活支持 `owner_only`、`activation_file`、`activated` 三种规则。激活文件必须包含授权人、
  批准时间和证据引用。

### 后台任务

Streamlit 的聊天、访谈提炼、同步、语音转写、RAG 回复、备份、恢复演练和密钥轮换通过
`TaskQueue` 将安全 JSON 载荷写入 SQLite；声音档案则直接调用归档用例，长音频不会进入任务载荷。
夜间反思在入队前将聊天 JSON 原子归档为高敏感 SourceArtifact，任务载荷仅保存 Artifact ID；
Worker 读取时重新校验授权字段、相对路径、字节数、SHA-256 和归档时绑定的激活批准快照。
`uv run reborn worker` 是唯一持有 `BackgroundTaskWorker` 和受控 `ThreadPoolExecutor` 的进程，
它按创建时间原子认领 queued 任务并通过 Container 注入的 handler 注册表执行。
Worker 启动时将上次已经开始的 running 任务标记为失败，避免非幂等副作用被盲目重试；
queued 任务保持可接管。本地部署继续使用 SQLite，不引入 Celery、Redis 或网络服务。

## 4. 运维命令

```bash
uv run reborn check
uv run reborn sync
uv run reborn identity-list
uv run reborn nightly-reflection path/to/chat.json --confirm-authorized
uv run reborn worker
uv run reborn identity-approve <snapshot-id> --note "reviewed"
uv run reborn backup
uv run reborn generate-encryption-key
uv run reborn verify-backup <path>
uv run reborn recovery-drill <path>
uv run reborn legacy-status
```

加密密钥必须保存在项目目录和备份介质之外。至少每年执行一次恢复演练，并保留演练记录。

## 5. 下一阶段演进路线

为确保系统在“数字遗产”这一定位上的稳健性，后续研发将按照难易度、优先级和模块依赖性，分为以下四个阶段进行：

### Phase 1: 架构规整与基础重构（高优先级，中/低难度）

- **已完成：将 Streamlit 页面拆分**：页面实现已移至 `src/reborn_core/interfaces/streamlit/`；根 `app.py` 仅保留兼容启动职责，资源仍由统一生命周期管理。
- **待后续：新增稳定 API 接口层**：在存在明确客户端需求后再评估 API 技术选型，不在本次重构中引入 Web 框架。
- **已完成：规范检索代次注入**：Avatar/RAG 用例由 `Container` 显式注入活动检索代次适配器；Qdrant/BM25、Prompt 文件加载、Obsidian 读写和记忆盲区 JSON 写入均位于 `infrastructure/`。
- **已完成：拆分单体 DBManager**：身份快照、后台任务、同步历史、备份与审计已使用独立 Repository adapter，并由独立 `MigrationRunner` 管理版本化迁移。

### Phase 2: 数据安全与数据模型演进（高优先级，中难度）

- **已完成：SourceArtifact 与声音档案**：SQLite v6 记录音频资产哈希、授权目标和高敏级别；原生 Streamlit 录音以原子文件写入纳入审计。
- **增加跨进程锁与租约**：在构建和切换检索代次时，引入基于文件系统或数据库的跨进程锁（Lock）与租约（Lease）机制，防止 Streamlit、CLI 和未来独立守护进程并发同步时发生冲突。

### Phase 3: 核心业务深度演进（中优先级，中/高难度）

- **已完成：夜间反思独立用例**：`ReflectionService` 负责授权来源归档和候选生成；队列仅保存 `SourceArtifact` ID，Worker 执行前复核文件完整性及其绑定的当前批准快照。
- **安全性与人格对齐测试**：引入自动评估机制（Evaluate Runner），包含儿童安全回归测试、人格回归测试和提示词版本评估，确保大模型基座或提示词变更时，数字分身的价值观不发生偏移。

### Phase 4: 系统运维与高可用生产化（中/低优先级，高难度）

- **已完成：SQLite 持久化队列底座**：全部生产后台任务具有可重放载荷，queued 任务可在重启后接管，running 任务不会被盲目重试。
- **已完成：备份密钥轮换与离线恢复**：支持新旧密钥短期并存、原子发布轮换备份，并提供独立恢复脚本与人性授权手册。

- **已完成：独立 SQLite Worker**：`TaskQueue` 只负责入队和查状态，`uv run reborn worker` 独占轮询与受控线程池；queued 可接管，running 失败后人工重试。
- **数据治理与人工操作手册**：增加开放标准的导出格式、支持备份加密密钥轮换，并编写真正符合人性授权、用于极端灾备情况下的离线恢复操作手册。
