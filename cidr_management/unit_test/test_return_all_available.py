# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# pylint: skip-file
"""Unit tests for return_available function"""
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


# test statusCode=404, No root CIDR list found
@patch('utils.cidr_lookups.extract_request_params')
@patch('utils.cidr_lookups.retrieve_region_cidr')
def test_handler_root_cidr_not_found(mock_retrieve_region_cidr,
                                     mock_extract_request_params):
    # Import
    from utils import cidr_lookups
    # Import cidr lock
    from cidr_management import return_all_available
    # Setup mock behavior
    mock_extract_request_params.return_value = {}
    mock_retrieve_region_cidr.side_effect = [cidr_lookups.MissingRegionError]
    # Call method
    result = return_all_available.handler(None, None)
    assert result['statusCode'] == 404
    assert result['body'] == 'No root CIDR list found for the specified region.'


# test statusCode=400, Bad Request. Cloud Provider not found
@patch('utils.cidr_lookups.extract_request_params')
def test_handler_bad_request(mock_extract_request_params):
    # Import
    from cidr_management import return_all_available
    from utils.cidr_lookups import InputValidationError
    # Setup mock behavior
    mock_extract_request_params.side_effect = InputValidationError('Invalid Cloud Provider.')
    # Call method
    result = return_all_available.handler(None, None)
    assert result['statusCode'] == 400
    assert result['body'] == 'Invalid Cloud Provider.'


# test statusCode=200, returns available cidr list
@patch('utils.cidr_lookups.extract_request_params')
@patch('utils.cidr_lookups.retrieve_used_cidrs')
@patch('utils.cidr_lookups.list_all_available_cidr')
@patch('utils.cidr_lookups.retrieve_region_cidr')
def test_handler_return_available_cidr(mock_retrieve_region_cidr,
                                       mock_list_all_available_cidr,
                                       mock_retrieve_used_cidrs,
                                       mock_extract_request_params):
    # Import
    from cidr_management import return_all_available
    # Setup mock behavior
    mock_retrieve_used_cidrs.return_value = [""]
    mock_list_all_available_cidr.return_value = ["10.1.0.0/27"]
    mock_extract_request_params.return_value = {
        'region': 'us-west-2',
        'assigned': False,
        'locked': False,
        'size': 27,
        'cloud_provider': 'AWS'
    }
    mock_retrieve_region_cidr.return_value = ["10.1.0.0/16"]
    # Call method
    result = return_all_available.handler(None, None)
    assert result['statusCode'] == 200
    assert result['body'] == '{"cidrs": ["10.1.0.0/27"]}'


# test statusCode=404, No available CIDRs found
@patch('utils.cidr_lookups.extract_request_params')
@patch('utils.cidr_lookups.retrieve_used_cidrs')
@patch('utils.cidr_lookups.list_all_available_cidr')
@patch('utils.cidr_lookups.retrieve_region_cidr')
def test_handler_return_no_available_cidr(mock_retrieve_region_cidr,
                                          mock_list_all_available_cidr,
                                          mock_retrieve_used_cidrs,
                                          mock_extract_request_params):
    # Import
    from cidr_management import return_all_available
    mock_retrieve_used_cidrs.return_value = [""]
    mock_list_all_available_cidr.return_value = []
    mock_extract_request_params.return_value = {
        'region': 'us-west-2',
        'assigned': False,
        'locked': False,
        'size': 16,
        'cloud_provider': 'AWS'
    }
    mock_retrieve_region_cidr.return_value = ["10.1.0.0/16"]
    # Call method
    result = return_all_available.handler(None, None)
    assert result['statusCode'] == 404
    assert result['body'] == "No CIDR blocks of appropriate size found."


# test statusCode=500, Exception thrown
@patch('utils.cidr_lookups.extract_request_params')
@patch('utils.cidr_lookups.retrieve_used_cidrs')
@patch('utils.cidr_lookups.list_all_available_cidr')
@patch('utils.cidr_lookups.retrieve_region_cidr')
def test_handler_return_exception(mock_retrieve_region_cidr,
                                  mock_list_all_available_cidr,
                                  mock_retrieve_used_cidrs,
                                  mock_extract_request_params):
    # Import
    from cidr_management import return_all_available
    mock_retrieve_used_cidrs.return_value = [""]
    mock_list_all_available_cidr.return_value = []
    mock_extract_request_params.return_value = {
        'region': 'us-west-2',
        'assigned': False,
        'locked': False,
        'size': 16,
        'cloud_provider': 'AWS'
    }
    mock_retrieve_region_cidr.side_effect = Exception("Mock exception")
    # Call method
    result = return_all_available.handler(None, None)
    assert result['statusCode'] == 500
