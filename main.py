import requests

r = requests.get('http://localhost:8000/person', headers={"accept-header": "application/ld+json"})
