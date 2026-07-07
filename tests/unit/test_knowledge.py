import pytest
from pathlib import Path
from reborn_core.infrastructure.knowledge.scanner import AssetScanner
import wave


@pytest.fixture
def mock_vault(tmp_path):
    vault = tmp_path / "obsidian_vault"
    vault.mkdir()

    # Create target folders
    values_dir = vault / "02_Values"
    values_dir.mkdir()
    stories_dir = vault / "03_Stories"
    stories_dir.mkdir()

    # Add some md files
    (values_dir / "honesty.md").write_text(
        "---\ntags: values\n---\n# Honesty\nWe always tell the truth.", encoding="utf-8"
    )
    (stories_dir / "childhood.md").write_text(
        "---\ndate: 2026-01-01\n---\n# Childhood\nI was born in...", encoding="utf-8"
    )

    # Add some wav files
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()

    def create_wav(path, duration_sec):
        with wave.open(str(path), "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(44100)
            f.writeframes(b"\x00" * int(44100 * 2 * duration_sec))

    create_wav(audio_dir / "test1.wav", 60)  # 1 minute
    create_wav(audio_dir / "test2.wav", 30)  # 0.5 minute

    return vault, audio_dir


def load_processed_knowledge_with_rag(*args, **kwargs):
    pytest.importorskip("langchain_community")
    from reborn_core.infrastructure.knowledge.pipeline import load_processed_knowledge

    return load_processed_knowledge(*args, **kwargs)


def test_load_processed_knowledge(mock_vault):
    vault_path, _ = mock_vault
    target_folders = ["02_Values", "03_Stories"]

    docs = load_processed_knowledge_with_rag(
        vault_path=vault_path,
        target_folders=target_folders,
    )

    assert len(docs) == 2
    assert any("Honesty" in d.page_content for d in docs)
    assert any("Childhood" in d.page_content for d in docs)
    # Check frontmatter was parsed and stripped
    assert all("---" not in d.page_content for d in docs)
    assert any(d.metadata.get("category") == "02_Values" for d in docs)


def test_load_processed_knowledge_missing_folder(mock_vault):
    vault_path, _ = mock_vault
    target_folders = ["02_Values", "04_NonExistent"]

    docs = load_processed_knowledge_with_rag(
        vault_path=vault_path,
        target_folders=target_folders,
    )
    assert len(docs) == 1


def test_load_processed_knowledge_invalid_path():
    from reborn_core.infrastructure.knowledge.pipeline import load_processed_knowledge

    docs = load_processed_knowledge(vault_path=Path("/non/existent/path"), target_folders=[])
    assert docs == []


def test_asset_scanner_notes_and_words(mock_vault):
    vault_path, audio_dir = mock_vault
    scanner = AssetScanner(vault_path, audio_dir)

    notes, words = scanner.count_notes_and_words()
    assert notes == 2
    assert words > 0


def test_asset_scanner_can_limit_notes_to_target_folders(mock_vault):
    vault_path, audio_dir = mock_vault
    private_dir = vault_path / "99_Private"
    private_dir.mkdir()
    (private_dir / "diary.md").write_text("this should not be counted", encoding="utf-8")
    scanner = AssetScanner(vault_path, audio_dir, target_folders=("02_Values",))

    notes, words = scanner.count_notes_and_words()

    assert notes == 1
    assert words > 0


def test_asset_scanner_audio_duration(mock_vault):
    vault_path, audio_dir = mock_vault
    scanner = AssetScanner(vault_path, audio_dir)

    duration = scanner.count_audio_duration()
    assert duration == 1.5  # 60s + 30s = 90s = 1.5 min


def test_asset_scanner_missing_paths():
    scanner = AssetScanner(Path("/non/existent/vault"), Path("/non/existent/audio"))
    assert scanner.count_notes_and_words() == (0, 0)
    assert scanner.count_audio_duration() == 0.0
