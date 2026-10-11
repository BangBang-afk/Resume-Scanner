import os
import pathlib
import sys

# Must run before any test module sets env or imports app.
os.environ.setdefault("AUTH_SECRET", "ci-test-secret")
os.environ.setdefault("LLM_PROVIDER", "none")
# Default: limiter off for every module except test_security.py, which pops the
# toggle itself and restores it (module-local env discipline keeps cross-file
# in-process order from leaking 429s into unrelated tests).
os.environ.setdefault("RATE_LIMIT_DISABLED", "1")

# Concurrent-suite safety net: pytest may execute modules either order; the
# env var is consulted per request so a mid-suite pop is honored immediately.
BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
