"""Custom log formatting for Scrappy Pyronear."""

from scrapy.logformatter import LogFormatter
from twisted.internet.defer import TimeoutError as DeferTimeoutError
from twisted.internet.error import TCPTimedOutError, TimeoutError
from twisted.web.client import ResponseNeverReceived


class SilentTimeoutLogFormatter(LogFormatter):
    """Custom log formatter that silences timeout-related errors to reduce log noise."""

    def download_error(self, failure, request, spider):
        """Silence timeout-related download errors."""
        # Ignore timeouts: aucun log émis pour ces erreurs
        if failure.check(TimeoutError, TCPTimedOutError, ResponseNeverReceived, DeferTimeoutError):
            return None
        return super().download_error(failure, request, spider)
