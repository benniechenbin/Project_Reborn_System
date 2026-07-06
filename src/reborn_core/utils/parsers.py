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


def clean_markdown_noise(text: str) -> str:
    """
    清洗 Obsidian 特有的 Markdown 噪音，提取高纯度文本供 RAG 使用。
    """
    if not text:
        return ""

    # 1. 移除图片 (Obsidian 本地格式 ![[...]] 和标准格式 ![...](...))
    text = re.sub(r"!\[\[.*?\]\]", "", text)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)

    # 2. 处理双向链接
    # 匹配带有别名的双链 [[源文件|别名]] -> 提取别名
    text = re.sub(r"\[\[[^\]]+\|([^\]]+)\]\]", r"\1", text)
    # 匹配普通双链 [[源文件]] -> 提取源文件名
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)

    # 3. 移除块引用标识符 (如段落末尾的 ^block-id)
    text = re.sub(r"\^[a-zA-Z0-9-]+(\s|$)", r"\1", text)

    # 4. 移除行内标签 (如 #亲子/故事)
    # 避开 Markdown 标题 (要求 # 必须在行首紧跟空格)，只匹配前面是空格或行首的标签
    text = re.sub(r"(^|\s)#[^\s#]+", r"\1", text)

    # 5. 清理因抹除内容而产生的多余空白字符和连续换行
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
