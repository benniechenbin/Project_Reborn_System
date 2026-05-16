
import json
from pathlib import Path
from datetime import datetime

from .llm_router import LLMRouter
from .prompts import AVATAR_RAG_FRAMEWORK
from backend.config import settings
from backend.memory.vector_store import QdrantDBProvider
from backend.observability import logger

class RAGEngine:
    def __init__(self):
        self.llm_router = LLMRouter()
        self.vector_db = QdrantDBProvider()
        # 确定记忆存储路径
        try:
            obsidian_root = Path(settings.active_obsidian_path) if settings.active_obsidian_path else Path("data/memories")
        except Exception:
            obsidian_root = Path("data/memories")
            
        self.core_memories_path = obsidian_root / "02_Values"
        self.reflections_path = self.core_memories_path / "00_AI_Reflections"
        
        # 🚀 新增：盲区记录文件路径
        self.gap_file = Path("data/memory_gaps.json")

        self.child_name = settings.child_name
        self.child_nickname = settings.child_nickname
        self.child_gender = settings.child_gender
        self.child_birthday = datetime.strptime(settings.child_birthday, "%Y-%m-%d")

    def _calculate_child_age_and_tone(self) -> str:
        """🌟 核心动态逻辑：年龄感知与语气路由"""
        now = datetime.now()
        age = now.year - self.child_birthday.year - ((now.month, now.day) < (self.child_birthday.month, self.child_birthday.day))
        pronoun = "他" if self.child_gender == "男" else "她"
        son_or_daughter = "儿子" if self.child_gender == "男" else "女儿"
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
        persona_file = self.core_memories_path / "00_Master_Identity.md" 
        directives_file = self.core_memories_path / "03_Prime_Directives.md"
        rom_content = ""
        if persona_file.exists():
            rom_content += persona_file.read_text(encoding='utf-8') + "\n"
        if directives_file.exists():
            rom_content += "### 最高行为准则\n" + directives_file.read_text(encoding='utf-8')
        now = datetime.now()
        env_info = f"\n---\n当前现实时间：{now.strftime('%Y-%m-%d %H:%M')}，星期{now.weekday()+1}。"
        age_routing_info = f"\n{self._calculate_child_age_and_tone()}"
        return rom_content + env_info + age_routing_info

    def _get_level_2_personality(self) -> str:
        if not self.reflections_path.exists():
            return "（近期性格稳定，暂无动态更新）"
        files = sorted(self.reflections_path.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)[:3]
        summaries = []
        for f in files:
            try:
                content = f.read_text(encoding='utf-8')
                summaries.append(f"【近期感悟】：{content}")
            except Exception as e:
                logger.error(f"读取反思文件失败: {e}")
        return "\n\n".join(summaries) if summaries else "（暂无近期性格碎片）"

    def _get_level_3_ram(self, query: str) -> tuple:
        """🚀 终极版：返回 (文本, 分数, 原始记忆源)"""
        try:
            memories = self.vector_db.search(query, top_k=3)
            if not memories:
                return "（此刻脑海中没有想起具体的往事细节）", -1.0, []
            
            # 提取最高分数
            max_score = memories[0].metadata.get("rerank_score", 0.0)
            ram_text = "\n".join([f"- {doc.page_content}" for doc in memories])
            
            # 必须把 memories (即 references) 也返回，给前端用
            return ram_text, max_score, memories
        except Exception as e:
            logger.error(f"RAM 检索失败: {e}")
            return "（记忆通路暂时阻塞）", -1.0, []

    def _record_memory_gap(self, query: str, score: float):
        """🚀 核心：记录记忆盲区日志"""
        gap_entry = {
            "query": query,
            "score": score,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        gaps = []
        if self.gap_file.exists():
            try:
                with open(self.gap_file, 'r', encoding='utf-8') as f:
                    gaps = json.load(f)
            except Exception:
                gaps = []
        
        # 只保留最近 100 条记录
        gaps.append(gap_entry)
        gaps = gaps[-100:]
        
        with open(self.gap_file, 'w', encoding='utf-8') as f:
            json.dump(gaps, f, ensure_ascii=False, indent=2)
        logger.warning(f"🕵️ 发现记忆盲区，已记录查询: {query} (Score: {score})")

    def generate_avatar_response(self, user_query: str, chat_history: list = None) -> tuple:
        """生成分身的最终回复"""
        l1 = self._get_level_1_rom()
        l2 = self._get_level_2_personality()
        
        # 🚀 完美接住三个返回值
        l3_text, max_score, references = self._get_level_3_ram(user_query)

        # 盲区监测
        if max_score < -0.8:
            self._record_memory_gap(user_query, max_score)

        full_system_prompt = AVATAR_RAG_FRAMEWORK.format(
            level_1_rom=l1,
            level_2_personality=l2,
            level_3_ram=l3_text
        )

        messages = [{"role": "system", "content": full_system_prompt}]
        if chat_history:
            history = [m for m in chat_history if m["role"] != "system"][-10:]
            messages.extend(history)
        messages.append({"role": "user", "content": user_query})

        logger.info(f"🧠 分身正在思考... RAM 召回分值: {max_score}")
        response_text = self.llm_router.generate_response(messages)
        
        # 🚀 必须返回元组，满足 app.py 的解包需求
        return response_text, references