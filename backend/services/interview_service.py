import pandas as pd
from backend.observability.logger import logger
from backend.brain.prompts import (
    MEMORY_EXTRACTION_PROMPT, 
    STORY_EXTRACTION_PROMPT,
    IDENTITY_CONSOLIDATION_PROMPT
)

class InterviewService:
    def __init__(self, llm_router, memory_writer):
        """注入依赖，解耦组件"""
        self.llm = llm_router
        self.mw = memory_writer

    def process_and_save_interview(self, chat_history: list, interview_mode: str, custom_title: str = None):
        """
        核心业务编排：提炼记忆 -> 保存笔记 -> 更新身份核
        """
        try:
            # 1. 准备对话文本
            history_str = "\n".join([
                f"{m['role']}: {m['content']}" 
                for m in chat_history if m['role'] != 'system'
            ])

            # 2. 提炼记忆碎片 (Insight Extraction)
            logger.info(f"开始提炼记忆，当前模式: {interview_mode}")
            extract_prompt = (
                MEMORY_EXTRACTION_PROMPT if interview_mode == "💡 提炼价值观 (ROM)" 
                else STORY_EXTRACTION_PROMPT
            )
            extract_msgs = [extract_prompt, {"role": "user", "content": f"请处理以下对话内容：\n{history_str}"}]
            insight = self.llm.generate_response(extract_msgs)

            # 3. 保存至 Obsidian
            final_title = custom_title if custom_title else f"记忆碎片_{pd.Timestamp.now().strftime('%m%d_%H%M')}"
            if interview_mode == "💡 提炼价值观 (ROM)":
                success = self.mw.save_core_value(final_title, insight)
            else:
                success = self.mw.save_story(final_title, insight)
            
            if not success:
                raise RuntimeError("写入 Obsidian 物理文件失败")

            # 4. 同步更新身份核 (Identity Consolidation)
            logger.info("开始同步更新身份核(Master Identity)...")
            old_identity = self.mw.read_master_identity()
            consolidation_msgs = [
                IDENTITY_CONSOLIDATION_PROMPT,
                {"role": "user", "content": f"旧身份核：\n{old_identity}\n\n新记忆碎片：\n{insight}"}
            ]
            updated_identity = self.llm.generate_response(consolidation_msgs)
            
            # 覆盖写入身份核
            if not self.mw.save_master_identity(updated_identity):
                raise RuntimeError("更新 Master Identity 文件失败")

            return True, insight
            
        except Exception as e:
            logger.error(f"业务层处理访谈失败: {e}")
            return False, str(e)