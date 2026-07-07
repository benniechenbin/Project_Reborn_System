# Project Reborn Architecture Baseline

## 1. 系统定位

Project Reborn 首先是需要跨越多年保存、验证和迁移的数字遗产系统，其次才是对话产品。

必须长期保持的不变量：

1. 原始资料与 AI 派生内容严格区分，生成内容不能静默成为“事实”。
2. 身份快照、检索索引和对话能力都可替换、可追溯、可回滚。
3. 孩子始终知道自己在与数字分身交互，而不是现实中的真人。
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
- `reborn_core.application`：访谈、同步和身份审批用例。
- `reborn_core.runtime`：后台任务运行器与持久化任务状态。
- `reborn_core.security`：访问策略和数字遗产激活规则。

所有入口必须使用 `build_app().start()` 或 `lifespan()`。生命周期副作用只能由
`reborn_core.lifecycle` 管理，项目不再保留第二套启动入口。

### 目录与命名空间结构规范 (Directory & Namespace Layout Rules)

为了保持系统各层级在业务概念上的高度内聚与对齐（认知对齐，避免跨子域的技术组件耦合），本项目遵循以下布局原则：

1. **子域 1:1 镜像关系**：在 `infrastructure/` 层级中，其内部子目录应尽量与 `domains/` 的业务子域进行 1:1 的镜像结构（例如：脑部域的领域逻辑位于 `domains/brain/`，则其具体的技术适配器/客户端实现应位于 `infrastructure/brain/`）。
2. **便于垂直切片（Vertical Slice）**：这有助于降低心智检索负担，并在未来需要将系统模块化或微服务化拆分时，能以业务子域为边界进行干净的解耦。
3. **通用基础设施扁平化**：对于跨多个子域的、扁平的通用基础设施（如 `backup.py` 或公共数据库管理），可以直接放置在 `infrastructure/` 的根部。

## 3. 已落地的关键流程

### 生命周期

`RebornApp.start()` 负责日志、目录、SQLite migration、检索代次目录和后台 worker；
`shutdown()` 负责等待任务并关闭日志。LLM、RAG、Embedding、Reranker 和 STT 都保持惰性，
由 worker 任务内首次加载。

### 检索代次与逻辑别名

本地嵌入式 Qdrant 使用文件系统逻辑别名，而不是先删除固定 collection：

```text
data/retrieval/
  active_generation.json       # 原子替换的活动别名
  generations/
    <generation-id>/
      manifest.json
      index/                    # 独立 Qdrant + BM25
```

同步先在独立目录构建并健康检查新代次，成功后使用 `os.replace` 原子切换
`active_generation.json`。构建失败时活动代次不变；旧代次可用于回滚。

### 身份快照治理

访谈提炼只创建 `pending_review` 身份快照，不再直接更新当前身份文件。SQLite 快照记录：

- 快照 ID、父快照 ID、内容哈希和来源 ID
- 模型供应商、模型名和 base URL
- 提示词 ID、版本和哈希
- 生成参数、创建时间、审核人、审核备注和状态

只有 `IdentityGovernanceService.approve()` 可将快照晋升为当前身份。Streamlit 提供差异查看、
批准和拒绝流程；CLI 也提供审批命令。

### 安全、备份与数字遗产

- 当前使用 `LocalOwnerAccessPolicy`，并通过 `AuditedAccessPolicy` 记录敏感操作。
- 登录界面尚未启用；未来认证系统只需替换访问策略适配器。
- 备份默认要求 `BACKUP_ENCRYPTION_KEY`，使用 Fernet 加密。
- 备份包含 SQLite 一致性快照、Obsidian 资料和数字遗产激活文件；可重建的模型与检索索引不纳入。
- 恢复演练会解密、校验每个文件哈希、在隔离临时目录解包，并执行 SQLite integrity check。
- 数字遗产激活支持 `owner_only`、`activation_file`、`activated` 三种规则。激活文件必须包含授权人、
  批准时间和证据引用。

### 后台任务

Streamlit 的聊天、访谈提炼、同步、语音转写、RAG 回复、备份和恢复演练都提交给
`BackgroundTaskRunner`。任务状态持久化到 SQLite；进程重启后未完成任务会明确标记失败。

当前 worker 是单进程线程池，适合个人单机阶段。未来接入 API、多设备或商业部署时，应以实现同一任务
接口的持久队列 worker 替换它。

## 4. 运维命令

```bash
uv run reborn check
uv run reborn sync
uv run reborn identity-list
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
- **将 Streamlit 页面拆分**：将现有的表现层代码从项目根目录移至 `src/reborn_core/interfaces/streamlit/`，实现纯粹的职责分离，并新增稳定的 API 接口层（如基于 FastAPI），为后续小程序/语音终端接入打下基础。
- **规范检索代次注入**：要求 RAG 引擎通过容器显式注入活动检索代次适配器，彻底移除领域层直接实例化或依赖默认静态路径 Qdrant 实例的备用路径。
- **拆分单体 DBManager**：遵循单一职责原则，将 `DBManager` 按身份快照、后台任务、同步历史、备份与审计仓储拆分为独立的 Repository 接口和适配器，并使用独立版本化的迁移运行器（Migration Runner）。

### Phase 2: 数据安全与数据模型演进（高优先级，中难度）
- **数据源追踪建模 (SourceArtifact)**：在数据库中为原始物料（音频、访谈、外源知识）增加独立记录，支持内容哈希校验、授权范围和敏感级别，作为合规与审计依据。
- **增加跨进程锁与租约**：在构建和切换检索代次时，引入基于文件系统或数据库的跨进程锁（Lock）与租约（Lease）机制，防止 Streamlit、CLI 和未来独立守护进程并发同步时发生冲突。

### Phase 3: 核心业务深度演进（中优先级，中/高难度）
- **拆分夜间反思独立用例**：将夜间反思从 `IdentityGovernanceService` 中拆出，封装为独立的后台作业。分析产生的反思源关联对应的 `SourceArtifact`，且只有具备稳定价值观的快照候选才允许进入人机审批流程。
- **安全性与人格对齐测试**：引入自动评估机制（Evaluate Runner），包含儿童安全回归测试、人格回归测试和提示词版本评估，确保大模型基座或提示词变更时，数字分身的价值观不发生偏移。

### Phase 4: 系统运维与高可用生产化（中/低优先级，高难度）
- **独立/持久化任务队列**：将进程内的 `BackgroundTaskRunner` 线程池升级为支持网络通信、可恢复的独立 Worker/分布式队列（如 Celery/Redis 或持久化队列数据库），以便部署于多设备或云端。
- **数据治理与人工操作手册**：增加开放标准的导出格式、支持备份加密密钥轮换，并编写真正符合人性授权、用于极端灾备情况下的离线恢复操作手册。
