"""Discover the Outreach provider from the private extension submodule.

The public Canon TUI has no hard dependency on the private
`toad.extensions.rpa_outreach` module. `discover()` import-probes for it
and returns the instantiated provider when both the module is available
and it has a DSN resolvable (from env var OR from the `.env` file
committed with the submodule). All other paths return None so the
right-pane silently omits the Outreach section.
"""

from __future__ import annotations

import logging

from toad.outreach.protocol import OutreachInfoProvider

_EXTENSION_MODULE = "toad.extensions.rpa_outreach"

logger = logging.getLogger(__name__)


def discover() -> OutreachInfoProvider | None:
    """Return the Outreach provider when available, else None.

    Returns None when:
    - the `toad.extensions.rpa_outreach` submodule cannot be imported, OR
    - the imported module does not expose a `provider` attribute that
      satisfies `OutreachInfoProvider`, OR
    - the provider has no DSN available (env var unset AND the
      submodule's committed `.env` is missing or does not declare the
      expected variable).

    The provider is responsible for DSN resolution — it reads the
    `CANON_RPA_OUTREACH_DATABASE_URL` env var first, then falls back to
    a `.env` file that the private submodule ships.
    """
    try:
        module = __import__(_EXTENSION_MODULE, fromlist=["provider"])
    except ImportError:
        logger.debug("Outreach extension not installed; panel disabled.")
        return None

    provider = getattr(module, "provider", None)
    if provider is None:
        logger.warning(
            "Outreach extension %s has no `provider` attribute; panel disabled.",
            _EXTENSION_MODULE,
        )
        return None

    if not isinstance(provider, OutreachInfoProvider):
        logger.warning(
            "Outreach extension provider does not satisfy OutreachInfoProvider; "
            "panel disabled."
        )
        return None

    if getattr(provider, "dsn", None) is None:
        logger.debug(
            "Outreach extension has no DSN (env var unset and .env missing); "
            "panel disabled."
        )
        return None

    return provider
