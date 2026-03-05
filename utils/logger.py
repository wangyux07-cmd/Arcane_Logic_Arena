import collections
from typing import List, Dict

class Logger:
    """A logger that holds game messages with associated types for colored rendering."""
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Logger, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, max_messages=4):
        if not hasattr(self, 'initialized'):
            self.messages = collections.deque(maxlen=max_messages)
            self.initialized = True

    def log(self, message: str, log_type: str = 'system'):
        """Adds a message to the log with a specified type."""
        self.messages.append({'text': message, 'type': log_type})

    def get_messages(self) -> List[Dict[str, str]]:
        """Returns a list of current message dictionaries."""
        return list(self.messages)

logger = Logger()