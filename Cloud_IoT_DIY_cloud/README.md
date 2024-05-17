
## Prerequisites
- Python 3.9
- AWS CLI
- CDK
- created and activated virtual environment `infra_venv` for infrastructure code and `lambda_venv` for lambda code using `infra_requirements.txt` and `lambda_requirements.txt` respectively
    - NOTE that each Lambda can have it's own `requirements.txt`. This is a convenient way to have different requirements for different Lambda Functions and for local/cloud. For example:
        - boto3 is available for any Lambda by default so you can include boto3 to `lambda_requirements.txt` to develop/debug locally but skip it in lambda specific `requirements.txt`
        - aiofiles is required for `LocalFolder` Datasource implementation only. Uou can include boto3 to `lambda_requirements.txt` to develop/debug locally but skip it in lambda specific `requirements.txt` if you are not using `LocalFolder` in the cloud

## Current limitations
1. While user roles are propagated into lambdas and microservices RBAC is not implemented yet. It can be done with decorator on microservices implementations but that's TODO
2. Unit tests coverage is really low. For the sake of manageability unit tests to be extended (using "local" implementations of data sources)

## Usage
There is a CDK application for infrastructure (`app.py` and `cloud_iot_diy_cloud` folder) and multiple Python Lambda functions in the `src` folder.

### Build Lambdas an create deployments
CDK application will deploy Lambda functions

### Project bootstrapping
__NOTE__ there is a pre-deploy and post-destroy steps which should be implemented BEFORE the FIRST deployment and AFTER the stack DESTROY.

This step will create some resources using boto3 which is then used by CDK during deployment. Resources includes:
- default thing group
- bootstrap certificate (trusted store will be updated and cert data stored locally)
- iot policy will be created for bootstrap certificate
- iot policy will be attached to bootstrap certificate 

Obviously these resources have to be removed when stack is destroyed.

To support/simplify this process an extra script available (`pre_deploy.py`) which requires multiple parameters which will be collected from `project_config.json`. So in general you can just run:
- `python pre_deploy.py --profile <profile_name>` BEFORE the first deployment in the activated `infra_venv`
and
- `python pre_deploy.py --destroy --profile <profile_name>` AFTER destroying the stack
in further versions as a extra 'bonus' command `pre_deploy.py --destroy` will also clean up CloudWatch log groups (created but not removed by CDK created resources)

__NOTE__ `pre_deploy` relies on `cloud_iot_diy_cloud/_prepare_bootstrap.py`

__NOTE__ `pre_deploy` will be executed automatically if you are using `bootstrap.py` tool (see Cloud_IoT_DIY_tools)

