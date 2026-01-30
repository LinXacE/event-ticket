"""Custom Application Exceptions

Defines custom exception classes for the event ticket system
to provide clear, specific error handling throughout the application.
"""


class EventTicketException(Exception):
    """Base exception for all event ticket application errors"""
    def __init__(self, message, status_code=500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ValidationException(EventTicketException):
    """Raised when ticket validation fails"""
    def __init__(self, message, status_code=400):
        super().__init__(message, status_code)


class DuplicateEntryException(EventTicketException):
    """Raised when a duplicate ticket scan is detected"""
    def __init__(self, message="Duplicate entry detected", status_code=409):
        super().__init__(message, status_code)


class TicketExpiredException(EventTicketException):
    """Raised when a ticket has expired"""
    def __init__(self, message="Ticket has expired", status_code=400):
        super().__init__(message, status_code)


class GateAccessDeniedException(EventTicketException):
    """Raised when entry through a gate is denied"""
    def __init__(self, message="Access denied for this gate", status_code=403):
        super().__init__(message, status_code)


class TicketNotFoundException(EventTicketException):
    """Raised when a ticket is not found in the database"""
    def __init__(self, message="Ticket not found", status_code=404):
        super().__init__(message, status_code)


class EventNotFoundException(EventTicketException):
    """Raised when an event is not found"""
    def __init__(self, message="Event not found", status_code=404):
        super().__init__(message, status_code)


class UserNotFoundException(EventTicketException):
    """Raised when a user is not found"""
    def __init__(self, message="User not found", status_code=404):
        super().__init__(message, status_code)


class UnauthorizedException(EventTicketException):
    """Raised when a user is not authorized to perform an action"""
    def __init__(self, message="Unauthorized", status_code=401):
        super().__init__(message, status_code)


class InvalidConfigurationException(EventTicketException):
    """Raised when application configuration is invalid"""
    def __init__(self, message, status_code=500):
        super().__init__(message, status_code)


class QRCodeGenerationException(EventTicketException):
    """Raised when QR code generation fails"""
    def __init__(self, message="Failed to generate QR code", status_code=500):
        super().__init__(message, status_code)


class BarcodeGenerationException(EventTicketException):
    """Raised when barcode generation fails"""
    def __init__(self, message="Failed to generate barcode", status_code=500):
        super().__init__(message, status_code)


class DatabaseException(EventTicketException):
    """Raised when a database operation fails"""
    def __init__(self, message, status_code=500):
        super().__init__(message, status_code)


class OfflineValidationException(EventTicketException):
    """Raised when offline validation fails"""
    def __init__(self, message="Offline validation error", status_code=500):
        super().__init__(message, status_code)
