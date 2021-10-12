@integration_test
@ABGN-8534-reserve-CIDR-block
Feature: Reserve CIDR block of requested size in the requested region

Scenario Outline: Positive Scenario: reserve CIDR block
  Given The API POST v1/clouds/ exists
  And The example CIDR region data for region is loaded into S3
  And The example reserved CIDR data is loaded into DynamoDB
  When We issue a request to reserve a CIDR with <region>, <size>, <cloud>, and <account> parameters
  Then The response code of the request is <status>
  And The response message is <return_string>
  And The <CIDR> is reserved in DynamoDB
  And The DynamoDB row contains cloud: <cloud>
  And The DynamoDB row contains account: <account>
  And The DynamoDB row contains region: <region>
  And The DynamoDB row contains default locked: true
  And The DynamoDB row contains default assigned: false

    Examples: CIDR requests
       | description                                | token   | cloud | region        | account |  size | status | return_string                           | CIDR                |
       | Exact fit                                  | valid   | aws   | us-east-1-bdd | itx-123 | /19   | 200    | 192.168.224.0/19                        | 192.168.224.0/19    |

Scenario Outline: Negative Scenario: reserve CIDR block
  Given The API POST v1/clouds/ exists
  And The example CIDR region data for region is loaded into S3
  And The example reserved CIDR data is loaded into DynamoDB
  When We issue a request to reserve a CIDR with <region>, <size>, <cloud>, and <account> parameters
  Then The response code of the request is <status>
  And The response message is <response>

    Examples: CIDR requests
       | description                                | token   | cloud | region        | size | status | response                                          | CIDR |
       | CIDR too big                               | valid   | aws   | us-east-1-bdd | /15  | 400    | Invalid CIDR Size.                                | None |
       | CIDR too small                             | valid   | aws   | us-east-1-bdd | /29  | 400    | Invalid CIDR Size.                                | None |
