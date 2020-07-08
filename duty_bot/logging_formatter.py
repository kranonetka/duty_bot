import logging
from functools import reduce


class SensitiveFormatter(logging.Formatter):
    def __init__(self, *args):
        super().__init__()
        self.sensitive = args

    def format(self, record: logging.LogRecord) -> str:
        original = logging.Formatter.format(record)
        escaped = reduce(lambda acc, new: acc.replace(new, "/HIDDEN/"), self.sensitive, original)
        return escaped
