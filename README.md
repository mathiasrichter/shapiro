# Shapiro

## Model as Code
Model data as knowledge graphs using the JSON-LD syntax and use these models in API definitions/implementations and all other code consuming data based on these models.

Make the use of these machine-readable model definitions pervasive throughout all phases of the software lifecycle (design, implement, test, release) and the lifecycle of the data originating from software built using these models.

Express non-functional requirements like security, traceability/lineage, data quality in the models and bind them to the instances of data wherever the data is distributed to and used.

Drive all documentation (model diagrams, documents, graph visualizations, etc.) from the same JSON-LD model definition (a.k.a. ontology/knowledge graph).

Start out with providing a toolset from developers for developers for formulating such models and using them in source code, gradually extending towards tools, editors, UIs, transformations making this modelling approach accessible to non-technical actors like business analysts, domain data owners, etc.

## What is Shapiro
Shapiro in its essence should eventually grow into an API for JSON-LD schema repositories to support the above approach. In my mind, such a schema repository should offer the following capabilities:

- **Serve up JSON-LD schemas**: acting as the target for all URI/IRI contained in schemas representing models for a specific domain (e.g. an organization wanting to put all of their proprietary schemas in one place).
- **Search, browse and visualize schemas**: support navigating the ontologies & the knowledge graph arising from the set of JSON-LD schemas stored in the repository.
- **Add, remove and change schemas**: support creating new schemas and changing existing schemas, thereby amending the ontology & the knowledge graph.
- **Author data models in Python**: The Shapiro modeller allows to express models in plain Python with the Shaprio generator producing JSON-LD including SHACL validations to be served up by the Shapiro repository.

Such a repository will allow anyone putting their models in one place, support the process of actually using the models or mine the knowledge graph in code by way of IRIs pointing to the schema repository. Furthermore, such a repository allows UI tools to offer browsing, visualizing and editing of the knowledge graph for non-technical users.

## Shapiro Modeller
The [`modeller`](https://github.com/mathiasrichter/shapiro/blob/main/modeller.py) provides a small DSL to express models with entities, their properties and relationships (including inheritance) in plain Python. The modeller produces a in-memory model (which is a [networkx MultiDiGraph](https://networkx.org) that is traversed by the [`generator`](https://github.com/mathiasrichter/shapiro/blob/main/generator.py) to generate standardized JSON-LD including SHACL validations that will subsequently be served up by the repository.
The DSL offered by the modeller is an oppinionated view on how to model - aiming at keeping the modelling principles as simple as possible so as to engage as many stakeholders as possible into formulating centralized data models as code:

- **Entity Relationship Modelling** The basic principle is to use basic ER-modelling. This is a modelling approach that has been used in the industry for decades and that many people can relate to. A model consists of entities which have properties and can be in different kinds of relationships to each other. This does not imply that the implementation of any model must be in a specific database paradigm (e.g. relational databases).
- **Properties are first-class citizens** As opposed to "classical" ER-modelling, properties and their constraints are modelled as first-class citiziens next to entities. That means that means that properties and their constraints regarding type and values (ranges, min/max values, length, mandatory, etc.) become reusable across multiple entities. This helps to retain consistency of concepts represented by properties across multiple entities.
- **Relationships between Entities** Relationships between entities must have a cardinality, otherwise they are like any relationships between entities in any datamodel.
- **Inheritance** Entities can be part of inheritance hierarchies. There can be three different flavors of inheritance. The simplest one is just building up a taxonomy, ie. the subentity does not inherit any property or relationship from its superentity. Alternatively, a subentity can inherit all properties and all relationships from its superentity. The third flavor allows to selectively inherit properties and/or relationships from a superentity to the subentity.

I will have to create a few examples and show what JSON-LD and SHACL they generate.

## Current State
This is extremely experimental while I am trying to get my head around how to achieve the above using JSON-LD. [`shapiro-openapi.json`](https://github.com/mathiasrichter/shapiro/blob/main/shapiro-openapi.json) is a first attempt to specify the API for JSON-LD schema repositories - currently defining the following operations:

- list schemas in the repository
- get a schema stored in the repository by its IRI
- get an element of a schema in the repository by its IRI
- add a schema with a specific name or update the schema under that name (without validation yet as I cannot seem to find a JSON-LD validator)
- the modeller is work in progress: you can express a model in plain Python and a first version of 

[`shapiro.py`](https://github.com/mathiasrichter/shapiro/blob/main/shapiro-server.py) is a very tactical FastAPI implementation of these operations reading schemas from a specific location in the filesystem of the server hosting Shapiro (current code just uses '.').

[`shapiro-ui.py`](https://github.com/mathiasrichter/shapiro/blob/main/shapiro-ui.py) is a UI based on [Streamlit](https://streamlit.io/).

## Installing and running Shapiro & Shapiro UI
1. Clone the Shapiro repository.
2. Install dependencies: `pip install -r requirements.txt`
3. Run Shapiro Server: `uvicorn shapiro-server:app`
4. Access the API at `http://localhost:8000`
5. Run the Shapiro UI: `streamlit shapiro-ui.py`
6. Browse & edit schemas via UI.
