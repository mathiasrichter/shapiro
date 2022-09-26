from fastapi.testclient import TestClient
from shapiro import shapiro_server

shapiro_server.CONTENT_DIR = './test/ontologies/'

client = TestClient(shapiro_server.app)

def test_get_non_existing_schema():
    response = client.get("/this_is_a_non_existing_ontology")
    assert response.status_code == 404

def test_get_existing_jsonld_schema_as_jsonld():
    response = client.get("/person", headers={"accept-header": "application/ld+json"})
    assert response.status_code == 200

def test_get_existing_jsonld_schema_as_ttl():
    response = client.get("/person", headers={"accept-header": "text/turtle"})
    assert response.status_code == 200
