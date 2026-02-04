"""Adapter package for external I/O implementations.

Purpose:
    Collect concrete implementations for domain ports (HTTP, filesystem,
    discovery, and test doubles) used by use cases.

Dependencies:
    Individual submodules depend on ``requests``, filesystem APIs, and domain
    protocol definitions.

Call context:
    Imported by app composition modules (for runtime wiring) and by tests (for
    mocks and transport-level behavior verification).
"""
