import re


def parse_think_tags(text: str) -> dict[str, str]:
    """
    解析大模型输出中包含的 <think> 标签。
    返回字典: {"thought": 思考过程, "response": 最终回复}
    """
    # 使用 re.DOTALL 使得 . 可以匹配换行符，应对模型多行思考的情况
    pattern = re.compile(r"<think>(.*?)</think>\s*(.*)", re.DOTALL | re.IGNORECASE)
    match = pattern.search(text)

    if match:
        return {"thought": match.group(1).strip(), "response": match.group(2).strip()}

    # 如果模型没有按规范输出 <think> 标签，则默认全文本都是回复
    return {"thought": "", "response": text.strip()}
