import os

import pythontoolbox.filemonitor.logger as logging
import utility.os_utils as osutils

"""
    GENERIC SETTINGS
"""
DATA_CACHE_FOLDER = os.path.join(osutils.remove_last_part_of_path(__file__, 1), 'cache')

# File monitoring
FILE_MONITOR_CACHE_FOLDER_NAME = 'file-monitor-cache'

"""
    LOG SETTINGS
"""
LOG_LEVEL = logging.LogLevel.INFO