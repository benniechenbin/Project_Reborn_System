# tests/unit/test_markdown_cleaner.py

from reborn_core.utils.parsers import clean_markdown_noise


def test_clean_obsidian_markdown():
    # 模拟极端脏乱的真实 Obsidian 笔记样本
    dirty_text = """
    # 动物园游记
    今天带 [[宁宁]] 去了野生动物园，这简直是最好玩的一天。
    ![[PXL_20260701.jpg]]
    ![孩子画的恐龙](https://example.com/dino.png)
    他指着长颈鹿说：“爸爸，看那个！” #亲子/故事 #陈斌/回忆
    想了解更多可以看看 [[2025-10-01_国庆日记|国庆节去野生动物园]]。
    这也是一段珍贵的记忆。^a1b2c3
    """

    clean_text = clean_markdown_noise(dirty_text)

    # 断言 1：双链被正确还原为自然语言
    assert "[[宁宁]]" not in clean_text
    assert "宁宁" in clean_text
    assert "[[2025-10-01_国庆日记|国庆节去野生动物园]]" not in clean_text
    assert "国庆节去野生动物园" in clean_text

    # 断言 2：多媒体图片和块级引用被彻底抹除
    assert "![[PXL_20260701.jpg]]" not in clean_text
    assert "![孩子画的恐龙]" not in clean_text
    assert "^a1b2c3" not in clean_text

    # 断言 3：行内标签被抹除，但大标题的 H1/H2 井号必须保留
    assert "#亲子/故事" not in clean_text
    assert "#陈斌/回忆" not in clean_text
    assert "# 动物园游记" in clean_text

    # 断言 4：不能有诡异的连续换行（清洗后格式应紧凑）
    assert "\n\n\n" not in clean_text
