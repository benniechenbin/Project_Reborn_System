import os
import logging
from pathlib import Path
from datetime import datetime
from backend.brain.llm_router import LLMRouter
from backend.brain.prompts import AVATAR_RAG_FRAMEWORK
from backend.memory.vector_store.vector_qdrant import QdrantDBProvider
from backend.config.settings import settings
from backend.observability.logger import logger

class RAGEngine:
    def __init__(self):
        self.llm_router = LLMRouter()
        self.vector_db = QdrantDBProvider()
        try:
            obsidian_root = Path(settings.active_obsidian_path) if settings.active_obsidian_path else Path("data/memories")
        except Exception:
            obsidian_root = Path("data/memories")
            
        self.core_memories_path = obsidian_root / "02_Values"
        self.reflections_path = self.core_memories_path / "00_AI_Reflections"

        self.child_name = settings.child_name
        self.child_nickname = settings.child_nickname
        self.child_gender = settings.child_gender
        self.child_birthday = datetime.strptime(settings.child_birthday, "%Y-%m-%d")

    def _calculate_child_age_and_tone(self) -> str:
        """🌟 核心动态逻辑：年龄感知与语气路由"""
        now = datetime.now()
        # 精确计算年龄（考虑今年的生日是否已过）
        age = now.year - self.child_birthday.year - ((now.month, now.day) < (self.child_birthday.month, self.child_birthday.day))
        
        pronoun = "他" if self.child_gender == "男" else "她"
        son_or_daughter = "儿子" if self.child_gender == "男" else "女儿"

        # 动态语气路由
        if age < 6:
            tone = f"{self.child_nickname}现在还很小（大约 {age} 岁）。你是{pronoun}的爸爸。请使用非常通俗、温柔、带有童话色彩的词汇。多用比喻，像讲故事一样跟{pronoun}说话，语气要充满父亲对{son_or_daughter}的宠溺与耐心。称呼{pronoun}时请使用小名'{self.child_nickname}'。"
        elif age < 13:
            tone = f"{self.child_nickname}现在上小学了（大约 {age} 岁）。请使用鼓励、引导的父亲口吻，可以教{pronoun}一些简单的科学道理和处事原则，像朋友一样平等交流。记得多叫{pronoun}的小名'{self.child_nickname}'。"
        elif age < 18:
            tone = f"{self.child_nickname}现在是青春期了（大约 {age} 岁）。请使用成熟、开明、带点极客幽默的口吻。尊重{pronoun}的独立思考，绝对不要说教，多引导{pronoun}探索世界。"
        else:
            tone = f"{self.child_nickname}现在已经是成年人了（大约 {age} 岁）。请使用成年人之间深沉、平等的对话方式，分享你的人生智慧和哲学思考。"
            
        return f"【动态感知】孩子大名：{self.child_name}，小名：{self.child_nickname}，性别：{self.child_gender}，当前年龄：{age} 岁。\n【强制语气约束】：{tone}"
    def _get_level_1_rom(self) -> str:
        """Level 1: 基础身份与安全锁 (约 200 Tokens)"""
        persona_file = self.core_memories_path / "00_Master_Identity.md" 
        directives_file = self.core_memories_path / "03_Prime_Directives.md"
        
        rom_content = ""
        if persona_file.exists():
            rom_content += persona_file.read_text(encoding='utf-8') + "\n"
        if directives_file.exists():
            rom_content += "### 最高行为准则\n" + directives_file.read_text(encoding='utf-8')

        # 🌟 注入实时环境与年龄感知
        now = datetime.now()
        env_info = f"\n---\n当前现实时间：{now.strftime('%Y-%m-%d %H:%M')}，星期{now.weekday()+1}。"
        age_routing_info = f"\n{self._calculate_child_age_and_tone()}"
        
        return rom_content + env_info + age_routing_info

    def _get_level_2_personality(self) -> str:
        """Level 2: 近期访谈提炼的性格画像 (约 500 Tokens)"""
        if not self.reflections_path.exists():
            return "（近期性格稳定，暂无动态更新）"
        
        # 按照修改时间排序，取最近的 3 个文件
        files = sorted(
            self.reflections_path.glob("*.md"), 
            key=lambda x: x.stat().st_mtime, 
            reverse=True
        )[:3]
        
        summaries = []
        for f in files:
            try:
                # 简单清洗，只取正文
                content = f.read_text(encoding='utf-8')
                summaries.append(f"【近期感悟】：{content}")
            except Exception as e:
                logger.error(f"读取反思文件失败: {e}")
        
        return "\n\n".join(summaries) if summaries else "（暂无近期性格碎片）"

    def _get_level_3_ram(self, query: str) -> str:
        """Level 3: 向量库检索到的往事 (约 1000 Tokens)"""
        try:
            # 召回最相关的 3 个故事片段
            memories = self.vector_db.search(query, top_k=3)
            if not memories:
                return "（此刻脑海中没有想起具体的往事细节）"
            
            return "\n".join([f"- {doc.page_content}" for doc in memories])
        except Exception as e:
            logger.error(f"RAM 检索失败: {e}")
            return "（记忆通路暂时阻塞）"

    def generate_avatar_response(self, user_query: str, chat_history: list = None) -> str:
        """生成分身的最终回复"""
        # 1. 采集各层级数据
        l1 = self._get_level_1_rom()
        l2 = self._get_level_2_personality()
        l3 = self._get_level_3_ram(user_query)

        # 2. 注入模版
        full_system_prompt = AVATAR_RAG_FRAMEWORK.format(
            level_1_rom=l1,
            level_2_personality=l2,
            level_3_ram=l3
        )

        # 3. 构造消息
        messages = [{"role": "system", "content": full_system_prompt}]
        if chat_history:
            # 只保留 user 和 assistant 的近期对话（滑动窗口）
            history = [m for m in chat_history if m["role"] != "system"][-10:]
            messages.extend(history)
        
        messages.append({"role": "user", "content": user_query})

        # 4. 生成
        logger.info(f"🧠 分身正在思考... RAM 召回长度: {len(l3)}")
        return self.llm_router.generate_response(messages)