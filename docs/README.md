# 📂 Project Reborn - 文档索引与规范 (Documentation Index)

本项目的所有开发与运维文档均存放在 `docs/` 目录下。为了保持清晰的架构追溯与长期维护，文档按照以下分类进行组织：

## 📁 目录结构与用途

* **[adr/](file:///e:/developer/Project_Reborn_System/docs/adr/)**：**架构决策记录 (Architecture Decision Records)**
  * 记录项目在演进过程中的重大技术选型与设计决策（如存储选型、生命周期管理、任务调度等）。文件命名规则为 `ADR-XXX-slug.md`。
* **[rfc/](file:///e:/developer/Project_Reborn_System/docs/rfc/)**：**技术与特性提案 (Request for Comments)**
  * 针对具体模块或新功能的详细技术设计方案与评审提案。
* **[interview/](file:///e:/developer/Project_Reborn_System/docs/interview/)**：**灵魂采访与人设对齐 (Soul Interview & Persona Design)**
  * 存放面向父母的访谈问题库，以及系统底层价值观 ROM（System Prompt）的设计与版本演进文档。
* **[legacy/](file:///e:/developer/Project_Reborn_System/docs/legacy/)**：**数字遗产与托付机制 (Trust & Legacy Activation)**
  * 记录数字生命的托付与激活协议、多重安全授权校验方案以及伦理边界规范。
* **[ops/](file:///e:/developer/Project_Reborn_System/docs/ops/)**：**部署与运维指南 (Operations & Setup Guides)**
  * 提供双机协同（Mac 与 Windows 强算力端）的部署步骤、数据加密备份策略及定期灾备恢复演练手册。
* **[eval/](file:///e:/developer/Project_Reborn_System/docs/eval/)**：**对齐与回归评估 (Evaluation & Alignment)**
  * 用于维护数字分身的性格漂移测试基准、儿童友好安全护栏评估用例。
* **[tasks/](file:///e:/developer/Project_Reborn_System/docs/tasks/)**：**里程碑与工作纪要 (Milestones & Work Logs)**
  * 记录各阶段（Phase）的开发总结、历史纪要以及未尽事宜。

---

## ✍️ 编写规范
* 文档应尽量保持中英文术语对照清晰（如 ROM/RAM、RAG 检索代次、备份恢复演练等）。
* 进行具有破坏性或跨模块的代码重构前，应先在 `rfc/` 下提出设计方案，并在评审通过后（如有必要）在 `adr/` 下沉淀最终技术决策。
