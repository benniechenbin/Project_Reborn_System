# Agent 行为准则 (Project Reborn System)

## 项目认知 (Project Context)
**Project Reborn (数字生命引擎)** 是一个跨代数字遗产保存与数字分身系统。核心目标是提取并固化创作者的底层逻辑与价值观（ROM），并结合第二大脑（Obsidian 知识库作为 RAM），生成具有真实人格厚度、能够独立思考并陪伴成长的数字实体。

## 核心架构原则 (Architectural Principles)
作为 AI 编程助手，在协助开发本系统时，必须严格遵守以下架构边界与原则：

1. **DDD / Clean Architecture**: 
   - 严格区分系统层级，代码主要分布在 `src/reborn_core` 中。
   - 层级包含：`infrastructure` (基础设施)、`domains` (领域模型)、`application` (应用用例) 和 `interfaces` (表现层)。
   - **禁止**跨层级直接调用底层实现。

2. **依赖倒置与解耦 (Dependency Inversion)**:
   - 领域层（`domains`）和应用层（`application`）禁止直接实例化外部依赖（如数据库、向量库 Qdrant、大模型 LLM）。
   - 所有的外部资源依赖必须抽象为接口（Protocol/ABC）并从外部注入。

3. **显式与惰性装配 (Lazy Injection)**:
   - 所有的核心服务、数据库连接和高内存占用的模型组件，必须通过 `src/reborn_core/container.py` 里的 `Container` 进行惰性加载（Lazy Loading）。
   - 不要使用单例模式滥用全局变量。

4. **生命周期管理**:
   - 严禁在模块顶层级别创建有副作用的全局资源（如直接在文件开头连接数据库或加载模型）。
   - 所有的启动、关闭、资源释放等生命周期副作用必须由 `src/reborn_core/lifecycle.py` 统一编排和托管。

5. **并发与后台任务管理**:
   - 后台任务必须使用 `BackgroundTaskRunner` (位于 `runtime/tasks.py`)，由 SQLite 持久化任务状态并使用 `ThreadPoolExecutor` 执行。
   - **禁止**随意使用 `threading` 或 `multiprocessing` 模块开启不受控制的野线程/进程。

## 开发规范 (Development Standards)
- **技术栈**: Python 3.11+, 使用 `uv` 进行依赖与虚拟环境管理, 使用 `hatchling` 构建。
- **代码规范**: 
  - 所有代码必须包含完整的 Type Hints。
  - 提交前必须保证通过 `ruff` (格式化与代码风格) 和 `mypy` (静态类型检查)。
- **测试覆盖**: 
  - 项目依赖 `pytest` 进行测试，当前已有 80+ 个测试用例。
  - 任何新增功能或重构必须保证所有用例 100% 通过（`uv run pytest`）。
  - 新增核心逻辑必须补充对应的单元测试。
- **持久化管理**: 
  - 修改存储逻辑（SQLite）时，必须同步检查和更新数据库迁移逻辑，绝对不能破坏向后兼容性与用户数据。

## 当前演进重点 (Current Roadmap Context)
目前项目已完成 Phase 1（底层架构、数据库、向量库搭建）和 Phase 2（Obsidian 闭环）。正在推进：
- **Phase 3**: RAG 引擎核心逻辑 (`rag_engine.py`) 与沙盒交互打通。
- **解耦优化**: 持续拆分如 `DBManager` 等大类到更符合 Repository 模式的小类。
- **UI 拆分**: 将 Streamlit 等前端组件干净地解耦到 `interfaces/streamlit/`。

## 工作流指引 (Workflow Guidelines)
1. **修改前确认**: 在修改核心 `src/reborn_core` 代码前，先运行 `uv run pytest` 确认当前基线健康。
2. **文档同步**: 任何对接口、架构或阶段性目标的重大修改，必须同步更新 `README.md` 或 `ARCHITECTURE.md`，保持文档与代码同步。
