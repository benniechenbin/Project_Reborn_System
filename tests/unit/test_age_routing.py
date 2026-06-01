import pytest
from datetime import datetime
from unittest.mock import patch
from backend.brain.rag_engine import RAGEngine

def test_calculate_child_age_and_tone_child(mock_settings, mock_vector_db, mock_llm_router):
    # 设置生日为 4 年前
    mock_settings.child_birthday = "2022-01-01"
    
    with patch("backend.brain.rag_engine.datetime") as mock_date:
        # Mock 当前时间为 2026-05-29
        mock_date.now.return_value = datetime(2026, 5, 29)
        mock_date.strptime = datetime.strptime
        
        engine = RAGEngine()
        tone_info = engine._calculate_child_age_and_tone()
        
        assert "4 岁" in tone_info
        assert "温柔、带有童话色彩" in tone_info
        assert "明明" in tone_info

def test_calculate_child_age_and_tone_teen(mock_settings, mock_vector_db, mock_llm_router):
    # 设置生日为 15 年前
    mock_settings.child_birthday = "2011-01-01"
    
    with patch("backend.brain.rag_engine.datetime") as mock_date:
        mock_date.now.return_value = datetime(2026, 5, 29)
        mock_date.strptime = datetime.strptime
        
        engine = RAGEngine()
        tone_info = engine._calculate_child_age_and_tone()
        
        assert "15 岁" in tone_info
        assert "极客幽默" in tone_info

def test_calculate_child_age_and_tone_adult(mock_settings, mock_vector_db, mock_llm_router):
    # 设置生日为 25 年前
    mock_settings.child_birthday = "2001-01-01"
    
    with patch("backend.brain.rag_engine.datetime") as mock_date:
        mock_date.now.return_value = datetime(2026, 5, 29)
        mock_date.strptime = datetime.strptime
        
        engine = RAGEngine()
        tone_info = engine._calculate_child_age_and_tone()
        
        assert "25 岁" in tone_info
        assert "成年人之间深沉、平等" in tone_info
