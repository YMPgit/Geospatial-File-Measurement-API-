"""Application-specific exceptions mapped to HTTP responses."""

from typing import Any


class GeospatialAPIError(Exception):
    """Base class for errors that translate directly into an HTTP error response."""

    status_code: int = 400

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class UnsupportedFileTypeError(GeospatialAPIError):
    """Uploaded file extension is not one of the supported formats."""

    status_code = 400


class FileTooLargeError(GeospatialAPIError):
    """Uploaded file exceeds the configured size limit."""

    status_code = 413


class InvalidArchiveError(GeospatialAPIError):
    """ZIP/KML archive is structurally invalid or unsafe."""

    status_code = 400


class GeospatialProcessingError(GeospatialAPIError):
    """Readable archive whose geospatial content could not be processed."""

    status_code = 400


class ProcessingFailedError(Exception):
    """Raised after a file record has been persisted with status FAILED.

    Carries the persisted record so the API layer can return the FAILED
    upload response body documented in the assignment.
    """

    def __init__(self, record: Any, detail: str):
        self.record = record
        self.detail = detail
        super().__init__(detail)
