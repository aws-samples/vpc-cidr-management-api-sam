# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# pylint: skip-file
from behave import *
import requests
import logging

# Initialize Logger
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)


@when('We issue a request with {region}, {size}, {locked}, {cloud}, and {assigned} parameters')
def step_impl(context, region, cloud, size, locked, assigned):
    # Form request
    query_params = str(cloud) + "/regions/" + str(region) + "/cidrs?assigned=" + str(assigned) + "&locked=" + str(locked) + "&size=" + size
    request_url = context.hostname + query_params
    # Prepare request headers
    headers = {
        'authorization': 'Bearer {}'.format(context.access_token),
        'Content-Type': 'application/json'
    }
    # Send request
    LOGGER.info("Request URL {}".format(request_url))
    context.response = requests.get(request_url, headers=headers)
