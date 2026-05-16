"""Pytest config for unit tests."""
import pytest

# Make all async tests work with pytest-anyio
pytest_plugins = ("anyio",)
