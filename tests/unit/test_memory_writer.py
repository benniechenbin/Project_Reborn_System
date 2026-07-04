from reborn_core.domains.memory.memory_writer import MemoryWriter


def test_derived_memory_references_immutable_transcript(tmp_path, test_settings):
    writer = MemoryWriter(app_settings=test_settings, obsidian_root=tmp_path)

    source_ref = writer.save_source_transcript("旅行", "user: 原始访谈", "life_story")
    assert writer.save_story("旅行", "提炼结果", source_ref=source_ref)

    source_files = list((tmp_path / "01_Source_Artifacts" / "Interviews").glob("*.md"))
    story = (tmp_path / "03_Stories" / "旅行.md").read_text(encoding="utf-8")
    assert len(source_files) == 1
    assert "user: 原始访谈" in source_files[0].read_text(encoding="utf-8")
    assert f'source_artifact: "{source_ref}"' in story
    assert "date: " in story
    assert "+00:00" in story


def test_master_identity_keeps_previous_snapshot(tmp_path, test_settings):
    writer = MemoryWriter(app_settings=test_settings, obsidian_root=tmp_path)

    assert writer.save_master_identity("version 1")
    assert writer.save_master_identity("version 2")

    history_files = list((tmp_path / "02_Values" / "00_Identity_History").glob("*.md"))
    assert len(history_files) == 1
    assert history_files[0].read_text(encoding="utf-8") == "version 1"
