from rdflib import Graph
from rdflib import URIRef

g = Graph()
g.parse("schemaorg-current-http.jsonld")
#g.parse('file:///Users/mrichter/cs-schema.jsonld')
#g.parse('file:///Users/mrichter/counterparty.json')

g1 = Graph()
g1.parse("https://json-ld.org/contexts/person.jsonld")

for s, p, o in g:
    if str(s) == 'http://schema.org/Person':
        print(s, p, o)

print("------- Properties of Person:")
for s, p, o in g:
    if str(o) == 'http://schema.org/Person' and str(p) == 'http://schema.org/domainIncludes':
        print(s)

print("------- Definition of person.jsonld")
for s, p, o in g1:
    print(s, p, o)
