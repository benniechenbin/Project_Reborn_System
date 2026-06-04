class RebornError(Exception):
    """Project Reborn 所有自定义异常的基类。"""

    pass


class ConfigurationError(RebornError):
    """当系统配置缺失、无效或冲突时抛出。"""

    pass


class DomainError(RebornError):
    """当业务逻辑或领域规则遭到破坏时抛出。"""

    pass


class InfrastructureError(RebornError):
    """当底层基础设施（数据库、文件系统、API）发生非预期故障时抛出。"""

    pass


class SecurityError(RebornError):
    """当检测到非法访问或安全策略冲突时抛出。"""

    pass
