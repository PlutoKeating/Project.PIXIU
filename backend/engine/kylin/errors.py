"""麒麟 SDK 相关异常。"""

from __future__ import annotations


class KylinSDKUnavailableError(RuntimeError):
    """麒麟 SDK（原生扩展/运行库）不可用。

    生产环境没有 mock 降级：SDK 缺失即抛出此异常，附构建指引。
    """
