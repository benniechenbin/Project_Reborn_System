import re
import os
from utils.logger import logger

logger.info("🚀 任务启动")

class ObsidianInjector:
    def __init__(self, vault_path):
        """初始化注入器，绑定 Obsidian 仓库根路径"""
        self.vault_path = vault_path

    def update_metrics(self, file_relative_path, metrics_data):
        target_file = os.path.join(self.vault_path, file_relative_path)
        
        if not os.path.exists(target_file):
            logger.error(f"找不到目标文件: {target_file}")
            return False

        # 🚨 修正点1：新内容首尾必须自带隐形锚点，为下次更新留门！
        new_content = f"""<!--METRICS_START-->
> [!info] 📊 数字生命底层数据同步监控
> 🎙️ **有效语音资产**: {metrics_data.get('audio_duration', 0)} 分钟 (GPT-SoVITS 底模训练进度)
> 📝 **结构化记忆库**: {metrics_data.get('notes_count', 0)} 篇 (RAG 检索节点)
> 💡 **知识库词汇量**: 约 {metrics_data.get('word_count', 0)} 字
> ⏱️ **最后同步时间**: {metrics_data.get('sync_time', '未知')}
<!--METRICS_END-->
"""

        try:
            with open(target_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"读取文件失败: {e}")
            return False

        # 🚨 修正点2：精准匹配锚点，绝对不能用 .*? 瞎替换
        left_bracket = "<" + "!--"
        right_bracket = "--" + ">"
        regex_pattern = rf'{left_bracket}\s*METRICS_START\s*{right_bracket}.*?{left_bracket}\s*METRICS_END\s*{right_bracket}'
        pattern = re.compile(regex_pattern, re.DOTALL)
        
        if not pattern.search(content):
            logger.warning(f"在 {file_relative_path} 中未找到替换锚点，请检查文档结构。")
            return False

        updated_content = pattern.sub(new_content, content)

        try:
            with open(target_file, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            logger.info(f"✅ 成功更新 Obsidian 文档: {file_relative_path}")
            return True
        except Exception as e:
            logger.error(f"写入文件失败: {e}")
            return False