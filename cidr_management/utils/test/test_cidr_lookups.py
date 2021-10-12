# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import ipaddress
import json
import os
import pytest
from unittest.mock import patch
import boto3

BASE_PATH = os.path.dirname(os.path.realpath(__file__))


class MockBoto3Table(object):
    """Used to mock boto3 DDB calls"""

    def __init__(self):
        self.exceptions = boto3.client('dynamodb', 'us-west-2').exceptions
        self.exceptions.NoSuchEntityException = Exception

    def put_item(self, **kwargs):
        return {'ResponseMetadata': {'HTTPStatusCode': 200}}

    def get_item(self, **kwargs):
        return {'Item': ''}

    def update_item(self, **kwargs):
        return {'ResponseMetadata': {'HTTPStatusCode': 200}}

    def scan(self, **kwargs):
        response = dict()
        response['Items'] = \
            [
                {"cidr_block": "LOCKED"},
                {"region": "us-west-2", "locked": True, "assigned": True, "cidr_block": "10.1.1.0/24", "cloud": "aws"},
                {"region": "us-west-2", "locked": True, "assigned": False, "cidr_block": "10.1.2.0/24", "cloud": "aws"},
                {"region": "us-west-2", "locked": True, "assigned": False, "cidr_block": "10.1.3.0/24", "cloud": "aws"}
            ]
        return response


class MockBoto3S3Object(object):
    """Used to mock boto3 S3_Object calls"""

    def __init__(self):
        self.exceptions = boto3.client('s3', 'us-west-2').exceptions
        self.exceptions.NoSuchEntityException = Exception

    def put(self, **kwargs):
        return {'ResponseMetadata': {'HTTPStatusCode': '200'}}

    def delete(self, **kwargs):
        return {'ResponseMetadata': {'HTTPStatusCode': '200'}}


@patch('boto3.resource')
def test_reserve_cidr(mock_ddb_resource):
    # Import
    from utils import cidr_lookups
    # Setup mocks
    mock_ddb_resource().Table.return_value = MockBoto3Table()
    # Invoke method
    result = cidr_lookups.reserve_cidr('10.0.1.0/24', 'us-west-2', 'itx-001', 'aws', 'MockDDBTable')
    # Evaluate results
    assert result['statusCode'] == 200
    assert result['body'] == '10.0.1.0/24'


@patch('boto3.resource')
def test_update_cidr_flag_locked(mock_ddb_resource):
    # Import
    from utils import cidr_lookups
    # Setup mocks
    mock_ddb_resource().Table.return_value = MockBoto3Table()
    # Invoke method
    result = cidr_lookups.update_cidr_flag('10.0.1.0/24', False, 'aws', 'us-east-1', 'MockDDBTable')
    # Evaluate results
    assert result['statusCode'] == 200


@patch('boto3.resource')
def test_update_cidr_flag_assigned(mock_ddb_resource):
    # Import
    from utils import cidr_lookups
    # Setup mocks
    mock_ddb_resource().Table.return_value = MockBoto3Table()
    # Invoke method
    result = cidr_lookups.update_cidr_flag('10.0.1.0/24', True, 'aws', 'us-east-1', 'MockDDBTable')
    # Evaluate results
    assert result is not None


@patch('boto3.resource')
def test_retrieve_used_cidrs(mock_ddb_resource):
    # Import
    from utils import cidr_lookups
    # Setup mocks
    mock_ddb_resource().Table.return_value = MockBoto3Table()
    # Invoke method
    result = cidr_lookups.retrieve_used_cidrs("us-west-2", False, False, 'aws', 'MockDDBTable')
    # Evaluate results
    assert result == ['10.1.1.0/24', '10.1.2.0/24', '10.1.3.0/24']


def read_mock_data(filename):
    # Read mock data
    file_reader = open(BASE_PATH + '/mock_data/lambda_events/' + filename, 'r')
    file_content = json.load(file_reader)
    file_reader.close()
    return file_content


def return_input_output_tuple(input_event, expected_output):
    # Return as tuple
    return read_mock_data(input_event), read_mock_data(expected_output)


@pytest.mark.parametrize("mock_input, expected_output",
                         [return_input_output_tuple('get_event_success.json', 'get_event_params.json')])
def test_extract_request_params_success(mock_input, expected_output):
    from utils import cidr_lookups
    params = cidr_lookups.extract_request_params(mock_input)
    for key in expected_output.keys():
        assert params[key] == expected_output[key]


@pytest.mark.parametrize("mock_input, expected_output",
                         [return_input_output_tuple('put_event_success.json',
                                                    'put_event_params.json')])
def test_extract_put_request_params_success(mock_input, expected_output):
    from utils import cidr_lookups
    params = cidr_lookups.extract_put_request_params(mock_input)
    for key in expected_output.keys():
        assert params[key] == expected_output[key]


@pytest.mark.parametrize("mock_input, expected_output",
                         [return_input_output_tuple('post_event_success.json', 'post_event_params.json')])
def test_extract_post_request_params_success(mock_input, expected_output):
    # Import
    from utils import cidr_lookups
    # Invoke
    params = cidr_lookups.extract_post_request_params(mock_input)
    # Evaluate results
    for key in expected_output.keys():
        assert params[key] == expected_output[key]


def test_extract_post_request_params_error():
    # Import
    from utils import cidr_lookups
    from utils.cidr_lookups import InputValidationError
    # Setup mocks
    input_event = read_mock_data('post_event_error.json')
    # Invoke
    with pytest.raises(InputValidationError) as e:
        cidr_lookups.extract_post_request_params(input_event)
    # Evaluate results
    assert e.value.args[0] == 'Missing account alias.'


@patch('boto3.client')
def test_retrieve_region_cidr(mock_boto_client):
    # Import
    from utils import cidr_lookups
    # Setup mocks
    file_reader = open(BASE_PATH + '/mock_data/region_cidr_blocks/assignments.json', "rb")
    mock_response = file_reader.read()
    file_reader.close()
    mock_boto_client().get_parameter.return_value = json.loads(mock_response)
    # Invoke
    result = cidr_lookups.retrieve_region_cidr('us-east-1', 'aws2')
    # Evaluate results
    assert result == ["192.171.0.0/16"]


@patch('boto3.client')
def test_retrieve_alt_region_cidr(mock_boto_client):
    # Import
    from utils import cidr_lookups
    # Setup mocks
    file_reader = open(BASE_PATH + '/mock_data/region_cidr_blocks/assignments.json', "rb")
    mock_response = file_reader.read()
    file_reader.close()
    mock_boto_client().get_parameter.return_value = json.loads(mock_response)
    # Invoke
    result = cidr_lookups.retrieve_region_cidr('us-east-1', 'aws2')
    # Evaluate results
    assert result == ["192.171.0.0/16"]


def test_valid_available_cidr_data():
    # Import
    from utils import cidr_lookups
    # Iterate over scenarios
    data_directory = BASE_PATH + '/mock_data/valid_data_cidr_search/'
    for entry in os.listdir(data_directory):
        if os.path.isfile(os.path.join(data_directory, entry)):
            # Setup mocks
            file_reader = open(data_directory + entry, 'r')
            mock_input_data = file_reader.read()
            file_reader.close()
            input_data = json.loads(mock_input_data)
            # Invoke
            response = cidr_lookups.find_available_cidr(input_data['master_cidr_list'],
                                                        input_data['allocated_cidr_list'], input_data['prefix'])
            # Evaluate results
            assert response == ipaddress.IPv4Network(input_data['expected_response'])


def test_error_available_cidr_data():
    # Import
    from utils import cidr_lookups
    # Iterate over scenarios
    data_directory = BASE_PATH + '/mock_data/invalid_data_cidr_search/'
    for entry in os.listdir(data_directory):
        # Setup mocks
        file_reader = open(data_directory + entry, 'r')
        mock_input_data = file_reader.read()
        file_reader.close()
        input_data = json.loads(mock_input_data)
        # Invoke and evaluate results
        try:
            cidr_lookups.find_available_cidr(input_data['master_cidr_list'],
                                             input_data['allocated_cidr_list'],
                                             input_data['prefix'])

        except Exception as e:
            if isinstance(e, cidr_lookups.SubnetSizeError) or isinstance(e, cidr_lookups.NoValidSubnetError):
                assert True


def test_valid_list_all_cidrs():
    # Import
    from utils import cidr_lookups
    # Iterate over scenarios
    data_directory = BASE_PATH + '/mock_data/all_available_cidr/valid/'
    for entry in os.listdir(data_directory):
        if os.path.isfile(os.path.join(data_directory, entry)):
            # Setup mocks
            file_reader = open(data_directory + entry, 'r')
            mock_input_data = file_reader.read()
            file_reader.close()
            input_data = json.loads(mock_input_data)
            # Invoke
            response = cidr_lookups.list_all_available_cidr(input_data['master_cidr_list'],
                                                        input_data['allocated_cidr_list'], input_data['prefix'])
            # Evaluate results
            expected_response = input_data['expected_response'].strip('"')
            assert "{}".format(response) == expected_response


def test_invalid_list_all_cidrs():
    # Import
    from utils import cidr_lookups
    # Iterate over scenarios
    data_directory = BASE_PATH + '/mock_data/all_available_cidr/invalid/'
    for entry in os.listdir(data_directory):
        if os.path.isfile(os.path.join(data_directory, entry)):
            # Setup mocks
            file_reader = open(data_directory + entry, 'r')
            mock_input_data = file_reader.read()
            file_reader.close()
            input_data = json.loads(mock_input_data)
            # Invoke
            response = cidr_lookups.list_all_available_cidr(input_data['master_cidr_list'],
                                                            input_data['allocated_cidr_list'],
                                                            input_data['prefix'])


def test_strtobool_success():
    # Import
    from utils.cidr_lookups import str_to_bool
    # Setup mocks
    params = ["True", "False"]
    expected_result = [True, False]
    # Invoke and eval results
    for idx, i in enumerate(params):
        assert str_to_bool(i) == expected_result[idx]
