from datetime import datetime
import argparse
import logging
import os
import prometheus_client
import prometheus_client.core
import prometheus_client.exposition
import requests
import sys
import time


log = logging.getLogger(__name__)
LOG_FORMAT = '%(asctime)s %(levelname)-5.5s %(message)s'


class Gauge(prometheus_client.core.GaugeMetricFamily):

    def clone(self):
        return type(self)(
            self.name, self.documentation, labels=self._labelnames)


class EventCollector:

    _cache_value = None
    _cache_updated_at = 0

    def configure(self, apitoken, cache_ttl):
        self.apitoken = apitoken
        self.cache_ttl = cache_ttl

    METRICS = {
        'events': Gauge(
            'bugsnag_events',
            'Error events collected by Bugsnag, by project',
            labels=['project']),
        'scrape_duration': Gauge(
            'bugsnag_scrape_duration_seconds',
            'Duration of Bugsnag API scrape'),
    }

    def describe(self):
        return self.METRICS.values()

    def collect(self):
        start = time.time()

        if start - self._cache_updated_at <= self.cache_ttl:
            log.info('Returning cached result from %s',
                     datetime.fromtimestamp(self._cache_updated_at))
            return self._cache_value

        # Use a separate instance for each scrape request, to prevent
        # race conditions with simultaneous scrapes.
        metrics = {
            key: value.clone() for key, value in self.METRICS.items()}

        log.info('Retrieving data from Bugsnag API')
        has_next = True
        while has_next:
            break
            metrics['events'].add_metric((project,), count)
        stop = time.time()
        metrics['scrape_duration'].add_metric((), stop - start)
        self._cache_value = metrics.values()
        self._cache_updated_at = stop
        return self._cache_value

    BATCH_SIZE = 50

    def _request(self, request, **params):
        verb, path = request.split(' ')
        method = getattr(requests, verb.lower())
        r = method(
            'https://api.bugsnag.com/' + path, params=params,
            headers={
                'Authorization': 'token %s' % self.apitoken,
                'X-Version': '2',
            })
        r.raise_for_status()
        return r.json()


COLLECTOR = EventCollector()
# We don't want the `process_` and `python_` metrics, we're a collector,
# not an exporter.
REGISTRY = prometheus_client.core.CollectorRegistry()
REGISTRY.register(COLLECTOR)
APP = prometheus_client.make_wsgi_app(REGISTRY)


def main():
    parser = argparse.ArgumentParser(
        description='Export bugsnag events as prometheus metrics')
    parser.add_argument('--apitoken', help='Bugsnag API token')
    parser.add_argument('--host', default='', help='Listen host')
    parser.add_argument('--port', default=9642, type=int, help='Listen port')
    parser.add_argument('--ttl', default=600, type=int, help='Cache TTL')
    options = parser.parse_args()
    if not options.apitoken:
        options.apitoken = os.environ.get('BUGSNAG_APITOKEN')

    if not options.apitoken:
        parser.print_help()
        raise SystemExit(1)
    logging.basicConfig(
        stream=sys.stdout, level=logging.INFO, format=LOG_FORMAT)

    COLLECTOR.configure(options.apitoken, options.ttl)

    log.info('Listening on 0.0.0.0:%s', options.port)
    httpd = prometheus_client.exposition.make_server(
        options.host, options.port, APP,
        handler_class=prometheus_client.exposition._SilentHandler)
    httpd.serve_forever()
