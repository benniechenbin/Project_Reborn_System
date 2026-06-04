from collections.abc import Mapping, Sequence
from typing import Any

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from reborn_core.application.models import ModelMetadata
from reborn_core.utils.parsers import parse_think_tags
from reborn_core.config import Settings, get_settings
from reborn_core.observability import logger


class LLMRouter:
    """
    统一的大模型路由中枢
    负责管理所有的对话请求，支持无缝切换不同的底层模型。
    """

    def __init__(
        self,
        app_settings: Settings | None = None,
        client: Any | None = None,
    ) -> None:
        settings = app_settings or get_settings()
        self.api_key = (
            settings.llm_api_key.get_secret_value() if settings.llm_api_key is not None else ""
        )
        self.base_url = settings.llm_base_url
        self.model_name = settings.llm_model_name

        if not self.api_key:
            raise ValueError("❌ 致命错误：未在 .env 中找到 LLM_API_KEY，或 settings 未能成功加载")

        # 初始化标准客户端
        self.client = client or OpenAI(api_key=self.api_key, base_url=self.base_url)

    @property
    def model_metadata(self) -> ModelMetadata:
        return ModelMetadata(
            provider="openai-compatible",
            model_name=self.model_name,
            base_url=self.base_url,
        )

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True
    )
    def generate_response(
        self,
        messages: Sequence[Mapping[str, str]],
        temperature: float = 0.7,
    ) -> str:
        """
        发送多轮对话并获取回复
        :param messages: 标准的消息列表 [{"role": "system", "content": "..."}, ...]
        """
        try:
            logger.debug(f"正在向大模型发送请求，包含 {len(messages)} 条上下文...")
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=list(messages),
                temperature=temperature,
                max_tokens=1500,
            )
            raw_text = response.choices[0].message.content

            parsed = parse_think_tags(raw_text)
            final_text = parsed["response"]

            if parsed["thought"]:
                logger.debug(f"🧠 分身内部反思 (未泄露给用户): \n{parsed['thought']}")

            forbidden_words = ["人工智能", "语言模型", "AI助理", "我是AI", "大语言模型"]
            if any(word in final_text for word in forbidden_words):
                logger.error(f"🚨 严重防火墙拦截！模型触发破壁词汇。被拦截原文: {final_text}")
                # 触发终极降级兜底，死守身份底线
                return "爸爸刚才走神了，你能再说一遍吗？"
            return final_text

        except Exception as e:
            logger.warning(f"⚠️ 大模型 API 调用异常，准备重试: {e}")
            raise


# 测试代码
if __name__ == "__main__":
    router = LLMRouter()
    test_msgs = [{"role": "user", "content": "你好，测试一下连接。"}]
    logger.info(router.generate_response(test_msgs))
