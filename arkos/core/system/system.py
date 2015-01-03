from systemtime import SystemTime
from users import Users
from services import Services

import stats
import network
import packages

from arkos.core.frameworks import Framework


class System(Framework):
    def on_init(self):
        pass

    def on_start(self):
        self.time = SystemTime(config=self.app.conf)
        self.time.verify_time(update=True)
        self.users = Users(config=self.app.conf)
        self.services = Services()
        self.stats = stats
        self.network = network
        self.packages = packages
