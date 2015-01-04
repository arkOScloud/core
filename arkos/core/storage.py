import json
import redis


class Storage(object):
    def __init__(self, app):
        self.app = app
        self.connect()

    def connect(self):
        # Connect to Redis server
        try:
            self.redis = redis.Redis(unix_socket_path="/tmp/arkos-redis.sock")
            self.redis.ping()
            self.redis.flushdb()
        except redis.exceptions.ConnectionError, e:
            raise Exception(str(e))

    def disconnect(self):
        # Disconnect from Redis server
        self.redis.flushdb()
        self.redis.connection_pool.disconnect()

    def check(self):
        # Make sure our connection to Redis is still active
        # If not, stop everything, reconnect and reload
        try:
            self.redis.ping()
        except:
            self.app.logger.error("Connection to Storage lost. Reloading")
            self.connect()

    def get(self, key, optkey=None):
        self.check()
        if optkey:
            return self._get(self.redis.hget("arkos:%s" % key, optkey))
        else:
            return self._get(self.redis.get("arkos:%s" % key))
    
    def get_all(self, key):
        values = self.redis.hgetall("arkos:%s" % key)
        for x in values:
            values[x] = self._get(values[x])
        return values

    def set(self, key, value, optval=None):
        self.check()
        if optval:
            self.redis.hset("arkos:%s" % key, value, optval)
        elif type(value) == list:
            for x in enumerate(value):
                if type(x[1]) in [list, dict]:
                    value[x[0]] = json.dumps(x[1])
            self.redis.rpush("arkos:%s" % key, *value)
        elif type(value) == dict:
            for x in value:
                if type(value[x]) in [list, dict]:
                    value[x] = json.dumps(value[x])
            self.redis.hmset("arkos:%s" % key, value)
        else:
            self.redis.set("arkos:%s" % key, value)
    
    def pop(self, key):
        return self._get(self.redis.lpop("arkos:%s" % key))

    def get_list(self, key):
        self.check()
        values = []
        for x in self.redis.lrange("arkos:%s" % key, 0, -1):
            values.append(self._get(x))
        return values

    def append(self, key, value):
        self.check()
        if type(value) in [list, dict]:
            value = json.dumps(value)
        self.redis.rpush("arkos:%s" % key, value)

    def append_all(self, key, values):
        if values:
            self.check()
            for x in enumerate(values):
                if type(x[1]) in [list, dict]:
                    values[x[0]] = json.dumps(x[1])
            self.redis.rpush("arkos:%s" % key, *values)
    
    def sortlist_getbyscore(self, key, priority, num=0):
        self.check()
        return self._get(self.redis.zrevrangebyscore("arkos:%s" % key, priority, num))

    def remove(self, key, value):
        newvals = []
        for x in self.get_list(key):
            x = self._get(x)
            if x == value:
                continue
            newvals.append(x)
        self.delete(key)
        self.append_all(newvals)

    def remove_all(self, key, values):
        newvals = []
        for x in self.get_list(key):
            x = self._get(x)
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
    
    def _get(self, value):
        if type(value) == str:
            return self._translate(value)
        elif type(value) == list:
            vals = []
            for x in value:
                vals.append(self._translate(x))
            return vals
        return value
    
    def _translate(self, value):
        if value.startswith(("[", "{")) and value.endswith(("]", "}")):
            return json.loads(value)
        return value
