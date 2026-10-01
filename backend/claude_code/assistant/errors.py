"""Chyby asistenta s HTTP stavem; jsou to `ValueError`, takže aplikace je umí i bez routeru."""


class AssistantError(ValueError):
    status = 409


class SessionNotFound(AssistantError):
    status = 404


class AssistantUnavailable(AssistantError):
    status = 503
