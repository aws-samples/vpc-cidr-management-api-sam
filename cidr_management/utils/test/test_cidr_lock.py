# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
from unittest.mock import patch


class MockBoto3Table(object):
    """Used to mock boto3 DDB calls"""

    def __init__(self):
        self.exceptions = boto3.client('dynamodb', 'us-west-2').exceptions

    def put_item(self, **kwargs):
        return {'ResponseMetadata': {'HTTPStatusCode': 200}}

    def delete_item(self, **kwargs):
        return None


@patch('boto3.resource')
def test_lock_cidr(mock_ddb_resource):
    # Import
    from utils import cidr_lock
    # Setup mocks
    mock_ddb_resource().Table.return_value = MockBoto3Table()
    # Invoke method
    result = cidr_lock.sync_obtain_table_lock("mock")
    # Evaluate results
    assert result


@patch('boto3.resource')
def test_clear_lock(mock_ddb_resource):
    # Import
    from utils import cidr_lock
    # Setup mocks
    mock_ddb_resource().Table.return_value = MockBoto3Table()
    # Invoke method
    result = cidr_lock.clear_table_lock("mock")
    # Evaluate results
    assert result
