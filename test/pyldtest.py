from pyld import jsonld
import json
import urllib.parse as urllib_parse

"""
def loader(url, options={}):
    pieces = urllib_parse.urlparse(url)
    if pieces.scheme != 'file':
        raise Exception(
            'URL could not be dereferenced; only "file" URLs are supported: '+url)
    f = open(pieces.path, "r")
    data = json.load(f)
    f.close()
    return {
        'contentType': "application/json",
        'contextUrl': None,
        'documentUrl': url,
        'document': data
    }


jsonld.set_document_loader(loader)
"""
"""
context =   {
    "@context":
      {
        "Counterparty": "http://localhost:8000/cs-schema/Counterparty",
        "cif" : "http://localhost:8000/cs-schema/cif",
        "parseid" : "http://localhost:8000/cs-schema/cif",
        "csid": "http://localhost:8000/cs-schema/cif"
      }
}

doc = {
  "@type": "Counterparty",
  "@id": "cif1234",
  "cif": "cif1234",
  "parseid": "parseid1234",
  "csid": "csid1234"
}
"""

context="https://json-ld.org/contexts/person.jsonld"

doc={
   "@context":
   {
      "Person": "http://xmlns.com/foaf/0.1/Person",
      "xsd": "http://www.w3.org/2001/XMLSchema#",
      "name": "http://xmlns.com/foaf/0.1/name",
      "nickname": "http://xmlns.com/foaf/0.1/nick",
      "affiliation": "http://schema.org/affiliation",
      "depiction":
      {
         "@id": "http://xmlns.com/foaf/0.1/depiction",
         "@type": "@id"
      },
      "image":
      {
         "@id": "http://xmlns.com/foaf/0.1/img",
         "@type": "@id"
      },
      "born":
      {
         "@id": "http://schema.org/birthDate",
         "@type": "xsd:date"
      },
      "child":
      {
         "@id": "http://schema.org/children",
         "@type": "@id"
      },
      "colleague":
      {
         "@id": "http://schema.org/colleagues",
         "@type": "@id"
      },
      "knows":
      {
         "@id": "http://xmlns.com/foaf/0.1/knows",
         "@type": "@id"
      },
      "died":
      {
         "@id": "http://schema.org/deathDate",
         "@type": "xsd:date"
      },
      "email":
      {
         "@id": "http://xmlns.com/foaf/0.1/mbox",
         "@type": "@id"
      },
      "familyName": "http://xmlns.com/foaf/0.1/familyName",
      "givenName": "http://xmlns.com/foaf/0.1/givenName",
      "gender": "http://schema.org/gender",
      "homepage":
      {
         "@id": "http://xmlns.com/foaf/0.1/homepage",
         "@type": "@id"
      },
      "honorificPrefix": "http://schema.org/honorificPrefix",
      "honorificSuffix": "http://schema.org/honorificSuffix",
      "jobTitle": "http://xmlns.com/foaf/0.1/title",
      "nationality": "http://schema.org/nationality",
      "parent":
      {
         "@id": "http://schema.org/parent",
         "@type": "@id"
      },
      "sibling":
      {
         "@id": "http://schema.org/sibling",
         "@type": "@id"
      },
      "spouse":
      {
         "@id": "http://schema.org/spouse",
         "@type": "@id"
      },
      "telephone": "http://schema.org/telephone",
      "Address": "http://www.w3.org/2006/vcard/ns#Address",
      "address": "http://www.w3.org/2006/vcard/ns#address",
      "street": "http://www.w3.org/2006/vcard/ns#street-address",
      "locality": "http://www.w3.org/2006/vcard/ns#locality",
      "region": "http://www.w3.org/2006/vcard/ns#region",
      "country": "http://www.w3.org/2006/vcard/ns#country",
      "postalCode": "http://www.w3.org/2006/vcard/ns#postal-code"
   }
}


expanded = jsonld.expand(doc)
print( "======= EXPANDED ========")
print(json.dumps(expanded, indent=2))

compacted = jsonld.compact(doc, context)
print( "======= COMPACTED ========")
print(json.dumps(compacted, indent=2))

flattened = jsonld.flatten(compacted)
print( "======= FLATTENED ========")
print(json.dumps(flattened, indent=2))
