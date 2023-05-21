#!/usr/bin/env python

import sys
import os
import argparse
import logging
import socket
from typing import Generator, Dict, Optional
import atexit
from time import time

from dotenv import load_dotenv
import requests
from wsgiref.simple_server import make_server, WSGIServer
from prometheus_client.core import REGISTRY, GaugeMetricFamily, Metric
from prometheus_client.exposition import make_wsgi_app, _SilentHandler
from prometheus_client.samples import Sample
from rfidclient.doorstate import DoorState

FORMAT = "[%(asctime)s %(levelname)s] %(message)s"
logging.basicConfig(level=logging.WARNING, format=FORMAT)
logger = logging.getLogger()

load_dotenv(dotenv_path="/etc/default/rfidclient")
ZONE: str = os.getenv("ZONE")


class LabeledGaugeMetricFamily(Metric):
    """Not sure why the upstream one doesn't allow labels..."""

    def __init__(
        self,
        name: str,
        documentation: str,
        value: Optional[float] = None,
        labels: Dict[str, str] = None,
        unit: str = '',
    ):
        Metric.__init__(self, name, documentation, 'gauge', unit)
        if labels is None:
            labels = {}
        self._labels = labels
        if value is not None:
            self.add_metric(labels, value)

    def add_metric(self, labels: Dict[str, str], value: float) -> None:
        """Add a metric to the metric family.
        Args:
          labels: A dictionary of labels
          value: A float
        """
        self.samples.append(
            Sample(self.name, dict(labels | self._labels), value, None)
        )


class RfidClientCollector:

    def __init__(self):
        logger.debug('Instantiating RfidClientCollector')
        self.shm: SharedMemory = SharedMemory(name='doorstateshm', create=False)
        atexit.register(lambda: self.shm.close())

    def collect(self) -> Generator[Metric, None, None]:
        ds: DoorState = DoorState.from_shm_buffer(self.shm)
        yield LabeledGaugeMetricFamily(
            'rfidclient_door_is_open', 'Whether the door is open (1) or not (0)',
            value=ds.door_is_open, labels={'zone': ZONE}, unit=''
        )
        yield LabeledGaugeMetricFamily(
            'rfidclient_process_uptime',
            'rfidclient process uptime in seconds',
            value=ds.process_uptime_seconds, labels={'zone': ZONE},
            unit='seconds'
        )
        yield LabeledGaugeMetricFamily(
            'rfidclient_door_opened_ago',
            'rfidclient time since door was last opened',
            value=ds.seconds_since_opened, labels={'zone': ZONE},
            unit='seconds'
        )
        yield LabeledGaugeMetricFamily(
            'rfidclient_door_closed_ago',
            'rfidclient time since door was last closed',
            value=ds.seconds_since_closed, labels={'zone': ZONE},
            unit='seconds'
        )
        yield LabeledGaugeMetricFamily(
            'rfidclient_authorized_scans',
            'rfidclient number of authorized scans since process started',
            value=ds.authorized_scans, labels={'zone': ZONE},
        )
        yield LabeledGaugeMetricFamily(
            'rfidclient_unauthorized_scans',
            'rfidclient number of unauthorized scans since process started',
            value=ds.unauthorized_scans, labels={'zone': ZONE},
        )


def _get_best_family(address, port):
    """
    Automatically select address family depending on address
    copied from prometheus_client.exposition.start_http_server
    """
    # HTTPServer defaults to AF_INET, which will not start properly if
    # binding an ipv6 address is requested.
    # This function is based on what upstream python did for http.server
    # in https://github.com/python/cpython/pull/11767
    infos = socket.getaddrinfo(address, port)
    family, _, _, _, sockaddr = next(iter(infos))
    return family, sockaddr[0]


def serve_exporter(port: int, addr: str = '0.0.0.0'):
    """
    Copied from prometheus_client.exposition.start_http_server, but doesn't run
    in a thread because we're just a proxy.
    """

    class TmpServer(WSGIServer):
        """Copy of WSGIServer to update address_family locally"""

    TmpServer.address_family, addr = _get_best_family(addr, port)
    app = make_wsgi_app(REGISTRY)
    httpd = make_server(
        addr, port, app, TmpServer, handler_class=_SilentHandler
    )
    httpd.serve_forever()


def parse_args(argv):
    p = argparse.ArgumentParser(description='Prometheus RfidClient exporter')
    p.add_argument(
        '-v', '--verbose', dest='verbose', action='count', default=0,
        help='verbose output. specify twice for debug-level output.'
    )
    PORT_DEF = int(os.environ.get('PORT', '8080'))
    p.add_argument(
        '-p', '--port', dest='port', action='store', type=int,
        default=PORT_DEF, help=f'Port to listen on (default: {PORT_DEF})'
    )
    args = p.parse_args(argv)
    return args


def set_log_info():
    set_log_level_format(
        logging.INFO, '%(asctime)s %(levelname)s:%(name)s:%(message)s'
    )


def set_log_debug():
    set_log_level_format(
        logging.DEBUG,
        "%(asctime)s [%(levelname)s %(filename)s:%(lineno)s - "
        "%(name)s.%(funcName)s() ] %(message)s"
    )


def set_log_level_format(level: int, format: str):
    """
    Set logger level and format.

    :param level: logging level; see the :py:mod:`logging` constants.
    :type level: int
    :param format: logging formatter format string
    :type format: str
    """
    formatter = logging.Formatter(fmt=format)
    logger.handlers[0].setFormatter(formatter)
    logger.setLevel(level)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    if args.verbose > 1:
        set_log_debug()
    elif args.verbose == 1:
        set_log_info()
    REGISTRY.register(RfidClientCollector())
    logger.info('Starting HTTP server on port %d', args.port)
    serve_exporter(args.port)
