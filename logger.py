import logging
import clock
import os


class Logger:
    def __init__(self,
                 name: str,
                 path: str = None,
                 level=logging.INFO):
        self.name = name
        self.logger = None
        self.level = level
        self.tc = clock.TimeController()
        self.path = path

        self.init_logger()

    def init_logger(self):
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(self.level)

        if self.path is not None:
            _init_path(self.path)
            file_handler = logging.FileHandler(self.path + clock.get_day() + self.name + '.log',
                                               encoding='utf-8')
            self.add_handler(file_handler)

        stream_handler = logging.StreamHandler()
        self.add_handler(stream_handler)

    def add_handler(self, handler):
        formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)s : %(message)s')
        handler.setFormatter(formatter)
        self.logger.add_handler(handler)

    def trigger(self):
        is_day_changed = self.tc.is_day_change()
        if is_day_changed:
            self.init_logger()

    def info(self, message: str):
        self.trigger()
        self.logger.info(message)

    def debug(self, message: str):
        self.trigger()
        self.logger.debug(message)

    def error(self, message: str):
        self.trigger()
        self.logger.error(message)


def _init_path(path: str):
    if not os.path.exists(path):
        os.makedirs(path)

