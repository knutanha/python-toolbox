import unittest
import filemonitor.filemonitor as fm
import filemonitor.settings as settings

class FileMonitorableClass(fm.FileMonitorable):

    @property
    def id(self):
        return "Test FileMonitorable Class"

    def file_monitor_get_files(self) -> list:
        return




class TestMonitorAction(unittest.TestCase):
    def test(self):
        settings.

    def __init__(self, methodName: str = ...) -> None:
        super().__init__(methodName)
