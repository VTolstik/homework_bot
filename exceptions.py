class ErrorApiAnswer(Exception):
    """Ошибка ответа API."""
    pass


class ErrorKeyApiAnswer(Exception):
    """В API ответе присутствуют ключи, сообщающие об ошибке."""
    pass
