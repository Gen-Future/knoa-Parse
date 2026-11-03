class ParseError(Exception):
    """A stable error code and safe public explanation."""

    def __init__(self, code: str, message: str, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ProviderError(ParseError):
    """Safe shared error for external providers; retryability is a hint, not a retry."""

    def __init__(self, code: str, message: str, status_code: int = 502, *, retryable: bool = False):
        super().__init__(code, message, status_code)
        self.retryable = retryable
