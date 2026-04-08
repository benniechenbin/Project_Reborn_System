# services/file_loader.py
import re
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from config.settings import settings
from langchain_core.documents import Document

def parse_frontmatter(content: str) -> dict:
    """【保留并沿用】审计员：负责从 MD 文本中提取 YAML 标签"""
    metadata = {"date": "未知日期", "tags": [], "source": "upload"}
    
    yaml_match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
    if yaml_match:
        yaml_str = yaml_match.group(1)
        
        # 1. 提取日期
        date_match = re.search(r'^date:\s*["\']?(\d{4}[-/]\d{2}[-/]\d{2})["\']?', yaml_str, re.MULTILINE)
        if date_match:
            metadata["date"] = date_match.group(1).replace('/', '-')

        # 2. 提取 Tags
        tags_match = re.search(r'^tags:\s*(.*)', yaml_str, re.MULTILINE)
        if tags_match:
            raw_tags = tags_match.group(1).strip().replace('[', '').replace(']', '').replace('"', '').replace("'", "")
            metadata["tags"] = [t.strip() for t in raw_tags.split(',') if t.strip()]

    return metadata

def load_processed_knowledge():
    """扫描标品库并进行深度审计"""
    loader = DirectoryLoader(
        str(settings.MD_KNOWLEDGE_DIR), 
        glob="**/*.md", 
        loader_cls=TextLoader,
        loader_kwargs={'encoding': 'utf-8'}
    )
    
    raw_docs = loader.load()
    final_docs = []

    for doc in raw_docs:
        # ✨ 关键动作：调用审计员解析元数据
        meta = parse_frontmatter(doc.page_content)
        
        # 将解析出的标签注入到 Document 的 metadata 中
        doc.metadata.update(meta)
        
        # 可选：如果不想让 YAML 头部污染向量库，可以把 header 部分从 page_content 中切除
        doc.page_content = re.sub(r'^---\n.*?\n---\n', '', doc.page_content, flags=re.DOTALL)
        
        final_docs.append(doc)
    
    print(f"✅ 审计完成，已加载 {len(final_docs)} 篇带标签的知识文档。")
    return final_docs