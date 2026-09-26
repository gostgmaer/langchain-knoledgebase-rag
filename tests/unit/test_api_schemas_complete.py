"""Every API schema must be fully defined. A missing import used in an annotation only fails when the route first
serialises a response (as `CitationSchema` once did, returning 500 on chat), so check them all up front."""

from __future__ import annotations

import importlib
import inspect
import pkgutil

import pytest
from pydantic import BaseModel

import packages.api.schemas as schemas_package


def _models():
    for module_info in pkgutil.iter_modules(schemas_package.__path__):
        module = importlib.import_module(f"{schemas_package.__name__}.{module_info.name}")
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, BaseModel) and cls.__module__ == module.__name__:
                yield cls


@pytest.mark.parametrize("model", list(_models()), ids=lambda m: f"{m.__module__.rsplit('.', 1)[-1]}.{m.__name__}")
def test_schema_is_fully_defined(model):
    assert model.model_rebuild(force=True) is not False
    assert model.__pydantic_complete__
