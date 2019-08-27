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
See the `Bugsnag documentation` for details.

.. `Bugsnag documentation`: https://bugsnagapiv2.docs.apiary.io/#introduction/authentication


Start HTTP service
------------------

Start the HTTP server like this::

    $ BUGSNAG_APITOKEN=MYTOKEN bugsnag_exporter --host=127.0.0.1 --port=9642

Pass ``--ttl=SECONDS`` to cache Bugsnag API results for the given time or -1 to disable (default is 600).
Prometheus considers metrics stale after 300s, so that's the highest scrape_interval one should use.
However it's usually unnecessary to hit the API that often, since the vulnerability alert information does not change that rapidly.


Configure Prometheus
--------------------

::

    scrape_configs:
      - job_name: 'bugsnag'
        scrape_interval: 1800s
        static_configs:
          - targets: ['localhost:9642']

We export one metric, a gauge called ``bugsnag_events``,
with labels ``{project="MyProject"}``.

Additionally, a ``bugsnag_scrape_duration_seconds`` gauge is exported.
