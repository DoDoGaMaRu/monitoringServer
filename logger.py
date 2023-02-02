import logging.handlers
import os


class LoggerFactory:
    logger = None

    @staticmethod
    def get_logger():

        if LoggerFactory.logger is None:
            print('Logger does not exist.')

        return LoggerFactory.logger

    @staticmethod
    def init_logger(name: str = 'log',
                    log_level: any = logging.INFO,
                    save_file: bool = False,
                    save_path: str = None):
        if LoggerFactory.logger is None:
            _init_path(save_path)
            LoggerFactory.logger = logging.getLogger(name)
            LoggerFactory.logger.setLevel(log_level)

            formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)s : %(message)s')

            stream_handler = _get_stream_handler(formatter)
            LoggerFactory.logger.addHandler(stream_handler)

            if save_file:
                file_handler = _get_file_handler(save_path, name, formatter)
                LoggerFactory.logger.addHandler(file_handler)
        else:
            print('Logger already exists.')


def _get_file_handler(path: str, name: str, formatter):
    file_path = path + '/' + name
    handler = logging.handlers.TimedRotatingFileHandler(filename=file_path, when='midnight',
                                                        interval=1, encoding='utf-8')
    handler.setFormatter(formatter)

    return handler


def _get_stream_handler(formatter):
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    return handler


def _init_path(path: str):
    if not os.path.exists(path):
        os.makedirs(path)