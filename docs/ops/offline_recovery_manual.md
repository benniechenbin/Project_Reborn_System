# Project Reborn 数字遗产离线恢复手册

本手册面向依法或依照家庭授权接管数字遗产的继承人。它假设 Project Reborn、Streamlit、
Qdrant 和原有虚拟环境都已无法运行，只保留一份 .zip.fernet 备份、对应 Fernet 密钥、
Python 3 和本仓库中的独立脚本 scripts/offline_restore.py。

## 1. 授权与操作原则

开始前请确认自己拥有遗嘱、家庭授权书、法院文件或其他明确授权。不要因为能够取得存储介质或
密钥就默认获得查看私人资料的权利。

- 永远保留原始备份，只在校验后的副本上操作。
- 不要通过聊天、邮件或截图传递完整 Fernet 密钥。
- 将备份、密钥和授权文件分开保管；记录领取人、时间、介质编号和文件 SHA-256。
- 在离线或受控计算机上恢复，完成后根据授权范围清理临时明文。
- 如果授权范围不清楚，停止操作并联系家庭指定执行人或法律顾问。

## 2. 所需材料

1. 一个 .zip.fernet 备份副本。
2. 与该备份匹配的 44 字符 Fernet 密钥。轮换过的备份必须使用轮换后的新密钥。
3. scripts/offline_restore.py 的纸质校验值或可信副本。
4. Python 3.11 或更新的兼容版本。
5. cryptography 包。建议现在就把与目标系统匹配的 wheel 和本手册一起保存在离线介质。

脚本不 import reborn_core，不需要项目依赖、数据库服务、Qdrant、模型或网络连接。

## 3. 准备离线环境

在一台可信计算机上安装 Python，然后从事先保存的 wheel 安装 cryptography：

```text
python -m pip install --no-index --find-links D:/offline-wheels cryptography
```

如果只能在线安装，先确认网络和软件源可信，再执行：

```text
python -m pip install cryptography
```

复制备份时不要移动或改名原件。可以用系统工具记录副本的 SHA-256：

```text
python -c "import hashlib,pathlib; p=pathlib.Path(r'D:/recovery/backup.zip.fernet'); print(hashlib.sha256(p.read_bytes()).hexdigest())"
```

## 4. 执行恢复

创建一个新的空目录，不要指向现有项目目录或个人资料目录：

```text
python scripts/offline_restore.py D:/recovery/backup.zip.fernet D:/recovery/restored
```

脚本会在终端中安全提示输入 Fernet 密钥，输入内容不会回显。不要把密钥直接写进命令行参数，
以免进入 shell 历史。

无人值守演练可以临时设置 REBORN_BACKUP_KEY 环境变量；真实继承恢复仍推荐交互输入，并在
执行后立即清除环境变量。

脚本会依次：

1. 识别当前 RBN1 分块 Fernet 格式或早期单 token Fernet 格式。
2. 在系统临时目录解密 ZIP，不修改源备份。
3. 校验 manifest.json 中每个文件的 SHA-256 和大小。
4. 拒绝绝对路径、父目录跳转路径和符号链接，防止归档越界写入。
5. 解压到指定空目录并运行 PRAGMA integrity_check。
6. 仅在全部检查通过后打印 JSON 恢复报告。

## 5. 恢复结果

重要资产位于：

- profile/project_profile.toml：家庭成员和项目基本资料。
- vault/**/*.md：日记、人生故事、价值观和其他 Markdown 记忆。
- sqlite/reborn.db：家庭 SQLite 数据库。
- governance/legacy_activation.json：如果创建备份时存在，则包含数字遗产激活凭证。
- manifest.json：文件清单、原始哈希和备份标识。

Qdrant/BM25 检索索引、本地模型和模型缓存不在备份中。它们属于可重建数据，不影响读取上述
TOML、Markdown 和 SQLite 原始资产。

可使用任何 SQLite 查看器读取数据库，也可以仅用 Python：

```text
python -c "import sqlite3; c=sqlite3.connect(r'D:/recovery/restored/sqlite/reborn.db'); print(c.execute('PRAGMA integrity_check').fetchone()[0]); c.close()"
```

## 6. 常见故障

### “密钥格式无效”

确认密钥是完整的 44 个 ASCII 字符，没有前后空格、引号、换行或被聊天软件截断。

### “密钥错误或文件已损坏”

先核对备份副本 SHA-256，再检查该文件是否经历过密钥轮换。不要反复修改原文件；换一个副本和
对应时期的密钥重试。

### “哈希校验失败”或“文件大小校验失败”

停止使用该副本。它可能损坏或被篡改。保留错误信息和 SHA-256，改用另一份离线备份。

### “SQLite 完整性检查失败”

不要修复原备份。保存恢复目录作为证据，换另一份备份重试；必要时让数据恢复专业人员在副本上操作。

### “输出目录必须为空”

选择一个新目录。脚本不会把恢复数据混入已有目录，也不会覆盖已有文件。

## 7. 恢复后的交接

记录备份标识、源文件 SHA-256、使用的密钥版本、恢复时间、操作者、授权依据和
sqlite_integrity 结果。将原备份重新设为只读并离线保存；明文恢复目录应根据授权范围交给指定
继承人，或在完成导出后安全清理。

至少每年执行一次不接触真实生产目录的恢复演练。密钥轮换后，应先用新备份完成本手册的独立演练，
确认成功后再移除临时的 BACKUP_PREVIOUS_ENCRYPTION_KEY；Project Reborn 不会自动删除旧备份。
