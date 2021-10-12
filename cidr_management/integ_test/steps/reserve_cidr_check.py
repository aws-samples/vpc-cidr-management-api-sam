# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from behave import *
import requests
import logging

# Initialize Logger
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)


@when('We issue a request to reserve a CIDR with {region}, {size}, {cloud}, and {account} parameters')
def step_impl(context, region, size, cloud, account):
    # Form request headers
    query_params = str(cloud) + "/regions/" + str(region) + "/cidrs"
    request_url = context.hostname + query_params
    # Prepare request headers
    headers = {
        'authorization': 'Bearer {}'.format(context.access_token),
        'Content-Type': 'application/json'
    }
    # Form request body
    request_body = {
        "size": size,
        "account_alias": account,
        "ticket_num": "1234"
    }
    # Send request
    LOGGER.info("Request URL for Reserve CIDR {}, request body is {}".format(request_url, request_body))
    context.response = requests.post(request_url, headers=headers, json=request_body)
    LOGGER.info("Response details are {} & {}".format(context.response, context.response.text))


@then('The DynamoDB row contains default locked: true')
def step_impl(context):
    # Get ddb item stored in context
    ddb_item = context.cidr_item
    LOGGER.info("DDB Item retrieved from context: {}".format(ddb_item))
    assert ddb_item['locked']


@then('The DynamoDB row contains default assigned: false')
def step_impl(context):
    # Get ddb item stored in context
    ddb_item = context.cidr_item
    LOGGER.info("DDB Item retrieved from context: {}".format(ddb_item))
    assert not ddb_item['assigned']
