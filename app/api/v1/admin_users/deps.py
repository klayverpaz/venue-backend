from __future__ import annotations
from app.api.v1.auth.deps import UserRepo
from app.use_cases.accounts.commands.deactivate_user import DeactivateUserHandler
from app.use_cases.accounts.commands.promote_user_role import PromoteUserRoleHandler


def get_promote_user_role_handler(repo: UserRepo) -> PromoteUserRoleHandler:
    return PromoteUserRoleHandler(repo)


def get_deactivate_user_handler(repo: UserRepo) -> DeactivateUserHandler:
    return DeactivateUserHandler(repo)
