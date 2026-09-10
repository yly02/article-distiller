"""文章完整性与连贯性质量门禁。"""

from .audit import assert_publishable, audit_distilled, choose_preferred

__all__ = ["audit_distilled", "assert_publishable", "choose_preferred"]
