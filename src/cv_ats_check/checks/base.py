"""Check protocol: a pure function from document (+ optional job ad) to a result."""

from __future__ import annotations

from collections.abc import Callable

from cv_ats_check.models import CheckResult, ExtractedDocument, JobAd

# A check returns None when it does not apply (e.g. keyword checks without a job ad).
CheckFn = Callable[[ExtractedDocument, JobAd | None], CheckResult | None]
