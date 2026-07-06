import re
from pathlib import Path
from collections.abc import Sequence

from reborn_core.config import get_settings
from reborn_core.observability import logger
from reborn_core.infrastructure.knowledge.frontmatter import parse_frontmatter
from reborn_core.utils.parsers import clean_markdown_noise


def load_processed_knowledge(
    vault_path: Path | None = None,
    target_folders: Sequence[str] | None = None,
):
    """扫描标品库并进行深度审计 (已支持指定目录白名单)"""
    settings = get_settings()
    vault_path = vault_path or settings.active_obsidian_path

    if vault_path is None or not vault_path.exists():
        logger.error("❌ 错误：未配置有效的 Obsidian 路径，或路径不存在。")
        return []

    try:
        from langchain_community.document_loaders import DirectoryLoader, TextLoader
    except ImportError as exc:
        raise RuntimeError(
            "Memory sync requires installing the `rag` optional dependencies."
        ) from exc

    target_folders = target_folders or settings.memory_index_folders
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
            loader_kwargs={"encoding": "utf-8"},
        )
        raw_docs = loader.load()

        for doc in raw_docs:
            meta = parse_frontmatter(doc.page_content)
            doc.metadata.update(meta)
            # 附加它所在的文件夹名，方便日后溯源
            doc.metadata["category"] = folder_name
            # 抹除 YAML 头部
            doc.page_content = re.sub(r"^---\n.*?\n---\n", "", doc.page_content, flags=re.DOTALL)

            # 👇 新增：调用我们刚刚写好的高纯度清洗器
            doc.page_content = clean_markdown_noise(doc.page_content)

            final_docs.append(doc)

    logger.info(
        f"✅ 审计完成，共从 {len(target_folders)} 个核心目录中提取 {len(final_docs)} 篇高纯度记忆。"
    )
    return final_docs
