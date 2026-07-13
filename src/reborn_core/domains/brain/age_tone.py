from datetime import date, datetime


def calculate_age(birthday: date, now: datetime) -> int:
    return now.year - birthday.year - ((now.month, now.day) < (birthday.month, birthday.day))


def build_child_age_tone(
    child_name: str,
    child_nickname: str,
    child_gender: str,
    child_birthday: date,
    now: datetime,
) -> str:
    age = calculate_age(child_birthday, now)
    if child_gender == "男":
        pronoun, son_or_daughter = "他", "儿子"
    elif child_gender == "女":
        pronoun, son_or_daughter = "她", "女儿"
    else:
        raise ValueError(f"Unsupported child gender: {child_gender!r}")

    if age < 6:
        tone = (
            f"{child_nickname}现在还很小（大约 {age} 岁）。你是{pronoun}的爸爸。"
            "请使用非常通俗、温柔、带有童话色彩的词汇。多用比喻，像讲故事一样"
            f"跟{pronoun}说话，语气要充满父亲对{son_or_daughter}的宠溺与耐心。"
            f"称呼{pronoun}时请使用小名'{child_nickname}'。"
        )
    elif age < 13:
        tone = (
            f"{child_nickname}现在上小学了（大约 {age} 岁）。请使用鼓励、引导的父亲"
            f"口吻，可以教{pronoun}一些简单的科学道理和处事原则，像朋友一样平等交流。"
            f"记得多叫{pronoun}的小名'{child_nickname}'。"
        )
    elif age < 18:
        tone = (
            f"{child_nickname}现在是青春期了（大约 {age} 岁）。请使用成熟、开明、"
            f"带点极客幽默的口吻。尊重{pronoun}的独立思考，绝对不要说教，"
            f"多引导{pronoun}探索世界。"
        )
    else:
        tone = (
            f"{child_nickname}现在已经是成年人了（大约 {age} 岁）。"
            "请使用成年人之间深沉、平等的对话方式，分享你的人生智慧和哲学思考。"
        )

    return (
        f"【动态感知】孩子大名：{child_name}，小名：{child_nickname}，"
        f"性别：{child_gender}，当前年龄：{age} 岁。\n"
        f"【强制语气约束】：{tone}"
    )
