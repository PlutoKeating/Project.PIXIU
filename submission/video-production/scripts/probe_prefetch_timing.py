#!/usr/bin/env python3
"""Controlled timing probe of the real provider; no LLM-success claim."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'third_party/kylin-agent-runtime'))
from integrations.kylin_agent.tests.test_provider import FakeClient
from integrations.kylin_agent.pixiu import PixiuMemoryProvider


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ready-before-prefetch', action='store_true')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output exists')
    entered, release = threading.Event(), threading.Event()

    class ControlledClient(FakeClient):
        def request(self, method, path, payload=None):
            if path == '/agent/context':
                entered.set()
                if not release.wait(3):
                    raise RuntimeError('Probe did not release context response')
                return {'context': '周六上午九点一起整理书房，书籍按主题分类。', 'items': []}
            return super().request(method, path, payload)

    with tempfile.TemporaryDirectory(prefix='pixiu-prefetch-probe-') as directory:
        provider = PixiuMemoryProvider(client=ControlledClient(), scope='shared:home',
            runtime_version='0.9.8', outbox_directory=Path(directory)/'outbox', retries=0)
        provider.initialize('video-first-turn', hermes_home=directory)
        try:
            provider.on_turn_start(1, '周六书房有什么安排？')
            assert entered.wait(1), 'Context request never started'
            if args.ready_before_prefetch:
                release.set()
                assert provider.wait_for_idle(1), 'Context request did not finish'
            first = provider.prefetch('周六书房有什么安排？')
            release.set()
            assert provider.wait_for_idle(1), 'Context request did not finish'
            later = provider.prefetch('周六书房有什么安排？')
            result = {'scenario': '新会话缓存读取时序对照',
                      'query_ready_before_read': args.ready_before_prefetch,
                      'first_turn_context': first, 'after_completion_context': later,
                      'first_turn_has_memory': bool(first),
                      'boundary': '真实 provider 与受控 API 响应；不是实际模型请求追踪或端到端回答验证。'}
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
            print(json.dumps(result, ensure_ascii=False))
        finally:
            release.set()
            provider.shutdown()
    assert first, 'First turn received no shared memory before the model loop'


if __name__ == '__main__':
    main()
