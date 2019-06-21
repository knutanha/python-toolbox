import abc
import enum
import json
import os
import time
import pytoolbox.utility.logger as logger
import pytoolbox.utility.os as os_utils
import pytoolbox.settings as settings

__version__ = '0.2'
__author__ = 'Knut Andreas Hasund'

# TODO: Add option to use caching or not
# TODO: Remove settings file


class FileMonitorable(metaclass=abc.ABCMeta):
    """Use this class as a parent if you want to create a handler for the file monitor"""

    @property
    @abc.abstractmethod
    def id(self):
        """Id that will be shown by the log output of the FileMonitor and used for the caching file."""
        pass

    @abc.abstractmethod
    def file_monitor_get_files(self) -> list:
        """Should return a list of strings containing all files that should be monitored each time it is called.
        The string must contain the absolute path of each file.
        """
        pass

    @abc.abstractmethod
    def file_monitor_action_on_change(self, change_list, file_list, **kwargs) -> None:
        """Performs some action when one or more file has been changed.

        Receives keyword arguments from the file monitor:
            change_list: A list of files that have been changed (absolute paths).
            file_list: A list of all the files being monitored (absolute paths).
            **action_kwargs: The extra keyword arguments provided to the FileMonitor class at initiation.
        """
        pass


class FileMonitorActionType(enum.Enum):
    SEARCH_FOR_NEW_FILES = 1
    SCAN_FILES_FOR_CHANGES = 2

    def __str__(self):
        return self.name


class FileMonitorAction:
    """Minimal implementation of a sortable action container"""
    def __init__(self, action_type: FileMonitorActionType, action_time: int):
        self.action_type = action_type
        self.action_time = action_time

    def __lt__(self, other):
        return self.action_time < other.action_time

    def __le__(self, other):
        return self.action_time <= other.action_time

    def __str__(self):
        return f'FileMonitorAction(action_type: {self.action_type}, action_time: {self.action_time})'

    def __repr__(self):
        return str(self)


class FileMonitorActionQueue:
    """Minimal implementation of a sorted queue"""
    # TODO: Insert without sorting the entire list (Only needed if more actions are added)
    def __init__(self):
        self.queue = []

    def put(self, action: FileMonitorAction):
        self.queue.append(action)
        self.queue.sort()

    def get(self):
        return self.queue.pop(0) if len(self.queue) > 0 else None

    def __str__(self):
        return str(self.queue)


class FileMonitor:
    """Class for monitoring a set of files.

    Takes an object of type FileMonitorable that provides data and executes actions on behalf on the monitor. For each
    update the data for the current file status is saved in a cache file, and used the next time the monitor is
    restarted.
    """
    # TODO: Do an update if the version has changed
    # static init
    __DEFAULT_NEW_FILES_SEARCH_FREQUENCY = 30
    __DEFAULT_FILE_UPDATE_SCAN_FREQUENCY = 480
    __NANO_DIVISOR = 1000000000
    __SECS_IN_HOUR = 60 * 60
    __NANO_SECS_IN_HOUR = __SECS_IN_HOUR * __NANO_DIVISOR
    __CACHE_FILE_ENDING = '.cache'

    def __init__(self,
                 subscriber: FileMonitorable,
                 new_files_search_frequency: int = __DEFAULT_NEW_FILES_SEARCH_FREQUENCY,
                 file_update_scan_frequency: int = __DEFAULT_FILE_UPDATE_SCAN_FREQUENCY,
                 fresh_start: bool = False,
                 **action_kwargs):
        """Constructor

        :param subscriber: The class-instance that provides the files to be monitored and executes actions based on
        changes. Should implement the FileMonitorable interface.

        :param new_files_search_frequency: Number representing the number of times per hour the monitor updates its
        file list (to check for deleted or added files).

        :param file_update_scan_frequency: Number representing the number of times per hour the monitor checks the files
        in its file list for changes.

        :param fresh_start: If true the monitor will ignore the cache and start as if it is run for the first time. This
        will trigger an update action for each file at the start of the run.

        :param action_kwargs: Dict of arguments that should be passed to the action method of the subscriber.
        """
        self.__subscriber = subscriber
        self.__new_files_search_frequency = new_files_search_frequency
        self.__file_update_scan_frequency = file_update_scan_frequency
        self.__metadata_cache_path = os.path.join(
            settings.DATA_CACHE_FOLDER,
            settings.FILE_MONITOR_CACHE_FOLDER_NAME,
            self.__subscriber.id + self.__CACHE_FILE_ENDING
        )
        self.action_kwargs = action_kwargs
        # Init logger
        self.__log_manager = logger.LogManager(f"FileMonitor<{self.__subscriber.id}>", settings.LOG_LEVEL)
        self.__log = self.__log_manager.log
        # Read from cache
        self.__file_cache: dict = dict()
        if os.path.exists(self.__metadata_cache_path) and not fresh_start:
            try:
                with open(self.__metadata_cache_path, 'r') as f:
                    file_cache = json.loads(f.read())
                    if not isinstance(file_cache, dict):
                        raise SyntaxError("Cache is not formatted correctly.")
                    self.__file_cache = file_cache
            except (json.JSONDecodeError, SyntaxError) as e:
                self.__log(f'Error when parsing file cache to JSON: "{e}", resetting cache.', logger.LogLevel.ERROR)
        # Find files
        self.__find_files()
        # Prepare queue for monitoring
        self.__action_queue = FileMonitorActionQueue()
        self.__queue_new_action(FileMonitorActionType.SCAN_FILES_FOR_CHANGES)
        self.__queue_new_action(FileMonitorActionType.SEARCH_FOR_NEW_FILES)

    def monitor(self):
        """Starts the monitoring."""
        lag_counter = 0
        self.__log(f'Monitoring {len(self.file_list)} files.')
        self.__log(f'Checking for changes every:   {self.__SECS_IN_HOUR / self.__DEFAULT_FILE_UPDATE_SCAN_FREQUENCY}s')
        self.__log(f'Checking for new files every: {self.__SECS_IN_HOUR / self.__DEFAULT_NEW_FILES_SEARCH_FREQUENCY}s')

        while True:
            self.__log(f'Current queue: {self.__action_queue}', logger.LogLevel.DEBUG)
            next_action: FileMonitorAction = self.__action_queue.get()

            self.__log(f'Next action: {next_action}', logger.LogLevel.DEBUG)
            wait_time = (next_action.action_time - time.time_ns()) / self.__NANO_DIVISOR
            if wait_time > 0:
                self.__log(f'Waiting for {wait_time}s', logger.LogLevel.DEBUG)
                lag_counter = 0
                time.sleep(wait_time)
            else:
                lag_counter += 1
                if lag_counter > 1:
                    self.__log('Lagging behind. Consider setting scan frequencies to a lower number.', logger.LogLevel.INFO)
            self.__queue_new_action(next_action.action_type)
            if next_action.action_type == FileMonitorActionType.SCAN_FILES_FOR_CHANGES:
                self.__scan_files_for_changes()
            elif next_action.action_type == FileMonitorActionType.SEARCH_FOR_NEW_FILES:
                self.__find_files()

    def __scan_files_for_changes(self):
        start_time = time.time_ns()
        # Check for changes
        changed_files = []
        removed_files = []
        for file in self.file_list:
            if os.path.isfile(file):
                try:
                    last_modified = os.stat(file).st_mtime_ns
                except OSError as e:
                    self.__log(f"Encountered an OSError, skipping file: {e}", logger.LogLevel.ERROR)
                    continue
                if not (file in self.__file_cache.keys() and int(self.__file_cache[file]) == last_modified):
                    changed_files.append(file)
                    self.__file_cache[file] = last_modified
            else:
                self.file_list.pop(self.file_list.index(file))
                self.__file_cache.pop(file)
                removed_files.append(file)

        if len(changed_files) > 0 or len(removed_files) > 0:
            self.__log()
            self.__log(f'Changes found: {len(changed_files) + len(removed_files)}', logger.LogLevel.INFO)
            self.__subscriber.file_monitor_action_on_change(change_list=changed_files,
                                                            file_list=self.file_list.copy(),
                                                            **self.action_kwargs)
            # write changes to cache
            os_utils.persist_file_path(self.__metadata_cache_path, True)
            with open(self.__metadata_cache_path, 'w') as f:
                f.write(json.dumps(self.__file_cache))

        time_spent = (time.time_ns() - start_time) / self.__NANO_DIVISOR
        self.__log(f'[{FileMonitorActionType.SCAN_FILES_FOR_CHANGES}] Time spent: {time_spent}s', logger.LogLevel.DEBUG)

    def __find_files(self):
        start_time = time.time_ns()
        self.file_list = self.__subscriber.file_monitor_get_files()
        time_spent = (time.time_ns() - start_time) / self.__NANO_DIVISOR
        self.__log(f'[{FileMonitorActionType.SEARCH_FOR_NEW_FILES}] Time spent: {time_spent}s', logger.LogLevel.DEBUG)

    def __queue_new_action(self, action_type: FileMonitorActionType):
        if action_type == FileMonitorActionType.SEARCH_FOR_NEW_FILES and self.__new_files_search_frequency > 0:
            self.__action_queue.put(
                FileMonitorAction(
                    FileMonitorActionType.SEARCH_FOR_NEW_FILES,
                    time.time_ns() + self.__NANO_SECS_IN_HOUR // self.__new_files_search_frequency
                )
            )
        elif action_type == FileMonitorActionType.SCAN_FILES_FOR_CHANGES and self.__file_update_scan_frequency > 0:
            self.__action_queue.put(
                FileMonitorAction(
                    FileMonitorActionType.SCAN_FILES_FOR_CHANGES,
                    time.time_ns() + self.__NANO_SECS_IN_HOUR // self.__file_update_scan_frequency
                )
            )


if __name__ == '__main__':
    print(__file__)