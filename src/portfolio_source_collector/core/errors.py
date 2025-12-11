class BrokerError(Exception):
    """Base class for broker-related errors."""


class AuthenticationError(BrokerError):
    """Raised when authentication fails with a broker."""


class RateLimitError(BrokerError):
    """Raised when requests are rate-limited."""


class NormalizationError(BrokerError):
    """Raised when payloads cannot be normalized into shared models."""

