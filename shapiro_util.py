from urllib.parse import urlparse

class BadSchemaException(Exception):

    def __init__(self):
        super().__init__()

class NotFoundException(Exception):

    def __init__(self, content:str):
        self.content = content

def prefix(iri:str, name:str) -> str:
    known = {
        'http://www.w3.org/2000/01/rdf-schema#': 'rdfs:',
        'http://www.w3.org/2004/02/skos/core#': 'skos:',
        'http://purl.org/dc/terms/': 'dct:' ,
        'http://www.w3.org/2002/07/owl#': 'owl:',
        'http://www.w3.org/ns/shacl#': 'shacl:',
        'http://www.w3.org/1999/02/22-rdf-syntax-ns#': 'rdf:',
        'http://schema.org': 'schema:',
        'http://www.w3.org/ns/adms#': 'adms:',
        'http://www.w3.org/2001/XMLSchema#': 'xsd:',
        'http://http://xmlns.com/foaf/0.1/': 'foaf:',
        'http://dbpedia.org/resource/': 'dbpedia:',
        'http://www.w3.org/ns/odrl1/2/': 'odrl:',
        'http://www.w3.org/ns/org#': 'org:',    
        'http://www.w3.org/2006/time#': 'time:',
        'http://www.w3.org/TR/vocab-dcat-2/#': 'dcat:',
        'http://purl.org/adms/status/': 'adms:'
    }
    for k in known.keys():
        if iri.lower().startswith(k.lower()):
            return known[k] + name
    return name

def prune_iri(iri:str, name_only:bool = False) -> str:
    url = urlparse(iri)
    result = url.path
    if result.startswith('/'):
        result = result[1:len(result)]
    if (url.fragment == '' or url.fragment is None): 
        if result.endswith('/'):
            result = result[0:len(result)-1]
        result = result[result.rfind('/')+1:len(result)]
    else:
        result = url.fragment
    if name_only is False:
        result = prefix(iri, result)
    if result.__contains__(':'):
        return result
    else:
        return result[0].upper() + result[1:len(result)]
    
