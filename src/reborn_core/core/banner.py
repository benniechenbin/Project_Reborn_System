def show_banner(
    text: str = "MULTI AGENT LAB",
    font: str = "slant",
    width: int = 80,
    justify: str = "center",
    color: bool = True,
):
    """
    动态生成并打印 ASCII Banner。

    常用字体推荐:
    - slant (经典斜体，强烈推荐)
    - standard (标准块状)
    - block (厚重方块)
    - digital (电子表风格)
    - banner (简约横幅)
    - bubble (气泡风格)
    - doh (卡通风格)
    - graffiti (涂鸦风格)

    pyfiglet 参数详解:
    :param text: 要显示的文本内容
    :param font: 字体名称 (默认: "slant")，可用字体可通过 pyfiglet.FigletFont.getFonts() 查看
    :param width: 输出宽度 (默认: 80)，控制 banner 的最大宽度
    :param justify: 对齐方式 (默认: "center")，可选: "left", "center", "right"
    :param color: 是否启用彩色输出 (默认: True)，使用 ANSI 转义序列

    依赖:
    - pyfiglet: ASCII 艺术生成库 (可选)
    """
    try:
        import pyfiglet

        # 1. 先生成内容
        banner_text = pyfiglet.figlet_format(text, font=font, width=width, justify=justify)

        # 2. 动态计算实际输出的最大宽度（去除末尾可能的多余空行）
        lines = banner_text.rstrip("\n").split("\n")
        actual_width = max((len(line) for line in lines), default=60)

        # 3. 按实际宽度打印顶部边框
        print("\n" + "=" * actual_width)

        # 4. 打印带颜色或不带颜色的内容
        if color:
            print(f"\033[1m\033[36m{banner_text}\033[0m", end="")
        else:
            print(banner_text, end="")

        # 5. 打印底部边框
        print("=" * actual_width + "\n")

    except ImportError:
        # 如果没有安装 pyfiglet，降级显示时也做个动态自适应
        fallback_text = f"🚀 {text}"
        actual_width = len(fallback_text) + 4  # 加点 padding 更美观
        print("\n" + "=" * actual_width)
        print(f"  {fallback_text}")
        print("=" * actual_width + "\n")


# 测试区
if __name__ == "__main__":
    print("=== 基础示例 ===")
    show_banner("AGENT LAB", font="slant")

    print("\n=== 自定义样式示例 ===")
    show_banner("PYTHON", font="block", width=60, justify="center", color=True)

    print("\n=== 不同字体对比 ===")
    test_fonts = ["standard", "digital", "bubble"]
    for fnt in test_fonts:
        print(f"\n字体: {fnt}")
        # 这里故意把 width 设窄，你会发现等号也会聪明地跟着变短
        show_banner("TEST", font=fnt, width=40)
