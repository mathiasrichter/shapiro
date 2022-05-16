from rdflib import Graph
from rdflib import URIRef
from pyshacl import validate

g = Graph()
g.parse("file:///Users/mrichter/test.jsonld")
#g.parse('file:///Users/mrichter/cs-schema.jsonld')
#g.parse('file:///Users/mrichter/counterparty.json')

print(validate(g))



g1 = Graph()
g1.parse("https://json-ld.org/contexts/person.jsonld")
print(validate(g1))

for s, p, o in g:
        print(s, p, o)
