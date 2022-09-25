# Shapiro

## Model as Code
Model data as knowledge graphs using the JSON-LD syntax and use these models in API definitions/implementations and all other code consuming data based on these models.

Make the use of these machine-readable model definitions pervasive throughout all phases of the software lifecycle (design, implement, test, release) and the lifecycle of the data originating from software built using these models.

Express non-functional requirements like security, traceability/lineage, data quality in the models and bind them to the instances of data wherever the data is distributed to and used.

Drive all documentation (model diagrams, documents, graph visualizations, etc.) from the same JSON-LD model definition (a.k.a. ontology/knowledge graph).

Start out with providing a toolset from developers for developers for formulating such models and using them in source code, gradually extending towards tools, editors, UIs, transformations making this modelling approach accessible to non-technical actors like business analysts, domain data owners, etc.

## What is Shapiro
Shapiro is a simple ontology/schema/model server serving turtle, json-ld or html (as indicated by the requesting client in the accept-header). It therefore provides a simple approach to serve up an organization's ontologies.

## Current State
Shapiro currently only implements the request to get a specific schema in JSON-LD or Turtle (HTML and JSON-SCHEMA to be implemented).

[`shapiro.py`](https://github.com/mathiasrichter/shapiro/blob/main/shapiro-server.py) is a very simple FastAPI implementation reading schemas from a specific location in the filesystem of the server hosting Shapiro (indicated by the value of environment variable SHAPIRO_CONTENT_DIR defaulting to './').

## Installing and running Shapiro
1. Clone the Shapiro repository.
2. Install dependencies: `pip install -r requirements.txt`
3. Set environment variable `SHAPIRO_CONTENT_DIR` to point to the directory hierarchy where your schemas/ontologies sit.
4. Run Shapiro Server: `uvicorn shapiro-server:app`
5. Access the API at `http://localhost:8000`
6. Access the API docs at `http://localhost:8000/docs`
7. Try `curl -X 'GET' 'http://localhost:8000/<SCHEMANAME HERE>' -H 'accept-header: application/ld+json'` to get JSON-LD from a schema in `$SHAPIRO_CONTENT_DIR`
8. Try `curl -X 'GET' 'http://localhost:8000/<SCHEMANAME HERE>' -H 'accept-header: text/turtle'` to get JSON-LD from a schema in `$SHAPIRO_CONTENT_DIR`
