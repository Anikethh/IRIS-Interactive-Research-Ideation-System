from pythonjsonlogger import jsonlogger

import logging


class Formatter(jsonlogger.JsonFormatter):
    """
    Custom log formatter that emits log messages as JSON, with the "severity" field
    which Google Cloud uses to differentiate message levels.
    """

    def __init__(self, task_id_aware_formatter = None):
        super().__init__()
        self.task_id_aware_formatter = task_id_aware_formatter

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["severity"] = record.levelname

    def format(self, record: logging.LogRecord) -> str:
        record.msg = {"message": self.task_id_aware_formatter.format(record)} if self.task_id_aware_formatter else record.msg
        return super().format(record)



class Handler(logging.StreamHandler):
    def __init__(self, stream=None):
        super().__init__(stream)
        self.setFormatter(Formatter())
