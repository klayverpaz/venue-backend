"""Mapping from VO/handler stable error codes to pt-BR display strings.

This is the only place pt-BR error text lives. Domain code emits codes
(e.g., "NameCannotBeEmpty"); the HTTP boundary translates them via this
table when building the response body.

Adding a new VO error code:
  1. Define it as a class constant on the VO (e.g., Foo.FOO_INVALID = "FooInvalid").
  2. Add the corresponding pt-BR entry below.
  3. The architecture test in tests/unit/architecture/test_error_code_coverage.py
     enforces 1:1 coverage and will fail CI if either side is missing.
"""
from __future__ import annotations

from app.domain.catalog.attribute import AttributeDefinition
from app.domain.shared.value_objects.attribute_key import AttributeKey
from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.shared.value_objects.brazilian_phone import BrazilianPhone
from app.domain.shared.value_objects.cancellation_cutoff import CancellationCutoff
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.email import Email
from app.domain.shared.value_objects.iana_timezone import IanaTimezone
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.name import Name
from app.domain.shared.value_objects.rating_score import RatingScore
from app.domain.shared.value_objects.short_description import ShortDescription
from app.domain.shared.value_objects.short_name import ShortName
from app.domain.shared.value_objects.slot_duration import SlotDuration
from app.domain.shared.value_objects.slug import Slug
from app.domain.accounts.user import User
from app.domain.resources.pricing_rule import PricingRule
from app.domain.resources.resource import Resource
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.bookings.status_change import StatusChange


ERROR_MESSAGES_PT_BR: dict[str, str] = {
    # Email
    Email.EMAIL_CANNOT_BE_EMPTY: "E-mail é obrigatório.",
    Email.EMAIL_INVALID_FORMAT: "E-mail em formato inválido.",
    Email.EMAIL_CANNOT_BE_GREATER_THAN_MAX_LENGTH: f"E-mail não pode exceder {Email.MAX_LENGTH} caracteres.",

    # BrazilianPhone
    BrazilianPhone.PHONE_CANNOT_BE_EMPTY: "Telefone é obrigatório.",
    BrazilianPhone.PHONE_CONTAINS_INVALID_CHARACTERS: "Telefone contém caracteres inválidos.",
    BrazilianPhone.PHONE_HAS_NO_DIGITS: "Telefone não contém dígitos.",
    BrazilianPhone.PHONE_INVALID_LENGTH: "Telefone deve ter 10 dígitos (fixo) ou 11 (celular).",
    BrazilianPhone.PHONE_INVALID_DDD: "DDD inválido.",
    BrazilianPhone.PHONE_MOBILE_MUST_START_WITH_9: "Celular deve começar com 9 após o DDD.",
    BrazilianPhone.PHONE_LANDLINE_MUST_START_WITH_2_TO_7: "Telefone fixo deve começar com dígito entre 2 e 7.",

    # Slug
    Slug.SLUG_CANNOT_BE_EMPTY: "Slug é obrigatório.",
    Slug.SLUG_INVALID_FORMAT: "Slug inválido — use apenas letras minúsculas, dígitos e hífens; sem hífens repetidos ou nas pontas.",
    Slug.SLUG_CANNOT_BE_GREATER_THAN_MAX_LENGTH: f"Slug não pode exceder {Slug.MAX_LENGTH} caracteres.",

    # Name
    Name.NAME_CANNOT_BE_EMPTY: "Nome é obrigatório.",
    Name.NAME_CANNOT_BE_GREATER_THAN_MAX_LENGTH: f"Nome não pode exceder {Name.MAX_LENGTH} caracteres.",
    Name.NAME_CONTAINS_INVALID_CHARACTERS: "Nome contém caracteres inválidos (controle/sem-imprimíveis).",

    # ShortName
    ShortName.SHORT_NAME_CANNOT_BE_EMPTY: "Rótulo é obrigatório.",
    ShortName.SHORT_NAME_CANNOT_BE_GREATER_THAN_MAX_LENGTH: f"Rótulo não pode exceder {ShortName.MAX_LENGTH} caracteres.",
    ShortName.SHORT_NAME_CONTAINS_INVALID_CHARACTERS: "Rótulo contém caracteres inválidos.",

    # ShortDescription
    ShortDescription.SHORT_DESCRIPTION_INVALID_TYPE: "Descrição em formato inválido.",
    ShortDescription.SHORT_DESCRIPTION_CANNOT_BE_GREATER_THAN_MAX_LENGTH: f"Descrição não pode exceder {ShortDescription.MAX_LENGTH} caracteres.",

    # AttributeKey
    AttributeKey.ATTRIBUTE_KEY_CANNOT_BE_EMPTY: "Chave de atributo é obrigatória.",
    AttributeKey.ATTRIBUTE_KEY_INVALID_FORMAT: "Chave de atributo inválida — use letras minúsculas, dígitos e underscores (snake_case).",
    AttributeKey.ATTRIBUTE_KEY_CANNOT_BE_GREATER_THAN_MAX_LENGTH: f"Chave de atributo não pode exceder {AttributeKey.MAX_LENGTH} caracteres.",

    # Money
    Money.MONEY_INVALID_TYPE: "Valor monetário deve ser inteiro (em centavos).",
    Money.MONEY_CANNOT_BE_NEGATIVE: "Valor monetário não pode ser negativo.",
    Money.MONEY_EXCEEDS_MAX: "Valor monetário excede o limite permitido.",
    Money.MONEY_INVALID_CENTAVOS: "Centavos devem ser inteiro entre 0 e 99.",

    # RatingScore
    RatingScore.RATING_SCORE_INVALID_TYPE: "Avaliação deve ser número inteiro.",
    RatingScore.RATING_SCORE_OUT_OF_RANGE: f"Avaliação deve estar entre {RatingScore.MIN_VALUE} e {RatingScore.MAX_VALUE} estrelas.",

    # SlotDuration
    SlotDuration.SLOT_DURATION_INVALID_TYPE: "Duração de slot deve ser inteiro (minutos).",
    SlotDuration.SLOT_DURATION_NOT_ALLOWED: "Duração de slot não permitida — escolha 30, 45, 60, 90 ou 120 minutos.",

    # CancellationCutoff
    CancellationCutoff.CANCELLATION_CUTOFF_INVALID_TYPE: "Antecedência de cancelamento deve ser inteiro (horas).",
    CancellationCutoff.CANCELLATION_CUTOFF_OUT_OF_RANGE: f"Antecedência de cancelamento deve estar entre {CancellationCutoff.MIN_HOURS} e {CancellationCutoff.MAX_HOURS} horas.",

    # IanaTimezone
    IanaTimezone.IANA_TIMEZONE_CANNOT_BE_EMPTY: "Fuso horário é obrigatório.",
    IanaTimezone.IANA_TIMEZONE_UNKNOWN: "Fuso horário desconhecido.",

    # TimeWindow
    TimeWindow.TIME_WINDOW_INVALID_TYPE: "Janela de horário em formato inválido.",
    TimeWindow.TIME_WINDOW_START_MUST_BE_BEFORE_END: "Horário inicial deve ser anterior ao final (sem virada de meia-noite).",

    # WeeklySchedule (resource VO)
    WeeklySchedule.WINDOWS_NOT_ORDERED: "Janelas de horário devem estar em ordem crescente.",
    WeeklySchedule.WINDOWS_OVERLAP: "Janelas de horário não podem se sobrepor.",
    WeeklySchedule.WINDOW_NOT_ALIGNED_TO_SLOT_GRID: "Janela de horário não está alinhada à grade de slots.",

    # PricingRule (resource VO)
    PricingRule.EMPTY_WEEKDAYS: "Regra de preço precisa ter ao menos um dia da semana.",

    # Resource entity (entity-level codes — registered in arch test allowlist)
    Resource.PRICING_RULES_OVERLAP: "Regras de preço se sobrepõem.",
    Resource.PRICING_RULE_NOT_ALIGNED_TO_SLOT_GRID: "Regra de preço não alinhada à grade de slots.",
    Resource.PRICING_RULE_OUTSIDE_OPERATING_HOURS: "Regra de preço fora do horário de funcionamento.",
    Resource.DUPLICATE_CUSTOM_ATTRIBUTE_KEY: "Atributo customizado duplicado.",
    Resource.CUSTOM_ATTRIBUTE_KEY_CONFLICTS_WITH_BASE: "Atributo customizado conflita com atributo base.",
    Resource.RESOURCE_ALREADY_DELETED: "Recurso já está deletado.",
    Resource.DELETED_AT_NOT_TZ_AWARE: "Data de exclusão precisa ser tz-aware UTC.",

    # User entity (entity-level codes — registered in arch test allowlist)
    User.PUBLIC_SLUG_REQUIRED_FOR_OWNER: "Owner precisa de slug público.",
    User.PUBLIC_SLUG_FORBIDDEN_FOR_NON_OWNER: "Slug público é exclusivo de owners.",

    # DateTimeRange
    DateTimeRange.DATE_TIME_RANGE_INVALID_TYPE: "Intervalo de datas em formato inválido.",
    DateTimeRange.DATE_TIME_RANGE_NOT_TZ_AWARE: "Datas precisam de fuso horário (tz-aware).",
    DateTimeRange.DATE_TIME_RANGE_NOT_UTC: "Datas precisam estar em UTC.",
    DateTimeRange.DATE_TIME_RANGE_START_MUST_BE_BEFORE_END: "Data inicial deve ser anterior à final.",

    # AttributeDefinition (catalog VO)
    AttributeDefinition.ENUM_TYPE_REQUIRES_VALUES: "Atributo do tipo enum precisa de valores possíveis.",
    AttributeDefinition.NON_ENUM_TYPE_CANNOT_HAVE_VALUES: "Atributo que não é enum não pode ter valores possíveis.",

    # Envelope code emitted by unwrap() when result.details is populated
    "ValidationFailed": "Falha de validação.",

    # Handler-level (not VO-bound) codes
    "PasswordHashCannotBeEmpty": "Hash de senha é obrigatório.",

    # Plan 05 follow-up #5 — RegisterUserHandler stable codes
    "AdminRegistrationForbidden": "Não é permitido registrar contas admin via cadastro público.",
    "PasswordTooShort": "Senha precisa ter ao menos 8 caracteres.",
    "EmailAlreadyRegistered": "Email já cadastrado.",

    # Resource handler-level (Plan 06)
    "PublicSlugAlreadyTaken": "Slug público já em uso.",
    "ResourceNotFound": "Recurso não encontrado.",
    "ResourceTypeInactive": "Tipo de recurso está inativo.",
    "TimeWindowInvalidType": "Janela de horário em formato inválido.",

    # Notifications (Plan 07) — handler-level
    "NotificationNotFound": "Notificação não encontrada.",

    # ResourceType (entity-level codes — registered in arch test allowlist)
    "DuplicateAttributeKey": "Atributos duplicados — chaves devem ser únicas dentro do tipo.",
    "RequiredAttributeMissing": "Atributo obrigatório ausente.",
    "UnknownAttributeKey": "Atributo desconhecido — não está no schema do tipo.",
    "AttributeTypeMismatch": "Valor do atributo não bate com o tipo declarado.",
    "AttributeEnumValueNotAllowed": "Valor do atributo enum fora dos valores permitidos.",
    "SlugAlreadyTaken": "Slug já está em uso.",
    "ResourceTypeNotFound": "Tipo de recurso não encontrado.",
    "InvalidDataType": "Tipo de dado de atributo desconhecido.",

    # Subscriptions (Plan 05) — handler-level
    "OwnerNotFound": "Proprietário não encontrado.",
    "UserIsNotOwner": "Usuário não é proprietário.",
    "SubscriptionNotFound": "Assinatura não encontrada.",
    "OwnerAlreadyHasSubscription": "Proprietário já possui assinatura.",
    "InvalidSubscriptionStatus": "Status de assinatura inválido.",
    # Subscriptions (Plan 05) — entity-level invariants (programming bugs;
    # never reach unwrap, but mapped for documentation + arch test parity).
    OwnerSubscription.OWNER_ID_REQUIRED: "ID do proprietário é obrigatório.",
    OwnerSubscription.TRIAL_ENDS_AT_REQUIRED_FOR_TRIALING:
        "Assinatura em TRIALING precisa de data de fim de trial.",
    OwnerSubscription.TRIAL_ENDS_AT_FORBIDDEN_OUTSIDE_TRIALING:
        "Data de fim de trial só é válida para status TRIALING.",
    OwnerSubscription.TRIAL_DURATION_DAYS_INVALID:
        "Duração de trial deve ser inteiro positivo.",
    OwnerSubscription.STATUS_CHANGED_AT_MUST_BE_TZ_AWARE:
        "Timestamp de mudança de status precisa ter fuso horário.",
    OwnerSubscription.TRIAL_ENDS_AT_MUST_BE_TZ_AWARE:
        "Data de fim de trial precisa ter fuso horário.",

    # StatusChange (Plan 08) — bookings audit VO
    StatusChange.STATUS_CHANGE_AT_NOT_TZ_AWARE: "Timestamp da mudança de status precisa ter fuso horário.",
    StatusChange.STATUS_CHANGE_REASON_TOO_LONG: "Motivo da mudança de status não pode ultrapassar 500 caracteres.",
    StatusChange.STATUS_CHANGE_INVALID_TRANSITION: "Transição de status inválida.",
}


def translate(code: str) -> str:
    """Return pt-BR display message for an error code, or the code itself if unmapped."""
    return ERROR_MESSAGES_PT_BR.get(code, code)
