import datetime
import logging
import sys
import threading
import time

from arkos import version
from arkos.core.utilities import *
from arkos.core.config import Config
from arkos.core.storage import Storage, StorageOps
from arkos.core.frameworks.manager import FrameworkManager


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

    dformatter = logging.Formatter('%(asctime)s [%(levelname)s] %(module)s: %(message)s')
    stdout.setFormatter(dformatter)
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

        arch = detect_architecture()
        platform = detect_platform()
        self.logger.info('Detected architecture/hardware: %s, %s' % arch)
        self.logger.info('Detected platform: %s' % platform)
        self.conf.set("enviro", "arch", arch[0])
        self.conf.set("enviro", "board", arch[1])
        
        self.ops = StorageOps(self)

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
            try:
                task = self.app.storage.pop("tasks")
                if not task:
                    time.sleep(1)
                    continue
                if task.get("group") and task["group"]:
                    for x in task["tasks"]:
                        status = self.process_tasks(x)
                        if not status:
                            break
                else:
                    status = self.process_tasks(task)
                if not status:
                    continue
            except MalformedObject, e:
                self.app.logger.error(str(e))
                continue
            except:
                process_exception(self.app, "task processor")
    
    def process_tasks(self, task):
        responses = []
        self.app.logger.debug("*** Starting task %s" % task["id"])
        if task.get("message") and task["message"].get("start"):
            self.app.ops.put_message("info", task["message"]["start"], task["id"])
        for x in sorted(task["tasks"]):
            getout = False
            if x[1]["unit"] == "shell":
                s = shell(x[1]["order"], stdin=x[1].get("data"))
                if s["code"] != 0:
                    responses.append((x[0], s["stderr"]))
                    getout = True
                    break
            elif x[1]["unit"] == "fetch":
                try:
                    download(x[1]["order"], x[1]["data"], True)
                except Exception, e:
                    code = 1
                    if hasattr(e, "code"):
                        code = e.code
                    responses.append((x[0], str(code)))
                    getout = True
                    break
            elif x[1]["unit"] == "setconf":
                self.app.conf.set(x[1]["order"][0], x[1]["order"][1], x[1]["data"])
            else:
                try:
                    func = getattr(self.app.manager.components[x[1]["unit"]], x[1]["order"])
                except (KeyError, NameError, AttributeError):
                    responses.append((x[0], str(MalformedObject(x[1]))))
                    getout = True
                    break
                try:
                    if x[1].get("data"):
                        response = func(task_id=task["id"], **x[1]["data"])
                    else:
                        response = func(task_id=task["id"])
                    responses.append((x[0], response))
                except Exception, e:
                    responses.append((x[0], str(e)))
                    getout = True
                    break
            responses.append((x[0], resp))
        if getout:
            self.app.logger.error("Failed to complete task %s at step %s: %s" % (task["id"], responses[-1][0]+1, responses[-1][1]))
            if task.get("message") and task["message"].get("error"):
                self.app.ops.put_message("error", "%s: %s" % (task["message"]["error"], responses[-1][1]), 
                    task["id"], True)
            return False
        self.app.logger.debug("*** Completed task %s" % task["id"])
        if task.get("message") and task["message"].get("success"):
            self.app.ops.put_message("success", task["message"]["success"], task["id"],
                True, responses)
        return True


class ScheduleProcessor(threading.Thread):
    def __init__(self, app):
        threading.Thread.__init__(self)
        self.app = app

    def run(self):
        while not self.app.stop_workers:
            try:
                now = time.time()
                tasks = self.app.storage.sortlist_getbyscore("scheduled", now, pop=True)
                if tasks:
                    pipe = self.app.storage.pipeline()
                for x in tasks:
                    self.app.logger.debug("*** Processing scheduled task %s" % x["id"])
                    self.app.ops.add_raw_task(x, pipe=pipe)
                    if x.get("reschedule") and x["reschedule"]:
                        newtask = x
                        newtask["id"] = random_string()[0:8]
                        self.app.ops.schedule_task(newtask, newtask["reschedule"], pipe=pipe)
                if tasks:
                    self.app.storage.execute(pipe)
                time.sleep(5)
            except:
                process_exception(self.app, "schedule processor")
