class TextUniqError(Exception):
    """Базовая ошибка приложения."""


class TranslationError(TextUniqError):
    """Переводчик не смог перевести текст или вернул пустой результат."""


class TranslatorUnavailableError(TextUniqError):
    """Переводчик нельзя запустить: нет библиотек, модели или пары языков."""


class DocumentError(TextUniqError):
    """Проблема с входным или выходным документом."""
