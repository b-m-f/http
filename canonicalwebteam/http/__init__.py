# Core packages
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

# Third-party packages
import redis
import requests
from cachecontrol import CacheControl
from cachecontrol.caches.redis_cache import RedisCache

try:
    # If prometheus is available, set up metric counters

    import prometheus_client

    TIMEOUT_COUNTER = prometheus_client.Counter(
        'feed_timeouts',
        'A counter of timed out requests',
        ['domain'],
    )
    CONNECTION_FAILED_COUNTER = prometheus_client.Counter(
        'feed_connection_failures',
        'A counter of requests which failed to connect',
        ['domain'],
    )
    LATENCY_HISTOGRAM = prometheus_client.Histogram(
        'feed_latency_seconds',
        'Feed requests retrieved',
        ['domain', 'code'],
        buckets=[0.25, 0.5, 0.75, 1, 2, 3],
    )
except ImportError:
    TIMEOUT_COUNTER = None
    CONNECTION_FAILED_COUNTER = None
    LATENCY_HISTOGRAM = None


class TimeoutHTTPAdapter(requests.adapters.HTTPAdapter):
    """
    A simple extension to the HTTPAdapter to add a 'timeout' parameter
    """

    def __init__(self, timeout=None, *args, **kwargs):
        self.timeout = timeout
        super(TimeoutHTTPAdapter, self).__init__(*args, **kwargs)

    def send(self, *args, **kwargs):
        kwargs['timeout'] = self.timeout
        return super(TimeoutHTTPAdapter, self).send(*args, **kwargs)


class BaseSession(object):
    """
    A base session interface to implement common functionality:

    - timeout: Set timeout for outgoing requests
    - headers: Additional headers to add to all outgoing requests
    """

    def __init__(self, timeout=(0.5, 3), headers={}, *args, **kwargs):
        super(BaseSession, self).__init__(*args, **kwargs)

        self.mount("http://", TimeoutHTTPAdapter(timeout=timeout))
        self.mount("https://", TimeoutHTTPAdapter(timeout=timeout))

        self.headers.update(headers)


    def request(self, method, url, **kwargs):
        domain = urlparse(url).netloc

        try:
            request = super(BaseSession, self).request(
                method=method, url=url, **kwargs
            )
        except requests.exceptions.Timeout as timeout_error:
            if TIMEOUT_COUNTER:
                TIMEOUT_COUNTER.labels(domain=domain).inc()

            raise timeout_error
        except requests.exceptions.ConnectionError as connection_error:
            if CONNECTION_FAILED_COUNTER:
                CONNECTION_FAILED_COUNTER.labels(domain=domain).inc()

            raise connection_error

        if LATENCY_HISTOGRAM:
            LATENCY_HISTOGRAM.labels(
                domain=domain, code=request.status_code
            ).observe(request.elapsed.total_seconds())

        return request


class UncachedSession(BaseSession, requests.Session):
    """
    A session object for making HTTP requests directly, using the default
    settings from BaseSession
    """

    pass


class CachedSession(BaseSession, requests.Session):
    """
    A session object for making HTTP requests with cached responses.

    Responses for an identical request will be naively returned from the
    cache if the cached copy if less than "expire_after" seconds old.
    """

    def __init__(
        self,
        redis_port='6379', redis_host='localhost', redis_db=0,
        *args,
        **kwargs
    ):

        super(CachedSession, self).__init__(
            *args,
            **kwargs
        )
        pool = redis.ConnectionPool(host=redis_host, port=redis_port, db=redis_db)
        r = redis.Redis(connection_pool=pool)
        self = CacheControl(self, RedisCache(r))
