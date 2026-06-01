import pytest
from unittest.mock import MagicMock
from pathlib import Path

@pytest.fixture
def mock_settings(mocker):
    """Mock 全局配置，防止测试读取真实的 .env 或路径"""
    mock = mocker.patch("backend.brain.rag_engine.settings")
    mock.child_name = "张小明"
    mock.child_nickname = "明明"
    mock.child_gender = "男"
    mock.child_birthday = "2020-01-01"
    mock.active_obsidian_path = "/tmp/fake_obsidian"
    return mock

@pytest.fixture
def mock_vector_db(mocker):
    """Mock 向量数据库，避免初始化真实的 Qdrant 连接"""
    return mocker.patch("backend.brain.rag_engine.QdrantDBProvider", autospec=True)

@pytest.fixture
def mock_llm_router(mocker):
    """Mock LLM 路由，避免产生真实的 API 调用费用"""
    return mocker.patch("backend.brain.rag_engine.LLMRouter", autospec=True)
