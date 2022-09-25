import requests
import json
import validators
import re

def classname(type_string:str):
    s = re.split("\'", str(type_string))
    if len(s) == 3:
        return s[1]
    else:
        return type_string

def resolve(url):
    if not validators.url(url):
        raise Exception("Must provide valid URL")
    try:
        get = requests.get(url)
        if get.status_code != 200:
            raise Exception("Could not resolve "+url)
    except:
        raise Exception("Could not resolve "+url)

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

def internal_traverse(key, value, callable, ignore_recursive_dict_or_array):
    result = []
    if type(value) == dict:
        if ignore_recursive_dict_or_array is False and key != '':
            result += callable(key, value)
        for k in value.keys():
            result += internal_traverse(k, value[k], callable, ignore_recursive_dict_or_array)
    elif type(value) == list:
        if ignore_recursive_dict_or_array is False:
            result += callable(key, value)
        for e in value:
            result += internal_traverse(key, e, callable, ignore_recursive_dict_or_array)
    else:
        result += callable(key, value)
    return result

def traverse(jsondict, callable, ignore_recursive_dict_or_array=True):
    """
    Traverses the specified dictionary and calls the specified callable on
    each key/value pair where the value is not a dict or an array, if ignore_recursive_dict_or_array
    is True, otherwise callable will also be executed for each key/value pair,
    where the value is a dict or an array.
    The callable takes a key/value pair as input arguments and returns
    an array result. This function returns the list of all arrays.
    """
    return internal_traverse('', jsondict, callable, ignore_recursive_dict_or_array)
