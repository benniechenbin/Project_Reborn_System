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

    vault_path = settings.active_obsidian_path
    
    if not vault_path:
        print("❌ 错误：未配置有效的 Obsidian 路径，请检查 .env 文件")
        return []

    # 1. 初始化加载器：指向当前系统激活的路径
    loader = DirectoryLoader(
        str(vault_path), 
        glob="**/*.md", 
        loader_cls=TextLoader,
        loader_kwargs={'encoding': 'utf-8'}
    )
    
    raw_docs = loader.load()
    final_docs = []

    for doc in raw_docs:
        # 2. 调用审计员解析元数据
        meta = parse_frontmatter(doc.page_content)
        
        # 3. 将解析出的标签注入到 Document 的 metadata 中
        doc.metadata.update(meta)
        
        # 4. 抹除 YAML 头部，防止干扰向量模型理解正文
        doc.page_content = re.sub(r'^---\n.*?\n---\n', '', doc.page_content, flags=re.DOTALL)
        
        final_docs.append(doc)
    
    print(f"✅ 审计完成，已从 {vault_path} 加载 {len(final_docs)} 篇知识文档。")
    return final_docs