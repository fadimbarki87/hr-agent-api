from __future__ import annotations


UNSUPPORTED_MSG = "Unsupported or vague question."
EMPTY_MSG = "Empty result."

STATUS_MESSAGES = {
    "en": {
        "unsupported": UNSUPPORTED_MSG,
        "empty": EMPTY_MSG,
    },
    "de": {
        "unsupported": "Nicht unterstützte oder zu vage Frage.",
        "empty": "Leeres Ergebnis.",
    },
    "es": {
        "unsupported": "Pregunta no compatible o demasiado vaga.",
        "empty": "Resultado vacío.",
    },
    "fr": {
        "unsupported": "Question non prise en charge ou trop vague.",
        "empty": "Résultat vide.",
    },
    "ar": {
        "unsupported": "السؤال غير مدعوم أو غامض جدًا.",
        "empty": "لا توجد نتائج.",
    },
}


def localize_status(message: str, language: str) -> str:
    translations = STATUS_MESSAGES.get(language, STATUS_MESSAGES["en"])
    if message == UNSUPPORTED_MSG:
        return translations["unsupported"]
    if message == EMPTY_MSG:
        return translations["empty"]
    return message
