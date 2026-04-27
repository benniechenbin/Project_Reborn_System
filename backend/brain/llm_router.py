# backend/brain/llm_router.py
from openai import OpenAI
from backend.config.settings import settings 

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

    def generate_response(self, messages: list, temperature: float = 0.7) -> str:
        """
        发送多轮对话并获取回复
        :param messages: 标准的消息列表 [{"role": "system", "content": "..."}, ...]
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=1500
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"❌ 大脑响应异常，请检查网络或 API 配置: {e}"

# 测试代码
if __name__ == "__main__":
    router = LLMRouter()
    test_msgs = [{"role": "user", "content": "你好，测试一下连接。"}]
    print(router.generate_response(test_msgs))