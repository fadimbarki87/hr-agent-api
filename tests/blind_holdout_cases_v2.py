"""Fresh v2 cases frozen before the first audited-planner acceptance run."""

from blind_holdout_cases import case


BLIND_HOLDOUT_CASES_V2 = [
    case(
        "Give the total headcount of employees paid no more than 88000.",
        "sql_only", "en", base="employees",
        select=(("employees.employee_id", "count"),),
        filters=(("employees.salary", "lte", 88000),),
    ),
    case(
        "Berechne das durchschnittliche Abteilungsbudget.",
        "sql_only", "de", base="departments",
        select=(("departments.budget", "avg"),),
    ),
    case(
        "Quels employés ont été embauchés le 2023-07-01 ?",
        "sql_only", "fr", base="employees",
        select=(("employees.first_name", None), ("employees.last_name", None)),
        filters=(("employees.hire_date", "eq", "2023-07-01"),),
    ),
    case(
        "Muestra las razones de las bajas por enfermedad que duraron al menos 4 días.",
        "sql_only", "es", base="absences",
        select=(("absences.reason", None),),
        filters=(("absences.absence_type", "eq", "sick"),
                 ("absences.days_absent", "gte", 4)),
    ),
    case(
        "اعرض أسماء الموظفين في الموارد البشرية مرتبة حسب تاريخ التعيين من الأحدث إلى الأقدم.",
        "sql_only", "ar", base="employees",
        select=(("employees.first_name", None), ("employees.last_name", None)),
        filters=(("departments.department_name", "eq", "HR"),),
        order_by=(("employees.hire_date", None, "desc"),),
    ),
    case(
        "Return employee and manager email addresses for people reporting to David Weber.",
        "sql_only", "en", base="employees",
        select=(("employees.email", None), ("manager.email", None)),
        filters=(("manager.first_name", "eq", "David"),
                 ("manager.last_name", "eq", "Weber")),
    ),
    case(
        "Wie viele unbezahlte Urlaubsfälle gibt es pro Mitarbeiter?",
        "sql_only", "de", base="absences",
        select=(("absences.employee_id", None), ("absences.absence_id", "count")),
        filters=(("absences.absence_type", "eq", "unpaid_vacation"),),
        group_by=("absences.employee_id",),
    ),
    case(
        "Affiche les deux départements au plus gros budget.",
        "sql_only", "fr", base="departments",
        select=(("departments.department_name", None), ("departments.budget", None)),
        order_by=(("departments.budget", None, "desc"),), limit=2,
    ),
    case(
        "Devuelve los nombres cuando la evaluación empieza literalmente por Excellent.",
        "sql_only", "es", base="employees",
        select=(("employees.first_name", None), ("employees.last_name", None)),
        filters=(("employees.performance_review", "starts_with", "Excellent"),),
    ),
    case(
        "ما هي سياسة العمل عن بعد المعتمدة في الشركة؟",
        "sql_only", "ar", supported=False,
    ),

    case(
        "Who is explicitly viewed as capable of taking on broader duties now?",
        "review_semantic", "en", scope="readiness",
    ),
    case(
        "Bei wem wird fehlende Konfliktfähigkeit als Schwäche beschrieben?",
        "review_semantic", "de", scope="development_need",
    ),
    case(
        "Qui pourrait à l'avenir exceller dans la coordination de projets ?",
        "review_semantic", "fr", scope="future_potential",
    ),
    case(
        "¿Quién demuestra ahora una comunicación clara con clientes?",
        "review_semantic", "es", scope="current_strength",
    ),
    case(
        "من لديه مؤشرات إيجابية عامة على الإبداع؟",
        "review_semantic", "ar", scope="broad_positive",
    ),
    case(
        "Whose feedback takes a neutral view of adapting to new tools?",
        "review_semantic", "en", scope="neutral",
    ),
    case(
        "Wer zeigt aktuell Ausdauer bei langwierigen Aufgaben?",
        "review_semantic", "de", scope="current_strength",
    ),
    case(
        "Qui doit progresser dans la prise de décision autonome ?",
        "review_semantic", "fr", scope="development_need",
    ),
    case(
        "¿Quién está listo hoy para orientar a compañeros nuevos?",
        "review_semantic", "es", scope="readiness",
    ),
    case(
        "من قد يصبح مستقبلا بارعا في التحليل؟",
        "review_semantic", "ar", scope="future_potential",
    ),

    case(
        "How many active Engineering employees currently demonstrate patience with customers?",
        "review_semantic_plus_sql", "en", scope="current_strength", base="employees",
        select=(("employees.employee_id", "count"),),
        filters=(("employees.employment_status", "eq", "active"),
                 ("departments.department_name", "eq", "Engineering")),
    ),
    case(
        "Zeige den bestbezahlten Mitarbeiter unter denjenigen, die künftig komplexe Projekte leiten könnten.",
        "review_semantic_plus_sql", "de", scope="future_potential", base="employees",
        select=(("employees.first_name", None), ("employees.last_name", None),
                ("employees.salary", None)),
        order_by=(("employees.salary", None, "desc"),), limit=1,
    ),
    case(
        "Parmi les employés sans manager, qui montre actuellement une forte autonomie ?",
        "review_semantic_plus_sql", "fr", scope="current_strength", base="employees",
        select=(("employees.first_name", None), ("employees.last_name", None)),
        filters=(("employees.manager_id", "is_null", None),),
    ),
    case(
        "Lista los correos de empleados de Ventas que necesitan mejorar al dar feedback.",
        "review_semantic_plus_sql", "es", scope="development_need", base="employees",
        select=(("employees.email", None),),
        filters=(("departments.department_name", "eq", "Sales"),),
    ),
    case(
        "من بين الموظفين الذين رواتبهم أقل من 70000، من لديه قدرة مستقبلية على التفاوض؟",
        "review_semantic_plus_sql", "ar", scope="future_potential", base="employees",
        select=(("employees.first_name", None), ("employees.last_name", None)),
        filters=(("employees.salary", "lt", 70000),),
    ),
    case(
        "For each department, count staff with positive evidence of resilience.",
        "review_semantic_plus_sql", "en", scope="broad_positive", base="employees",
        select=(("departments.department_name", None), ("employees.employee_id", "count")),
        group_by=("departments.department_name",),
    ),
    case(
        "Welche vor dem 01.06.2021 eingestellten Mitarbeiter sind heute bereit, andere anzuleiten?",
        "review_semantic_plus_sql", "de", scope="readiness", base="employees",
        select=(("employees.first_name", None), ("employees.last_name", None)),
        filters=(("employees.hire_date", "lt", "2021-06-01"),),
    ),
    case(
        "Donne les deux employés les plus récemment embauchés qui font actuellement preuve de créativité.",
        "review_semantic_plus_sql", "fr", scope="current_strength", base="employees",
        select=(("employees.first_name", None), ("employees.last_name", None)),
        order_by=(("employees.hire_date", None, "desc"),), limit=2,
    ),
    case(
        "¿Qué empleados con bajas por enfermedad muestran actualmente una planificación cuidadosa?",
        "review_semantic_plus_sql", "es", scope="current_strength", base="employees",
        select=(("employees.first_name", None), ("employees.last_name", None)),
        filters=(("absences.absence_type", "eq", "sick"),),
    ),
    case(
        "من يعمل في قسم خدمة العملاء ويظهر تعاطفا؟",
        "sql_only", "ar", supported=False,
    ),
]

assert len(BLIND_HOLDOUT_CASES_V2) == 30
