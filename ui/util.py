import requests
import json

def get(request_url, request_body=None):
    """
    Helper method to send get requests to the server.
    """
    if request_body is None:
        response = requests.get(request_url)
        if response.status_code != 200:
            raise Exception("Server returned status {}".format(response.status_code))
        else:
            return response.json()

def put(request_url, request_body):
    """
    Helper method to send post requests to the server
    """
    response = requests.put(request_url, request_body)
    if response.status_code != 200:
        raise Exception("Server returned status {}".format(response.status_code))
    else:
        return response.json()

def uri_link(context, key, compact = False):
    """
    Return a href link for the given key in the given context.
    If copmact is true, the hlink's text will not include the
    binding. If the key does not have a binding, then return the plain key.
    """
    if ':' in key:
        elems = key.split(":")
        binding = context[elems[0]]
        remainder = ''.join(elems[1:len(elems)])
        if compact is True:
            return '<a href="{}">{}</a>'.format(binding + remainder, remainder)
        else:
            return '<a href="{}">{}</a>'.format(binding + remainder, key)
    else:
        return key

def uri(context, key):
    """
    Return a URI for the given key in the given context.
    """
    if ':' in key:
        elems = key.split(":")
        binding = context[elems[0]]
        remainder = ''.join(elems[1:len(elems)])
        return binding + remainder
    else:
        return key

def compact(context, uri):
    """
    Return the compacted form of the specified URI in the specified context.
    If the URI is not bound in the context, the original URI is returned.
    """
    for binding in context.keys():
        if uri.startswith(context[binding]):
            return "{}:{}".format(binding, uri[len(context[binding]):len(uri)])
    return uri
