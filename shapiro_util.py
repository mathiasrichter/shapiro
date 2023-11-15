from urllib.parse import urlparse
import colorlog
import logging

handler = colorlog.StreamHandler()
handler.setFormatter(
    colorlog.ColoredFormatter(
        "%(asctime)s  %(log_color)s%(levelname)-8s  %(name)-14s  %(reset)s%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
)


def get_logger(name: str):
    logger = colorlog.getLogger(name)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


class BadSchemaException(Exception):
    def __init__(self):
        super().__init__()


class NotFoundException(Exception):
    def __init__(self, content: str):
        self.content = content

class ConflictingPropertyException(Exception):
    def __init__(self, content: str):
        self.content = content

def prefix(iri: str, name: str) -> str:
    known = {
        "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
        "http://www.w3.org/2004/02/skos/core#": "skos:",
        "http://purl.org/dc/terms/": "dct:",
        "http://www.w3.org/2002/07/owl#": "owl:",
        "http://www.w3.org/ns/shacl#": "shacl:",
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
        "http://schema.org": "schema:",
        "http://www.w3.org/ns/adms#": "adms:",
        "http://www.w3.org/2001/XMLSchema#": "xsd:",
        "http://http://xmlns.com/foaf/0.1/": "foaf:",
        "http://dbpedia.org/resource/": "dbpedia:",
        "http://www.w3.org/ns/odrl1/2/": "odrl:",
        "http://www.w3.org/ns/org#": "org:",
        "http://www.w3.org/2006/time#": "time:",
        "http://www.w3.org/TR/vocab-dcat-2/#": "dcat:",
        "https://www.w3.org/ns/dcat#": "dcat:",
        "http://purl.org/adms/status/": "adms:",
        "http://xmlns.com/foaf/0.1/": "foaf:",
    }
    for k in known.keys():
        if iri.lower().startswith(k.lower()):
            return known[k] + name
    return name


def prune_iri(iri: str, name_only: bool = False) -> str:
    url = urlparse(iri)
    result = url.path
    if result.startswith("/"):
        result = result[1 : len(result)]
    if url.fragment == "" or url.fragment is None:
        if result.endswith("/"):
            result = result[0 : len(result) - 1]
        result = result[result.rfind("/") + 1 : len(result)]
    else:
        result = url.fragment
    if name_only is False:
        result = prefix(iri, result)
    return result