"""Wyjątki modułu storage."""


class DuplicateDocumentError(ValueError):
    """Dokument o tej samej treści (content_hash) już istnieje pod innym id."""
