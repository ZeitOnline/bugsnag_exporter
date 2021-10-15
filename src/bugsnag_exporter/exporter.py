from prometheus_client.utils import INF, floatToGoString
from datetime import datetime
import argparse
import collections
import logging
import os
import prometheus_client
import prometheus_client.core
import prometheus_client.exposition
import prometheus_client.samples
import requests
import sys
import time


log = logging.getLogger(__name__)
LOG_FORMAT = '%(asctime)s %(levelname)-5.5s %(message)s'


class Cloneable(object):

    def clone(self):
        return type(self)(
            self.name, self.documentation, labels=self._labelnames)


class Gauge(prometheus_client.core.GaugeMetricFamily, Cloneable):
    pass


class Histogram(prometheus_client.core.HistogramMetricFamily, Cloneable):
    pass


class EventCollector:

    _cache_value = None
    _cache_updated_at = 0

    def configure(self, apitoken, cache_ttl, buckets):
        self.apitoken = apitoken
        self.cache_ttl = cache_ttl
        self.buckets = buckets

    METRICS = {
        'events': Histogram(
            'bugsnag_events',
            'Error events collected by Bugsnag, by project',
            labels=['project', 'release_stage']),
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
        for organization in self._paginate('/user/organizations'):
            for project in self._paginate(
                    '/organizations/%s/projects' % organization['id']):
                by_stage = collections.defaultdict(collections.Counter)
                for error in self._paginate(
                        '/projects/%s/errors' % project['id'], **{
                            'filters[error.status][][type]': 'eq',
                            'filters[error.status][][value]': 'open',
                            'sort': 'unsorted',
                        }):
                    for stage in error['release_stages']:
                        count = by_stage[stage]
                        value = error['events']
                        for bucket in self.buckets:
                            if value <= bucket:
                                count[bucket] += 1
                        count[INF] += 1
                        count['sum'] += value

                for stage, counts in by_stage.items():
                    sum_value = counts.pop('sum')
                    buckets = [(floatToGoString(x), counts[x])
                               for x in sorted(counts.keys())]
                    metrics['events'].add_metric(
                        (project['name'], stage), buckets, sum_value)

        stop = time.time()
        metrics['scrape_duration'].add_metric((), stop - start)
        self._cache_value = metrics.values()
        self._cache_updated_at = stop
        return self._cache_value

    BATCH_SIZE = '100'

    def _paginate(self, path, **kw):
        if 'url' in kw:
            time.sleep(8)  # XXX Try to prevent rate limit

        kw.setdefault('per_page', self.BATCH_SIZE)
        r = self._request(path, **kw)
        data = r.json()
        for item in data:
            yield item
        next_link = [v for k, v in r.headers.items()
                     if k == 'Link' and 'rel="next"' in v]
        if next_link:
            link = next_link[0].split(';')[0]
            link = link[1:-1]  # Cut off enclosing `<>`
            for item in self._paginate(None, url=link):
                yield item

    def _request(self, path, url=None, **params):
        if path is not None:
            url = 'https://api.bugsnag.com/' + path
        r = requests.get(url, params=params, headers={
            'Authorization': 'token %s' % self.apitoken,
            'X-Version': '2',
        })
        if not r.ok:
            r.reason = "%s (%s)" % (r.reason, r.text)
        r.raise_for_status()
        return r


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
    parser.add_argument('--buckets', default='10,100,1000,10000,50000,100000',
                        help='Histogram buckets')
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

    buckets = sorted([int(x) for x in options.buckets.split(',')])
    COLLECTOR.configure(options.apitoken, options.ttl, buckets)

    log.info('Listening on 0.0.0.0:%s', options.port)
    httpd = prometheus_client.exposition.make_server(
        options.host, options.port, APP,
        handler_class=prometheus_client.exposition._SilentHandler)
    httpd.serve_forever()
