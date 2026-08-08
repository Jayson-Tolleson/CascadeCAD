class CadOperationException(Exception):
    """Custom exception for errors during CAD operations."""
    pass

class ImportException(CadOperationException):
    """Custom exception for file import errors."""
    pass

class ExportException(CadOperationException):
    """Custom exception for file export errors."""
    pass

class CapabilityException(Exception):
    """Exception raised when an operation is attempted but the capability is missing."""
    pass