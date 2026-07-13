from enum import StrEnum


class LegacyActivationMode(StrEnum):
    """控制数字遗产陪伴功能是否可以被激活。"""

    OWNER_ONLY = "owner_only"
    ACTIVATION_FILE = "activation_file"
    ACTIVATED = "activated"
