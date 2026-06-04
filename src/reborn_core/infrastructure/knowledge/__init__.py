from .frontmatter import parse_frontmatter

__all__ = ["AssetScanner", "load_processed_knowledge", "parse_frontmatter"]


def __getattr__(name: str):
    if name == "AssetScanner":
        from .scanner import AssetScanner

        return AssetScanner
    if name == "load_processed_knowledge":
        from .pipeline import load_processed_knowledge

        return load_processed_knowledge
    raise AttributeError(name)
