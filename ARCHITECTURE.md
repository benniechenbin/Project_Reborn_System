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

- `reborn_core.config`：配置组件入口；`core.config` 仅作弃用兼容转发。
- `reborn_core.observability`：日志及未来指标/追踪入口；`core.logger` 仅作兼容转发。
- `reborn_core.lifecycle`：唯一拥有启动与关闭副作用的入口。
- `reborn_core.container.Container`：惰性依赖装配，不在构造时加载模型。
- `reborn_core.application`：访谈、同步和身份审批用例。
- `reborn_core.runtime`：后台任务运行器与持久化任务状态。
- `reborn_core.security`：访问策略和数字遗产激活规则。

所有入口必须使用 `build_app().start()` 或 `lifespan()`。生命周期副作用只能由
`reborn_core.lifecycle` 管理，项目不再保留第二套启动入口。

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

## 5. 下一阶段

- 将 Streamlit 页面拆到 `interfaces/streamlit/`，并增加稳定 API。
- 将进程内 worker 替换为可恢复的独立 worker/队列。
- 为 SourceArtifact 增加独立数据库记录、内容哈希、授权范围和敏感级别。
- 增加开放导出格式、密钥轮换、真正的人工授权恢复操作手册。
- 增加儿童安全回归测试、人格回归测试和提示词版本评估。
