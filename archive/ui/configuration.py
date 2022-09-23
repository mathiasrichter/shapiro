import json

class Configuration:

    SERVER = "SERVER"
    SERVER_VALUE = 'http://localhost:8000/'

    ONTOLOGIES = "ONTOLOGIES"
    ONTOLOGIES_VALUE =    [
                        "https://brickschema.org/schema/Brick#",
                        "http://www.w3.org/ns/csvw#",
                        "http://purl.org/dc/elements/1.1/",
                        "http://purl.org/dc/dcam/",
                        "http://www.w3.org/ns/dcat#",
                        "http://purl.org/dc/dcmitype/",
                        "http://purl.org/dc/terms/",
                        "http://usefulinc.com/ns/doap#",
                        "http://xmlns.com/foaf/0.1/",
                        "http://www.w3.org/ns/odrl/2/",
                        "http://www.w3.org/ns/org#",
                        "http://www.w3.org/2002/07/owl#",
                        "http://www.w3.org/ns/dx/prof/",
                        "http://www.w3.org/ns/prov#",
                        "http://purl.org/linked-data/cube#",
                        "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                        "http://www.w3.org/2000/01/rdf-schema#",
                        "https://schema.org/",
                        "http://www.w3.org/ns/shacl#",
                        "http://www.w3.org/2004/02/skos/core#",
                        "http://www.w3.org/ns/sosa/",
                        "http://www.w3.org/ns/ssn/",
                        "http://www.w3.org/2006/time#",
                        "http://purl.org/vocab/vann/",
                        "http://rdfs.org/ns/void#",
                        "http://www.w3.org/2001/XMLSchema#"
                    ]

    def __init__(self, json = None):
        self.data = {}
        if json is None:
            self.buildDefault()
        else:
            self.data = json.loads(json)

    def get(self, key):
        return self.data[key]

    def set(self, key, value):
        self.data[key] = value

    def getServer(self):
        return self.get(self.SERVER)

    def setServer(self, value):
        self.set(self.SERVER, value)

    def getOntologies(self):
        return self.get(self.ONTOLOGIES)

    def setOntologies(self, value):
        self.set(self.ONTOLOGIES, value)

    def addOntology(self, link):
        self.getOntologies().append(link)

    def removeOntology(self, link):
        self.getOntologies().remove(link)

    def buildDefault(self):
        self.setServer(self.SERVER_VALUE)
        self.setOntologies(self.ONTOLOGIES_VALUE)
