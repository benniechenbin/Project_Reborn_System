import time
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from backend.observability.logger import logger
from backend.config.settings import settings
from openai import OpenAI

class LLMRouter:
    """
    统一的大模型路由中枢
    负责管理所有的对话请求，支持无缝切换不同的底层模型。
    """
    def __init__(self):
        # 统一使用 settings 读取配置，彻底抛弃 os.getenv
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url
        self.model_name = settings.llm_model_name
        
        if not self.api_key:
            raise ValueError("❌ 致命错误：未在 .env 中找到 LLM_API_KEY，或 settings 未能成功加载")

        # 初始化标准客户端
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),        
        reraise=True
    )
    def generate_response(self, messages: list, temperature: float = 0.7) -> str:
        """
        发送多轮对话并获取回复
        :param messages: 标准的消息列表 [{"role": "system", "content": "..."}, ...]
        """
        try:
            logger.debug(f"正在向大模型发送请求，包含 {len(messages)} 条上下文...")
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=1500
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"⚠️ 大模型 API 调用异常，准备重试: {e}")
            raise e

# 测试代码
if __name__ == "__main__":
    router = LLMRouter()
    test_msgs = [{"role": "user", "content": "你好，测试一下连接。"}]
    logger.info(router.generate_response(test_msgs))