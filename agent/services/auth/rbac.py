"""
Dynamic RBAC service for Smart Lock AI Support SaaS Platform.

GAP #16 + #6 -- extends the static 4-role system to a dynamic,
configurable RBAC with 7 built-in roles and a resource-action
permission matrix.
"""

from __future__ import annotations

import functools
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Permission:
    """A single permission: one resource + one action."""

    resource: str
    action: str

    def __str__(self) -> str:
        return f"{self.resource}:{self.action}"


@dataclass
class RoleDefinition:
    """A named role with its associated permissions."""

    name: str
    display_name: str
    description: str
    permissions: list[Permission] = field(default_factory=list)
    is_system: bool = False


# ---------------------------------------------------------------------------
# Default role catalogue
# ---------------------------------------------------------------------------

def _perms(*pairs: tuple[str, str]) -> list[Permission]:
    """Shorthand to build a permission list from (resource, action) tuples."""
    return [Permission(resource=r, action=a) for r, a in pairs]


# All possible actions for every resource -- used by super_admin.
_ALL_RESOURCES = (
    "users", "conversations", "work_orders", "invoices",
    "refunds", "complaints", "reports", "settings",
)
_ALL_ACTIONS = ("create", "read", "update", "delete", "export", "approve")
_FULL_PERMISSIONS = _perms(
    *((r, a) for r in _ALL_RESOURCES for a in _ALL_ACTIONS)
)

DEFAULT_ROLES: dict[str, RoleDefinition] = {
    "super_admin": RoleDefinition(
        name="super_admin",
        display_name="超級管理員",
        description="Full system access -- platform owner.",
        permissions=_FULL_PERMISSIONS,
        is_system=True,
    ),
    "admin": RoleDefinition(
        name="admin",
        display_name="管理員",
        description="Manage users, work orders, and finance.",
        permissions=_perms(
            ("users", "create"), ("users", "read"), ("users", "update"),
            ("conversations", "read"), ("conversations", "export"),
            ("work_orders", "create"), ("work_orders", "read"),
            ("work_orders", "update"), ("work_orders", "delete"),
            ("work_orders", "export"), ("work_orders", "approve"),
            ("invoices", "create"), ("invoices", "read"),
            ("invoices", "update"), ("invoices", "export"),
            ("refunds", "create"), ("refunds", "read"), ("refunds", "approve"),
            ("complaints", "read"), ("complaints", "update"),
            ("reports", "read"), ("reports", "export"),
            ("settings", "read"), ("settings", "update"),
        ),
        is_system=True,
    ),
    "reviewer": RoleDefinition(
        name="reviewer",
        display_name="審查員",
        description="SOP review and quality audit.",
        permissions=_perms(
            ("users", "read"),
            ("conversations", "read"),
            ("work_orders", "read"), ("work_orders", "approve"),
            ("invoices", "read"),
            ("refunds", "read"), ("refunds", "approve"),
            ("complaints", "read"), ("complaints", "approve"),
            ("reports", "read"),
        ),
        is_system=True,
    ),
    "technician": RoleDefinition(
        name="technician",
        display_name="技師",
        description="Operate own work orders and submit reports.",
        permissions=_perms(
            ("users", "read"),
            ("conversations", "read"),
            ("work_orders", "read"), ("work_orders", "update"),
            ("invoices", "read"),
            ("complaints", "read"),
        ),
        is_system=True,
    ),
    "brand_oem": RoleDefinition(
        name="brand_oem",
        display_name="品牌商",
        description="View warranty stats and upload brand data (read-only on platform data).",
        permissions=_perms(
            ("work_orders", "read"),
            ("complaints", "read"),
            ("reports", "read"),
        ),
        is_system=True,
    ),
    "distributor": RoleDefinition(
        name="distributor",
        display_name="經銷商",
        description="View regional reports and manage sub-accounts.",
        permissions=_perms(
            ("users", "read"),
            ("work_orders", "read"),
            ("invoices", "read"),
            ("complaints", "read"),
            ("reports", "read"),
        ),
        is_system=True,
    ),
    "line_user": RoleDefinition(
        name="line_user",
        display_name="LINE 使用者",
        description="Default role -- own conversations and profile.",
        permissions=_perms(
            ("users", "read"),
            ("conversations", "read"),
            ("work_orders", "read"),
            ("invoices", "read"),
            ("refunds", "create"), ("refunds", "read"),
            ("complaints", "create"), ("complaints", "read"),
        ),
        is_system=True,
    ),
}


# ---------------------------------------------------------------------------
# RBACService
# ---------------------------------------------------------------------------

class RBACService:
    """Dynamic Role-Based Access Control service.

    Parameters
    ----------
    db_uri_env:
        Name of the environment variable holding the PostgreSQL connection URI.
    """

    def __init__(self, db_uri_env: str = "POSTGRES_URI") -> None:
        self._db_uri = os.getenv(db_uri_env, "")

        # In-memory stores; production should be backed by database tables.
        self._roles: dict[str, RoleDefinition] = dict(DEFAULT_ROLES)
        self._user_roles: dict[str, str] = {}  # user_id -> role_name

    # ------------------------------------------------------------------
    # Permission queries
    # ------------------------------------------------------------------

    async def get_user_permissions(self, user_id: str) -> list[Permission]:
        """Return the effective permissions for a user based on their role."""
        role_name = self._user_roles.get(user_id, "line_user")
        role = self._roles.get(role_name)
        if role is None:
            logger.warning("Unknown role '%s' for user %s, falling back to line_user", role_name, user_id)
            role = self._roles["line_user"]
        return list(role.permissions)

    async def check_permission(self, user_id: str, resource: str, action: str) -> bool:
        """Return True if the user's role grants the requested permission.

        ``super_admin`` always returns True without checking the matrix.
        """
        role_name = self._user_roles.get(user_id, "line_user")

        # Super admin bypass.
        if role_name == "super_admin":
            return True

        role = self._roles.get(role_name)
        if role is None:
            return False

        target = Permission(resource=resource, action=action)
        return target in role.permissions

    # ------------------------------------------------------------------
    # Role CRUD
    # ------------------------------------------------------------------

    async def get_role(self, role_name: str) -> RoleDefinition | None:
        """Return a role by name, or None if not found."""
        return self._roles.get(role_name)

    async def list_roles(self) -> list[RoleDefinition]:
        """Return all registered roles."""
        return list(self._roles.values())

    async def create_role(
        self,
        name: str,
        display_name: str,
        description: str,
        permissions: list[Permission],
    ) -> RoleDefinition:
        """Create a new custom role.

        Raises
        ------
        ValueError
            If a role with the given name already exists.
        """
        if name in self._roles:
            raise ValueError(f"Role already exists: {name}")

        role = RoleDefinition(
            name=name,
            display_name=display_name,
            description=description,
            permissions=permissions,
            is_system=False,
        )
        self._roles[name] = role
        logger.info("Created custom role: %s", name)
        return role

    async def update_role_permissions(
        self,
        role_name: str,
        permissions: list[Permission],
    ) -> RoleDefinition:
        """Replace the permission set for an existing role.

        Raises
        ------
        ValueError
            If the role does not exist.
        """
        role = self._roles.get(role_name)
        if role is None:
            raise ValueError(f"Role not found: {role_name}")

        role.permissions = permissions
        logger.info("Updated permissions for role '%s': %d permissions", role_name, len(permissions))
        return role

    async def assign_role(self, user_id: str, role_name: str) -> None:
        """Assign a role to a user.

        Raises
        ------
        ValueError
            If the target role does not exist.
        """
        if role_name not in self._roles:
            raise ValueError(f"Role not found: {role_name}")

        previous = self._user_roles.get(user_id, "(none)")
        self._user_roles[user_id] = role_name
        logger.info("Assigned role '%s' to user %s (was: %s)", role_name, user_id, previous)

    # ------------------------------------------------------------------
    # Seeding
    # ------------------------------------------------------------------

    async def seed_default_roles(self) -> None:
        """Idempotent seeding of DEFAULT_ROLES.

        For each default role:
        - If absent, insert it.
        - If present, update its permissions to match the defaults.

        Production implementation should write to the database.
        """
        for name, definition in DEFAULT_ROLES.items():
            existing = self._roles.get(name)
            if existing is None:
                self._roles[name] = RoleDefinition(
                    name=definition.name,
                    display_name=definition.display_name,
                    description=definition.description,
                    permissions=list(definition.permissions),
                    is_system=definition.is_system,
                )
                logger.info("Seeded new role: %s", name)
            else:
                existing.permissions = list(definition.permissions)
                existing.display_name = definition.display_name
                existing.description = definition.description
                logger.debug("Updated seeded role: %s", name)

        logger.info("Default role seeding complete: %d roles", len(DEFAULT_ROLES))


# ---------------------------------------------------------------------------
# FastAPI decorator
# ---------------------------------------------------------------------------

def require_permission(resource: str, action: str) -> Callable[..., Any]:
    """Decorator for FastAPI endpoints that enforces a permission check.

    Usage::

        @app.get("/work-orders")
        @require_permission("work_orders", "read")
        async def list_work_orders(request: Request):
            ...

    The decorator expects:
    - ``request.state.user_id`` to be set by authentication middleware.
    - ``request.app.state.rbac`` to hold an ``RBACService`` instance.

    Returns HTTP 403 if the user lacks the required permission.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Import here to avoid circular dependency at module load time.
            from fastapi import HTTPException, Request

            # Locate the Request object in args/kwargs.
            request: Request | None = kwargs.get("request")
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request is None:
                raise HTTPException(
                    status_code=500,
                    detail="Internal error: Request object not found.",
                )

            user_id: str | None = getattr(request.state, "user_id", None)
            if user_id is None:
                raise HTTPException(status_code=401, detail="Authentication required.")

            rbac: RBACService | None = getattr(request.app.state, "rbac", None)
            if rbac is None:
                raise HTTPException(
                    status_code=500,
                    detail="Internal error: RBAC service not configured.",
                )

            allowed = await rbac.check_permission(user_id, resource, action)
            if not allowed:
                logger.warning(
                    "Permission denied: user=%s resource=%s action=%s",
                    user_id, resource, action,
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"Permission denied: {resource}:{action}",
                )

            return await fn(*args, **kwargs)

        return wrapper

    return decorator
