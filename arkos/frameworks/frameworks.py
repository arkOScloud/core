from arkos.core.utilities import random_string


class Framework(object):
    REQUIRES = []

    def __init__(self, app, **kwargs):
        self.app = app

    def _assign(self):
        for x in self.app.manager.components:
            setattr(self, x, self.app.manager.components[x])
    
    def _on_init(self):
        self.on_init()
    
    def _on_start(self):
        self.on_start()

    def on_init(self):
        pass

    def on_start(self):
        pass
