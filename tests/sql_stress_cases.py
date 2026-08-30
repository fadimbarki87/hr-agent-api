"""Frozen SQL-only benchmark created before its first live Azure run.

If a case fails, record the result. Do not tune production prompts or code
against this benchmark.
"""


LANGUAGES = ("en", "de", "fr", "es", "ar")


def intent(
    category,
    questions,
    *,
    base,
    select,
    filters=(),
    group_by=(),
    order_by=(),
    limit=None,
):
    assert set(questions) == set(LANGUAGES)
    return {
        "category": category,
        "questions": questions,
        "base": base,
        "select": select,
        "filters": filters,
        "group_by": group_by,
        "order_by": order_by,
        "limit": limit,
    }


SQL_STRESS_INTENTS = (
    intent(
        "multi_filter_order",
        {
            "en": "Return first name, last name, and email for active Sales staff, ordered by last name ascending.",
            "de": "Gib Vorname, Nachname und E-Mail der aktiven Beschäftigten im Vertrieb aus, aufsteigend nach Nachname sortiert.",
            "fr": "Renvoie le prénom, le nom et l’adresse e-mail du personnel actif des ventes, triés par nom croissant.",
            "es": "Devuelve el nombre, apellido y correo del personal activo de Ventas, ordenado por apellido ascendente.",
            "ar": "اعرض الاسم الأول واسم العائلة والبريد الإلكتروني للموظفين النشطين في قسم المبيعات، مرتبين تصاعديًا حسب اسم العائلة.",
        },
        base="employees",
        select=(("employees.first_name", None), ("employees.last_name", None),
                ("employees.email", None)),
        filters=(("employees.employment_status", "eq", "active"),
                 ("departments.department_name", "eq", "Sales")),
        order_by=(("employees.last_name", None, "asc"),),
    ),
    intent(
        "numeric_range_order",
        {
            "en": "Show first name, last name, and salary for employees earning from 60000 through 90000 inclusive, highest salary first.",
            "de": "Zeige Vorname, Nachname und Gehalt der Mitarbeiter mit einem Gehalt von einschließlich 60000 bis 90000, höchstes Gehalt zuerst.",
            "fr": "Affiche le prénom, le nom et le salaire des employés gagnant entre 60000 et 90000 inclus, salaire le plus élevé en premier.",
            "es": "Muestra el nombre, apellido y salario de quienes ganan entre 60000 y 90000 inclusive, con el salario más alto primero.",
            "ar": "اعرض الاسم الأول واسم العائلة والراتب للموظفين الذين تتراوح رواتبهم بين 60000 و90000 شاملًا، مع الأعلى أولًا.",
        },
        base="employees",
        select=(("employees.first_name", None), ("employees.last_name", None),
                ("employees.salary", None)),
        filters=(("employees.salary", "between", (60000, 90000)),),
        order_by=(("employees.salary", None, "desc"),),
    ),
    intent(
        "date_range",
        {
            "en": "List first name, last name, and hire date for employees hired from 2020-01-01 through 2021-12-31 inclusive.",
            "de": "Liste Vorname, Nachname und Einstellungsdatum der vom 2020-01-01 bis einschließlich 2021-12-31 eingestellten Mitarbeiter.",
            "fr": "Liste le prénom, le nom et la date d’embauche des employés recrutés du 2020-01-01 au 2021-12-31 inclus.",
            "es": "Enumera el nombre, apellido y fecha de contratación de los empleados contratados desde 2020-01-01 hasta 2021-12-31 inclusive.",
            "ar": "اعرض الاسم الأول واسم العائلة وتاريخ التعيين للموظفين المعينين من 2020-01-01 حتى 2021-12-31 شاملًا.",
        },
        base="employees",
        select=(("employees.first_name", None), ("employees.last_name", None),
                ("employees.hire_date", None)),
        filters=(("employees.hire_date", "between",
                  ("2020-01-01", "2021-12-31")),),
    ),
    intent(
        "set_membership",
        {
            "en": "Give first name, last name, and job title for employees belonging to either Engineering or HR.",
            "de": "Gib Vorname, Nachname und Stellenbezeichnung der Mitarbeiter aus, die entweder zur Entwicklung oder zur Personalabteilung gehören.",
            "fr": "Donne le prénom, le nom et le poste des employés appartenant soit à l’ingénierie, soit aux ressources humaines.",
            "es": "Da el nombre, apellido y puesto de los empleados que pertenecen a Ingeniería o a Recursos Humanos.",
            "ar": "اعرض الاسم الأول واسم العائلة والمسمى الوظيفي للموظفين الذين ينتمون إلى قسم الهندسة أو الموارد البشرية.",
        },
        base="employees",
        select=(("employees.first_name", None), ("employees.last_name", None),
                ("employees.job_title", None)),
        filters=(("departments.department_name", "in", ("Engineering", "HR")),),
    ),
    intent(
        "filtered_count",
        {
            "en": "Count the active employees in Human Resources.",
            "de": "Zähle die aktiven Mitarbeiter in der Personalabteilung.",
            "fr": "Compte les employés actifs des ressources humaines.",
            "es": "Cuenta los empleados activos de Recursos Humanos.",
            "ar": "احسب عدد الموظفين النشطين في قسم الموارد البشرية.",
        },
        base="employees",
        select=(("employees.employee_id", "count"),),
        filters=(("employees.employment_status", "eq", "active"),
                 ("departments.department_name", "eq", "HR")),
    ),
    intent(
        "filtered_average",
        {
            "en": "Calculate the average employee salary in the Engineering department.",
            "de": "Berechne das durchschnittliche Mitarbeitergehalt in der Entwicklungsabteilung.",
            "fr": "Calcule le salaire moyen des employés du service d’ingénierie.",
            "es": "Calcula el salario medio de los empleados del departamento de Ingeniería.",
            "ar": "احسب متوسط رواتب الموظفين في قسم الهندسة.",
        },
        base="employees",
        select=(("employees.salary", "avg"),),
        filters=(("departments.department_name", "eq", "Engineering"),),
    ),
    intent(
        "grouped_sum",
        {
            "en": "For every department, return the department name and the sum of employee salaries.",
            "de": "Gib für jede Abteilung den Abteilungsnamen und die Summe der Mitarbeitergehälter aus.",
            "fr": "Pour chaque service, renvoie le nom du service et la somme des salaires des employés.",
            "es": "Para cada departamento, devuelve el nombre del departamento y la suma de los salarios de sus empleados.",
            "ar": "لكل قسم، اعرض اسم القسم ومجموع رواتب الموظفين فيه.",
        },
        base="employees",
        select=(("departments.department_name", None),
                ("employees.salary", "sum")),
        group_by=("departments.department_name",),
    ),
    intent(
        "grouped_count",
        {
            "en": "Return each department name together with its employee count.",
            "de": "Gib jeden Abteilungsnamen zusammen mit der Anzahl seiner Mitarbeiter aus.",
            "fr": "Renvoie chaque nom de service avec son nombre d’employés.",
            "es": "Devuelve cada nombre de departamento junto con su número de empleados.",
            "ar": "اعرض اسم كل قسم مع عدد موظفيه.",
        },
        base="employees",
        select=(("departments.department_name", None),
                ("employees.employee_id", "count")),
        group_by=("departments.department_name",),
    ),
    intent(
        "descending_limit",
        {
            "en": "Return first name, last name, and hire date for the four most recently hired employees.",
            "de": "Gib Vorname, Nachname und Einstellungsdatum der vier zuletzt eingestellten Mitarbeiter aus.",
            "fr": "Renvoie le prénom, le nom et la date d’embauche des quatre employés recrutés le plus récemment.",
            "es": "Devuelve el nombre, apellido y fecha de contratación de los cuatro empleados contratados más recientemente.",
            "ar": "اعرض الاسم الأول واسم العائلة وتاريخ التعيين لأحدث أربعة موظفين تعيينًا.",
        },
        base="employees",
        select=(("employees.first_name", None), ("employees.last_name", None),
                ("employees.hire_date", None)),
        order_by=(("employees.hire_date", None, "desc"),),
        limit=4,
    ),
    intent(
        "ascending_limit",
        {
            "en": "Return first name, last name, and salary for the three lowest-paid employees.",
            "de": "Gib Vorname, Nachname und Gehalt der drei am niedrigsten bezahlten Mitarbeiter aus.",
            "fr": "Renvoie le prénom, le nom et le salaire des trois employés les moins payés.",
            "es": "Devuelve el nombre, apellido y salario de los tres empleados con menor salario.",
            "ar": "اعرض الاسم الأول واسم العائلة والراتب لأقل ثلاثة موظفين أجرًا.",
        },
        base="employees",
        select=(("employees.first_name", None), ("employees.last_name", None),
                ("employees.salary", None)),
        order_by=(("employees.salary", None, "asc"),),
        limit=3,
    ),
    intent(
        "department_filter_order",
        {
            "en": "Show department name and budget where the budget is at least 200000, ordered from largest budget to smallest.",
            "de": "Zeige Abteilungsname und Budget für Budgets von mindestens 200000, vom größten zum kleinsten Budget sortiert.",
            "fr": "Affiche le nom et le budget des services dont le budget est d’au moins 200000, du plus grand au plus petit.",
            "es": "Muestra el nombre y presupuesto de los departamentos cuyo presupuesto es al menos 200000, del mayor al menor.",
            "ar": "اعرض اسم القسم وميزانيته عندما تكون الميزانية 200000 على الأقل، مرتبة من الأكبر إلى الأصغر.",
        },
        base="departments",
        select=(("departments.department_name", None),
                ("departments.budget", None)),
        filters=(("departments.budget", "gte", 200000),),
        order_by=(("departments.budget", None, "desc"),),
    ),
    intent(
        "manager_lookup",
        {
            "en": "Return the manager’s first name, last name, and email for Eva Becker.",
            "de": "Gib Vorname, Nachname und E-Mail der Führungskraft von Eva Becker aus.",
            "fr": "Renvoie le prénom, le nom et l’adresse e-mail du responsable d’Eva Becker.",
            "es": "Devuelve el nombre, apellido y correo del responsable de Eva Becker.",
            "ar": "اعرض الاسم الأول واسم العائلة والبريد الإلكتروني لمدير Eva Becker.",
        },
        base="employees",
        select=(("manager.first_name", None), ("manager.last_name", None),
                ("manager.email", None)),
        filters=(("employees.first_name", "eq", "Eva"),
                 ("employees.last_name", "eq", "Becker")),
    ),
    intent(
        "direct_reports",
        {
            "en": "Return first name, last name, and email for everyone who reports directly to David Weber.",
            "de": "Gib Vorname, Nachname und E-Mail aller Personen aus, die direkt an David Weber berichten.",
            "fr": "Renvoie le prénom, le nom et l’adresse e-mail de toutes les personnes rattachées directement à David Weber.",
            "es": "Devuelve el nombre, apellido y correo de todas las personas que dependen directamente de David Weber.",
            "ar": "اعرض الاسم الأول واسم العائلة والبريد الإلكتروني لكل من يتبع مباشرةً David Weber.",
        },
        base="employees",
        select=(("employees.first_name", None), ("employees.last_name", None),
                ("employees.email", None)),
        filters=(("manager.first_name", "eq", "David"),
                 ("manager.last_name", "eq", "Weber")),
    ),
    intent(
        "null_filter",
        {
            "en": "List first name, last name, and job title for employees who do not have a manager.",
            "de": "Liste Vorname, Nachname und Stellenbezeichnung der Mitarbeiter ohne Führungskraft.",
            "fr": "Liste le prénom, le nom et le poste des employés qui n’ont pas de responsable.",
            "es": "Enumera el nombre, apellido y puesto de los empleados que no tienen responsable.",
            "ar": "اعرض الاسم الأول واسم العائلة والمسمى الوظيفي للموظفين الذين ليس لديهم مدير.",
        },
        base="employees",
        select=(("employees.first_name", None), ("employees.last_name", None),
                ("employees.job_title", None)),
        filters=(("employees.manager_id", "is_null", None),),
    ),
    intent(
        "absence_filter_order",
        {
            "en": "Return absence ID, start date, end date, and days absent for paid vacation, ordered by start date ascending.",
            "de": "Gib Abwesenheits-ID, Startdatum, Enddatum und Abwesenheitstage für bezahlten Urlaub aus, aufsteigend nach Startdatum sortiert.",
            "fr": "Renvoie l’identifiant d’absence, la date de début, la date de fin et les jours d’absence pour les congés payés, triés par date de début croissante.",
            "es": "Devuelve el ID de ausencia, fecha de inicio, fecha de fin y días ausentes de las vacaciones pagadas, ordenados por fecha de inicio ascendente.",
            "ar": "اعرض معرف الغياب وتاريخ البداية وتاريخ النهاية وعدد أيام الغياب للإجازات المدفوعة، مرتبة تصاعديًا حسب تاريخ البداية.",
        },
        base="absences",
        select=(("absences.absence_id", None), ("absences.start_date", None),
                ("absences.end_date", None), ("absences.days_absent", None)),
        filters=(("absences.absence_type", "eq", "paid_vacation"),),
        order_by=(("absences.start_date", None, "asc"),),
    ),
    intent(
        "filtered_sum",
        {
            "en": "Calculate the total number of absent days across all sick absences.",
            "de": "Berechne die Gesamtzahl der Abwesenheitstage über alle Krankheitsfälle.",
            "fr": "Calcule le nombre total de jours d’absence pour toutes les absences maladie.",
            "es": "Calcula el total de días ausentes de todas las bajas por enfermedad.",
            "ar": "احسب مجموع أيام الغياب لجميع حالات الغياب المرضي.",
        },
        base="absences",
        select=(("absences.days_absent", "sum"),),
        filters=(("absences.absence_type", "eq", "sick"),),
    ),
    intent(
        "absence_grouped_count",
        {
            "en": "For each absence type, return the absence type and its number of absence records.",
            "de": "Gib für jede Abwesenheitsart die Art und die Anzahl ihrer Abwesenheitseinträge aus.",
            "fr": "Pour chaque type d’absence, renvoie le type et son nombre d’enregistrements d’absence.",
            "es": "Para cada tipo de ausencia, devuelve el tipo y su número de registros de ausencia.",
            "ar": "لكل نوع غياب، اعرض نوع الغياب وعدد سجلات الغياب الخاصة به.",
        },
        base="absences",
        select=(("absences.absence_type", None),
                ("absences.absence_id", "count")),
        group_by=("absences.absence_type",),
    ),
    intent(
        "cross_table_absences",
        {
            "en": "Return absence ID, start date, and end date for absences belonging to Engineering employees.",
            "de": "Gib Abwesenheits-ID, Startdatum und Enddatum für Abwesenheiten von Mitarbeitern der Entwicklungsabteilung aus.",
            "fr": "Renvoie l’identifiant, la date de début et la date de fin des absences des employés de l’ingénierie.",
            "es": "Devuelve el ID, la fecha de inicio y la fecha de fin de las ausencias de empleados de Ingeniería.",
            "ar": "اعرض معرف الغياب وتاريخ البداية وتاريخ النهاية لغيابات موظفي قسم الهندسة.",
        },
        base="absences",
        select=(("absences.absence_id", None), ("absences.start_date", None),
                ("absences.end_date", None)),
        filters=(("departments.department_name", "eq", "Engineering"),),
    ),
    intent(
        "literal_review_text",
        {
            "en": "Return employee first and last names when performance_review literally contains the exact phrase detail-oriented.",
            "de": "Gib Vor- und Nachnamen aus, wenn performance_review wörtlich die exakte Zeichenfolge detail-oriented enthält.",
            "fr": "Renvoie le prénom et le nom lorsque performance_review contient littéralement la chaîne exacte detail-oriented.",
            "es": "Devuelve el nombre y apellido cuando performance_review contiene literalmente la cadena exacta detail-oriented.",
            "ar": "اعرض الاسم الأول واسم العائلة عندما يحتوي حقل performance_review حرفيًا على العبارة المطابقة detail-oriented.",
        },
        base="employees",
        select=(("employees.first_name", None), ("employees.last_name", None)),
        filters=(("employees.performance_review", "contains", "detail-oriented"),),
    ),
    intent(
        "valid_empty_result",
        {
            "en": "Return first name, last name, and salary for employees whose salary exceeds 200000.",
            "de": "Gib Vorname, Nachname und Gehalt der Mitarbeiter mit einem Gehalt über 200000 aus.",
            "fr": "Renvoie le prénom, le nom et le salaire des employés dont le salaire dépasse 200000.",
            "es": "Devuelve el nombre, apellido y salario de los empleados cuyo salario supera 200000.",
            "ar": "اعرض الاسم الأول واسم العائلة والراتب للموظفين الذين يتجاوز راتبهم 200000.",
        },
        base="employees",
        select=(("employees.first_name", None), ("employees.last_name", None),
                ("employees.salary", None)),
        filters=(("employees.salary", "gt", 200000),),
    ),
)


SQL_STRESS_CASES = tuple(
    {
        "intent": intent_index,
        "category": item["category"],
        "question": item["questions"][language],
        "route": "sql_only",
        "language": language,
        "supported": True,
        "scope": "none",
        "base": item["base"],
        "select": item["select"],
        "filters": item["filters"],
        "group_by": item["group_by"],
        "order_by": item["order_by"],
        "limit": item["limit"],
    }
    for intent_index, item in enumerate(SQL_STRESS_INTENTS, start=1)
    for language in LANGUAGES
)


assert len(SQL_STRESS_INTENTS) == 20
assert len(SQL_STRESS_CASES) == 100
