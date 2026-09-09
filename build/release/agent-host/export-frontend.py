#!/usr/bin/env python3
"""Export product frontend inputs and the stable upstream CMake entry point."""
import json
from pathlib import Path
import shutil
import sys

root, target = map(Path, sys.argv[1:])
manifest = Path(__file__).with_name('frontend-sources.json')
for entry in json.loads(manifest.read_text()):
    destination = target / entry['destination']
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / entry['source'], destination)
    destination.chmod(0o644)
entrypoint = target / 'pixiu/frontend/management/CMakeLists.txt'
entrypoint.parent.mkdir(parents=True, exist_ok=True)
entrypoint.write_text('set(PIXIU_EMBEDDED_HOST ON)\nadd_subdirectory(.. "${CMAKE_CURRENT_BINARY_DIR}/frontend")\n')
