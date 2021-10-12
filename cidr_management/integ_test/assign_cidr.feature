@integration_test
@ABGN-TBD-reserve-CIDR-block
Feature: Flag CIDR block of requested size in the requested region

Scenario Outline: Positive Scenario: flag CIDR block
  Given The API PUT v1/clouds/ exists
  And The example CIDR region data for region is loaded into S3
  And The example reserved CIDR data is loaded into DynamoDB
  When We issue a request to change a flag for region <region>, cloud <cloud>, CIDR <CIDR> to <assigned>
  Then The response code of the request is <status>
  And The response message is <response>
  And The <CIDR> is reserved in DynamoDB
  And The DynamoDB row contains region: <region>
  And The DynamoDB row contains locked: <locked>
  And The DynamoDB row contains assigned: <assigned>

    Examples: CIDR requests
       | description                                | token   | region        | cloud |  CIDR              | locked | assigned | status | response            |
       | Change assigned status from false to true  | valid   | us-east-1-bdd | aws   |  192.168.32.0/19   | true   | true     | 200    | CIDR flag updated.  |

Scenario Outline: Negative Scenario: flag CIDR block
  Given The API PUT v1/clouds/ exists
  And The example CIDR region data for region is loaded into S3
  And The example reserved CIDR data is loaded into DynamoDB
  When We issue a request to change a flag for region <region>, cloud <cloud>, CIDR <CIDR> to <assigned>
  Then The response code of the request is <status>
  And The response message is <response>

    Examples: CIDR requests
       | description                                 | token   | region        | cloud | CIDR              | assigned | status | response                                    |
       | No CIDR found                               | valid   | us-east-1-bdd | aws   | 192.171.0.192/26  | true     | 400    | CIDR cannot be assigned.                    |
