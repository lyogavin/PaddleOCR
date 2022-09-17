
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v1.api.events_api import EventsApi
from datadog_api_client.v1.model.event_create_request import EventCreateRequest


from datetime import datetime

from datadog_api_client.v1.api.metrics_api import MetricsApi
from datadog_api_client.v1.model.metrics_payload import MetricsPayload
from datadog_api_client.v1.model.point import Point
from datadog_api_client.v1.model.series import Series


import sys

import os, logging
sys.path.append('../utils')
import logging_utils
logger = logging.getLogger(__name__)

import socket
hostname = socket.gethostname()

configuration = Configuration()


configuration.api_key["apiKeyAuth"] = "8aa814353c94254b915cbe7b95224a25"
configuration.api_key["appKeyAuth"] = "7f202d85164da88cb6b5dcb08de3f7126d8fa3b8"
configuration.server_variables["site"] = "us5.datadoghq.com"


with ApiClient(configuration) as api_client:


    #https://github.com/DataDog/datadog-api-client-python/blob/72345f8108fe2b6d3a7f10be7507cc8d2a926c74/src/datadog_api_client/v1/model/event_create_request.py#L12
    def send_datadog_event(title, tags, message="msg"):
        try:
            tags.append(f"PID-{os.getpid()}")
            body = EventCreateRequest(
                title=title,
                text=message,
                host=hostname,
                tags=tags,
            )

            api_instance = EventsApi(api_client)
            response = api_instance.create_event(body=body)

            logger.debug(f"datadog api response: {response}")

            return response
        except Exception as err:
            logger.warning(f"datadog err: {err}")


    #https://github.com/DataDog/datadog-api-client-python/blob/master/examples/v1/metrics/SubmitMetrics.py
    #
    #https://github.com/DataDog/datadog-api-client-python/blob/a707ce3ae4fc530779d2e31eac5776eb48fa752f/src/datadog_api_client/v1/model/series.py#L13
    def send_datadog_metric(name, value, tags):
        try:
            tags.append(f"PID-{os.getpid()}")

            body = MetricsPayload(
                series=[
                    Series(
                        metric=name,
                        type="gauge",
                        host=hostname,
                        points=[
                            Point(
                                [
                                    datetime.now().timestamp(),
                                    value,
                                ]
                            ),
                        ],
                        tags=tags,
                    ),
                ],
            )

            api_instance = MetricsApi(api_client)
            response = api_instance.submit_metrics(body=body)

            logger.debug(f"datadog api response: {response}")

            return response
        except Exception as err:
            logger.warning(f"datadog err: {err}")

if __name__ == '__main__':
    import random
    ri = random.randint(0,100)
    print(f"test sending event rand int {ri}")
    r = send_datadog_event('test', ['test'])
    print(r)

    print(f"test sending metric rand int {ri}")
    r = send_datadog_metric(f'test_{ri}', ri, ['test'])
    print(r)