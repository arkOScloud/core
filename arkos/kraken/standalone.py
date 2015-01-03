import time

from application import Application, TaskProcessor, ScheduleProcessor


def run_daemon(log_level=logging.INFO, config_file=''):
    app = Application()
    app.start(log_level=20, config_file=config_file)

    workers = []
    num = app.conf.get("general", "task_workers", 1)

    # Launch workers
    app.logger.info("Launching workers...")
    for x in range(num):
        task = TaskProcessor(app)
        task.start()
        workers.append(task)
    sched = ScheduleProcessor(app)
    sched.start()
    workers.append(sched)

    app.logger.info('Kraken is running')
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        app.logger.info("Interrupt received")
        app.stop()
        for x in workers:
            x.join()
        app.logger.info("Stopped by request")
