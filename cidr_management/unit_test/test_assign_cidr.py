# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# pylint: skip-file
"""Unit tests for flag function"""
import os
from unittest import mock
from unittest.mock import patch
import pytest
import sys

BASE_PATH = os.path.dirname(__file__)
sys.path.append(os.path.join(BASE_PATH, '..'))
sys.path.append(os.path.join(BASE_PATH, '../..'))

MOCK_ENV_VARS = {
    "LDAP_SERVER": "mock",
    "LDAP_USERNAME": "mock",
    "SHARED_LDAP_PASSWORD_SECRET_NAME": "mock",
    "LDAP_SEARCH_BASE": "mock",
    "LDAP_OBJECT_CLASS": "mock",
    "LDAP_GROUP_NAME": "mock",
    "LDAP_LOOKUP_ATTRIBUTE": "mock",
    "MSFT_IDP_TENANT_ID": "mock",
    "MSFT_IDP_APP_ID": "mock",
    "MSFT_IDP_CLIENT_ROLES": "mock",
    "ALLOCATED_CIDR_DDB_TABLE_NAME": "mock"
}


@pytest.fixture(autouse=True)
def mock_settings_env_vars():
    with mock.patch.dict(os.environ, MOCK_ENV_VARS):
        yield


@pytest.fixture(autouse=True)
def mock_obtain_table_lock():
    with mock.patch('utils.cidr_lock.sync_obtain_table_lock') as mock_table_lock:
        mock_table_lock.return_value = True
        yield mock_table_lock


@pytest.fixture(autouse=True)
def mock_clear_table_lock():
    with mock.patch('utils.cidr_lock.clear_table_lock') as mock_clear_table_lock:
        mock_clear_table_lock.return_value = True
        yield mock_clear_table_lock


# test statusCode=404, CIDR block not found
@patch('utils.cidr_lookups.extract_put_request_params')
@patch('utils.cidr_lookups.update_cidr_flag')
@patch('utils.cidr_lookups.retrieve_region_cidr')
def test_handler_root_cidr_not_found(mock_retrieve_region_cidr,
                                     mock_update_cidr_flag,
                                     mock_extract_put_request_params):

    # Import
    from cidr_management import assign_cidr
    # Setup mock behavior
    mock_retrieve_region_cidr.return_value = None
    mock_extract_put_request_params.return_value = {}
    mock_update_cidr_flag.return_value = {
        'statusCode': 404
    }
    # Call method
    result = assign_cidr.handler(None, None)
    assert result['statusCode'] == 404


# test statusCode=400, Bad Request. Cloud Provider not found
@patch('utils.cidr_lookups.extract_put_request_params')
def test_handler_bad_request(mock_extract_put_request_params):

    # Import
    from cidr_management import assign_cidr
    from utils.cidr_lookups import InputValidationError
    # Setup mock behavior
    mock_extract_put_request_params.side_effect = InputValidationError('Invalid Cloud Provider.')
    # Call method
    result = assign_cidr.handler(None, None)
    assert result['statusCode'] == 400
    assert result['body'] == 'Invalid Cloud Provider.'

