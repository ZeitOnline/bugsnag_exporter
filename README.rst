========================================
Prometheus Bugsnag error events exporter
========================================

This package exports metrics about `Bugsnag`_ error events as `Prometheus`_ metrics.

.. _`Bugsnag`: https://bugsnag.com
.. _`Prometheus`: https://prometheus.io


Usage
=====

Configure API token
-------------------

You'll need to provide an API token to access the Bugsnag Data Access API.
See the `Bugsnag documentation`_ for details.

.. _`Bugsnag documentation`: https://bugsnagapiv2.docs.apiary.io/#introduction/authentication


Start HTTP service
------------------

Start the HTTP server like this::

    $ BUGSNAG_APITOKEN=MYTOKEN bugsnag_exporter --host=127.0.0.1 --port=9642

Pass ``--ttl=SECONDS`` to cache Bugsnag API results for the given time or -1 to disable (default is 600).
Prometheus considers metrics stale after 300s, so that's the highest scrape_interval one should use.
However it's usually unnecessary to hit the API that often, since the vulnerability alert information does not change that rapidly.

You can pass `--buckets` with a comma-separated list to define the upper bucket bounds that are used to generate the histogram metric.


Configure Prometheus
--------------------

::

    scrape_configs:
      - job_name: 'bugsnag'
        scrape_interval: 300s
        static_configs:
          - targets: ['localhost:9642']

We export one metric, a histogram called ``bugsnag_events``,
with labels ``{project="MyProject", release_stage="production"}``.

A typical alerting PromQL query might be ``bugsnag_events_bucket{le="+Inf",release_stage="production"} - ignoring (le) bugsnag_events_bucket{le="1000.0",release_stage="production"} > 0``

Additionally, a ``bugsnag_scrape_duration_seconds`` gauge is exported.
