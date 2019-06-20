import datetime
import enum


class LogLevel(enum.Enum):
    ERROR = 0
    INFO = 1
    DEBUG = 2


class LogManager:
    def __init__(self, domain_name, log_level=LogLevel.INFO, output_type='text'):
        self.__domain_name = domain_name
        self.__output_type = output_type
        self.__log_level = self.__get_log_level_type(log_level)

    def log(self, message: str = None, log_level=LogLevel.INFO):
        if self.__log_level.value >= self.__get_log_level_type(log_level).value:
            if message:
                print(f'[{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")}][{log_level.name}][{self.__domain_name}] {message}')
            else:
                # New line
                print()

    @staticmethod
    def __get_log_level_type(log_level):
        if isinstance(log_level, LogLevel):
            return log_level
        elif isinstance(log_level, int):
            return LogLevel(log_level)