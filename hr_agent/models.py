from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


ROUTES = {
    "sql_only",
    "review_semantic",
    "review_semantic_plus_sql",
}
UNSUPPORTED_CATEGORIES = {
    "none",
    "vague",
    "out_of_scope",
    "unavailable_data",
    "unsupported_operation",
}
ANSWER_LANGUAGES = {"en", "de", "es", "fr", "ar"}
SEMANTIC_SCOPES = {
    "none",
    "broad_positive",
    "current_strength",
    "future_potential",
    "readiness",
    "development_need",
    "neutral",
}
AGGREGATES = {"count", "sum", "avg", "min", "max"}
FILTER_OPERATORS = {
    "eq",
    "neq",
    "gt",
    "gte",
    "lt",
    "lte",
    "between",
    "contains",
    "starts_with",
    "ends_with",
    "in",
    "is_null",
    "is_not_null",
}
ALLOWED_FIELDS = {
    "employees.employee_id",
    "employees.first_name",
    "employees.last_name",
    "employees.email",
    "employees.hire_date",
    "employees.job_title",
    "employees.department_id",
    "employees.manager_id",
    "employees.salary",
    "employees.employment_status",
    "employees.performance_review",
    "employees.*",
    "departments.department_id",
    "departments.department_name",
    "departments.budget",
    "departments.*",
    "absences.absence_id",
    "absences.employee_id",
    "absences.absence_type",
    "absences.start_date",
    "absences.end_date",
    "absences.days_absent",
    "absences.reason",
    "absences.*",
    "manager.employee_id",
    "manager.first_name",
    "manager.last_name",
    "manager.email",
    "manager.job_title",
}
WILDCARD_FIELDS = {"employees.*", "departments.*", "absences.*"}
CANONICAL_FILTER_VALUES = {
    "departments.department_name": {"Engineering", "HR", "Sales"},
    "absences.absence_type": {"sick", "paid_vacation", "unpaid_vacation"},
}
ALIAS_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


class PlanValidationError(ValueError):
    pass


@dataclass(frozen=True)
class SelectExpression:
    field: str
    aggregate: str | None = None
    distinct: bool = False
    alias: str | None = None


@dataclass(frozen=True)
class FilterExpression:
    field: str
    operator: str
    value: Any = None


@dataclass(frozen=True)
class OrderExpression:
    field: str
    direction: str
    aggregate: str | None = None


@dataclass(frozen=True)
class QueryPlan:
    base_table: str
    select: tuple[SelectExpression, ...]
    filters: tuple[FilterExpression, ...]
    group_by: tuple[str, ...]
    order_by: tuple[OrderExpression, ...]
    limit: int | None


@dataclass(frozen=True)
class AgentPlan:
    supported: bool
    unsupported_category: str
    route: str
    answer_language: str
    semantic_query: str
    semantic_scope: str
    query: QueryPlan | None


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PlanValidationError(f"{key} must be a non-empty string")
    return value.strip()


def _reject_unknown_keys(
    payload: dict[str, Any],
    allowed: set[str],
    context: str,
) -> None:
    unknown = set(payload) - allowed
    if unknown:
        raise PlanValidationError(
            f"unknown {context} keys: {', '.join(sorted(unknown))}"
        )


def _optional_string(value: Any, key: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise PlanValidationError(f"{key} must be null or a non-empty string")
    return value.strip()


def _allowed_field(payload: dict[str, Any], key: str = "field") -> str:
    field = _required_string(payload, key)
    if field not in ALLOWED_FIELDS:
        raise PlanValidationError(f"invalid {key}")
    return field


def _validate_filter_value(operator: str, value: Any) -> None:
    if operator in {"is_null", "is_not_null"}:
        if value is not None:
            raise PlanValidationError(f"{operator} requires a null value")
        return
    if operator in {"eq", "neq"} and value is None:
        return
    if operator in {"eq", "neq", "gt", "gte", "lt", "lte"}:
        if value is None or isinstance(value, (dict, list)):
            raise PlanValidationError(f"{operator} requires a scalar value")
        return
    if operator == "between":
        if not isinstance(value, list) or len(value) != 2:
            raise PlanValidationError("between requires two values")
        if any(item is None or isinstance(item, (dict, list)) for item in value):
            raise PlanValidationError("between values must be scalar")
        return
    if operator == "in":
        if not isinstance(value, list) or not 1 <= len(value) <= 100:
            raise PlanValidationError("in requires 1 to 100 values")
        if any(item is None or isinstance(item, (dict, list)) for item in value):
            raise PlanValidationError("in values must be scalar")
        return
    if not isinstance(value, str) or not value:
        raise PlanValidationError(f"{operator} requires non-empty text")


def _validate_canonical_filter_value(field: str, operator: str, value: Any) -> None:
    allowed = CANONICAL_FILTER_VALUES.get(field)
    if allowed is None or operator not in {"eq", "neq", "in"}:
        return
    values = value if operator == "in" else [value]
    if not isinstance(values, list) or any(item not in allowed for item in values):
        raise PlanValidationError(f"invalid canonical value for {field}")


def _parse_query(payload: Any) -> QueryPlan:
    if not isinstance(payload, dict):
        raise PlanValidationError("query must be an object")
    _reject_unknown_keys(
        payload,
        {"base_table", "select", "filters", "group_by", "order_by", "limit"},
        "query",
    )

    base_table = _required_string(payload, "base_table")
    if base_table not in {"employees", "departments", "absences"}:
        raise PlanValidationError("invalid base_table")

    raw_select = payload.get("select")
    if not isinstance(raw_select, list) or not 1 <= len(raw_select) <= 20:
        raise PlanValidationError("select must contain 1 to 20 expressions")
    select = []
    for item in raw_select:
        if not isinstance(item, dict):
            raise PlanValidationError("select expressions must be objects")
        _reject_unknown_keys(
            item,
            {"field", "aggregate", "distinct", "alias"},
            "select expression",
        )
        aggregate = _optional_string(item.get("aggregate"), "aggregate")
        if aggregate is not None and aggregate not in AGGREGATES:
            raise PlanValidationError("invalid aggregate")
        distinct = item.get("distinct", False)
        if not isinstance(distinct, bool):
            raise PlanValidationError("distinct must be boolean")
        field = _allowed_field(item)
        alias = _optional_string(item.get("alias"), "alias")
        if alias is not None and not ALIAS_PATTERN.fullmatch(alias):
            raise PlanValidationError("invalid aggregate alias")
        if aggregate is not None and alias is None:
            raise PlanValidationError("aggregate selections require an alias")
        if aggregate is None and distinct:
            raise PlanValidationError("distinct requires an aggregate")
        select.append(
            SelectExpression(
                field=field,
                aggregate=aggregate,
                distinct=distinct,
                alias=alias,
            )
        )

    raw_filters = payload.get("filters", [])
    if not isinstance(raw_filters, list) or len(raw_filters) > 20:
        raise PlanValidationError("filters must be a list of at most 20 items")
    filters = []
    for item in raw_filters:
        if not isinstance(item, dict):
            raise PlanValidationError("filters must be objects")
        _reject_unknown_keys(item, {"field", "operator", "value"}, "filter")
        operator = _required_string(item, "operator")
        if operator not in FILTER_OPERATORS:
            raise PlanValidationError("invalid filter operator")
        field = _allowed_field(item)
        value = item.get("value")
        _validate_filter_value(operator, value)
        _validate_canonical_filter_value(field, operator, value)
        filters.append(
            FilterExpression(
                field=field,
                operator=operator,
                value=value,
            )
        )

    raw_group_by = payload.get("group_by", [])
    if not isinstance(raw_group_by, list) or len(raw_group_by) > 10:
        raise PlanValidationError("group_by must be a list of at most 10 fields")
    group_by = tuple(_allowed_field({"field": field}) for field in raw_group_by)
    if any(field in WILDCARD_FIELDS for field in group_by):
        raise PlanValidationError("group_by cannot contain a wildcard")

    raw_order_by = payload.get("order_by", [])
    if not isinstance(raw_order_by, list) or len(raw_order_by) > 10:
        raise PlanValidationError("order_by must be a list of at most 10 items")
    order_by = []
    for item in raw_order_by:
        if not isinstance(item, dict):
            raise PlanValidationError("order_by expressions must be objects")
        _reject_unknown_keys(
            item,
            {"field", "aggregate", "direction"},
            "order expression",
        )
        direction = _required_string(item, "direction").lower()
        if direction not in {"asc", "desc"}:
            raise PlanValidationError("invalid order direction")
        aggregate = _optional_string(item.get("aggregate"), "aggregate")
        if aggregate is not None and aggregate not in AGGREGATES:
            raise PlanValidationError("invalid order aggregate")
        order_by.append(
            OrderExpression(
                field=_allowed_field(item),
                direction=direction,
                aggregate=aggregate,
            )
        )

    limit = payload.get("limit")
    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise PlanValidationError("limit must be an integer or null")
        if not 1 <= limit <= 1000:
            raise PlanValidationError("limit must be between 1 and 1000")

    wildcards = [expression for expression in select if expression.field in WILDCARD_FIELDS]
    if wildcards:
        if len(select) != 1:
            raise PlanValidationError("wildcard must be the only selection")
        wildcard = wildcards[0]
        if wildcard.field.split(".", 1)[0] != base_table:
            raise PlanValidationError("wildcard must match base_table")
        if wildcard.aggregate or wildcard.distinct or wildcard.alias:
            raise PlanValidationError("wildcard selection cannot be modified")

    if any(expression.aggregate for expression in select):
        non_aggregate_fields = {
            expression.field
            for expression in select
            if expression.aggregate is None
        }
        if not non_aggregate_fields.issubset(set(group_by)):
            raise PlanValidationError(
                "non-aggregated selections must appear in group_by"
            )

    output_names = [
        expression.alias or expression.field.rsplit(".", 1)[-1]
        for expression in select
        if expression.field not in WILDCARD_FIELDS
    ]
    if len(output_names) != len(set(output_names)):
        raise PlanValidationError("selected result column names must be unique")

    return QueryPlan(
        base_table=base_table,
        select=tuple(select),
        filters=tuple(filters),
        group_by=group_by,
        order_by=tuple(order_by),
        limit=limit,
    )


def parse_agent_plan(payload: Any) -> AgentPlan:
    if not isinstance(payload, dict):
        raise PlanValidationError("plan must be an object")
    _reject_unknown_keys(
        payload,
        {
            "supported",
            "unsupported_category",
            "route",
            "answer_language",
            "semantic_query",
            "semantic_scope",
            "query",
        },
        "plan",
    )

    supported = payload.get("supported")
    if not isinstance(supported, bool):
        raise PlanValidationError("supported must be boolean")

    unsupported_category = _required_string(
        payload,
        "unsupported_category",
    ).lower()
    if unsupported_category not in UNSUPPORTED_CATEGORIES:
        raise PlanValidationError("invalid unsupported_category")

    route = _required_string(payload, "route")
    if route not in ROUTES:
        raise PlanValidationError("invalid route")

    answer_language = _required_string(payload, "answer_language").lower()
    if answer_language not in ANSWER_LANGUAGES:
        raise PlanValidationError("invalid answer_language")

    semantic_query = payload.get("semantic_query", "")
    if not isinstance(semantic_query, str):
        raise PlanValidationError("semantic_query must be a string")
    semantic_query = semantic_query.strip()
    if len(semantic_query) > 500:
        raise PlanValidationError("semantic_query exceeds 500 characters")

    semantic_scope = _required_string(payload, "semantic_scope").lower()
    if semantic_scope not in SEMANTIC_SCOPES:
        raise PlanValidationError("invalid semantic_scope")

    query_payload = payload.get("query")
    query = None if query_payload is None else _parse_query(query_payload)

    if supported:
        if unsupported_category != "none":
            raise PlanValidationError(
                "supported plans must use unsupported_category none"
            )
        if route == "sql_only" and semantic_query:
            raise PlanValidationError("sql_only must not include semantic_query")
        if route == "sql_only" and semantic_scope != "none":
            raise PlanValidationError("sql_only must use semantic_scope none")
        if route in {"sql_only", "review_semantic_plus_sql"} and query is None:
            raise PlanValidationError("this route requires a query plan")
        if route in {"review_semantic", "review_semantic_plus_sql"}:
            if not semantic_query:
                raise PlanValidationError("semantic routes require semantic_query")
            if semantic_scope == "none":
                raise PlanValidationError("semantic routes require a semantic_scope")
        if route == "review_semantic" and query is not None:
            raise PlanValidationError("review_semantic must not include SQL query plan")
        if (
            route == "review_semantic_plus_sql"
            and query is not None
            and query.base_table != "employees"
        ):
            raise PlanValidationError("hybrid plans require employees base_table")
    else:
        if unsupported_category == "none":
            raise PlanValidationError(
                "unsupported plans require an unsupported_category"
            )
        if (
            route != "sql_only"
            or semantic_query
            or semantic_scope != "none"
            or query is not None
        ):
            raise PlanValidationError(
                "unsupported plans must use the empty sql_only shape"
            )

    return AgentPlan(
        supported=supported,
        unsupported_category=unsupported_category,
        route=route,
        answer_language=answer_language,
        semantic_query=semantic_query,
        semantic_scope=semantic_scope,
        query=query,
    )
