def show_banner(
    text: str = "MULTI AGENT LAB",
    font: str = "slant",
    width: int = 80,
    justify: str = "center",
    color: bool = True
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
    # 顶部留白，彻底与上一条日志隔开
    print("\n" + "=" * 60)
    
    try:
        import pyfiglet
        banner_text = pyfiglet.figlet_format(
            text, 
            font=font,
            width=width,
            justify=justify
        ) 
        if color:
            print(f"\033[1m\033[36m{banner_text}\033[0m", end="")
        else:
            print(banner_text, end="")
        
    except ImportError:       
        print(f"🚀 {text}")
        
    print("=" * 60 + "\n")

# 如果你想测试字体，可以直接运行这个文件
if __name__ == "__main__":
    # 基础用法
    print("=== 基础示例 ===")
    show_banner("AGENT LAB", font="slant")
    
    # 自定义参数示例
    print("\n=== 自定义样式示例 ===")
    show_banner(
        "PYTHON", 
        font="block", 
        width=60, 
        justify="center", 
        color=True
    )
    
    # 不同字体对比
    print("\n=== 不同字体对比 ===")
    test_fonts = ["standard", "digital", "bubble"]
    for fnt in test_fonts:
        print(f"\n字体: {fnt}")
        show_banner("TEST", font=fnt, width=40)