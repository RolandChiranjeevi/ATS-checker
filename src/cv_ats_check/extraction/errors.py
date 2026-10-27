"""Exceptions raised when a CV file cannot be read."""


class ExtractionError(Exception):
    """Base class for all extraction problems; the message is user-facing."""


class MissingFile(ExtractionError):
    """The path does not point to an existing file."""


class UnsupportedFileType(ExtractionError):
    """The file extension is not one we can parse."""


class EmptyFile(ExtractionError):
    """The file has zero bytes."""


class CorruptFile(ExtractionError):
    """The file exists but cannot be parsed (damaged, encrypted, not a real PDF/DOCX)."""
