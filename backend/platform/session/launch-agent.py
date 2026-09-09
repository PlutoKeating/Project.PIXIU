"""Read the active Agent profile without executing it, then launch the sole host."""

from __future__ import annotations

import io
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

from dotenv import dotenv_values
from dotenv.parser import parse_stream


def resolve_environment(environment: dict[str, str]) -> dict[str, str]:
    profile = Path(environment.get("HERMES_HOME", str(Path.home() / ".kylin-agent-runtime")))
    if not profile.is_absolute():
        raise ValueError("Agent profile must be an absolute path")
    # Runtime's user profile overrides stale shell exports. Use its dotenv parser,
    # but never call the upstream loader that may repair/rewrite the user's file.
    data = (profile / ".env").read_bytes()
    try:
        contents = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        contents = data.decode("latin-1")
    if any(binding.error for binding in parse_stream(io.StringIO(contents))):
        raise ValueError("Agent profile contains invalid dotenv syntax")
    values = dotenv_values(stream=io.StringIO(contents))
    scope = values.get("PIXIU_AGENT_SCOPE", environment.get("PIXIU_AGENT_SCOPE", "user:default"))
    endpoint = values.get("PIXIU_AGENT_ENDPOINT", environment.get(
        "PIXIU_AGENT_ENDPOINT", "http://127.0.0.1:8765"))
    if not isinstance(scope, str) or not re.fullmatch(r"(user|shared):[A-Za-z0-9._-]+", scope):
        raise ValueError("Agent memory scope is invalid")
    if not isinstance(endpoint, str) or any(character.isspace() for character in endpoint):
        raise ValueError("Agent memory endpoint is invalid")
    url = urlsplit(endpoint)
    if (url.scheme not in {"http", "https"} or not url.hostname
            or url.username is not None or url.password is not None
            or url.query or url.fragment or url.port == 0):
        raise ValueError("Agent memory endpoint is invalid")
    endpoint = endpoint.rstrip("/")
    legacy_endpoint = environment.get("PIXIU_BACKEND_URL")
    if legacy_endpoint is not None and legacy_endpoint.rstrip("/") != endpoint:
        raise ValueError("PIXIU_BACKEND_URL conflicts with the active Agent memory endpoint")
    result = dict(environment)
    # Export only the memory connection contract, never profile credentials or
    # arbitrary shell/loader variables. Preserve the caller's other environment.
    result.update(PIXIU_AGENT_SCOPE=scope, PIXIU_AGENT_ENDPOINT=endpoint,
                  PIXIU_BACKEND_URL=endpoint)
    return result


def main() -> int:
    try:
        environment = resolve_environment(dict(os.environ))
    except (OSError, ValueError):
        # Do not echo the profile, URL, credential-bearing values or parser errors.
        print("PIXIU: cannot resolve a consistent Agent memory configuration; "
              "check the active profile and PIXIU_BACKEND_URL.", file=sys.stderr)
        return 2
    os.execve("/usr/bin/kylin-agent", ["kylin-agent", *sys.argv[1:]], environment)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
