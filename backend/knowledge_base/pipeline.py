import re
import os
from pathlib import Path
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from backend.core.settings import settings
from backend.core.logger import logger

def parse_frontmatter(content: str) -> dict:
    """提取 YAML 标签"""
    metadata = {"date": "未知日期", "tags": [], "source": "upload"}
    yaml_match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
    if yaml_match:
        yaml_str = yaml_match.group(1)
        date_match = re.search(r'^date:\s*["\']?(\d{4}[-/]\d{2}[-/]\d{2})["\']?', yaml_str, re.MULTILINE)
        if date_match:
            metadata["date"] = date_match.group(1).replace('/', '-')
        tags_match = re.search(r'^tags:\s*(.*)', yaml_str, re.MULTILINE)
        if tags_match:
            raw_tags = tags_match.group(1).strip().replace('[', '').replace(']', '').replace('"', '').replace("'", "")
            metadata["tags"] = [t.strip() for t in raw_tags.split(',') if t.strip()]
    return metadata

def load_processed_knowledge():
    """扫描标品库并进行深度审计 (已支持指定目录白名单)"""
    vault_path = Path(settings.active_obsidian_path)
    
    if not vault_path.exists():
        logger.error("❌ 错误：未配置有效的 Obsidian 路径，或路径不存在。")
        return []

    target_folders = settings.REBORN_TARGET_FOLDERS
    final_docs = []

    # 遍历白名单中的文件夹进行定向扫描
    for folder_name in target_folders:
        folder_path = vault_path / folder_name
        
        if not folder_path.exists():
            logger.warning(f"⚠️ 目标文件夹不存在，已跳过: {folder_path}")
            continue
            
        logger.info(f"🔎 正在扫描专属目录: {folder_name} ...")
        loader = DirectoryLoader(
            str(folder_path), 
            glob="**/*.md", 
            loader_cls=TextLoader,
            loader_kwargs={'encoding': 'utf-8'}
        )
        raw_docs = loader.load()

        for doc in raw_docs:
            meta = parse_frontmatter(doc.page_content)
            doc.metadata.update(meta)
            # 附加它所在的文件夹名，方便日后溯源
            doc.metadata["category"] = folder_name
            # 抹除 YAML 头部
            doc.page_content = re.sub(r'^---\n.*?\n---\n', '', doc.page_content, flags=re.DOTALL)
            final_docs.append(doc)
    
    logger.info(f"✅ 审计完成，共从 {len(target_folders)} 个核心目录中提取 {len(final_docs)} 篇高纯度记忆。")
    return final_docs