"""Processing error classes for standalone package."""

from enum import Enum
from typing import Any, Dict, Optional


class ErrorCode(Enum):
    """Error codes for processing errors."""
    NETWORK_CONNECTION_FAILED = "network_connection_failed"
    HTTP_ERROR = "http_error"
    FILE_NOT_FOUND = "file_not_found"
    PARSING_ERROR = "parsing_error"
    VALIDATION_ERROR = "validation_error"


class ErrorContext:
    """Context information for errors."""
    
    def __init__(self, **kwargs: Any):
        self.metadata: Dict[str, Any] = kwargs
    
    def __getitem__(self, key: str) -> Any:
        return self.metadata[key]
    
    def __setitem__(self, key: str, value: Any) -> None:
        self.metadata[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        return self.metadata.get(key, default)


class ProcessingError(Exception):
    """Base processing error."""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[ErrorCode] = None,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.error_code = error_code
        self.context = context or ErrorContext()
        self.cause = cause


class NetworkError(ProcessingError):
    """Network-related processing error."""
    pass


class ValidationError(ProcessingError):
    """Validation error.""" 
    pass