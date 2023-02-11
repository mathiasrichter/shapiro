class BadSchemaException(Exception):

    def __init__(self):
        super().__init__()

class NotFoundException(Exception):

    def __init__(self, content:str):
        self.content = content
