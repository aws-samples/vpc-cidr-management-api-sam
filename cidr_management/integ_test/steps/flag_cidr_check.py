# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from behave import *
import requests
import json
import logging
from urllib.parse import quote

# Initialize Logger
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)


@when('We issue a request to change a flag for region {region}, cloud {cloud}, CIDR {CIDR} to {assigned}')
def step_impl(context, CIDR, region, assigned, cloud):
    # Form request
    path_params = str(cloud) +"/regions/" + str(region) + "/cidrs/" + quote(str(CIDR), safe='')
    request_url = context.hostname + path_params
    # Prepare request headers
    headers = {
        'authorization': 'Bearer {}'.format(context.access_token),
        'Content-Type': 'application/json'
    }
    # Prepare request body
    body = {
        'assigned': str(assigned)
    }
    # Send request
    LOGGER.info("Request URL {}".format(request_url))
    context.response = requests.put(request_url, headers=headers, data=json.dumps(body))
