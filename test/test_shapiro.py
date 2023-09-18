from fastapi.testclient import TestClient
import pytest
from time import sleep
import shutil
import shapiro_server
from shapiro_util import BadSchemaException, NotFoundException, prune_iri
from shapiro_model import Subscriptable
from shapiro_render import JsonSchemaRenderer
import subprocess
from datetime import datetime
import os
from jsonschema import validate

###########################################################################################
# for running with an html coverage report :
# pytest --cov=shapiro_render --cov=shapiro_util --cov=shapiro_server  --cov=shapiro_model --cov-report=html
###########################################################################################

shapiro_server.CONTENT_DIR = "./test/ontologies"
shapiro_server.build_base_url("127.0.0.1:8000", False)

shutil.rmtree(
    shapiro_server.INDEX_DIR, ignore_errors=True
)  # remove previous full-text-search indexes

# need a back instance of Shapiro to resolve IRI requests from rdflib during HTML rendering
shapiro_back_instance = subprocess.Popen(
    ["python3", "shapiro_server.py", "--content_dir", "./test/ontologies"]
)

shapiro_server.init()
sleep(
    3
)  # Shapiro's houskeeper threads need a few seconds to do their bit, otherwise some tests will not succeed simply because some data is not ready yet

client = TestClient(
    shapiro_server.app, "http://127.0.0.1:8000"
)  # need to use 127.0.0.1:8000 as base url to ensure tests succeed with test ontologies and test data

client1 = TestClient(
    shapiro_server.app, "http://localhost:8000"
)  # try resolving against localhost instead 127.0.0.1


def test_get_server():
    server = shapiro_server.get_server(
        "127.0.0.1",
        8000,
        "127.0.0.1:8000",
        shapiro_server.CONTENT_DIR,
        "info",
        "text/turtle",
        ["schema.org", "w3.org", "example.org"],
        "./fts_index",
    )
    assert server is not None


def test_get_badschemas():
    response = client.get("/badschemas/")
    assert response.status_code == 200
    assert len(response.json()["badschemas"]) == len(shapiro_server.BAD_SCHEMAS)


def test_get_existing_bad_schemas():
    result = shapiro_server.BAD_SCHEMAS
    assert len(result) == 5
    response = client.get("/bad/person1_with_syntax_error")
    assert response.status_code == 406
    mime = "application/ld+json"
    response = client.get("/bad/person2_with_syntax_error", headers={"accept": mime})
    assert response.status_code == 406


def test_commandline_parse_to_default():
    args = shapiro_server.get_args()
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.domain == "127.0.0.1:8000"
    assert args.content_dir == "./"
    assert args.log_level == "info"
    assert args.default_mime == "text/turtle"
    assert args.features == "all"
    assert args.ignore_namespaces == ["schema.org", "w3.org", "example.org"]
    assert args.index_dir == "./fts_index/"
    assert args.ssl_keyfile is None
    assert args.ssl_certfile is None
    assert args.ssl_ca_certs is None


def test_commandline_parse_to_specified_values():
    args = shapiro_server.get_args(
        [
            "--host",
            "0.0.0.0",
            "--port",
            "1234",
            "--domain",
            "schemas.example.org",
            "--content_dir",
            "./foo",
            "--log_level",
            "bar",
            "--default_mime",
            "foobar",
            "--features",
            "validate",
            "--ignore_namespaces",
            "foo",
            "bar",
            "--index_dir",
            "/tmp",
            "--ssl_keyfile",
            "./certs/key.key",
            "--ssl_certfile",
            "./certs/cert.crt",
            "--ssl_ca_certs",
            "./certs/ca_cert.crt",
        ]
    )
    assert args.host == "0.0.0.0"
    assert args.port == 1234
    assert args.domain == "schemas.example.org"
    assert args.content_dir == "./foo"
    assert args.log_level == "bar"
    assert args.default_mime == "foobar"
    assert args.features == "validate"
    assert args.ignore_namespaces == ["foo", "bar"]
    assert args.index_dir == "/tmp"
    assert args.ssl_keyfile == "./certs/key.key"
    assert args.ssl_certfile == "./certs/cert.crt"
    assert args.ssl_ca_certs == "./certs/ca_cert.crt"


def test_schema_fulltext_search():
    response = client.get("/search/?query=real")
    hits = response.json()
    assert hits["schemas"] is not None
    assert len(hits["schemas"]) == 3
    assert hits["schemas"][0]["schema_path"].startswith("com/example/org/person")
    assert response.status_code == 200
    response = client.get("/search/?query=")
    assert response.status_code == 200
    shutil.rmtree(
        shapiro_server.INDEX_DIR, ignore_errors=True
    )  # remove full-text-search indexes


def test_schema_fultext_search_exception():
    shutil.rmtree(
        shapiro_server.INDEX_DIR, ignore_errors=True
    )  # remove full-text-search indexes so search fails
    response = client.get("/search/?query=real")
    assert response.status_code == 500


def test_get_schema_list():
    response = client.get("/schemas/")
    assert response.status_code == 200


def test_get_static_resources():
    response = client.get("/static/favicon.ico")
    assert response.status_code == 200
    response = client.get("/static/scripts.js")
    assert response.status_code == 200
    response = client.get("/static/styles.css")
    assert response.status_code == 200
    response = client.get("/static/shapiro.png")
    assert response.status_code == 200


def test_shapiro_util():
    with pytest.raises(BadSchemaException):
        raise BadSchemaException()
    with pytest.raises(NotFoundException):
        raise NotFoundException("Test Error")


def test_get_welcome_page():
    response = client.get("/welcome/")
    assert response.status_code == 200

def test_get_version():
    response = client.get("/version/")
    assert response.status_code == 200
    result = response.json()
    assert result['version'] != ''

def test_redirect_to_welcome_page():
    response = client.get("/")
    assert response.status_code == 200


def test_render_model():
    mime_in = "text/html"
    response = client.get("/com/example/org/person", headers={"accept": mime_in})
    assert response.headers["content-type"].startswith(mime_in)
    assert response.status_code == 200


def test_render_model_with_trailing_slash():
    mime_in = "text/html"
    response = client.get("/com/example/org/person/", headers={"accept": mime_in})
    assert response.headers["content-type"].startswith(mime_in)
    assert response.status_code == 200


def test_render_model_with_ontology_url_fragment():
    mime_in = "text/html"
    response = client.get("/com/example/org/person_1", headers={"accept": mime_in})
    assert response.headers["content-type"].startswith(mime_in)
    assert response.status_code == 200


def test_render_model_with_ontology_url_slash():
    mime_in = "text/html"
    response = client.get("/com/example/org/person_2", headers={"accept": mime_in})
    assert response.headers["content-type"].startswith(mime_in)
    assert response.status_code == 200


def test_render_enum_shape():
    mime_in = "text/html"
    response = client.get(
        "/com/example/org/model_for_jsonschema/EnumExampleShape",
        headers={"accept": mime_in},
    )
    assert response.headers["content-type"].startswith(mime_in)
    assert response.status_code == 200


def test_render_class():
    mime_in = "text/html"
    response = client.get("/com/example/org/person/Person", headers={"accept": mime_in})
    assert response.headers["content-type"].startswith(mime_in)
    assert response.status_code == 200


def test_render_owl_class():
    mime_in = "text/html"
    response = client.get(
        "/com/example/org/otherModel/SomeOwlClass", headers={"accept": mime_in}
    )
    assert response.headers["content-type"].startswith(mime_in)
    assert response.status_code == 200


def test_render_instance():
    mime_in = "text/html"
    response = client.get(
        "/com/example/org/otherModel/SomeInstance", headers={"accept": mime_in}
    )
    assert response.headers["content-type"].startswith(mime_in)
    assert response.status_code == 200


def test_render_class_with_instances():
    mime_in = "text/html"
    response = client.get(
        "/com/example/org/person/Nationality", headers={"accept": mime_in}
    )
    assert response.headers["content-type"].startswith(mime_in)
    assert response.status_code == 200


def test_render_instance():
    mime_in = "text/html"
    response = client.get("/com/example/org/person/CH", headers={"accept": mime_in})
    assert response.headers["content-type"].startswith(mime_in)
    assert response.status_code == 200


def test_render_shape():
    mime_in = "text/html"
    response = client.get(
        "/com/example/org/person/PersonShape", headers={"accept": mime_in}
    )
    assert response.headers["content-type"].startswith(mime_in)
    assert response.status_code == 200


def test_render_property():
    mime_in = "text/html"
    response = client.get(
        "/com/example/org/person/PersonName", headers={"accept": mime_in}
    )
    assert response.headers["content-type"].startswith(mime_in)
    assert response.status_code == 200


def test_render_shacl_property():
    mime_in = "text/html"
    response = client.get(
        "/com/example/org/person/PersonNameShape", headers={"accept": mime_in}
    )
    assert response.headers["content-type"].startswith(mime_in)
    assert response.status_code == 200


def test_get_non_existing_schema_jsonld():
    mime_in = "application/ld+json"
    mime_out = "application/json"
    response = client.get(
        "/this_is_a_non_existing_ontology", headers={"accept": mime_in}
    )
    assert response.headers["content-type"].startswith(mime_out)
    assert response.status_code == 404


def test_get_non_existing_schema_ttl():
    mime_in = "text/turtle"
    mime_out = "application/json"
    response = client.get(
        "/this_is_a_non_existing_ontology", headers={"accept": mime_in}
    )
    assert response.headers["content-type"].startswith(mime_out)
    assert response.status_code == 404


def test_get_non_existing_schema_html():
    mime_in = "text/html"
    response = client.get(
        "/this_is_a_non_existing_ontology", headers={"accept": mime_in}
    )
    assert response.headers["content-type"].startswith(mime_in)
    assert response.status_code == 404


def test_get_non_existing_schema_element_html():
    mime_in = "text/html"
    response = client.get("/com/example/org/person/Foo", headers={"accept": mime_in})
    assert response.headers["content-type"].startswith(mime_in)
    assert response.status_code == 404


def test_get_existing_jsonld_schema_as_jsonld():
    mime = "application/ld+json"
    response = client.get("/person_1", headers={"accept": mime})
    assert response.headers["content-type"].startswith(mime)
    assert response.status_code == 200


def test_get_existing_jsonld_schema_as_jsonld_with_multiple_weighted_accept_headers():
    mime_in = "application/ld+json;q=0.9,text/turtle;q=0.8"
    mime_out = "application/ld+json"
    response = client.get("/person_1", headers={"accept": mime_in})
    assert response.headers["content-type"].startswith(mime_out)
    assert response.status_code == 200


def test_get_existing_jsonld_schema_as_ttl():
    mime = "text/turtle"
    response = client.get("/person_1", headers={"accept": mime})
    assert response.headers["content-type"].startswith(mime)
    assert response.status_code == 200


def test_get_existing_jsonld_schema_as_ttl_with_long_accept_header():
    mime_in = (
        "application/rdf+xml,application/ld+json;q=1,text/turtle;v=b3;q=0.5,text/html"
    )
    response = client.get("/person_1", headers={"accept": mime_in})
    assert response.headers["content-type"].startswith("application/ld+json")
    assert response.status_code == 200


def test_get_existing_jsonld_schema_as_ttl_with_long_accept_header_lower_q():
    mime_in = "application/rdf+xml,application/ld+json;q=0.5,text/turtle;v=b3;q=0.8,text/html;q=0.9"
    response = client.get("/com/example/org/person", headers={"accept": mime_in})
    assert response.headers["content-type"].startswith("text/html")
    assert response.status_code == 200


def test_get_existing_ttl_schema_deep_down_in_the_hierarchy_as_jsonld():
    mime = "application/ld+json"
    response = client.get("/com/example/org/person", headers={"accept": mime})
    assert response.headers["content-type"].startswith(mime)
    assert response.status_code == 200


def test_get_existing_ttl_schema_deep_down_in_the_hierarchy_as_jsonld_ignoring_element_reference_with_os_path_sep():
    mime = "application/ld+json"
    response = client.get("/com/example/org/person/firstname", headers={"accept": mime})
    assert response.headers["content-type"].startswith(mime)
    assert response.status_code == 200


def test_get_existing_ttl_schema_deep_down_in_the_hierarchy_as_jsonld_ignoring_element_reference_with_anchor():
    mime = "application/ld+json"
    response = client.get("/com/example/org/person#firstname", headers={"accept": mime})
    assert response.headers["content-type"].startswith(mime)
    assert response.status_code == 200


def test_get_existing_ttl_schema_deep_down_in_the_hierarchy_as_ttl():
    mime = "text/turtle"
    response = client.get("/com/example/org/person", headers={"accept": mime})
    assert response.headers["content-type"].startswith(mime)
    assert response.status_code == 200


def test_get_existing_jsonld_schema_as_default_without_accept_header():
    mime = ""
    response = client.get("/person_1", headers={"accept": mime})
    assert response.headers["content-type"].startswith(shapiro_server.MIME_DEFAULT)
    assert response.status_code == 200


def test_get_existing_ttl_schema_as_default_without_accept_header():
    mime = ""
    response = client.get("/com/example/org/person", headers={"accept": mime})
    assert response.headers["content-type"].startswith(shapiro_server.MIME_DEFAULT)
    assert response.status_code == 200


def test_get_existing_schema_with_duplicates():
    response = client.get("/dupes/person")
    assert response.status_code == 404


def test_get_query_ui():
    response = client.get("/query/")
    assert response.status_code == 200


def test_correct_sparql_query():
    response = client.post(
        "/query/",
        content="""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?instance ?type
            WHERE
            {
                ?instance rdf:type ?type .
            }
        """,
    )
    assert response.headers["content-type"].startswith("application/json")
    assert response.status_code == 200
    assert len(response.json()) > 2  # must not be empty, ie. []""


def test_incorrect_sparql_query():
    response = client.post(
        "/query/",
        content="""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#
            SELECT DISTINCT ?instance
            WHERE
                ?instance rdf:type rdfs:Property 
            }
        """,
    )
    assert response.status_code == 406


def test_get_existing_schema_with_uncovered_mime_type():
    mime = "text/text"
    response = client.get("/com/example/org/person", headers={"accept": mime})
    assert response.headers["content-type"].startswith(shapiro_server.MIME_DEFAULT)
    assert response.status_code == 200


def test_get_existing_bad_schema_with_html_mime_type():
    mime = "text/html"
    response = client.get("/person", headers={"accept": mime})
    assert response.headers["content-type"].startswith(mime)
    assert response.status_code == 406


def test_convert_with_unkown_mime_yields_none():
    result = shapiro_server.convert(
        "irrelevant path", "irrelevantFilename", "irrelevantContent", "fantasymimetype"
    )
    assert result is None


def test_get_existing_nodeshape_as_json_schema():
    mime = "application/schema+json"
    response = client.get(
        "/com/example/org/person/PersonShape", headers={"accept": mime}
    )
    response.json()  # ensure JSON-SCHEMA generated is proper JSON
    assert response.headers["content-type"].startswith(mime)
    assert response.status_code == 200


def test_enums_with_json_schema():
    mime = "application/schema+json"
    response = client.get(
        "/com/example/org/model_for_jsonschema/EnumExampleShape",
        headers={"accept": mime},
    )
    response.json()  # ensure JSON-SCHEMA generated is proper JSON
    assert response.headers["content-type"].startswith(mime)
    assert response.status_code == 200


def test_get_existing_nodeshape_with_inheritance_conflict_as_json_schema():
    mime = "application/schema+json"
    response = client.get(
        "/com/example/org/multiple_nodeshapes_inherit_conflict/CShape",
        headers={"accept": mime},
    )
    assert response.status_code == 422


def test_get_existing_nodeshape_with_inheritance_as_json_schema():
    mime = "application/schema+json"
    response = client.get(
        "/com/example/org/nodeshapes_inheritance/CShape", headers={"accept": mime}
    )
    result = response.json()  # ensure JSON-SCHEMA generated is proper JSON
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(mime)
    assert len(result["required"]) == 4
    assert (
        "P1" in result["required"]
        and "P2" in result["required"]
        and "P3" in result["required"]
        and "P4" in result["required"]
    )
    assert len(result["properties"]) == 4
    assert (
        "P1" in result["properties"].keys()
        and "P2" in result["properties"].keys()
        and "P3" in result["properties"].keys()
        and "P4" in result["properties"].keys()
    )


def test_get_non_nodeshape_as_json_schema():
    mime = "application/schema+json"
    response = client.get("/com/example/org/person/Person", headers={"accept": mime})
    response.json()  # ensure JSON-SCHEMA generated is proper JSON
    assert response.headers["content-type"].startswith(mime)
    assert response.status_code == 200


def test_complex_model_as_json_schema():
    mime = "application/schema+json"
    response = client.get(
        "/com/example/org/model_for_jsonschema/SimplePersonShape",
        headers={"accept": mime},
    )
    assert response.headers["content-type"].startswith(mime)
    assert response.status_code == 200
    schema = response.json()  # ensure JSON-SCHEMA generated is proper JSON
    data = {
        "Name": ["MATHIAS"],
        "Age": 97,
        "SchemaName": ["Mathias Richter"],
        "primaryAddress": {"street": "1 Recursion Drive", "city": "Coderville"},
        "otherAddress": [
            {"street": "5 Left Join Street", "city": "Data City"},
            {"street": "2 Coverage Boulevard", "city": "Test Town"},
        ],
    }
    validate(data, schema)  # ensure data validates against schema


def test_validate_with_compliant_jsonld_data():
    with open("./test/data/person2_data_valid.jsonld") as data_file:
        response = client.post(
            "/validate/com/example/org/person",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_JSONLD},
        )
        assert response.headers["content-type"].startswith(shapiro_server.MIME_JSONLD)
        assert response.status_code == 200
        report = response.json()
        assert report[0]["http://www.w3.org/ns/shacl#conforms"][0]["@value"] == True


def test_validate_with_uncompliant_jsonld_data():
    with open("./test/data/person2_data_invalid.jsonld") as data_file:
        response = client.post(
            "/validate/com/example/org/person",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_JSONLD},
        )
        assert response.headers["content-type"].startswith(shapiro_server.MIME_JSONLD)
        assert response.status_code == 200
        report = response.json()
        assert report[0]["http://www.w3.org/ns/shacl#conforms"][0]["@value"] == False


def test_validate_with_compliant_jsonld_list_data():
    with open("./test/data/person_list1_data_valid.jsonld") as data_file:
        response = client.post(
            "/validate/com/example/org/person",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_JSONLD},
        )
        assert response.headers["content-type"].startswith(shapiro_server.MIME_JSONLD)
        assert response.status_code == 200
        report = response.json()
        assert report[0]["http://www.w3.org/ns/shacl#conforms"][0]["@value"] == True


def test_validate_with_uncompliant_jsonld_list_data():
    with open("./test/data/person_list1_data_invalid.jsonld") as data_file:
        response = client.post(
            "/validate/com/example/org/person",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_JSONLD},
        )
        assert response.headers["content-type"].startswith(shapiro_server.MIME_JSONLD)
        assert response.status_code == 200
        report = response.json()
        assert report[0]["http://www.w3.org/ns/shacl#conforms"][0]["@value"] == False


def test_validate_with_compliant_ttl_data():
    with open("./test/data/person1_data_valid.ttl") as data_file:
        response = client.post(
            "/validate/com/example/org/person",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_TTL},
        )
        assert response.headers["content-type"].startswith(shapiro_server.MIME_JSONLD)
        assert response.status_code == 200
        report = response.json()
        assert report[0]["http://www.w3.org/ns/shacl#conforms"][0]["@value"] == True


def test_validate_with_uncompliant_ttl_data():
    with open("./test/data/person1_data_invalid.ttl") as data_file:
        response = client.post(
            "/validate/com/example/org/person",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_TTL},
        )
        assert response.headers["content-type"].startswith(shapiro_server.MIME_JSONLD)
        assert response.status_code == 200
        report = response.json()
        assert report[0]["http://www.w3.org/ns/shacl#conforms"][0]["@value"] == False


def test_validate_with_compliant_ttl_list_data():
    with open("./test/data/person_list2_data_valid.ttl") as data_file:
        response = client.post(
            "/validate/com/example/org/person",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_TTL},
        )
        assert response.headers["content-type"].startswith(shapiro_server.MIME_JSONLD)
        assert response.status_code == 200
        report = response.json()
        assert report[0]["http://www.w3.org/ns/shacl#conforms"][0]["@value"] == True


def test_validate_with_uncompliant_ttl_list_data():
    with open("./test/data/person_list2_data_invalid.ttl") as data_file:
        response = client.post(
            "/validate/com/example/org/person",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_TTL},
        )
        assert response.headers["content-type"].startswith(shapiro_server.MIME_JSONLD)
        assert response.status_code == 200
        report = response.json()
        assert report[0]["http://www.w3.org/ns/shacl#conforms"][0]["@value"] == False


def test_validate_with_syntax_error_ttl_data():
    with open("./test/data/person1_data_syntax_error.ttl") as data_file:
        response = client.post(
            "/validate/com/example/org/person",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_TTL},
        )
        assert response.status_code == 422


def test_validate_with_syntax_error_jsonld_data():
    with open("./test/data/person2_data_syntax_error.jsonld") as data_file:
        response = client.post(
            "/validate/com/example/org/person",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_JSONLD},
        )
        assert response.status_code == 422


def test_validate_with_unsupported_data_content_type():
    response = client.post(
        "/validate/com/example/org/person",
        content="irrelevant",
        headers={"content-type": "text/text"},
    )
    assert response.status_code == 415


def test_validate_with_remote_schema_that_cannot_be_found():
    with open("./test/data/person2_data_valid.jsonld") as data_file:
        response = client.post(
            "/validate/schema.org/person",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_JSONLD},
        )
        assert response.status_code == 422


def test_validate_with_local_schema_that_cannot_be_found():
    with open("./test/data/person2_data_valid.jsonld") as data_file:
        response = client.post(
            "/validate/foo",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_JSONLD},
        )
        assert response.status_code == 422


def test_validate_with_remote_schema():
    with open("./test/data/person2_data_valid.jsonld") as data_file:
        response = client.post(
            "/validate/www.w3.org/2000/01/rdf-schema",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_JSONLD},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(shapiro_server.MIME_JSONLD)
        report = response.json()
        assert report[0]["http://www.w3.org/ns/shacl#conforms"][0]["@value"] == True


def test_features_switching_only_serve():
    shapiro_server.activate_routes("serve")
    response = client.get("/person_1")
    assert response.status_code == 200
    response = client.post(
        "/validate/com/example/org/person",
        content="irrelevant content",
        headers={"content-type": shapiro_server.MIME_TTL},
    )
    # with the validate route disabled, the request will land with the get_schema route and therefore return a 405 (and not a 404)
    assert response.status_code == 405


def test_features_switching_only_validate():
    shapiro_server.activate_routes("validate")
    response = client.get("/person_1")
    assert response.status_code == 404
    with open("./test/data/person2_data_invalid.jsonld") as data_file:
        response = client.post(
            "/validate/com/example/org/person",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_JSONLD},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(shapiro_server.MIME_JSONLD)
        report = response.json()
        assert report[0]["http://www.w3.org/ns/shacl#conforms"][0]["@value"] == False


def test_validate_with_inference_with_compliant_jsonld_data():
    with open("./test/data/person2_data_valid.jsonld") as data_file:
        response = client.post(
            "/validate/",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_JSONLD},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(shapiro_server.MIME_JSONLD)
        report = response.json()
        assert report[0]["http://www.w3.org/ns/shacl#conforms"][0]["@value"] == True


def test_validate_with_inference_with_uncompliant_jsonld_data():
    with open("./test/data/person2_data_invalid.jsonld") as data_file:
        response = client.post(
            "/validate/",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_JSONLD},
        )
        assert response.headers["content-type"].startswith(shapiro_server.MIME_JSONLD)
        assert response.status_code == 200
        report = response.json()
        assert report[0]["http://www.w3.org/ns/shacl#conforms"][0]["@value"] == False


def test_validate_with_inference_with_compliant_jsonld_list_data():
    with open("./test/data/person_list1_data_valid.jsonld") as data_file:
        response = client.post(
            "/validate/",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_JSONLD},
        )
        assert response.headers["content-type"].startswith(shapiro_server.MIME_JSONLD)
        assert response.status_code == 200
        report = response.json()
        assert report[0]["http://www.w3.org/ns/shacl#conforms"][0]["@value"] == True


def test_validate_with_inference_with_uncompliant_jsonld_list_data():
    with open("./test/data/person_list1_data_invalid.jsonld") as data_file:
        response = client.post(
            "/validate/",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_JSONLD},
        )
        assert response.headers["content-type"].startswith(shapiro_server.MIME_JSONLD)
        assert response.status_code == 200
        report = response.json()
        assert report[0]["http://www.w3.org/ns/shacl#conforms"][0]["@value"] == False


def test_validate_with_inference_with_compliant_ttl_data():
    with open("./test/data/person1_data_valid.ttl") as data_file:
        response = client.post(
            "/validate/",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_TTL},
        )
        assert response.headers["content-type"].startswith(shapiro_server.MIME_JSONLD)
        assert response.status_code == 200
        report = response.json()
        assert report[0]["http://www.w3.org/ns/shacl#conforms"][0]["@value"] == True


def test_validate_with_inference_with_uncompliant_ttl_data():
    with open("./test/data/person1_data_invalid.ttl") as data_file:
        response = client.post(
            "/validate/",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_TTL},
        )
        assert response.headers["content-type"].startswith(shapiro_server.MIME_JSONLD)
        assert response.status_code == 200
        report = response.json()
        assert report[0]["http://www.w3.org/ns/shacl#conforms"][0]["@value"] == False


def test_validate_with_inference_with_compliant_ttl_list_data():
    with open("./test/data/person_list2_data_valid.ttl") as data_file:
        response = client.post(
            "/validate/",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_TTL},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(shapiro_server.MIME_JSONLD)
        report = response.json()
        assert report[0]["http://www.w3.org/ns/shacl#conforms"][0]["@value"] == True


def test_validate_with_inference_with_uncompliant_ttl_list_data():
    with open("./test/data/person_list2_data_invalid.ttl") as data_file:
        response = client.post(
            "/validate/",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_TTL},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(shapiro_server.MIME_JSONLD)
        report = response.json()
        assert report[0]["http://www.w3.org/ns/shacl#conforms"][0]["@value"] == False


def test_validate_with_inference_with_syntax_error_ttl_data():
    with open("./test/data/person1_data_syntax_error.ttl") as data_file:
        response = client.post(
            "/validate/",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_TTL},
        )
        assert response.status_code == 422


def test_validate_with_inference_with_syntax_error_jsonld_data():
    with open("./test/data/person2_data_syntax_error.jsonld") as data_file:
        response = client.post(
            "/validate/",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_JSONLD},
        )
        assert response.status_code == 422


def test_validate_with_inference_with_unsupported_data_content_type():
    response = client.post(
        "/validate/", content="irrelevant", headers={"content-type": "text/text"}
    )
    assert response.status_code == 415


def test_validate_with_localhost_with_compliant_ttl_list_data():
    with open("./test/data/person_list2_data_valid.ttl") as data_file:
        response = client1.post(
            "/validate/com/example/org/person",
            content=data_file.read(),
            headers={"content-type": shapiro_server.MIME_TTL},
        )
        assert response.headers["content-type"].startswith(shapiro_server.MIME_JSONLD)
        assert response.status_code == 200
        report = response.json()
        assert report[0]["http://www.w3.org/ns/shacl#conforms"][0]["@value"] == True


def test_get_ranked_mime_types_with_none():
    result = shapiro_server.get_ranked_mime_types(None)
    assert result == [""]


def test_prune():
    p = prune_iri("/a/b/c/")
    assert p == "C"


def test_subscriptable():
    s = Subscriptable()
    with pytest.raises(Exception):
        s["non_existing_key"]


def test_schema_housekeeping():
    s = shapiro_server.SchemaHousekeeping(10)
    s.perform_housekeeping_on([])


def test_search_housekeeping_unsuccessful():
    shapiro_server.SearchIndexHousekeeping(index_dir="./")


def test_ekg_housekeeping_unsuccessful():
    e = shapiro_server.EKGHouseKeeping()
    e.add_schema("invalidpath", "invalidname", "invalidschemapath", "invalidsuffix")


def test_bad_schema_housekeeping():
    try:
        b = shapiro_server.BadSchemaHousekeeping()
        b.last_execution_time = datetime.now()
        sleep(3)  # give it a few seconds
        schema_file_name = "./test/ontologies/test_bad_schema.ttl"
        # syntax error - missing a '.' at the end
        bad_schema = """
            @prefix : <http://127.0.0.1:8000/test_bad_schema/> .
            @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
            :Person a rdfs:Class
        """
        assert schema_file_name not in shapiro_server.BAD_SCHEMAS.keys()
        with open(schema_file_name, "w") as f:
            f.write(bad_schema)
        b.perform_housekeeping_on([schema_file_name])
        assert schema_file_name in shapiro_server.BAD_SCHEMAS.keys()
        os.remove(schema_file_name)
        # same as bad, but with syntax error corrected
        good_schema = """
            @prefix : <http://127.0.0.1:8000/test_bad_schema/> .
            @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
            :Person a rdfs:Class.
        """
        with open(schema_file_name, "w") as f:
            f.write(good_schema)
        b.last_execution_time = datetime.now()
        sleep(3)  # give it a few seconds
        b.perform_housekeeping_on([schema_file_name])
        assert schema_file_name not in shapiro_server.BAD_SCHEMAS.keys()
    finally:
        os.remove(schema_file_name)


def test_build_base_url():
    shapiro_server.build_base_url("myHost", True)
    assert shapiro_server.BASE_URL == "https://myHost/"
    shapiro_server.build_base_url("myHost", False)
    assert shapiro_server.BASE_URL == "http://myHost/"
    shapiro_server.build_base_url("myHost:1234/", True)
    assert shapiro_server.BASE_URL == "https://myHost:1234/"


# ensure this executes second to last
def test_teardown():
    shapiro_server.shutdown()
    shapiro_back_instance.terminate()
    shutil.rmtree(
        shapiro_server.INDEX_DIR, ignore_errors=True
    )  # clean up full-text-search indexes


# ensure this executes last
def test_shapiro_main():
    shapiro_server.main([])
    shapiro_server.shutdown()
    subprocess.run(["python3", "shapiro_server.py", "--help"])
