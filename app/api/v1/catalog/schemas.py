from __future__ import annotations
from app.api.v1.admin_resource_types.schemas import (
    ResourceTypeResponse,
    ResourceTypeListResponse,
)

# Public storefront uses the same response shape — no admin-only fields exposed
# yet (is_active is implicit since public listings filter to active only).
__all__ = ["ResourceTypeResponse", "ResourceTypeListResponse"]
