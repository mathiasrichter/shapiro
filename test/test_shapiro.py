from fastapi.testclient import TestClient
from shapiro import shapiro_server
import os

shapiro_server.CONTENT_DIR = './test/ontologies'

client = TestClient(shapiro_server.app)

def test_get_server():
    server = shapiro_server.get_server('127.0.0.1', 8000, shapiro_server.CONTENT_DIR, 'info')
    assert server is not None

def test_commandline_parse_to_default():
    args = shapiro_server.get_args([])
    assert args.host == '127.0.0.1'
    assert args.port == 8000
    assert args.content_dir == './'
    assert args.log_level == 'info'

def test_commandline_parse_to_specified_values():
    args = shapiro_server.get_args(['--host', '0.0.0.0', '--port', '1234', '--content_dir', './foo', '--log_level', 'bar'])
    assert args.host == '0.0.0.0'
    assert args.port == 1234
    assert args.content_dir == './foo'
    assert args.log_level == 'bar'

def test_get_non_existing_schema():
    response = client.get("/this_is_a_non_existing_ontology")
    assert response.status_code == 404

def test_get_existing_jsonld_schema_as_jsonld():
    mime = 'application/ld+json'
    response = client.get("/person", headers={"accept-header": mime})
    assert response.headers['content-type'].startswith(mime)
    assert response.status_code == 200

def test_get_existing_jsonld_schema_as_jsonld_with_multiple_weighted_accept_headers():
    mime_in = 'application/ld+json;q=0.9,text/turtle;q=0.8'
    mime_out = 'application/ld+json'
    response = client.get("/person", headers={"accept-header": mime_in})
    assert response.headers['content-type'].startswith(mime_out)
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

def test_get_existing_ttl_schema_deep_down_in_the_hierarchy_as_jsonld_ignoring_element_reference_with_os_path_sep():
    mime = 'application/ld+json'
    response = client.get("/com/example/org/person/firstname", headers={"accept-header": mime})
    assert response.headers['content-type'].startswith(mime)
    assert response.status_code == 200

def test_get_existing_ttl_schema_deep_down_in_the_hierarchy_as_jsonld_ignoring_element_reference_with_anchor():
    mime = 'application/ld+json'
    response = client.get("/com/example/org/person#firstname", headers={"accept-header": mime})
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

def test_get_existing_schema_with_uncovered_mime_type():
    mime = 'text/text'
    response = client.get("/com/example/org/person", headers={"accept-header": mime})
    assert response.headers['content-type'].startswith(shapiro_server.MIME_DEFAULT)
    assert response.status_code == 200

def test_convert_with_unkown_mime_yields_none():
    result = shapiro_server.convert('irrelevantPath', 'irrelevantContent', 'fantasymimetype')
    assert result is None
