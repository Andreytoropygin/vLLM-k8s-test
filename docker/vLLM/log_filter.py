import logging

class PrivacyFilter(logging.Filter):
    """Фильтр, блокирующий вывод текстов промптов и сгенерированных ответов модели."""
    BLOCKED_PATTERNS = (
        "prompt:",
        "prompt_token_ids:",
        "generated_text:",
        "Received request",
        "Added request",
    )

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not any(pattern in message for pattern in self.BLOCKED_PATTERNS)
