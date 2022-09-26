from fastapi.testclient import TestClient
from shapiro import shapiro_server

shapiro_server.CONTENT_DIR = './test/ontologies/'

client = TestClient(shapiro_server.app)

def test_get_non_existing_schema():
    response = client.get("/this_is_a_non_existing_ontology")
    assert response.status_code == 404

def test_get_existing_jsonld_schema_as_jsonld():
    mime = 'application/ld+json'
    response = client.get("/person", headers={"accept-header": mime})
    assert response.headers['content-type'].startswith(mime)
    assert response.status_code == 200

def test_get_existing_jsonld_schema_as_ttl():
    mime = 'text/turtle'
    response = client.get("/person", headers={"accept-header": mime})
    assert response.headers['content-type'].startswith(mime)
    assert response.status_code == 200

def test_get_existing_ttl_schema_deep_down_in_the_hierarchy_as_jsonld():
    mime = 'application/ld+json'
    response = client.get("/com/example/org/person", headers={"accept-header": mime})
    assert response.headers['content-type'].startswith(mime)
    assert response.status_code == 200

def test_get_existing_ttl_schema_deep_down_in_the_hierarchy_as_ttl():
    mime = 'text/turtle'
    response = client.get("/com/example/org/person", headers={"accept-header": mime})
    assert response.headers['content-type'].startswith(mime)
    assert response.status_code == 200

def test_get_existing_jsonld_schema_as_default_without_accept_header():
    mime = ''
    response = client.get("/person", headers={"accept-header": mime})
    assert response.headers['content-type'].startswith(shapiro_server.MIME_DEFAULT)
    assert response.status_code == 200

def test_get_existing_ttl_schema_as_default_without_accept_header():
    mime = ''
    response = client.get("/com/example/org/person", headers={"accept-header": mime})
    assert response.headers['content-type'].startswith(shapiro_server.MIME_DEFAULT)
    assert response.status_code == 200

def test_get_existing_schema_with_duplicates():
    response = client.get("/dupes/person")
    assert response.status_code == 404
