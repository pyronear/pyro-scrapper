from scrapy.logformatter import LogFormatter
from twisted.internet.error import TimeoutError, TCPTimedOutError
from twisted.internet.defer import TimeoutError as DeferTimeoutError
from twisted.web.client import ResponseNeverReceived

class SilentTimeoutLogFormatter(LogFormatter):
    """
    Custom log formatter that silences timeout-related errors to reduce log noise.

    The following errors are ignored and not logged:
        - TimeoutError
        - TCPTimedOutError
        - ResponseNeverReceived
        - DeferTimeoutError

    All other download errors are logged as usual.
    """
    def download_error(self, failure, request, spider):
        # Ignore timeouts: aucun log émis pour ces erreurs
        if failure.check(TimeoutError, TCPTimedOutError, ResponseNeverReceived, DeferTimeoutError):
            return None
        return super().download_error(failure, request, spider)