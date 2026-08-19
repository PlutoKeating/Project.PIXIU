"""测试专用桩 —— 仅存在于 tests/，不参与生产代码。

生产代码默认优先麒麟 SDK，并在 Debian 环境使用独立的可移植软件实现。
本文件仅为隔离管线单元测试、精确控制向量输出而存在。
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
