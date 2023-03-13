from shapiro_render import JsonSchemaRenderer
import json

j = JsonSchemaRenderer()
s = j.render_nodeshape("http://127.0.0.1:8000/com/example/org/model_for_jsonschema/SimplePersonShape")
print(s)

d = json.loads(s)
