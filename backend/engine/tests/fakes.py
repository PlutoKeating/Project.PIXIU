"""测试专用桩 —— 仅存在于 tests/，不参与生产代码。

生产代码不包含任何 mock：embedding 一律走麒麟 SDK（KylinTextEmbedding）。
本文件仅为在无麒麟 SDK 的开发机上运行管线逻辑测试而存在。
"""

from __future__ import annotations

import hashlib
import random


class StubTextEmbedder:
    """确定性文本向量桩（测试专用）：返回 dim 维 [-1, 1) 向量。"""

    def __init__(self, dim: int = 32) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        rng = random.Random(int.from_bytes(digest[:8], "big"))
        return [rng.uniform(-1.0, 1.0) for _ in range(self.dim)]
