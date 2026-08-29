from __future__ import annotations

from dataclasses import dataclass
import re

from .models import (
    FilterExpression,
    OrderExpression,
    QueryPlan,
    SelectExpression,
)


class QueryBuildError(ValueError):
    pass


@dataclass(frozen=True)
class BuiltQuery:
    sql: str
    parameters: tuple[object, ...]


FIELD_SQL = {
    "employees.employee_id": "e.employee_id",
    "employees.first_name": "e.first_name",
    "employees.last_name": "e.last_name",
    "employees.email": "e.email",
    "employees.hire_date": "e.hire_date",
    "employees.job_title": "e.job_title",
    "employees.department_id": "e.department_id",
    "employees.manager_id": "e.manager_id",
    "employees.salary": "e.salary",
    "employees.employment_status": "e.employment_status",
    "employees.performance_review": "e.performance_review",
    "departments.department_id": "d.department_id",
    "departments.department_name": "d.department_name",
    "departments.budget": "d.budget",
    "absences.absence_id": "a.absence_id",
    "absences.employee_id": "a.employee_id",
    "absences.absence_type": "a.absence_type",
    "absences.start_date": "a.start_date",
    "absences.end_date": "a.end_date",
    "absences.days_absent": "a.days_absent",
    "absences.reason": "a.reason",
    "manager.employee_id": "m.employee_id",
    "manager.first_name": "m.first_name",
    "manager.last_name": "m.last_name",
    "manager.email": "m.email",
    "manager.job_title": "m.job_title",
}

WILDCARD_SQL = {
    "employees.*": "e.*",
    "departments.*": "d.*",
    "absences.*": "a.*",
}

NUMERIC_FIELDS = {
    "employees.employee_id",
    "employees.department_id",
    "employees.manager_id",
    "employees.salary",
    "departments.department_id",
    "departments.budget",
    "absences.absence_id",
    "absences.employee_id",
    "absences.days_absent",
    "manager.employee_id",
}

PRIMARY_FIELDS = {
    "employees": "employees.employee_id",
    "departments": "departments.department_id",
    "absences": "absences.absence_id",
}

ALIAS_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def _field_sql(field: str) -> str:
    try:
        return FIELD_SQL[field]
    except KeyError as error:
        raise QueryBuildError(f"field is not allowed: {field}") from error


def _source_for_field(field: str) -> str:
    source = field.split(".", 1)[0]
    if source not in {"employees", "departments", "absences", "manager"}:
        raise QueryBuildError(f"field source is not allowed: {field}")
    return source


def _validate_alias(alias: str | None) -> str:
    if alias is None:
        return ""
    if not ALIAS_PATTERN.fullmatch(alias):
        raise QueryBuildError("invalid result alias")
    return f' AS "{alias}"'


def _compile_aggregate(field: str, aggregate: str | None, distinct: bool) -> str:
    field_sql = _field_sql(field)
    if aggregate is None:
        if distinct:
            raise QueryBuildError("distinct requires an aggregate")
        return field_sql
    if aggregate in {"sum", "avg"} and field not in NUMERIC_FIELDS:
        raise QueryBuildError(f"{aggregate} requires a numeric field")
    distinct_sql = "DISTINCT " if distinct else ""
    return f"{aggregate.upper()}({distinct_sql}{field_sql})"


def _compile_select(expression: SelectExpression) -> str:
    if expression.field in WILDCARD_SQL:
        if expression.aggregate or expression.distinct or expression.alias:
            raise QueryBuildError("wildcard selections cannot be modified")
        return WILDCARD_SQL[expression.field]
    return (
        _compile_aggregate(
            expression.field,
            expression.aggregate,
            expression.distinct,
        )
        + _validate_alias(expression.alias)
    )


def _compile_order(expression: OrderExpression) -> str:
    sql = _compile_aggregate(expression.field, expression.aggregate, False)
    return f"{sql} {expression.direction.upper()}"


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _compile_filter(
    expression: FilterExpression,
) -> tuple[str, list[object]]:
    field_sql = _field_sql(expression.field)
    operator = expression.operator
    value = expression.value

    if operator in {"is_null", "is_not_null"}:
        if value is not None:
            raise QueryBuildError(f"{operator} does not accept a value")
        return (
            f"{field_sql} IS {'NOT ' if operator == 'is_not_null' else ''}NULL",
            [],
        )

    if operator in {"eq", "neq"} and value is None:
        return (f"{field_sql} IS {'NOT ' if operator == 'neq' else ''}NULL", [])

    if operator in {"eq", "neq", "gt", "gte", "lt", "lte"}:
        if isinstance(value, (dict, list)) or value is None:
            raise QueryBuildError(f"{operator} requires a scalar value")
        sql_operator = {
            "eq": "=",
            "neq": "!=",
            "gt": ">",
            "gte": ">=",
            "lt": "<",
            "lte": "<=",
        }[operator]
        collation = " COLLATE NOCASE" if isinstance(value, str) else ""
        return f"{field_sql} {sql_operator} ?{collation}", [value]

    if operator == "between":
        if not isinstance(value, list) or len(value) != 2:
            raise QueryBuildError("between requires exactly two values")
        if any(isinstance(item, (dict, list)) or item is None for item in value):
            raise QueryBuildError("between values must be scalar")
        return f"{field_sql} BETWEEN ? AND ?", list(value)

    if operator in {"contains", "starts_with", "ends_with"}:
        if not isinstance(value, str) or not value:
            raise QueryBuildError(f"{operator} requires non-empty text")
        escaped = _escape_like(value)
        if operator == "contains":
            parameter = f"%{escaped}%"
        elif operator == "starts_with":
            parameter = f"{escaped}%"
        else:
            parameter = f"%{escaped}"
        return (
            f"LOWER({field_sql}) LIKE LOWER(?) ESCAPE '\\'",
            [parameter],
        )

    if operator == "in":
        if not isinstance(value, list) or not 1 <= len(value) <= 100:
            raise QueryBuildError("in requires 1 to 100 values")
        if any(isinstance(item, (dict, list)) or item is None for item in value):
            raise QueryBuildError("in values must be scalar")
        placeholders = ", ".join("?" for _ in value)
        return f"{field_sql} IN ({placeholders})", list(value)

    raise QueryBuildError(f"operator is not allowed: {operator}")


def _all_referenced_fields(plan: QueryPlan) -> list[str]:
    fields = [expression.field for expression in plan.select]
    fields.extend(expression.field for expression in plan.filters)
    fields.extend(plan.group_by)
    fields.extend(expression.field for expression in plan.order_by)
    return fields


def _compile_joins(base_table: str, sources: set[str]) -> list[str]:
    joins: list[str] = []
    if base_table == "employees":
        if "departments" in sources:
            joins.append(
                "JOIN departments d ON e.department_id = d.department_id"
            )
        if "absences" in sources:
            joins.append("JOIN absences a ON a.employee_id = e.employee_id")
        if "manager" in sources:
            joins.append("JOIN employees m ON e.manager_id = m.employee_id")
    elif base_table == "departments":
        if sources & {"employees", "absences", "manager"}:
            joins.append(
                "LEFT JOIN employees e ON e.department_id = d.department_id"
            )
        if "absences" in sources:
            joins.append("LEFT JOIN absences a ON a.employee_id = e.employee_id")
        if "manager" in sources:
            joins.append("LEFT JOIN employees m ON e.manager_id = m.employee_id")
    elif base_table == "absences":
        if sources & {"employees", "departments", "manager"}:
            joins.append("JOIN employees e ON a.employee_id = e.employee_id")
        if "departments" in sources:
            joins.append(
                "JOIN departments d ON e.department_id = d.department_id"
            )
        if "manager" in sources:
            joins.append("JOIN employees m ON e.manager_id = m.employee_id")
    return joins


def build_query(
    plan: QueryPlan,
    *,
    semantic_candidate_ids: list[int] | None = None,
) -> BuiltQuery:
    base_alias = {"employees": "e", "departments": "d", "absences": "a"}[
        plan.base_table
    ]

    wildcard_expressions = [
        expression
        for expression in plan.select
        if expression.field in WILDCARD_SQL
    ]
    if wildcard_expressions and len(plan.select) != 1:
        raise QueryBuildError("wildcard must be the only selected expression")

    aggregate_expressions = [
        expression for expression in plan.select if expression.aggregate
    ]
    if aggregate_expressions:
        for expression in aggregate_expressions:
            if expression.alias is None:
                raise QueryBuildError("aggregate selections require an alias")
        non_aggregate_fields = {
            expression.field
            for expression in plan.select
            if expression.aggregate is None
        }
        if not non_aggregate_fields.issubset(set(plan.group_by)):
            raise QueryBuildError(
                "non-aggregated selections must appear in group_by"
            )

    output_names = []
    for expression in plan.select:
        if expression.field in WILDCARD_SQL:
            continue
        output_names.append(expression.alias or expression.field.rsplit(".", 1)[-1])
    if len(output_names) != len(set(output_names)):
        raise QueryBuildError("selected result column names must be unique")

    referenced_fields = _all_referenced_fields(plan)
    sources = {_source_for_field(field) for field in referenced_fields}
    for expression in plan.select:
        if expression.field in WILDCARD_SQL:
            wildcard_source = expression.field.split(".", 1)[0]
            if wildcard_source != plan.base_table:
                raise QueryBuildError("wildcard must match the base table")
            sources.add(wildcard_source)

    if semantic_candidate_ids is not None:
        if plan.base_table != "employees":
            raise QueryBuildError("semantic candidates require employees base table")
        if any(
            isinstance(employee_id, bool)
            or not isinstance(employee_id, int)
            or employee_id <= 0
            for employee_id in semantic_candidate_ids
        ):
            raise QueryBuildError("invalid semantic employee id")
        sources.add("employees")

    select_sql = ", ".join(_compile_select(item) for item in plan.select)
    sql_parts = [f"SELECT {select_sql}", f"FROM {plan.base_table} {base_alias}"]
    sql_parts.extend(_compile_joins(plan.base_table, sources))

    conditions: list[str] = []
    parameters: list[object] = []
    for expression in plan.filters:
        condition, values = _compile_filter(expression)
        conditions.append(condition)
        parameters.extend(values)

    if semantic_candidate_ids is not None:
        candidate_ids = list(dict.fromkeys(semantic_candidate_ids))
        if candidate_ids:
            placeholders = ", ".join("?" for _ in candidate_ids)
            conditions.append(f"e.employee_id IN ({placeholders})")
            parameters.extend(candidate_ids)
        else:
            conditions.append("1 = 0")
    else:
        candidate_ids = []

    if conditions:
        sql_parts.append("WHERE " + " AND ".join(conditions))

    if plan.group_by:
        sql_parts.append(
            "GROUP BY " + ", ".join(_field_sql(field) for field in plan.group_by)
        )

    order_by = [_compile_order(item) for item in plan.order_by]
    has_aggregate = any(item.aggregate for item in plan.select)
    if not order_by and candidate_ids and not has_aggregate and not plan.group_by:
        relevance_cases = " ".join(
            f"WHEN ? THEN {position}"
            for position, _employee_id in enumerate(candidate_ids)
        )
        order_by = [
            f"CASE e.employee_id {relevance_cases} "
            f"ELSE {len(candidate_ids)} END ASC",
            "e.employee_id ASC",
        ]
        parameters.extend(candidate_ids)
    elif not order_by:
        if plan.group_by:
            order_by = [f"{_field_sql(field)} ASC" for field in plan.group_by]
        elif not has_aggregate:
            order_by = [f"{_field_sql(PRIMARY_FIELDS[plan.base_table])} ASC"]
    elif not has_aggregate and not plan.group_by:
        primary_sql = _field_sql(PRIMARY_FIELDS[plan.base_table])
        if not any(primary_sql in item for item in order_by):
            order_by.append(f"{primary_sql} ASC")
    if order_by:
        sql_parts.append("ORDER BY " + ", ".join(order_by))

    if plan.limit is not None:
        sql_parts.append("LIMIT ?")
        parameters.append(plan.limit)

    return BuiltQuery(sql="\n".join(sql_parts), parameters=tuple(parameters))
