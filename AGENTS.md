# AGENTS.md

## Project Context

Project Reborn（数字生命引擎）的最终目标是一个数字陪伴系统，旨在孩子幼年时父母离世后，提供一个陪伴孩子成长的数字生命体。未来若商业化，这也将是一个双阶段的私人定制产品。

项目整体发展分为两个阶段：
* **第一阶段（当前重点）**：通过手写以及 AI 采访等方式，记录父母的生活习惯、价值观、语言习惯等，建立可本地运行的个人知识与数字分身基础库。
* **第二阶段（未来规划）**：后续接入数字人、语音克隆等技术栈，实现完整的视觉与语音交互陪伴。

目前系统的核心架构（服务于第一阶段和底层基座）由三部分组成：

* **ROM**：稳定的个人价值观、原则、身份认知和底层判断逻辑。
* **RAM**：来自 Obsidian 等第二大脑系统的动态知识库。
* **RAG**：围绕个人知识库进行检索、推理和上下文增强。

当前开发目标是构建一个可维护、可扩展、可本地运行的核心架构。不要将本项目过度设计成大型分布式平台、企业级微服务系统或复杂 SaaS 架构。

---

## Repository Layout

主要代码位于：

* `src/reborn_core/`

核心层级包括：

* `src/reborn_core/domains/`：领域模型与核心业务规则。
* `src/reborn_core/application/`：应用用例、服务编排和业务流程。
* `src/reborn_core/infrastructure/`：数据库、向量库、LLM、文件系统等外部资源实现。为维持业务边界对齐（认知对齐，防止组件杂乱），基础设施层的子目录结构应尽量与 domains 层子目录保持 1:1 镜像关系（例如：`domains/brain/` 对应 `infrastructure/brain/`）。
* `src/reborn_core/interfaces/`：CLI、Streamlit、API、UI 等表现层入口。
* `src/reborn_core/container.py`：依赖装配与核心服务构建。
* `src/reborn_core/lifecycle.py`：启动、关闭、资源释放等生命周期管理。
* `src/reborn_core/runtime/tasks.py`：后台任务运行器与任务状态管理。

如果以上路径在后续重构中发生变化，必须先检查当前仓库结构，不要基于旧路径假设文件位置。

---

## Architecture Rules

本项目遵循 DDD / Clean Architecture 思路。AI 编程助手必须遵守以下边界。

### Allowed Dependency Direction

允许：

* `interfaces` 调用 `application`。
* `application` 调用 `domains`。
* `infrastructure` 实现 `application` 或 `domains` 中定义的接口、Protocol 或抽象。
* `container.py` 或其他明确的 composition root 负责连接各层依赖。
* 表现层可以触发应用用例，但不应承载核心业务逻辑。

### Forbidden Dependency Direction

禁止：

* `domains` import `application`、`infrastructure` 或 `interfaces`。
* `application` 直接实例化数据库、向量库、LLM、文件系统、UI 或其他外部资源实现。
* `infrastructure` 调用 Streamlit、CLI、UI 或表现层代码。
* 将核心业务逻辑写在 `interfaces` 层。
* 为了方便而绕过抽象接口，直接跨层调用底层实现。

---

## Dependency Inversion

领域层和应用层不得直接依赖外部实现。

必须通过以下方式解耦：

* 使用 `Protocol`、ABC 或明确的接口抽象外部依赖。
* 由 `container.py` 或 composition root 负责注入具体实现。
* 数据库、Qdrant、LLM、Embedding、文件系统、Obsidian 访问等都必须作为外部资源处理。
* 不要在领域对象内部创建外部客户端。
* 不要在应用服务内部硬编码具体 provider。

---

## Lifecycle and Resource Management

所有有副作用的资源必须纳入生命周期管理。

禁止：

* 在模块顶层连接数据库。
* 在模块顶层加载模型。
* 在模块顶层创建 Qdrant、LLM、Embedding、SQLite 等客户端。
* 使用全局变量伪装单例服务。
* 在 import 阶段触发耗时任务或外部资源初始化。

要求：

* 核心服务、数据库连接、高内存模型组件必须通过 `Container` 惰性加载。
* 启动、关闭、资源释放必须由 `lifecycle.py` 或明确的生命周期入口统一托管。
* 新增长期运行资源时，必须同时考虑初始化、关闭、异常恢复和测试隔离。

---

## Background Task Rules

后台任务必须使用项目既有的任务运行机制。

要求：

* 使用 `BackgroundTaskRunner` 管理后台任务。
* 任务状态应通过 SQLite 持久化。
* 执行机制应通过受控的 `ThreadPoolExecutor` 或项目现有封装完成。
* 新增后台任务时，必须考虑任务状态、失败恢复、幂等性和日志记录。

禁止：

* 随意使用 `threading` 开启不受控制的野线程。
* 随意使用 `multiprocessing` 创建不受管理的进程。
* 在 UI 层或接口层直接启动不可追踪的后台任务。
* 创建无法取消、无法追踪、无法恢复的后台执行逻辑。

---

## Development Standards

技术栈：

* Python 3.11+
* `uv` 用于依赖管理与虚拟环境管理。
* `hatchling` 用于构建。
* `pytest` 用于测试。
* `ruff` 用于格式化和代码风格检查。
* `mypy` 用于静态类型检查。

代码规范：

* 生产代码中的 public function、method、dataclass、Protocol、service boundary 必须包含清晰的 type hints。
* 测试代码应尽量保持类型清晰，但可读性优先于形式上的完整标注。
* 不要引入不必要的抽象层。
* 不要为了“看起来更企业级”而增加复杂框架。
* 保持函数、类、模块职责清晰。
* 优先做小范围、可验证、可回滚的修改。

---

## Dependency Rules

新增依赖必须谨慎。

禁止：

* 未经明确要求新增重型 runtime dependency。
* 未经明确要求引入新的 Web 框架、ORM、任务队列、Agent 框架或复杂工作流引擎。
* 为简单问题引入大型库。
* 因为代码生成方便而扩张依赖边界。

要求：

* 简单任务优先使用标准库或项目已有依赖。
* 如果确实需要新增依赖，必须说明：

  * 为什么现有依赖不够。
  * 新依赖解决什么问题。
  * 是否影响安装体积、运行环境或长期维护。
  * 是否需要更新 `pyproject.toml`、锁文件和文档。

---

## Testing and Validation

修改代码前，优先确认当前测试基线是否健康。

常用验证命令包括：

```bash
uv run pytest
uv run ruff check .
uv run mypy .
```

执行规则：

* 修改核心代码前，尽量先运行 `uv run pytest` 确认当前基线。
* 小范围修改后，至少运行相关模块的 targeted tests。
* 大范围修改后，应运行完整测试。
* 新增核心逻辑必须补充对应单元测试。
* 修改存储、迁移、RAG、后台任务、生命周期相关逻辑时，必须补充或更新测试。
* 不要声称测试通过，除非实际运行过对应命令并成功。
* 如果因为环境、依赖、耗时或外部资源限制无法运行测试，必须明确说明原因。

不要将“所有测试通过”误解为“测试覆盖率必须达到 100%”。当前要求是：已有测试不能被破坏，新增核心逻辑应有合理测试覆盖。

---

## Data Safety

本项目涉及用户知识库、SQLite 数据、向量索引和 Obsidian 源文件，必须谨慎处理数据。

禁止：

* 未经明确要求删除、覆盖或重写用户数据。
* 未经明确要求批量修改 Obsidian 源文件。
* 未经明确要求清空 SQLite 数据库、向量库索引或生成结果。
* 使用破坏性迁移替代兼容性迁移。

要求：

* 修改 SQLite schema 时，必须同步检查和更新迁移逻辑。
* 数据迁移应尽量保持向后兼容。
* 涉及用户数据写入时，应优先考虑备份、幂等性和失败恢复。
* 对存储逻辑的修改必须有测试或清晰的手动验证步骤。

---

## Change Scope Rules

AI 编程助手必须严格控制修改范围。

要求：

* 优先进行小范围、明确目标的修改。
* 不要修改与当前任务无关的文件。
* 不要因为格式、命名、风格偏好而顺手重构无关代码。
* 不要在没有任务说明的情况下移动目录、重命名模块或修改 public API。
* 不要在一次任务中同时修改架构、业务逻辑、测试、文档和依赖，除非任务明确要求。
* 如果发现需要更大范围重构，应先提出计划，而不是直接修改。

破坏性重构要求：

* 必须先有 RFC 或明确的 task spec。
* 必须分阶段进行。
* 每个阶段都应保持可测试、可回滚。
* 必须说明迁移影响和兼容性风险。

---

## Documentation Rules

以下情况需要同步更新文档：

* 修改核心架构边界。
* 修改 public API。
* 修改启动方式、配置方式或依赖管理方式。
* 修改数据库 schema、迁移逻辑或持久化格式。
* 修改 RAG 流程、Obsidian 接入方式或后台任务机制。
* 新增重要模块或删除旧模块。

常见文档位置：

* `README.md`
* `ARCHITECTURE.md`
* `docs/architecture/`
* `docs/rfc/`
* `docs/tasks/`
* `docs/reviews/`

不要为了小型内部实现细节强行更新大量文档。文档更新应服务于长期维护，而不是形式主义。

---

## Current Roadmap Context

当前项目已完成：

* Phase 1：底层架构、数据库、向量库基础能力。
* Phase 2：Obsidian 闭环。

当前推进重点：

* Phase 3：RAG 引擎核心逻辑与沙盒交互打通。
* `rag_engine.py` 相关逻辑完善。
* 持续拆分 `DBManager` 等大类，使其更符合 Repository 模式。
* 将 Streamlit 等前端组件解耦到 `interfaces/streamlit/`。
* 保持领域层、应用层、基础设施层、表现层之间的边界清晰。

Roadmap 信息只用于帮助理解当前优先级。不要因为 Roadmap 存在就主动实现未被要求的功能。

---

## Agent Workflow

### Before Editing

在修改前：

1. 阅读当前任务说明。
2. 检查相关目录和文件。
3. 必要时阅读 `README.md`、`ARCHITECTURE.md`、`docs/architecture/`、`docs/rfc/` 或 `docs/tasks/`。
4. 明确本次修改范围。
5. 对大修改先输出简短计划，不要直接改代码。

### During Editing

修改过程中：

* 保持改动小而集中。
* 遵守架构依赖方向。
* 避免无关格式化。
* 避免修改生成文件、历史产物和用户数据。
* 优先补充 targeted tests。
* 如果发现设计冲突，先说明问题，再提出选择。

### After Editing

完成后必须总结：

* 修改了哪些文件。
* 为什么修改。
* 是否超出原始任务范围。
* 运行了哪些测试或检查。
* 测试是否通过。
* 还有哪些风险或未完成事项。
* 哪些文件是有意没有修改的。

---

## Final Response Requirements

每次完成代码修改后，最终回复必须包含：

```text
Changed:
- ...

Validation:
- ...

Risks:
- ...

Notes:
- ...
```

如果没有运行测试，必须写明：

```text
Validation:
- Not run. Reason: ...
```

禁止使用模糊说法，例如：

* “应该没问题”
* “看起来可以”
* “测试应当会通过”
* “我已经优化了整个项目”

必须用具体事实说明修改和验证情况。

---

## When Unsure

如果任务不清楚：

* 不要猜测性大改。
* 先读取相关文件。
* 基于现有代码提出最小可行方案。
* 对高风险修改先给出计划。
* 如果存在多个合理方案，说明取舍，不要擅自引入复杂架构。
