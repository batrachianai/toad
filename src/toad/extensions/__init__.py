"""Canon TUI extensions namespace.

Private extensions are mounted as git submodules under this package. Each
submodule's repository has the conventional ``src``-style layout where the
actual Python package lives one directory below the repo root (e.g.
``rpa_outreach/rpa_outreach/__init__.py``). We extend ``__path__`` to
include each submodule's working tree so that ``toad.extensions.<name>``
resolves to the nested package without needing to restructure the private
repo.
"""

from __future__ import annotations

from pathlib import Path

_here = Path(__file__).parent
for _sub in _here.iterdir():
    if _sub.is_dir() and (_sub / _sub.name / "__init__.py").exists():
        __path__.append(str(_sub))
