"""MX-record verification for the Settings > Enrichment "Syntax + MX" mode.

Syntax-level validation (`app.scraping.common.email_miner.is_valid_email`)
always runs during extraction and can't be turned off -- it's mail-shape
filtering, not a separate step. This module adds the *additional* check the
"Syntax + MX" setting names: does the address's domain even have a mail
server to deliver to.

Not yet called from the scrape pipeline (app.workers.tasks) -- wiring a DNS
lookup into every place scrape means a network round-trip per lead's email
domain on every job, which is a real cost/latency change to the scrape path
itself, not a one-screen Settings change. `get_email_verification_mode`
(app.core.runtime_settings) stores and returns the operator's choice
correctly; this function is what "Syntax + MX" would call if/when that
wiring is scoped and built. Documented as a known limitation, not silently
faked -- the setting does not yet change what a running job does.
"""

import logging

import dns.exception
import dns.resolver

logger = logging.getLogger(__name__)

_RESOLVER_TIMEOUT_S = 5.0


def has_mx_record(domain: str) -> bool:
    """Whether `domain` publishes at least one MX record.

    A resolver error (NXDOMAIN, timeout, no answer) is treated as "no", same
    as a domain that doesn't exist -- there is no safe way to distinguish
    "verification failed" from "actually invalid" without retry/backoff
    machinery this function doesn't need yet.
    """
    try:
        answer = dns.resolver.resolve(
            domain, "MX", lifetime=_RESOLVER_TIMEOUT_S
        )
        return len(answer) > 0
    except (
        dns.resolver.NXDOMAIN,
        dns.resolver.NoAnswer,
        dns.resolver.NoNameservers,
        dns.exception.Timeout,
    ):
        return False
    except Exception:
        logger.warning("MX lookup failed unexpectedly", exc_info=True, extra={"domain": domain})
        return False
