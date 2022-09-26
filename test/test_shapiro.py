from fastapi.testclient import TestClient
from ..shapiro_server import get_server

client = TestClient(get_server(3333, './test/ontologies', 'info').serve)

def test_get_existing_schema():
    response = client.get("/person")
    assert response.status_code == 200
    assert response.text == 'foo'
