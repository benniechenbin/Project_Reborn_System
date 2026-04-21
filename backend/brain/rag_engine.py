import logging
from pathlib import Path
from backend.brain.llm_router import LLMRouter
from backend.brain.prompts import AVATAR_RAG_FRAMEWORK
from backend.memory.vector_store.vector_qdrant import QdrantDBProvider
from backend.core.settings import settings
from backend.brain.prompts import AVATAR_RAG_FRAMEWORK

logger = logging.getLogger(__name__)

class RAGEngine:
    """
    Project Reborn 核心检索生成引擎
    负责组装“只读记忆(ROM)”与“随机存取记忆(RAM)”，驱动分身思考。
    """
    def __init__(self):
        self.llm_router = LLMRouter()
        self.vector_db = QdrantDBProvider()
        # 核心价值观文件夹 (ROM)
        self.core_values_dir = Path("data/memories/core_values")

    def _load_rom_persona(self) -> str:
        """读取 data/memories/core_values 下的所有固化 Markdown，作为最高指令"""
        rom_texts = []
        if self.core_values_dir.exists():
            for md_file in self.core_values_dir.glob("*.md"):
                try:
                    content = md_file.read_text(encoding='utf-8')
                    rom_texts.append(f"### {md_file.stem}\n{content}")
                except Exception as e:
                    logger.error(f"读取核心记忆失败 {md_file.name}: {e}")
        
        return "\n\n".join(rom_texts) if rom_texts else "（暂无固化价值观数据）"

    def generate_avatar_response(self, user_query: str, chat_history: list = None) -> str:
        """
        生成分身的最终回复
        """
        # 1. 召回动态记忆碎片 (RAM)
        logger.info(f"🔎 正在为提问召回记忆碎片: {user_query}")
        memories = self.vector_db.search(user_query, top_k=3)
        
        memory_context = ""
        if memories:
            memory_context = "\n".join([f"- {doc.page_content}" for doc in memories])
        else:
            memory_context = "（未在潜意识池中找到相关具体往事）"

        # 2. 获取固化人设 (ROM)
        core_persona = self._load_rom_persona()

        # 3. 构造终极 System Prompt
        # 注入你预定义的人设模板，并融合实时召回的上下文
        full_system_prompt = AVATAR_RAG_FRAMEWORK.format(
            core_persona=core_persona,
            memory_context=memory_context
        )

        # 4. 构建消息队列
        messages = [{"role": "system", "content": full_system_prompt}]
        
        if chat_history:
            # 过滤掉系统提示词，只保留对话
            history = [m for m in chat_history if m["role"] != "system"]
            messages.extend(history)
            
        messages.append({"role": "user", "content": user_query})

        # 5. 调用大模型
        return self.llm_router.generate_response(messages)