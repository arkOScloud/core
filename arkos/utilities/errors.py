class ConnectionError(Exception):
    def __init__(self, id):
        self.id = id

    def __str__(self):
        return "Failed to connect to %s service" % self.id
    

class DefaultException(Exception):
    def __init__(self, msg):
        self.msg = msg
    
    def __str__(self):
        return self.msg
