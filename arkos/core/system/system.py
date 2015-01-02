from arkos.core import Framework


class System(Framework):
    def on_init(self):
        pass

    def on_start(self):
        self.time = SystemTime(config=self.config)
        self.time.verify_time(update=True)
        self.users = Users(config=self.config)
        self.services = Services()
        self.stats = Stats()
        self.network = Network()
        self.packages = Packages()
