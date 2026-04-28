"""Architecture test: every VO error code must have a pt-BR translation.

Catches the failure mode where someone adds a new constant on a VO but
forgets to add the corresponding entry in app/api/error_codes.py. CI
fails before the gap reaches main.
"""
from __future__ import annotations
import importlib
import inspect
import pkgutil
from app import domain as domain_pkg
from app.domain.shared.value_object import BaseValueObject
from app.api.error_codes import ERROR_MESSAGES_PT_BR


def _walk_modules(package):
    """Recursively yield every module reachable from `package`.

    Walks both shared (e.g., `app.domain.shared.value_objects`) and feature-
    level (e.g., `app.domain.catalog`) trees so VOs declared inside features
    are discovered too.
    """
    for mod_info in pkgutil.walk_packages(package.__path__, prefix=f"{package.__name__}."):
        if mod_info.ispkg:
            continue
        try:
            yield importlib.import_module(mod_info.name)
        except Exception:
            # Some modules may import lazily / require runtime config; skip
            # rather than fail the architecture test on import order issues.
            continue


def _collect_vo_classes():
    classes = []
    for module in _walk_modules(domain_pkg):
        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if (
                obj is not BaseValueObject
                and inspect.isclass(obj)
                and issubclass(obj, BaseValueObject)
                and obj.__module__ == module.__name__
            ):
                classes.append(obj)
    return classes


def _collect_error_codes(vo_class) -> list[tuple[str, str]]:
    """Return (constant_name, code_value) pairs declared on the VO class."""
    codes = []
    for attr_name in dir(vo_class):
        if attr_name.startswith("_"):
            continue
        if attr_name.isupper():
            value = getattr(vo_class, attr_name)
            # Stable code identifiers are PascalCase strings without spaces.
            # Filter out MAX_LENGTH-style numeric, ALLOWED-style frozenset, etc.
            if isinstance(value, str) and value and value[0].isupper() and " " not in value:
                codes.append((attr_name, value))
    return codes


def test_every_vo_error_code_has_pt_br_translation():
    missing: list[str] = []
    for vo_class in _collect_vo_classes():
        for const_name, code in _collect_error_codes(vo_class):
            if code not in ERROR_MESSAGES_PT_BR:
                missing.append(f"{vo_class.__name__}.{const_name} = {code!r}")

    assert not missing, (
        "These VO error codes have no pt-BR translation in "
        "app/api/error_codes.py:\n  " + "\n  ".join(missing)
    )


def test_no_orphan_translations_in_mapping():
    """Every key in ERROR_MESSAGES_PT_BR must originate from a VO constant.

    Prevents stale entries lingering after a VO code is renamed or removed.
    """
    declared_codes: set[str] = set()
    for vo_class in _collect_vo_classes():
        for _const_name, code in _collect_error_codes(vo_class):
            declared_codes.add(code)

    orphans = sorted(set(ERROR_MESSAGES_PT_BR) - declared_codes)
    # Allow handler-level codes by listing them here as the pattern emerges in
    # later plans. For now (Plan 03), only VO-level codes exist.
    handler_level_allowlist: set[str] = {
        "PasswordHashCannotBeEmpty",
        "DuplicateAttributeKey",
        "RequiredAttributeMissing",
        "UnknownAttributeKey",
        "AttributeTypeMismatch",
        "AttributeEnumValueNotAllowed",
        "SlugAlreadyTaken",
        "ResourceTypeNotFound",
        "InvalidDataType",
        "ValidationFailed",
        # Plan 05 — subscriptions
        "OwnerNotFound",
        "UserIsNotOwner",
        "SubscriptionNotFound",
        "OwnerAlreadyHasSubscription",
        "InvalidSubscriptionStatus",
        "OwnerIdRequired",
        "TrialEndsAtRequiredForTrialing",
        "TrialEndsAtForbiddenOutsideTrialing",
        "TrialDurationDaysInvalid",
        "StatusChangedAtMustBeTzAware",
        "TrialEndsAtMustBeTzAware",
        # Plan 05 follow-up #5 — RegisterUserHandler stable codes
        "AdminRegistrationForbidden",
        "PasswordTooShort",
        "EmailAlreadyRegistered",
        # Plan 06 — resources + accounts extension
        "PublicSlugRequiredForOwner",
        "PublicSlugForbiddenForNonOwner",
        "PublicSlugAlreadyTaken",
        "PricingRulesOverlap",
        "PricingRuleNotAlignedToSlotGrid",
        "PricingRuleOutsideOperatingHours",
        "DuplicateCustomAttributeKey",
        "CustomAttributeKeyConflictsWithBase",
        "ResourceAlreadyDeleted",
        "ResourceDeletedAtNotTzAware",
        "ResourceNotFound",
        "ResourceTypeInactive",
        "TimeWindowInvalidType",
        # Plan 07 — notifications
        "NotificationNotFound",
        # Plan 08 — bookings handler-level
        "BookingNotFound",
        "ResourceNotPublished",
        "OwnerSubscriptionInactive",
        "BookingSlotInPast",
        "BookingSlotNotAligned",
        "BookingOutsideOperatingHours",
        "BookingAlreadyExists",
        "BookingInvalidStateTransition",
        "BookingCancellationPastCutoff",
        "BookingHasApprovedOverlap",
        "AgendaRangeTooWide",
        "ResourceHasFutureApprovedBookings",
    }
    real_orphans = [c for c in orphans if c not in handler_level_allowlist]

    assert not real_orphans, (
        "These pt-BR mapping keys do not match any VO error code:\n  "
        + "\n  ".join(real_orphans)
    )
