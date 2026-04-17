import pytest
import importlib
import sys
from werkzeug.test import Client
from werkzeug.wrappers import Response

def _app_module():
    return importlib.import_module("app")


def _client():
    return Client(_app_module().create_app(), Response)

def test_healthcheck_ready_route():
    response = _client().get("/healthcheck/ready")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Application OK' in body
