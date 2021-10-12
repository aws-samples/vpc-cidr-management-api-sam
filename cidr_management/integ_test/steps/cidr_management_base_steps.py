# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from behave import *
import requests
import json
import logging
from utils import cidr_lookups
from utils.bdd_utils import bdd_utils

# Initialize Logger
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)


@given('The API GET v1/clouds/ exists')
def step_impl(context):
    # Check load balancer DNS name is set in context variable
    assert bool(context.hostname) is True
    # Check if endpoint is reachable
    response = requests.get(context.hostname)
    assert response.status_code < 500


@given('The API PUT v1/clouds/ exists')
def step_impl(context):
    # Check load balancer DNS name is set in context variable
    assert bool(context.hostname) is True
    # Check if endpoint is reachable
    response = requests.put(context.hostname)
    assert response.status_code < 500


@given('The API POST v1/clouds/ exists')
def step_impl(context):
    # Check load balancer DNS name is set in context variable
    assert bool(context.hostname) is True
    # Check if endpoint is reachable
    response = requests.post(context.hostname)
    assert response.status_code < 500

@given('The example CIDR region data for region is loaded into S3')
def step_impl(context):
    assert context.cidr_file is True


@given('The example reserved CIDR data is loaded into DynamoDB')
def step_impl(context):
    assert context.reserved_cidr_data is True


@then('The response code of the request is {status}')
def step_impl(context, status):
    assert int(status) == int(context.response.status_code)


@then('The response message is {return_string}')
def step_impl(context, return_string):
    # If returning actual data, need to cast to JSON
    if "cidrs" in context.response.text:
        json_response = json.loads(context.response.text)
        LOGGER.info("Expected response {}, actual response {}".format(return_string, json_response['cidrs']))
        assert str(json_response['cidrs']) == return_string
    # If returning string, simply need to evaluate string
    else:
        assert context.response.text == return_string


@then('The {CIDR} is reserved in DynamoDB')
def step_impl(context, CIDR):
    # Get item from dynamodb
    LOGGER.info("Retrieving CIDR from DynamoDB: {}".format(CIDR))
    response = bdd_utils.get_dynamodb_entry(CIDR, context.cidr_ddb_table_name)
    LOGGER.info("bdd_utils.get_dynamodb_entry() response: {}".format(response))
    # Validate response statusCode
    assert response['statusCode'] == 200
    # Set Item in context for subsequent validation
    context.cidr_item = response['body']

@step('The {CIDR} in region: {region} is in assigned: {assigned} and locked: {locked} state')
def step_impl(context, CIDR, region, assigned, locked):
    # Get item from dynamodb
    LOGGER.info("Retrieving CIDR from DynamoDB: {}".format(CIDR))
    response = bdd_utils.get_dynamodb_entry(CIDR, context.cidr_ddb_table_name)
    LOGGER.info("bdd_utils.get_dynamodb_entry() response: {}".format(response))
    # Validate response statusCode
    assert response['statusCode'] == 200
    # Validate assigned, locked state
    assert response['body']['region'] == region.upper()
    assert  response['body']['locked'] == cidr_lookups.str_to_bool(locked)
    assert response['body']['assigned'] == cidr_lookups.str_to_bool(assigned)
    # Set Item in context for subsequent validation
    context.cidr_item = response['body']


@then('The DynamoDB row contains region: {region}')
def step_impl(context, region):
    # Get ddb item stored in context
    ddb_item = context.cidr_item
    LOGGER.info("DDB Item retrieved from context: {}".format(ddb_item))
    assert ddb_item['region'] == region.upper()


@then('The DynamoDB row contains locked: {locked}')
def step_impl(context, locked):
    # Get ddb item stored in context
    ddb_item = context.cidr_item
    LOGGER.info("DDB Item retrieved from context: {}".format(ddb_item))
    assert ddb_item['locked'] == cidr_lookups.str_to_bool(locked)


@then('The DynamoDB row contains assigned: {assigned}')
def step_impl(context, assigned):
    # Get ddb item stored in context
    ddb_item = context.cidr_item
    LOGGER.info("DDB Item retrieved from context: {}".format(ddb_item))
    assert ddb_item['assigned'] == cidr_lookups.str_to_bool(assigned)


@then('The DynamoDB row contains cloud: {cloud}')
def step_impl(context, cloud):
    # Get ddb item stored in context
    ddb_item = context.cidr_item
    LOGGER.info("DDB Item retrieved from context: {}".format(ddb_item))
    assert ddb_item['cloud'].upper() == cloud.upper()


@then('The DynamoDB row contains account: {account}')
def step_impl(context, account):
    # Get ddb item stored in context
    ddb_item = context.cidr_item
    LOGGER.info("DDB Item retrieved from context: {}".format(ddb_item))
    assert ddb_item['account_alias'].upper() == account.upper()
