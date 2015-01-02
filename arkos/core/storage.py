import json
import redis


class Storage(object):
    def __init__(self, app):
        self.app = app
        self.connect()

    def connect(self):
        # Connect to Redis server
        try:
            self.redis = redis.Redis(unix_socket_path="/run/arkos-redis.sock")
            self.redis.ping()
        except redis.exceptions.ConnectionError, e:
            raise Exception(str(e))

    def disconnect(self):
        # Disconnect from Redis server
        self.redis.connection_pool.disconnect()

    def check(self):
        # Make sure our connection to Redis is still active
        # If not, stop everything, reconnect and reload
        self.check()
        try:
            self.redis.ping()
        except:
            self.app.logger.error("Connection to Storage lost. Reloading")
            self.connect()

    def get(self, key, optkey=None):
        self.check()
        if optkey:
            value = self.redis.hget("arkos:%s" % key, optkey)
        else:
            value = self.redis.get("arkos:%s" % key)
        if value.startswith(("[", "{")) and value.endswith(("]", "}")):
            return json.loads(value)
        return value

    def set(self, key, value, optval=None):
        self.check()
        if optval and type(optval) in [list, dict]:
            optval = json.dumps(optval)
        elif type(value) in [list, dict]:
            value = json.dumps(value)
        if optval:
            self.redis.hset("arkos:%s" % key, value, optval)
        else:
            self.redis.set("arkos:%s" % key, value)

    def get_list(self, key):
        self.check()
        values = []
        for x in self.redis.lrange("arkos:%s" % key, 0, -1):
            if x.startswith(("[", "{")) and x.endswith(("]", "}")):
                x = json.loads(x)
            values.append(x)
        return values

    def append(self, key, value):
        self.check()
        if type(value) in [list, dict]:
            value = json.dumps(value)
        self.redis.rpush("arkos:%s" % key, value)

    def append_all(self, key, values):
        self.check()
        for x in enumerate(values):
            if type(x[1]) in [list, dict]:
                values[x[0]] = json.dumps(x[1])
        self.redis.rpush("arkos:%s" % key, **values)

    def remove(self, key, value):
        newvals = []
        for x in self.get_list(key):
            if x.startswith(("[", "{")) and x.endswith(("]", "}")):
                x = json.loads(x)
            if x == value:
                continue
            newvals.append(x)
        self.delete(key)
        self.append_all(newvals)

    def remove_all(self, key, values):
        newvals = []
        for x in self.get_list(key):
            if x.startswith(("[", "{")) and x.endswith(("]", "}")):
                x = json.loads(x)
            if x in values:
                continue
            newvals.append(x)
        self.delete(key)
        self.append_all(newvals)

    def delete(self, key):
        self.check()
        self.redis.delete("arkos:%s" % key)

    def scan(self, key):
        return self.redis.scan(0, "arkos:%s" % key)[1]
