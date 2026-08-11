"""dbxmig -- Unity Catalog metastore migration toolkit for cross-cloud moves.

Companion code for the Databricks cross-cloud migration runbook. The runbook
explains what to do and why; this package does the mechanical parts of it
repeatably: inventory the source metastore, order the objects by dependency,
emit reviewable DDL and GRANT statements, execute them resumably, and prove the
result reconciles.

Nothing here is Databricks-official. Validate every generated statement against
your own environment before running it in production.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
