import datetime
import logging
import sys
import threading
import time

from arkos import version
from arkos.core.utilities import *
from arkos.core.config import Config
from arkos.core.storage import Storage
from arkos.core.frameworks.manager import FrameworkManager


class DebugHandler(logging.StreamHandler):
    def __init__(self):
        self.capturing = False
        self.buffer = ''

    def start(self):
        self.capturing = True

    def stop(self):
        self.capturing = False

    def handle(self, record):
        if self.capturing:
            self.buffer += self.formatter.format(record) + '\n'


class ConsoleHandler(logging.StreamHandler):
    def __init__(self, stream, debug):
        self.debug = debug
        logging.StreamHandler.__init__(self, stream)

    def handle(self, record):
        if not self.stream.isatty():
            return logging.StreamHandler.handle(self, record)

        s = ''
        d = datetime.datetime.fromtimestamp(record.created)
        s += d.strftime("\033[37m%d.%m.%Y %H:%M \033[0m")
        if self.debug:
            s += ('%s:%s'%(record.filename,record.lineno)).ljust(30)
        l = ''
        if record.levelname == 'DEBUG':
            l = '\033[37mDEBUG\033[0m '
        if record.levelname == 'INFO':
            l = '\033[32mINFO\033[0m  '
        if record.levelname == 'WARNING':
            l = '\033[33mWARN\033[0m  '
        if record.levelname == 'ERROR':
            l = '\033[31mERROR\033[0m '
        s += l.ljust(9)
        s += record.msg
        s += '\n'
        self.stream.write(s)


def make_log(debug=False, log_level=logging.INFO):
    log = logging.getLogger('genesis')
    log.setLevel(logging.DEBUG)

    stdout = ConsoleHandler(sys.stdout, debug)
    stdout.setLevel(log_level)

    log.blackbox = DebugHandler()
    log.blackbox.setLevel(logging.DEBUG)
    dformatter = logging.Formatter('%(asctime)s [%(levelname)s] %(module)s: %(message)s')
    log.blackbox.setFormatter(dformatter)
    stdout.setFormatter(dformatter)
    log.addHandler(log.blackbox)

    log.addHandler(stdout)

    return log


class Application(object):
    def __init__(self):
        self.logger = None
        self.conf = None
        self.storage = None
        self.stop_workers = False
    
    def start(self, log_level, config_file):
        self.logger = make_log(debug=log_level==logging.DEBUG, log_level=log_level)
        self.logger.info('arkOS krakend %s' % version())
        
        # Connect to Redis storage
        self.logger.info("Connecting to storage")
        try:
            self.storage = Storage(self)
        except Exception, e:
            self.logger.error("Failed to connect to storage: %s" % str(e))
            sys.exit(1)

        # Set up config
        self.conf = Config(self.storage)
        self.logger.info("Using config file at %s" % config_file)
        self.conf.load(config_file)
        
        # Start recording log for the bug reports
        self.logger.blackbox.start()

        arch = detect_architecture()
        platform = detect_platform()
        self.logger.info('Detected architecture/hardware: %s, %s' % arch)
        self.logger.info('Detected platform: %s' % platform)
        self.conf.set("enviro", "arch", arch[0])
        self.conf.set("enviro", "board", arch[1])

        # Load components
        self.logger.info("Loading components...")
        self.manager = FrameworkManager(self)
        self.manager.start()
        self.logger.info("Done loading components")
    
    def stop(self):
        self.stop_workers = True
        self.conf.save()
        if self.storage:
            self.storage.disconnect()


class TaskProcessor(threading.Thread):
    def __init__(self, app):
        threading.Thread.__init__(self)
        self.app = app
    
    def run(self):
        while not self.app.stop_workers:
            task = self.app.storage.pop("tasks")
            if not task:
                time.sleep(1)
                continue
            responses = []
            getout = False
            self.app.logger.debug("*** Starting task %s" % task["id"])
            self.app.storage.append("messages", {"id": task["id"], "status": "processing"})
            for x in sorted(task["tasks"]):
                getout = False
                if x[1]["unit"] == "shell":
                    s = shell(x[1]["order"], stdin=x[1].get("data"))
                    resp = {"status": "complete", "code": s["code"],
                        "result": s["stdout"], "stderr": s["stderr"]}
                    if s["code"] != 0:
                        responses.append((x[0], resp))
                        getout = True
                        break
                elif x[1]["unit"] == "fetch":
                    try:
                        download(x[1]["order"], x[1]["data"], True)
                        resp = {"status": "complete", "code": 200, "result": x[1]["data"]}
                    except Exception, e:
                        code = 1
                        if hasattr(e, "code"):
                            code = e.code
                        resp = {"status": "failed", "code": code}
                        responses.append((x[0], resp))
                        getout = True
                        break
                else:
                    func = getattr(self.app.manager.components[x[1]["unit"]], x[1]["order"])
                    try:
                        response = func(_task_id=task["id"], **x[1]["data"])
                        resp = {"status": "complete", "code": 0, "result": response}
                    except Exception, e:
                        resp = {"status": "failed", "code": 1, "result": response}
                        responses.append((x[0], resp))
                        getout = True
                        break
                responses.append((x[0], resp))
                self.app.storage.append("messages", {"id": task["id"], "status": "processing",
                    "completion": (x[0]+1, len(task["tasks"])), "responses": responses})
            if getout:
                self.app.logger.error("Failed to complete task %s at step %s: %s" % (task["id"], responses[-1][0]+1, responses[-1][1]))
                self.app.storage.append("messages", {"id": task["id"], "status": "failed",
                    "finished": True, "responses": responses})
                continue
            self.app.logger.debug("*** Completed task %s" % task["id"])
            self.app.storage.append("messages", {"id": task["id"], "status": "complete",
                "finished": True, "responses": responses})


class ScheduleProcessor(threading.Thread):
    def __init__(self, app):
        threading.Thread.__init__(self)
        self.app = app
    
    def run(self):
        while not self.app.stop_workers:
            now = time.time()
            tasks = self.app.storage.sortlist_getbyscore("scheduled", now)
            if tasks:
                pipe = self.app.storage.redis.pipeline()
            for x in tasks:
                self.app.logger.debug("*** Processing scheduled task %s" % task["id"])
                pipe.rpush("arkos:tasks", x)
                pipe.zrem("arkos:scheduled", x)
                if x["reschedule"]:
                    x["id"] = random_string()[0:8]
                    retime = now + x["reschedule"]
                    pipe.zadd("arkos:scheduled", x, retime)
            if tasks:
                pipe.execute()
            time.sleep(5)
