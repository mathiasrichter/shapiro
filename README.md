# Shapiro

## Model as Code
Model data as knowledge graphs using the JSON-LD syntax and use these models in API definitions/implementations and all other code consuming data based on these models.

Make the use of these machine-readable model definitions pervasive throughout all phases of the software lifecycle (design, implement, test, release) and the lifecycle of the data originating from software built using these models.

Express non-functional requirements like security, traceability/lineage, data quality in the models and bind them to the instances of data wherever the data is distributed to and used.

Drive all documentation (model diagrams, documents, graph visualizations, etc.) from the same JSON-LD model definition (a.k.a. ontology/knowledge graph).

Start out with providing a toolset from developers for developers for formulating such models and using them in source code, gradually extending towards tools, editors, UIs, transformations making this modelling approach accessible to non-technical actors like business analysts, domain data owners, etc.

## What is Shapiro
Shapiro is a simple ontology/schema/model server serving turtle, json-ld or html (as indicated by the requesting client in the accept-header). It therefore provides a simple approach to serving up an organization's ontologies.

## Serving Schemas
Shapiro serves schemas from a directory hierarchy in the file system (specifiec by the `content_dir`parameter at startup). Shapiro will regularly check new o modified schemas for syntax errors and exclude such "bad schemas" from getting served. Schemas can be moved into Shapiro's content_dir while it is running. This decouples the lifecycle for schemas from the lifecycle of Shapiro - the basic idea being that the lifecycle of schemas is managed in some code repository where changes get pushed into Shapiro's content directory without Shapiro having to be restarted.

## Hierarchical Namespaces
Shapiro allows you to keep schemas/ontologies in arbitrary namespace hierarchies - simply by reflecting namespaces as a directory hierarchy. This allows organizations to separate their schemas/ontologies across a hierarchical namespace and avoid any clashes. This also means you can have a more realxed governance around the various ontologies/schemas across a collaborating community. The assumption is that you manage your schemas/ontologies in a code repository (Github, etc.) and manage releases form there onto a Shapiro instance serving these schemas in a specific environment (dev/test/prod).

## Validation with Shapiro
Validation is a bit more involved, in particular since Shapiro allows you to enable/disable API features (serving schemas and validating data against schemas).
If both serving schemas and validation are activated, you can validate against schemas residing on the same Shapiro instance offering the validation:

`http://localhost:8000/validate/org/example/myschemas/person`

Posting against this url (with a request body containing the data to be validated), will get the schema named `org/example/myschemas/person` from `localhost:8000` to validate the data against. Obviously, this will not work if you've switched off the 'serve' feature on `localhost:8000`.

Assume you want to validate your data against a schema sitting on a different schema server, you can do:

`http://localhost:8000/validate/www.w3.org/ms/shacl/something`

This would validate the data provided in the body of the post request against the schema served at `http://wwww3.org/ms/shacl` under the name of `something`.

Assume you want to use one instance of Shapiro to just serve schemas, and another instance of Shapiro to just validate schemas. Assume the instance serving schemas sits under `localhost:8000` and the instance just validating schemas sits under `localhost:3333`. You would run your post request against the following URL:

`http://localhost:3333/validate/localhost:8000/org/example/myschemas/person`

This would look for the schema names `org/example/myschemas/person`on `localhost:8000` (the instance that just serves schemas) and validate the schema obtained from there in `localhost:8000` against the data provided in the body of the request.

You don't need to specify an explicit schema to validate data against. If you specify no schema, Shapiro will infer the schemas to validate the data against using the prefix IRIs defined from the prefixes used in the data graph. The algorithm uses a configurable list of namespaces to ignore when infering the schemas - this list can be set using the command line parameter `--ignore_namespaces`and defaults to `['schema.org', 'w3.org', 'example.org']`. This means that prefixes pointing to these namespaces are assumed never to contain SHACL constraints to validate a given data graph against.

## Searching Shapiro
Shapiro uses Whoosh Full-text-search to index all schemas it serves. Shapiro regularly checks for modified or new schemas in its content directory and indexes them.

## Shapiro UI
Shapiro provides a minimal UI available at `/welcome/`. Any `GET`request to `/` without a schema name to retrieve will also redirect to the UI. The ui lists all schemas served by Shapiro at a given point in time and allows to full-text-search schema content.

## Installing and running Shapiro
1. Clone the Shapiro repository.
2. Install dependencies: `pip install -r requirements.txt`
4. Run Shapiro Server: `python shapiro_server.py` with optional commandline paramaters `--host`(default 127.0.0.1) `--port`(default 8000), `--content_dir`(default `./`) and `--log_level`(default `info`), `--features` (default `all`), `--ignore_namespaces` (default `['schema.org', 'w3.org', 'example.org']`).
5. Access the UI at `http://localhost:8000/welcome/`
6. Access the API docs at `http://localhost:8000/docs`
7. Try `curl -X 'GET' 'http://localhost:8000/<SCHEMANAME HERE>' -H 'accept-header: application/ld+json'` to get JSON-LD from a schema in the content dir
8. Try `curl -X 'GET' 'http://localhost:8000/<SCHEMANAME HERE>' -H 'accept-header: text/turtle'` to get JSON-LD from a schema in the content dir.

Make sure you run `python shapiro_server.py --help`for a full reference of command line parameters (host, port, content dir, log level, default mime type, features, ignore namespaces, index directory).
