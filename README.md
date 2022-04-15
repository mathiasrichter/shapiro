# Shapiro

## Model as Code
Model data as knowledge graphs using the JSON-LD syntax and use these models in API definitions/implementations and all other code consuming data based on these models.

Make the use of these machine-readable model definitions pervasive throughout all phases of the software lifecycle (design, implement, test, release) and the lifecycle of the data originating from software built using these models.

Express non-functional requirements like security, traceability/lineage, data quality in the models and bind them to the instances of data wherever the data is distributed to and used.

Drive all documentation (model diagrams, documents, graph visualizations, etc.) from the same JSON-LD model definition (a.k.a. ontology/knowledge graph).

Start out with providing a toolset from developers for developers for formulating such models and using them in source code, gradually extending towards tools, editors, UIs, transformations making this modelling approach accessible to non-technnical actors like business analysts, domain data owners, etc.

## What is Shapiro
Shapiro in its essence should eventually grow into an API for JSON-LD schema repositories to support the above approach. In my mind, such a schema repository should offer the following capabilities:

- **Serve up JSON-LD schemas**: acting as the target for all URI/IRI contained in schemas representing models for a specific domain (e.g. an organization wanting to put all of their proprietary schemas in one place).
- **Search, browse and visualize schemas**: support navigating the ontologies & the knowledge graph arising from the set of JSON-LD schemas stored in the repository.
- **Add, remove and change schemas**: support creating new schemas and changing existing schemas, thereby amending the ontology & the knowledge graph.

Such a repository will allow anyone putting their models in one place, support the process of actually using the models or mine the knowledge graph in code by way of IRIs pointing to the schema repository. Furthermore, such a repository allows UI tools to offer browsing, visualizing and editing of the knowledge graph for non-technical users.

## Current State
This is extremely experimental while I am trying to get my head around how to achieve the above using JSON-LD. [`shapiro-openapi.yml`](https://github.com/mathiasrichter/shapiro/blob/main/shapiro-openapi.yml) is a first attempt to specify the API for JSON-LD schema repositories - currently defining the following operations:

- list schemas in the repository
- get a schema stored in the repository by its IRI
- get an element of a schema in the repository by its IRI
- add a schema with a specific name or update the schema under that name (without validation yet as I cannot seem to find a JSON-LD validator)

[`shapiro.py`](https://github.com/mathiasrichter/shapiro/blob/main/shapiro.py) is a very tactical FastAPI implementation of these operations reading schemas from a specific location in the filesystem of the server hosting Shapiro (current code just uses '.').

## Installing and running Shapiro
1. Clone the Shapiro repository.
2. Install FastAPI: `pip install fastapi`
3. Run Shapiro: `uvicorn shapiro:app`
4. Access the API at `http://localhost:8000`
