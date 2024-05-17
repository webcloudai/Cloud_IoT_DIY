from typing import Dict, List
from pathlib import Path
import platform
import json
from jinja2.nativetypes import NativeEnvironment
from jinja2 import DebugUndefined

import logging
_top_logger = logging.getLogger(__name__)

#-------------------CDK stuff------------------------------------------
from aws_cdk import (
    aws_lambda,
    aws_apigateway,
    aws_route53,
    aws_s3,
    aws_dynamodb,
    aws_events,
    aws_events_targets,
    aws_cognito,
    aws_iam,
    aws_iot,
    aws_iot_actions_alpha,
    aws_iot_alpha,
    aws_logs,
    aws_s3_deployment,
    Duration, 
    RemovalPolicy,
    Stack,
    CfnOutput,
    CfnTag,
)
from constructs import Construct

#--------------------Internal stuff-----------------------------------------
from cloud_iot_diy_cloud.default_options import default_lambda_props, default_s3bucket_props, is_dev_stack
from cloud_iot_diy_cloud.cognito_construct import CognitoConstructL3, SupportedProviders
from cloud_iot_diy_cloud.restapi_construct import RestApiConstructL3
from cloud_iot_diy_cloud.website_construct import WebSitePrivateBucketConstructL3
from cloud_iot_diy_cloud.provisioning_templates import ProvisioningTemplate
from common_project_config import ProjectConfig


''' This class defines the whole project infrastructure '''
class CloudIoTDiyCloudStack(Stack):

    deployments_folder:Path = Path("./deploy_lambda")

    @staticmethod
    def depl_package_for(function_name:str)->str:
        ''' just a naming and location convention for deployment packages '''
        dp_path = CloudIoTDiyCloudStack.deployments_folder / f"{function_name}_lambda-deployment-package.zip"
        if platform.system().lower() == "windows":
            return str(dp_path)
        return dp_path.as_posix()

    def __init__(
        self, 
        scope: Construct, construct_id: str,

        config:ProjectConfig,

        **kwargs
        ) -> None:
        
        super().__init__(scope, construct_id, **kwargs)

        self.cnstrct_id = construct_id
        self.scope = scope
        # type: begin ignore
        self.group_name = config.things_group_name 
        CloudIoTDiyCloudStack.deployments_folder = Path(config.lambda_deployments_folder)
        self.domain_name = config.domain_name
        self.auth_subdomain = config.auth_subdomain
        self.user_pool_name = config.user_pool_name
        self.uiapi_subdomain = config.uiapi_subdomain
        self.web_site_depl_location = config.web_site_depl_location
        self.mtlsapi_subdomain = config.mtlsapi_subdomain
        self.mtlsapi_truststoreprefix = config.mtlsapi_truststoreprefix
        self.mtlsapi_truststorekey = f"{config.mtlsapi_truststoreprefix}/{config.mtlsapi_truststore_name}"
        self.mtlsapi_truststore_local_folder:Path = Path(config.mtlsapi_mythings_location) / self.mtlsapi_truststoreprefix
        self.data_plane_name = config.data_plane_name
        self.status_plane_name = config.status_plane_name
        self.control_plane_name = config.control_plane_name
        self.mqtt_app_name = config.mqtt_app_name
        self.auth_resource_server_id = config.auth_resource_server_id
        self.client_callback_urls = config.auth_callback_urls or [f"https://{self.domain_name}/callback.html"]
        self.client_logout_urls = config.auth_logout_urls or [f"https://{self.domain_name}"]
        self.client_scopes = config.auth_scopes
        self.web_scope = config.web_app_scope
        self.mobile_scope = config.mobile_app_scope
        self.desktop_scope = config.desktop_app_scope
        self.user_groups = config.user_groups
        self.telemetry_ingest_rule_prefix = config.telemetry_ingest_rule_prefix
        self.status_ingest_rule_prefix = config.status_ingest_rule_prefix
        self.export_data:Dict[str,str] = {}
        self.telemetry_topic = config.telemetry_topic
        self.status_topic = config.status_topic
        self.control_topic = config.control_topic
        self.status_key = config.status_key
        self.telemetry_key = config.telemetry_key
        self.telemetry_ingest_rule_prefix = config.telemetry_ingest_rule_prefix
        self.dashboard_key = config.dashboard_key
        self.topic_field = config.topic_field
        self.timestamp_field = config.timestamp_field
        self.iot_default_thing_type = config.iot_default_thing_type
        self.iot_bootstrapping_role_name = config.iot_bootstrapping_role_name or f"bootstrap_role_{self.cnstrct_id}"
        self.iot_provisioning_template_name = config.iot_provisioning_template_name or f"prov_template_{self.cnstrct_id}"
        self.iot_provisioning_role_name = config.iot_provisioning_role_name or f"prov_role_{self.cnstrct_id}"
        self.iot_logging_role_name = config.iot_logging_role_name or f"iot_logging_role_{self.cnstrct_id}"
        self.proj_environment:dict = config.environment
        self.proj_account = self.proj_environment.get("account","us-east-1")

        self.proj_tags = config.proj_tags
        #-----------------------------------------
        self.upload_trusted_store = True
        # collect hosted zone where all related URLs will be defined
        _top_logger.info(f"Collect Hosted Zone")
        self.hosted_zone = aws_route53.HostedZone.from_hosted_zone_attributes(
            self, f"HostedZone{self.cnstrct_id}",
            zone_name=config.hosted_zone_name,
            hosted_zone_id=config.hosted_zone_id,
        )
        self.export_data[self.hosted_zone.hosted_zone_arn]=self.hosted_zone.zone_name
        # type: end ignore

        # define all Storage Constructs
        self._storage()
        # define all Lambda Layers Constructs
        self._lambda_layers()
        # define all Lambdas Constructs
        #* NOTE that it's important that storage is defined first!
        # lambdas will also add storage access permissions for each lambda
        self._lambdas()

        #############################################################
        # ***** Static Web Site (Single Page web Application) *****
        # --------------------
        # While the SPA itself is located in the separate root subfolder
        #   we need to define the web-site here.
        #   Site deployment is a part of the definitions
        # - https only web-site with CloudFormation backed by S3 bucket
        # - content will be uploaded from its location
        # *NOTE* this pattern register "parent" domain for all other services
        #*       all patterns with custom domain will depend on web_site_pattern.a_record !
        #############################################################
        _top_logger.info(f"Define Static WebSite")
        self.web_site_pattern = WebSitePrivateBucketConstructL3(
            self, f"WebSite{self.cnstrct_id}",
            site_bucket=self.website_s3,
            site_domain_name=self.domain_name,
            hosted_zone=self.hosted_zone,
            content_location=Path(self.web_site_depl_location)
        )
        self.root_domain_record = self.web_site_pattern.a_record
        #############################################################
        # ***** Cognito User Pool for UI authentication *****
        # --------------------
        # Cognito will be used as IDP for UI
        # So Cognito User Pool created will be used by
        # - REST API for UI
        # - Web App for Login/Logout process
        # CognitoConstructL3 creates a bunch of stuff including UserPool
        #############################################################
        _top_logger.info(f"Define Cognito User Pool and User Pool Client")
        self.cognito_pattern = CognitoConstructL3(
            self, f"Cognito{self.cnstrct_id}",
            hosted_zone=self.hosted_zone,
            client_callback_urls=self.client_callback_urls,
            client_logout_urls=self.client_logout_urls,
            resource_server_id=self.auth_resource_server_id,
            client_scopes=self.client_scopes,
            parent_domain_name=self.domain_name,
            auth_subdomain=self.auth_subdomain,
            user_pool_name=self.user_pool_name,
            auth_subdomain_certificate_arn=config.config_data.get("auth_subdomain_certificate_arn", None),
            identity_providers=[SupportedProviders.COGNITO]
        )
        self.cognito_pattern.node.add_dependency(self.root_domain_record)
        self.export_data["idp_base_url"] = self.cognito_pattern.cognito_user_pool_domain.base_url()
        for i,u in enumerate(self.client_callback_urls):
            sign_in_u = self.cognito_pattern.cognito_user_pool_domain.sign_in_url(
                self.cognito_pattern.cognito_user_pool_client,
                redirect_uri=u
            )
            self.export_data[f"idp_signin_url_{i:02d}"] = f"{u}|||{sign_in_u}"
        #-----------------------------------------------------------
        _top_logger.info(f"Define Cognito User Pool Authorizer")
        self.cognito_authorizer = aws_apigateway.CognitoUserPoolsAuthorizer(
            self, f"CognitoAuthorizer{self.cnstrct_id}",
            cognito_user_pools=[self.cognito_pattern.cognito_user_pool],
            authorizer_name=f"CognitoAuthorizer{self.cnstrct_id}",
            identity_source=aws_apigateway.IdentitySource.header("Authorization"),
            results_cache_ttl=Duration.minutes(0)
        )
        #-----------------------------------------------------------
        # we need to update scopes with respect to Resource Server created
        self.client_scopes = [f"{self.cognito_pattern.resource_server_id}/{v}" for v in self.client_scopes]
        #-----------------------------------------------------------
        # we need to create user groups (they'll be used for RBAC)
        self.user_group_constructs = [
            aws_cognito.CfnUserPoolGroup(self, f"UserGroup{group_name}{self.cnstrct_id}",
                    user_pool_id=self.cognito_pattern.cognito_user_pool.user_pool_id,
                    description=group_name,
                    group_name=group_name
                )
            for group_name in self.user_groups
        ]

        #############################################################
        # ***** REST API for UI backend *****
        # --------------------
        # We need REST API to support our Single Page web Application (SPA)
        #   and any other UI in our system
        # This API will use Cognito for AuthN/Z
        # RestApiConstructL3 creates a bunch of stuff
        #############################################################
        _top_logger.info(f"Define UI REST API secured with Cognito User Pool Authorizer")
        self.uiapi_pattern = RestApiConstructL3(
            self, f"UIAPI{self.cnstrct_id}",
            hosted_zone=self.hosted_zone,
            api_name=f"DiyUiApi{self.cnstrct_id}",
            api_description="REST API backend for IoT-DIY UI",
            parent_domain_name=self.domain_name,
            api_subdomain=self.uiapi_subdomain,
            # By default RestApiConstructL3 will add parent domain as allowed origin
            # But for development stage it's useful to have different origins allowed
            # uncomment the line below if you need to temporary enable '*'
            cors_allow_origins=["*"],           #! <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<!!!!!
            stage_variables={
                "diy_group_name": self.group_name,
                "mqtt_app_name": self.mqtt_app_name,
                "usergroup_demo": config.usergroup_demo,
                "usergroup_readonly": config.usergroup_readonly,
                "usergroup_fullaccess": config.usergroup_fullaccess,
                "service_bucket_name": self.service_s3_bucket_name,
                "telemetry_bucket_name": self.telemetry_s3_bucket_name,
                "historical_bucket_name": self.historical_s3_bucket_name,
                "dashboards_bucket_name": self.dashboards_s3_bucket_name,
                "saved_dashboards_prefix": config.saved_dashboards_key_prefix,
                "state_table_name": self.state_table_name,
                "things_group_name": self.group_name
                #* NOTE that RestApiConstructL3 will add multiple 'service' stage variables
                # including CORS data
            },
            # cognito_userpools=[self.cognito_pattern.user_pool],
            # cognito_client=self.cognito_pattern.user_pool_client
        )
        self.uiapi_pattern.node.add_dependency(self.root_domain_record)
        self.uiapi_pattern.node.add_dependency(self.cognito_pattern)
        #-----------------------------------------------------------        
        _top_logger.info(f"Add endpoints to UI REST API")
        # Add REST API endpoints
        # *NOTE* we are heavily relying on multiple AWS CDK defaults for ResourceOptions, MethodOptions and IntegrationOptions!
        # *NOTE* no information about request parameters or model is defined!
        uiapi_root = self.uiapi_pattern.api.root
        #
        # *DASHBOARDS*
        # /dashboards
        uiapi_dashboards = uiapi_root.add_resource("dashboards")
        uiapi_dashboards.add_method("GET", 
            aws_apigateway.LambdaIntegration(self.lambda_api_ui_dashboards_get),
            operation_name="get_dashboards_list",
            # *NOTE* authorization_type is optional for Cognito and Custom Authorizers
            authorization_type=aws_apigateway.AuthorizationType.COGNITO,
            authorizer=self.cognito_authorizer,
            authorization_scopes=self.client_scopes,    # for now all scopes for any method
        )
        # /dashboards/{dashboard_id}
        uiapi_dashboards_dashboardid = uiapi_dashboards.add_resource("{dashboard_id}")
        uiapi_dashboards_dashboardid.add_method("GET", 
            aws_apigateway.LambdaIntegration(self.lambda_api_ui_dashboards_dashboardid_get),
            authorizer=self.cognito_authorizer,
            authorization_scopes=self.client_scopes,    # for now all scopes for any method
            operation_name="get_dashboard",
        )
        uiapi_dashboards_dashboardid.add_method("POST", 
            aws_apigateway.LambdaIntegration(self.lambda_api_ui_dashboards_dashboardid_post),
            authorizer=self.cognito_authorizer,
            authorization_scopes=self.client_scopes,    # for now all scopes for any method
            operation_name="put_dashboard",
        )
        uiapi_dashboards_dashboardid.add_method("DELETE", 
            aws_apigateway.LambdaIntegration(self.lambda_api_ui_dashboards_dashboardid_delete),
            authorizer=self.cognito_authorizer,
            authorization_scopes=self.client_scopes,    # for now all scopes for any method
            operation_name="delete_dashboard",
        )
        #
        # *DEVICES*
        # /devices
        uiapi_devices = uiapi_root.add_resource("devices")
        uiapi_devices.add_method("GET", 
            aws_apigateway.LambdaIntegration(self.lambda_api_ui_devices_get),
            operation_name="get_devices_list",
            # *NOTE* authorization_type is optional for Cognito and Custom Authorizers
            authorization_type=aws_apigateway.AuthorizationType.COGNITO,
            authorizer=self.cognito_authorizer,
            authorization_scopes=self.client_scopes,    # for now all scopes for any method
        )
        # /devices/{device_id}
        uiapi_devices_deviceid = uiapi_devices.add_resource("{device_id}")
        uiapi_devices_deviceid.add_method("GET", 
            aws_apigateway.LambdaIntegration(self.lambda_api_ui_devices_deviceid_get),
            authorizer=self.cognito_authorizer,
            authorization_scopes=self.client_scopes,    # for now all scopes for any method
            operation_name="get_device_details",
        )
        #
        # *DEVICES COLLECTED DATA*
        # All these resources supports additional query parameters!
        # TODO: there are query parameters supported by this resource - WE NEED add them to API Model!
        # query parameters supported for now: values=$dataPoint AND &format=$dataFormat
        # - values could be a comma-separated list of data points of interest
        # - format could change the resulting json format to simplify rendering in the UI
        # see implementation in 
        #   - Cloud_IoT_DIY_ui//cloud_iot_diy/lib/project_config_base.dart
        #   - Cloud_IoT_DIY_cloud/src/api_ui_devices_deviceid_telemetry_get/lambda_code.py
        #   - Cloud_IoT_DIY_cloud/src/api_ui_devices_deviceid_historical_get/lambda_code.py
        #
        # /devices/{device_id}/telemetry
        uiapi_devices_deviceid_telemetry = uiapi_devices_deviceid.add_resource("telemetry")
        uiapi_devices_deviceid_telemetry.add_method("GET", 
            aws_apigateway.LambdaIntegration(self.lambda_api_ui_devices_deviceid_telemetry_get),
            authorizer=self.cognito_authorizer,
            authorization_scopes=self.client_scopes,    # for now all scopes for any method
            operation_name="get_device_telemetry",
        )
        # /devices/{device_id}/historical
        uiapi_devices_deviceid_historical = uiapi_devices_deviceid.add_resource("historical")
        uiapi_devices_deviceid_historical.add_method("GET", 
            aws_apigateway.LambdaIntegration(self.lambda_api_ui_devices_deviceid_historical_get),
            authorizer=self.cognito_authorizer,
            authorization_scopes=self.client_scopes,    # for now all scopes for any method
            operation_name="get_device_historical",
        )
        #
        # *DEVICES COMMANDS*
        # /devices/{device_id}/command
        uiapi_devices_deviceid_command = uiapi_devices_deviceid.add_resource("command")
        uiapi_devices_deviceid_command.add_method("POST", 
            aws_apigateway.LambdaIntegration(self.lambda_api_ui_devices_deviceid_command_post),
            authorizer=self.cognito_authorizer,
            authorization_scopes=self.client_scopes,    # for now all scopes for any method
            operation_name="post_device_command",
        )
        # /devices/{device_id}/command/{session_id}
        uiapi_devices_deviceid_command_sessionid = uiapi_devices_deviceid_command.add_resource("{session_id}")
        uiapi_devices_deviceid_command_sessionid.add_method("GET", 
            aws_apigateway.LambdaIntegration(self.lambda_api_ui_devices_deviceid_command_sessionid_get),
            authorizer=self.cognito_authorizer,
            authorization_scopes=self.client_scopes,    # for now all scopes for any method
            operation_name="get_command_session_info",
        )
        
        #############################################################
        # ***** MTLS REST API for devices *****
        # --------------------
        # Additional REST API will be created for devices to transfer large data
        #   for now the only endpoint will be /devices/{device_id}/updates/{update_id}
        # API will use Mutual TLS for the AuthN/Z with no other authorizers
        #   however IAM is available by default if needed
        # RestApiConstructL3 creates a bunch of stuff
        # @see https://docs.aws.amazon.com/apigateway/latest/developerguide/rest-api-mutual-tls.html
        #############################################################
        #--- We need to upload the trusted store to S3 at first
        # *NOTE* trusted store is empty and the beginning and will contain sensitive data later
        # *NOTE* during the project bootstrapping the whole "MyThings" folder is EXCLUDED from git (added to .gitignore)
        # *NOTE* during thing provisioning certificate public key has to be added to trusted store
        # *NOTE* update MTLS API domain name HAS TO BE EXECUTED after any trusted store update
        # @see https://docs.aws.amazon.com/apigateway/latest/developerguide/rest-api-mutual-tls.html
        _top_logger.info(f"Check if this is first S3 deployment")
        self.trusted_store_deployment = None
        if self.upload_trusted_store:
            _top_logger.info(f"Upload initial trusted store for MTLS API")
            self.trusted_store_deployment = aws_s3_deployment.BucketDeployment(
                self, f"TrustedStoreDeployment{self.cnstrct_id}",
                destination_bucket=self.service_s3,
                destination_key_prefix=self.mtlsapi_truststoreprefix,
                sources=[aws_s3_deployment.Source.asset(str(self.mtlsapi_truststore_local_folder))],
                log_retention=aws_logs.RetentionDays.ONE_WEEK,
                prune=False, # If this is set to false, files in the destination bucket that do not exist in the asset, will NOT be deleted during deployment (create/update). Default: true
                # *NOTE* Multiple AWS CDK defaults are in use !
                # @see https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_s3_deployment/BucketDeployment.html
                # access_control=None, cache_control=None,
                # content_disposition=None, content_encoding=None,
                # content_language=None, content_type=None,
                # destination_key_prefix=None, ephemeral_storage_size=None,
                # distribution=self.cloud_formation_distribution,
                # distribution_paths=["/*"],
                # exclude=None, expires=None, memory_limit=None, metadata=None,
                # retain_on_delete=None, role=None,
                # server_side_encryption=None, server_side_encryption_aws_kms_key_id=None,
                # server_side_encryption_customer_algorithm=None,
                # storage_class=None, use_efs=None, vpc=None, vpc_subnets=None,
                # website_redirect_location=None
            )     
            with open(self.mtlsapi_truststore_local_folder / "upload_completed.txt", "w") as f:
                f.writelines(["This is dummy file just to mark that initial trusted store upload completed", "Delete this file if you'll ever need to reupload local truststore again."])

        _top_logger.info(f"Define MTLS REST API")
        self.mtlsapi_pattern = RestApiConstructL3(
            self, f"MTLSAPI{self.cnstrct_id}",
            hosted_zone=self.hosted_zone,
            api_name=f"DiyMtlsApi{self.cnstrct_id}",
            api_description="MTLS REST API backend for devices",
            parent_domain_name=self.domain_name,
            api_subdomain=self.mtlsapi_subdomain,
            mtls_bucket=self.service_s3,
            mtls_truststore_key=self.mtlsapi_truststorekey,
            stage_variables={
                "diy_group_name": self.group_name,
                "mqtt_app_name": self.mqtt_app_name,
                "service_bucket_name": self.service_s3_bucket_name,
                "updates_prefix": config.mtls_updates_key_prefix,
            },
            cognito_userpools=None,
            cognito_client=None
        )
        self.mtlsapi_pattern.node.add_dependency(self.root_domain_record)
        if self.trusted_store_deployment:
            self.mtlsapi_pattern.node.add_dependency(self.trusted_store_deployment)
        _top_logger.info(f"Add endpoints to MTLS REST API")
        mtlsapi_root = self.mtlsapi_pattern.api.root
        mtlsapi_devices = mtlsapi_root.add_resource("devices")
        mtlsapi_devices_deviceid = mtlsapi_devices.add_resource("{device_id}")
        mtlsapi_devices_deviceid_update = mtlsapi_devices_deviceid.add_resource("updates")
        mtlsapi_devices_deviceid_update_updateid = mtlsapi_devices_deviceid_update.add_resource("{update_id}")
        mtlsapi_devices_deviceid_update_updateid.add_method("GET",
            aws_apigateway.LambdaIntegration(self.lambda_api_mtls_devices_deviceid_update_get),
            #! NOTE this API will be still protected with MTLS !
            authorization_type=aws_apigateway.AuthorizationType.NONE,
            operation_name="get_device_updates",
        )
        #############################################################
        # ***** Scheduled Events *****
        # --------------------
        # We need to have some schedule for
        # - start data aggregation daily
        # -
        #############################################################
        _top_logger.info(f"Define events (schedules)")
        self.scheduled_aggregation_target = aws_events_targets.LambdaFunction(
            self.lambda_scheduled_telemetry_aggregation,
            event=None, dead_letter_queue=None, max_event_age=Duration.hours(23), retry_attempts=None
        )
        self.scheduled_aggregation_event = aws_events.Rule(
            self, f"TelemetryAggregationDailyEvent{self.cnstrct_id}",
            rule_name=f"TelemetryAggregationDaily{self.cnstrct_id}",
            description=f"Trigger Telemetry aggregation daily for {self.mqtt_app_name}",
            enabled=True,
            schedule=aws_events.Schedule.cron(
                year="*", month="*", day="*",
                hour="4", minute="1"
                ),
            targets=[ self.scheduled_aggregation_target ],
            # *NOTE* AWS CDK defaults are in use !
            event_pattern=None,
            event_bus=None, cross_stack_scope=None
        )
        #############################################################
        # ***** IoT *****
        self._iot()

        #############################################################
        # last-but-not-least
        # *CREATE CDK OUTPUT*
        #
        # for i,(k,v) in enumerate(self.export_data.items()):
        #     if isinstance(v, dict):
        #         for j,(subk,subv) in enumerate(v.items()):
        #             CfnOutput(self, id=f"{self.cnstrct_id}{i:03d}{j:03d}", export_name=f"{i:03d}{j:03d}", value=f"{k}|||{subk}|||{subv}")
        #     else:
        #         CfnOutput(self, id=f"{self.cnstrct_id}{i:03d}", export_name=f"{i:03d}", value=f"{k}|||{v}")
        # CfnOutput(self, id=f"{self.cnstrct_id}{(i+1):03d}", export_name=f"{(i+1):03d}", value=json.dumps(self.export_data))


    def _storage(self):
        ''' all storage definitions - separated just for code organization '''
        #############################################################
        # ***** PERSISTENT STORAGE *****
        #############################################################
        # Telemetry Storage
        # will be using S3 bucket for incoming telemetry
        self.telemetry_s3_bucket_name = f"{self.cnstrct_id}TelemetryData".lower()
        s3_props = aws_s3.BucketProps(
            **{
                **default_s3bucket_props,
                **{
                    "bucket_name": self.telemetry_s3_bucket_name,
                    # this is telemetry storage. Data will be moved from this Bucket to historical data.
                    # so we don't need to store extra data here - 3 days is more than enough to cover situations when aggregation function didn't run
                    "lifecycle_rules": [aws_s3.LifecycleRule(expiration=Duration.days(3), enabled=True)], 
                }
            }
        )
        self.telemetry_s3:aws_s3.IBucket = aws_s3.Bucket( self, f"{self.cnstrct_id}TelemetryBucket", **s3_props._values )
        self.export_data[self.telemetry_s3.bucket_arn] = self.telemetry_s3.bucket_name
        #---------------------------------------
        # Historical data Storage
        # we need another S3 bucket for historical data - aggregations of telemetry data with (potentially) extra data
        self.historical_s3_bucket_name = f"{self.cnstrct_id}HistoricalData".lower()
        s3_props = aws_s3.BucketProps(
            **{
                **default_s3bucket_props,
                **{
                    "bucket_name": self.historical_s3_bucket_name,
                    # this is historical data storage.
                    # so data here is never expired but we may want to move very old data to another storage class
                    "lifecycle_rules": [aws_s3.LifecycleRule(enabled=True, transitions=[
                        aws_s3.Transition(transition_after=Duration.days(2*365), storage_class=aws_s3.StorageClass.INFREQUENT_ACCESS)
                    ] )], 
                }
            }
        )
        self.historical_s3 = aws_s3.Bucket( self, f"{self.cnstrct_id}HistoricalBucket", **s3_props._values )
        self.export_data[self.historical_s3.bucket_arn] = self.historical_s3.bucket_name
        #---------------------------------------
        # Dashboards Storage
        # we need another S3 bucket for dashboards and potentially other Dashboards UI support data
        self.dashboards_s3_bucket_name = f"{self.cnstrct_id}Dashboards".lower()
        s3_props = aws_s3.BucketProps(
            **{
                **default_s3bucket_props,
                **{
                    "bucket_name": self.dashboards_s3_bucket_name,
                    # this is persistent data storage.
                    # so data here is never expired and there is no need to move old data to another storage class
                }
            }
        )
        self.dashboards_s3 = aws_s3.Bucket( self, f"{self.cnstrct_id}DashboardsBucket", **s3_props._values )
        self.export_data[self.dashboards_s3.bucket_arn] = self.dashboards_s3.bucket_name
        #---------------------------------------
        # Internal service storage (content has to be uploaded once!)
        # we need a storage to store keys for MTLS, firmware updates, etc
        # a small trick here to support one time upload
        self.service_s3_bucket_name = f"{self.cnstrct_id}Internal".lower()
        _top_logger.info(f"Check if this is first S3 deployment")
        try:
            upload_confirmation = [v for v in self.mtlsapi_truststore_local_folder.glob("*") if v.stem=="upload_completed"]
            if len(upload_confirmation) > 0:
                _top_logger.info(f"Service bucket found - no trusted store upload will be needed!")
                self.upload_trusted_store = False
            else:
                _top_logger.info(f"Service bucket not found - initial trusted store upload will be needed!")
                self.upload_trusted_store = True
        except Exception as e:
            _top_logger.info(f"Trusted store will be uploaded as upload check raised an exception {e}")
            self.upload_trusted_store = True
        # -----------
        s3_props = aws_s3.BucketProps(
            **{
                **default_s3bucket_props,
                **{
                    "bucket_name": self.service_s3_bucket_name,
                    # *NOTE* we will store 5 versions to support trusted store rollback (in case incorrect certificate upload)
                    "versioned": True,
                    # this is internal service data storage.
                    # so data here is never expired BUT we need to delete older versions
                    "lifecycle_rules": [aws_s3.LifecycleRule(enabled=True, noncurrent_versions_to_retain=5, noncurrent_version_expiration=Duration.days(30))], 
                }
            }
        )
        self.service_s3 = aws_s3.Bucket( self, f"{self.cnstrct_id}ServiceBucket", **s3_props._values )
        self.export_data[self.service_s3.bucket_arn] = self.service_s3.bucket_name
        #---------------------------------------
        # Static web-site storage (content will be updated with every deployment! See static site construct)
        s3_props = aws_s3.BucketProps(
            **{
                **default_s3bucket_props,
                **{
                    "bucket_name": f"{self.cnstrct_id}WebSite{self.node.addr}".lower(),
                    # this is web-site source
                    # so data here is never expired
                    # "lifecycle_rules": [aws_s3.LifecycleRule(enabled=True,  )], 
                }
            }
        )
        self.website_s3 = aws_s3.Bucket( self, f"{self.cnstrct_id}WebSiteBucket", **s3_props._values )
        self.export_data[self.website_s3.bucket_arn] = self.website_s3.bucket_name
        #############################################################
        # DynamoDB table to control state
        # self.state_table_name = f"States{self.cnstrct_id}"
        self.state_table_name = f"SessionsState{self.cnstrct_id}"
        self.state_table = aws_dynamodb.Table(
            self, f"{self.cnstrct_id}StateTable", **{
                "table_name": self.state_table_name,
                "partition_key": aws_dynamodb.Attribute(name="thing_id",type=aws_dynamodb.AttributeType.STRING),
                "sort_key": aws_dynamodb.Attribute(name="session_id", type=aws_dynamodb.AttributeType.STRING),
                "billing_mode": aws_dynamodb.BillingMode.PAY_PER_REQUEST,
                "table_class": aws_dynamodb.TableClass.STANDARD,
                "encryption": aws_dynamodb.TableEncryption.AWS_MANAGED,
                "removal_policy": RemovalPolicy.DESTROY if is_dev_stack else RemovalPolicy.RETAIN
            }
        )
        self.export_data[self.state_table.table_arn] = self.state_table.table_name

    def _lambda_layers(self):
        ''' All Lambda Layers - separated just for code organization '''
        #############################################################
        # ***** Lambda Layers *****
        # --------------------
        # we have multiple Lambda Layers to make common code available for multiple functions
        # - nosql_datasource - abstraction layer for DynamoDb or other NoSQL database
        # - objects_datasource - abstraction layer for S3 Bucket or other objects storage
        # For every layer we'll expect to have
        # - source code located in src folder but with '_' prefix
        # - packaged deployment zip in the deploy_lambda folder with '_' prefix
        #   zip-file (and Lambda subfolder) MUST be named exactly as Lambda Layer + '_' prefix
        #   use lbuild.py to build and pack all lambdas
        #   layer MUST have __init__.py file
        #############################################################
        # nosql_datasource Lambda Layer
        l_name = "nosql_datasource"
        self.layer_nosql_datasource = aws_lambda.LayerVersion(
            self, f"Layer{l_name}{self.cnstrct_id}",
            layer_version_name=f"{l_name}{self.cnstrct_id}",
            description=f"Abstraction layer for {l_name}",
            code=aws_lambda.Code.from_asset(CloudIoTDiyCloudStack.depl_package_for(f"_{l_name}")),
            compatible_architectures=[aws_lambda.Architecture.ARM_64,aws_lambda.Architecture.X86_64],
        )
        # objects_datasource Lambda Layer
        l_name = "objects_datasource"
        self.layer_objects_datasource = aws_lambda.LayerVersion(
            self, f"Layer{l_name}{self.cnstrct_id}",
            layer_version_name=f"{l_name}{self.cnstrct_id}",
            description=f"Abstraction layer for {l_name}",
            code=aws_lambda.Code.from_asset(CloudIoTDiyCloudStack.depl_package_for(f"_{l_name}")),
            compatible_architectures=[aws_lambda.Architecture.ARM_64,aws_lambda.Architecture.X86_64],
        )
        # objects_datasource Lambda Layer
        l_name = "devices_registry"
        self.layer_devices_registry = aws_lambda.LayerVersion(
            self, f"Layer{l_name}{self.cnstrct_id}",
            layer_version_name=f"{l_name}{self.cnstrct_id}",
            description=f"Abstraction layer for {l_name}",
            code=aws_lambda.Code.from_asset(CloudIoTDiyCloudStack.depl_package_for(f"_{l_name}")),
            compatible_architectures=[aws_lambda.Architecture.ARM_64,aws_lambda.Architecture.X86_64],
        )
        # api_handlers_common Lambda Layer
        l_name = "api_handlers_common"
        self.layer_api_handlers_common = aws_lambda.LayerVersion(
            self, f"Layer{l_name}{self.cnstrct_id}",
            layer_version_name=f"{l_name}{self.cnstrct_id}",
            description=f"Set of helpers {l_name}",
            code=aws_lambda.Code.from_asset(CloudIoTDiyCloudStack.depl_package_for(f"_{l_name}")),
            compatible_architectures=[aws_lambda.Architecture.ARM_64,aws_lambda.Architecture.X86_64],
        )

    def _lambdas(self):
        ''' All Lambdas - separated just for code organization '''
        #############################################################
        # ***** Lambda Functions *****
        # --------------------
        # we have multiple types of Lambda functions
        # - triggered by IoT Core Rule action
        # - serving UI API
        # - serving MTLS API
        # - standalone functions (like telemetry->history)
        # For every function we'll expect to have
        # - packaged deployment zip in the lambda_deployment folder
        #   zip-file (and Lambda subfolder) MUST be named exactly as Lambda
        #   use lbuild.py to build and pack all lambdas
        #   name of the handling function MUST be handler
        # - subsection of cdk.json "context" with required env vars
        #   subsection MUST be named exactly as Lambda
        # API serving Lambdas can also rely on Stage Variables
        # Stage variables to be available in cdk.json "context"
        #############################################################
        #------------------------------------------------------------
        # we'll need to export information about log groups created by our functions for future cleanup
        self.export_data.setdefault("log_groups", {}) # type: ignore
        self.export_data["log_groups"].setdefault("lambda", []) # type: ignore
        #
        # we'll need to provides some lambdas with information about topics
        # We'll use Jinja2 to render rules topics from configuration data
        lambdas_jjenv = NativeEnvironment(undefined=DebugUndefined)
        # the data to fill the template (note we do not use # just +) 
        lambdas_jjenv_data = {
            "telemetry_ingest_rule_prefix": self.telemetry_ingest_rule_prefix,
            "status_ingest_rule_prefix": self.status_ingest_rule_prefix,
            "mqtt_app_name": self.mqtt_app_name,
            "data_plane_name": self.data_plane_name,
            "status_plane_name": self.status_plane_name,
            "control_plane_name": self.control_plane_name,
            "things_group_name": self.group_name,
            # we want these part of topic to remain jinja
            # "building_id": None,
            # "location_id": None,
            # "thing_type": None,
            # "thing_name": None
        }
        telemetry_topics_lambda = lambdas_jjenv.from_string(self.telemetry_topic).render(**lambdas_jjenv_data)
        status_topics_lambda = lambdas_jjenv.from_string(self.status_topic).render(**lambdas_jjenv_data)
        control_topics_lambda = lambdas_jjenv.from_string(self.control_topic).render(**lambdas_jjenv_data)

        #------------------------------------------------------------
        # Lambda serving GET available dashboards data on UI API
        f_name = "api_ui_dashboards_get"
        self.lambda_api_ui_dashboards_get = aws_lambda.Function(
            self, f"Lambda{f_name}{self.cnstrct_id}", **{
                **default_lambda_props,
                **{
                    "code": aws_lambda.Code.from_asset(CloudIoTDiyCloudStack.depl_package_for(f_name)),
                    "description": "lambda for GET available dashboards endpoint on UI REST API",
                    "function_name": f"{self.cnstrct_id}-{f_name}",
                    "handler": "lambda_code.lambda_handler",
                    "log_retention": aws_logs.RetentionDays.ONE_WEEK,
                    "timeout": Duration.seconds(29),
                    "architecture": aws_lambda.Architecture.ARM_64,
                    "memory_size": 256,
                    "layers": [ self.layer_api_handlers_common, self.layer_objects_datasource ],
                    "tracing": None,
                    "environment": {
                        "dashboard_key": self.dashboard_key
                    }
                }
            }
        )
        # grant this lambda required permissions
        self.dashboards_s3.grant_read(self.lambda_api_ui_dashboards_get)
        #------------------------------------------------------------
        # Lambda serving GET dashboard data on UI API
        f_name = "api_ui_dashboards_dashboardid_get"
        self.lambda_api_ui_dashboards_dashboardid_get = aws_lambda.Function(
            self, f"Lambda{f_name}{self.cnstrct_id}", **{
                **default_lambda_props,
                **{
                    "code": aws_lambda.Code.from_asset(CloudIoTDiyCloudStack.depl_package_for(f_name)),
                    "description": "lambda for GET dashboard data endpoint on UI REST API",
                    "function_name": f"{self.cnstrct_id}-{f_name}",
                    "handler": "lambda_code.lambda_handler",
                    "log_retention": aws_logs.RetentionDays.ONE_WEEK,
                    "timeout": Duration.seconds(29),
                    "architecture": aws_lambda.Architecture.ARM_64,
                    "memory_size": 256,
                    "layers": [ self.layer_api_handlers_common, self.layer_objects_datasource ],
                    "tracing": None,
                    "environment": {
                        "dashboard_key": self.dashboard_key
                    }
                }
            }
        )
        # grant this lambda required permissions
        self.dashboards_s3.grant_read(self.lambda_api_ui_dashboards_dashboardid_get)
        #------------------------------------------------------------
        # Lambda serving POST dashboard data on UI API
        f_name = "api_ui_dashboards_dashboardid_post"
        self.lambda_api_ui_dashboards_dashboardid_post = aws_lambda.Function(
            self, f"Lambda{f_name}{self.cnstrct_id}", **{
                **default_lambda_props,
                **{
                    "code": aws_lambda.Code.from_asset(CloudIoTDiyCloudStack.depl_package_for(f_name)),
                    "description": "lambda for POST dashboard data endpoint on UI REST API",
                    "function_name": f"{self.cnstrct_id}-{f_name}",
                    "handler": "lambda_code.lambda_handler",
                    "log_retention": aws_logs.RetentionDays.ONE_WEEK,
                    "timeout": Duration.seconds(29),
                    "architecture": aws_lambda.Architecture.ARM_64,
                    "memory_size": 256,
                    "layers": [ self.layer_api_handlers_common, self.layer_objects_datasource ],
                    "tracing": None,
                    "environment": {
                        "dashboard_key": self.dashboard_key
                    }
                }
            }
        )
        # grant this lambda required permissions
        self.dashboards_s3.grant_read_write(self.lambda_api_ui_dashboards_dashboardid_post)
        #------------------------------------------------------------
        # Lambda serving DELETE dashboard data on UI API
        f_name = "api_ui_dashboards_dashboardid_delete"
        self.lambda_api_ui_dashboards_dashboardid_delete = aws_lambda.Function(
            self, f"Lambda{f_name}{self.cnstrct_id}", **{
                **default_lambda_props,
                **{
                    "code": aws_lambda.Code.from_asset(CloudIoTDiyCloudStack.depl_package_for(f_name)),
                    "description": "lambda for DELETE dashboard data endpoint on UI REST API",
                    "function_name": f"{self.cnstrct_id}-{f_name}",
                    "handler": "lambda_code.lambda_handler",
                    "log_retention": aws_logs.RetentionDays.ONE_WEEK,
                    "timeout": Duration.seconds(29),
                    "architecture": aws_lambda.Architecture.ARM_64,
                    "memory_size": 256,
                    "layers": [ self.layer_api_handlers_common, self.layer_objects_datasource ],
                    "tracing": None,
                    "environment": {
                        "dashboard_key": self.dashboard_key
                    }
                }
            }
        )
        # grant this lambda required permissions
        self.dashboards_s3.grant_read_write(self.lambda_api_ui_dashboards_dashboardid_delete)
        #------------------------------------------------------------
        # Lambda serving as pre-provisioning hook for "Provisioning by claim" workflows
        f_name = "iot_preprov_hook"
        self.lambda_iot_preprov_hook = aws_lambda.Function(
            self, f"Lambda{f_name}{self.cnstrct_id}", **{
                **default_lambda_props,
                **{
                    "code": aws_lambda.Code.from_asset(CloudIoTDiyCloudStack.depl_package_for(f_name)),
                    "description": "lambda invoked when new thing request provisioning",
                    "function_name": f"{self.cnstrct_id}-{f_name}",
                    "handler": "lambda_code.lambda_handler",
                    "log_retention": aws_logs.RetentionDays.ONE_YEAR,
                    "timeout": Duration.seconds(10),
                    "architecture": aws_lambda.Architecture.ARM_64,
                    "memory_size": 256,
                    "layers": None,
                    "tracing": None,
                    "environment": {
                        "service_bucket": self.service_s3_bucket_name,
                        "state_table": self.state_table_name,
                        "mqtt_app_name": self.mqtt_app_name,
                        "things_group_name": self.group_name,
                        "prov_template": self.iot_provisioning_template_name
                    }
                }
            }
        )
        self.lambda_iot_preprov_hook.grant_invoke(aws_iam.ServicePrincipal("iot.amazonaws.com"))
        self.export_data[self.lambda_iot_preprov_hook.function_arn] = self.lambda_iot_preprov_hook.function_name
        self.export_data["log_groups"]["lambda"].append(self.lambda_iot_preprov_hook.function_name) # type: ignore
        #------------------------------------------------------------
        # Lambda serving IoT Core Rule for MQTT Status topic
        f_name = "mqtt_status_received"
        self.lambda_iot_status_received = aws_lambda.Function(
            self, f"Lambda{f_name}{self.cnstrct_id}", **{
                **default_lambda_props,
                **{
                    "code": aws_lambda.Code.from_asset(CloudIoTDiyCloudStack.depl_package_for(f_name)),
                    "description": "lambda invoked when Status message received",
                    "function_name": f"{self.cnstrct_id}-{f_name}",
                    "handler": "lambda_code.lambda_handler",
                    "log_retention": aws_logs.RetentionDays.ONE_MONTH,
                    "timeout": Duration.seconds(10),
                    "architecture": aws_lambda.Architecture.ARM_64,
                    "memory_size": 256,
                    "layers": [ self.layer_devices_registry ], # self.layer_api_handlers_common, 
                    "tracing": None,
                    "environment": {
                        "service_bucket": self.service_s3_bucket_name,
                        "telemetry_bucket": self.telemetry_s3_bucket_name,
                        "historical_bucket": self.historical_s3_bucket_name,
                        "state_table": self.state_table_name,
                        "mqtt_app_name": self.mqtt_app_name,
                        "things_group_name": self.group_name,
                        "status_topic": self.status_topic,
                    }
                }
            }
        )
        self.lambda_iot_status_received.add_to_role_policy(
            aws_iam.PolicyStatement(
                effect=aws_iam.Effect.ALLOW,
                actions=[
                    # this maybe too many allowed actions but "status received" is an entry point for multiple ops
                    "iot:DescribeThing", "iot:DescribeThingGroup",
                    "iot:ListThingsInThingGroup", "iot:ListThings",
                    "iot:UpdateThing",
                    "iot:ListThingTypes", "iot:CreateThingType"
                ],
                resources=[f"arn:aws:iot:us-east-1:{self.proj_account}:*"]
            )
        )
        self.export_data[self.lambda_iot_status_received.function_arn] = self.lambda_iot_status_received.function_name
        self.export_data["log_groups"]["lambda"].append(self.lambda_iot_status_received.function_name) # type: ignore
        #------------------------------------------------------------
        # Lambda serving list devices on UI API
        f_name = "api_ui_devices_get"
        self.lambda_api_ui_devices_get = aws_lambda.Function(
            self, f"Lambda{f_name}{self.cnstrct_id}", **{
                **default_lambda_props,
                **{
                    "code": aws_lambda.Code.from_asset(CloudIoTDiyCloudStack.depl_package_for(f_name)),
                    "description": "lambda for GET devices endpoint on UI REST API",
                    "function_name": f"{self.cnstrct_id}-{f_name}",
                    "handler": "lambda_code.lambda_handler",
                    "log_retention": aws_logs.RetentionDays.ONE_WEEK,
                    "timeout": Duration.seconds(29),
                    "architecture": aws_lambda.Architecture.ARM_64,
                    "memory_size": 256,
                    "layers": [ self.layer_api_handlers_common, self.layer_devices_registry ],
                    "tracing": None,
                    "environment": {}
                }
            }
        )
        # Allow access to IoT Registry
        self.lambda_api_ui_devices_get.add_to_role_policy(
            aws_iam.PolicyStatement(
                effect=aws_iam.Effect.ALLOW,
                actions=["iot:ListThingsInThingGroup", "iot:ListThings"],
                resources=[f"arn:aws:iot:us-east-1:{self.proj_account}:*"]
            )
        )
        # self.export_data[self.lambda_api_ui_devices_get.function_arn] = self.lambda_api_ui_devices_get.function_name
        # self.export_data["log_groups"]["lambda"].append(self.lambda_api_ui_devices_get.function_name) # type: ignore
        #------------------------------------------------------------
        # Lambda serving get one device on UI API
        f_name = "api_ui_devices_deviceid_get"
        self.lambda_api_ui_devices_deviceid_get = aws_lambda.Function(
            self, f"Lambda{f_name}{self.cnstrct_id}", **{
                **default_lambda_props,
                **{
                    "code": aws_lambda.Code.from_asset(CloudIoTDiyCloudStack.depl_package_for(f_name)),
                    "description": "lambda for GET one device details endpoint on UI REST API",
                    "function_name": f"{self.cnstrct_id}-{f_name}",
                    "handler": "lambda_code.lambda_handler",
                    "log_retention": aws_logs.RetentionDays.ONE_WEEK,
                    "timeout": Duration.seconds(29),
                    "architecture": aws_lambda.Architecture.ARM_64,
                    "memory_size": 256,
                    "layers": [ self.layer_api_handlers_common, self.layer_devices_registry ],
                    "tracing": None,
                    "environment": { }
                }
            }
        )
        # Allow access to IoT Registry
        self.lambda_api_ui_devices_deviceid_get.add_to_role_policy(
            aws_iam.PolicyStatement(
                effect=aws_iam.Effect.ALLOW,
                actions=["iot:DescribeThing", "iot:DescribeThingGroup"],
                resources=[f"arn:aws:iot:us-east-1:{self.proj_account}:*"]
            )
        )
        # self.export_data[self.lambda_api_ui_devices_deviceid_get.function_arn] = self.lambda_api_ui_devices_deviceid_get.function_name
        # self.export_data["log_groups"]["lambda"].append(self.lambda_api_ui_devices_deviceid_get.function_name) # type: ignore
        #------------------------------------------------------------
        # Lambda serving get telemetry data on UI API
        f_name = "api_ui_devices_deviceid_telemetry_get"
        self.lambda_api_ui_devices_deviceid_telemetry_get = aws_lambda.Function(
            self, f"Lambda{f_name}{self.cnstrct_id}", **{
                **default_lambda_props,
                **{
                    "code": aws_lambda.Code.from_asset(CloudIoTDiyCloudStack.depl_package_for(f_name)),
                    "description": "lambda for GET device telemetry data endpoint on UI REST API",
                    "function_name": f"{self.cnstrct_id}-{f_name}",
                    "handler": "lambda_code.lambda_handler",
                    "log_retention": aws_logs.RetentionDays.ONE_WEEK,
                    "timeout": Duration.seconds(29),
                    "architecture": aws_lambda.Architecture.ARM_64,
                    "memory_size": 256,
                    "layers": [ self.layer_api_handlers_common, self.layer_objects_datasource, self.layer_devices_registry ],
                    "tracing": None,
                    "environment": {
                        "telemetry_topic": telemetry_topics_lambda,
                        "telemetry_ingest_rule_prefix": self.telemetry_ingest_rule_prefix,
                        # *NOTE* this key format MUST be the same as key for IoT Rule !
                        "telemetry_key": self.telemetry_key,
                    }
                }
            }
        )
        # grant this lambda required permissions
        self.telemetry_s3.grant_read(self.lambda_api_ui_devices_deviceid_telemetry_get)
        # Allow access to IoT Registry
        self.lambda_api_ui_devices_deviceid_telemetry_get.add_to_role_policy(
            aws_iam.PolicyStatement(
                effect=aws_iam.Effect.ALLOW,
                actions=["iot:DescribeThing", "iot:DescribeThingGroup"],
                resources=[f"arn:aws:iot:us-east-1:{self.proj_account}:*"]
            )
        )
        # store some data for stack output        
        self.export_data[self.lambda_api_ui_devices_deviceid_telemetry_get.function_arn] = self.lambda_api_ui_devices_deviceid_telemetry_get.function_name
        self.export_data["log_groups"]["lambda"].append(self.lambda_api_ui_devices_deviceid_telemetry_get.function_name) # type: ignore
        #------------------------------------------------------------
        # Lambda serving get historical data on UI API
        f_name = "api_ui_devices_deviceid_historical_get"
        self.lambda_api_ui_devices_deviceid_historical_get = aws_lambda.Function(
            self, f"{self.cnstrct_id}Lambda{f_name}", **{
                **default_lambda_props,
                **{
                    "code": aws_lambda.Code.from_asset(CloudIoTDiyCloudStack.depl_package_for(f_name)),
                    "description": "lambda for GET device historical data endpoint on UI REST API",
                    "function_name": f"{self.cnstrct_id}-{f_name}",
                    "handler": "lambda_code.lambda_handler",
                    "log_retention": aws_logs.RetentionDays.ONE_WEEK,
                    "timeout": Duration.seconds(29),
                    "architecture": aws_lambda.Architecture.ARM_64,
                    "memory_size": 256,
                    "layers": [ self.layer_api_handlers_common, self.layer_objects_datasource, self.layer_devices_registry ],
                    "tracing": None,
                    "environment": {
                        "telemetry_topic": telemetry_topics_lambda,
                        "telemetry_ingest_rule_prefix": self.telemetry_ingest_rule_prefix,
                        # *NOTE* this key format MUST be the same as key for IoT Rule !
                        "telemetry_key": self.telemetry_key,                        
                    }
                }
            }
        )
        # grant this lambda required permissions
        self.historical_s3.grant_read(self.lambda_api_ui_devices_deviceid_historical_get)
        self.lambda_api_ui_devices_deviceid_historical_get.add_to_role_policy(
            aws_iam.PolicyStatement(
                effect=aws_iam.Effect.ALLOW,
                actions=["iot:DescribeThing", "iot:DescribeThingGroup"],
                resources=[f"arn:aws:iot:us-east-1:{self.proj_account}:*"]
            )
        )
        # store some data for stack output        
        self.export_data[self.lambda_api_ui_devices_deviceid_historical_get.function_arn] = self.lambda_api_ui_devices_deviceid_historical_get.function_name
        self.export_data["log_groups"]["lambda"].append(self.lambda_api_ui_devices_deviceid_historical_get.function_name) # type: ignore
        #------------------------------------------------------------
        # Lambda serving send command to device on UI API
        f_name = "api_ui_devices_deviceid_command_post"
        self.lambda_api_ui_devices_deviceid_command_post = aws_lambda.Function(
            self, f"{self.cnstrct_id}Lambda{f_name}", **{
                **default_lambda_props,
                **{
                    "code": aws_lambda.Code.from_asset(CloudIoTDiyCloudStack.depl_package_for(f_name)),
                    "description": "lambda for POST command endpoint on UI REST API",
                    "function_name": f"{self.cnstrct_id}-{f_name}",
                    "handler": "lambda_code.lambda_handler",
                    "log_retention": aws_logs.RetentionDays.ONE_WEEK,
                    "timeout": Duration.seconds(29),
                    "architecture": aws_lambda.Architecture.ARM_64,
                    "memory_size": 256,
                    "layers": [ self.layer_api_handlers_common, self.layer_devices_registry ],
                    "tracing": None,
                    "environment": {
                        "control_plane_name": self.control_plane_name,
                        "control_topic": self.control_topic
                    }
                }
            }
        )
        self.lambda_api_ui_devices_deviceid_command_post.add_to_role_policy(
            aws_iam.PolicyStatement(
                effect=aws_iam.Effect.ALLOW,
                actions=["iot:DescribeThing", "iot:DescribeThingGroup"],
                resources=[f"arn:aws:iot:us-east-1:{self.proj_account}:*"]
            )
        )
        self.export_data[self.lambda_api_ui_devices_deviceid_command_post.function_arn] = self.lambda_api_ui_devices_deviceid_command_post.function_name
        self.export_data["log_groups"]["lambda"].append(self.lambda_api_ui_devices_deviceid_command_post.function_name) # type: ignore
        #------------------------------------------------------------
        # Lambda serving get command session info on UI API
        f_name = "api_ui_devices_deviceid_command_sessionid_get"
        self.lambda_api_ui_devices_deviceid_command_sessionid_get = aws_lambda.Function(
            self, f"{self.cnstrct_id}Lambda{f_name}", **{
                **default_lambda_props,
                **{
                    "code": aws_lambda.Code.from_asset(CloudIoTDiyCloudStack.depl_package_for(f_name)),
                    "description": "lambda for GET command session info on UI REST API",
                    "function_name": f"{self.cnstrct_id}-{f_name}",
                    "handler": "lambda_code.lambda_handler",
                    "log_retention": aws_logs.RetentionDays.ONE_WEEK,
                    "timeout": Duration.seconds(29),
                    "architecture": aws_lambda.Architecture.ARM_64,
                    "memory_size": 256,
                    "layers": [ self.layer_api_handlers_common, self.layer_nosql_datasource ],
                    "tracing": None,
                    "environment": {
                        "control_plane_name": self.control_plane_name,
                        "control_topic": self.control_topic
                    }
                }
            }
        )
        # grant this lambda required permissions
        self.state_table.grant_read_data(self.lambda_api_ui_devices_deviceid_command_sessionid_get)
        # store some data for stack output        
        self.export_data[self.lambda_api_ui_devices_deviceid_command_post.function_arn] = self.lambda_api_ui_devices_deviceid_command_post.function_name
        self.export_data["log_groups"]["lambda"].append(self.lambda_api_ui_devices_deviceid_command_post.function_name) # type: ignore
        #------------------------------------------------------------
        # Lambda performing once a day aggregation of telemetry to historical
        f_name = "scheduled_telemetry_aggregation"
        self.lambda_scheduled_telemetry_aggregation = aws_lambda.Function(
            self, f"{self.cnstrct_id}Lambda{f_name}", **{
                **default_lambda_props,
                **{
                    "code": aws_lambda.Code.from_asset(CloudIoTDiyCloudStack.depl_package_for(f_name)),
                    "description": "on schedule aggregation of telemetry data",
                    "function_name": f"{self.cnstrct_id}-{f_name}",
                    "handler": "lambda_code.lambda_handler",
                    "log_retention": aws_logs.RetentionDays.ONE_WEEK,
                    "timeout": Duration.seconds(898),
                    "architecture": aws_lambda.Architecture.X86_64,
                    "memory_size": 1024,
                    "layers": [ self.layer_objects_datasource ],    # aggregation function needs this datasource to work with S3 buckets
                    "tracing": None,
                    "environment": {
                        # "service_bucket": self.service_s3_bucket_name,
                        "telemetry_bucket": self.telemetry_s3_bucket_name,
                        "historical_bucket": self.historical_s3_bucket_name,
                        # "state_table": self.state_table_name,
                        # "things_group_name": self.group_name,
                        # *NOTE* this key format MUST be the same as key for IoT Rule !
                        "telemetry_key": self.telemetry_key
                    }
                }
            }
        )
        # grant this lambda required permissions
        self.telemetry_s3.grant_read_write(self.lambda_scheduled_telemetry_aggregation)
        self.historical_s3.grant_read_write(self.lambda_scheduled_telemetry_aggregation)
        # store some data for stack output
        self.export_data[self.lambda_scheduled_telemetry_aggregation.function_arn] = self.lambda_scheduled_telemetry_aggregation.function_name
        self.export_data["log_groups"]["lambda"].append(self.lambda_scheduled_telemetry_aggregation.function_name) # type: ignore
        #------------------------------------------------------------
        # Lambda serving get /devices/{deviceid}/updates/{update_id} on MTLS API
        f_name = "api_mtls_devices_deviceid_update_updateid_get"
        self.lambda_api_mtls_devices_deviceid_update_get = aws_lambda.Function(
            self, f"{self.cnstrct_id}Lambda{f_name}", **{
                **default_lambda_props,
                **{
                    "code": aws_lambda.Code.from_asset(CloudIoTDiyCloudStack.depl_package_for(f_name)),
                    "description": "Lambda for GET update for device on MTLS API",
                    "function_name": f"{self.cnstrct_id}-{f_name}",
                    "handler": "lambda_code.lambda_handler",
                    "log_retention": aws_logs.RetentionDays.ONE_WEEK,
                    "timeout": Duration.seconds(29),
                    "architecture": aws_lambda.Architecture.ARM_64,
                    "memory_size": 256,
                    "layers": None,
                    "tracing": None,
                    "environment": {
                        "service_bucket": self.service_s3_bucket_name,
                        "state_table": self.state_table_name,
                        "things_group_name": self.group_name
                    }
                }
            }
        )
        # grant this lambda required permissions
        self.service_s3.grant_read(self.lambda_api_mtls_devices_deviceid_update_get)
        # store some data for stack output
        self.export_data[self.lambda_api_mtls_devices_deviceid_update_get.function_arn] = self.lambda_api_mtls_devices_deviceid_update_get.function_name
        self.export_data["log_groups"]["lambda"].append(self.lambda_api_mtls_devices_deviceid_update_get.function_name)

    def _iot(self):
        #############################################################
        # ***** IoT Core *****
        #
        #? We will NOT use custom domain for IoT Core
        #?     instead AWS proprietary endpoint will be the part of configuration
        # With IoT Core we don't need to define topics
        # However we need to create Thing Group, define Rules, some Roles, etc
        #! We'll use ALPHA version of CDK to simplify Rule definition
        # TODO: When ALPHA functionality will be added to main CDK some refactoring will he needed
        # *NOTE* Topic Naming Convention is extremely important for Rules!
        # <plane_id>/<app_name>/<building_id>/<location_id>/<thing_group>/<thing_type>/<thing_name>
        #############################################################
        _top_logger.info(f"Start with IoT Core")
        #---------------------
        # We'll use Jinja2 to render rules topics from configuration data
        jjenv = NativeEnvironment()
        # the data to fill the template (note we do not use # just +) 
        jjenv_data = {
            "telemetry_ingest_rule_prefix": self.telemetry_ingest_rule_prefix,
            "status_ingest_rule_prefix": self.status_ingest_rule_prefix,
            "mqtt_app_name": self.mqtt_app_name,
            "data_plane_name": self.data_plane_name,
            "status_plane_name": self.status_plane_name,
            "control_plane_name": self.control_plane_name,
            "building_id": "+",                         # we want the rule to server all values
            "location_id": "+",                         # we want the rule to server all values
            "things_group_name": self.group_name,
            "thing_type": "+",                          # we want the rule to server all values
            "thing_name": "+"                           # we want the rule to server all values
        }
        telemetry_rule_sql = jjenv.from_string(self.telemetry_topic).render(**jjenv_data)
        status_rule_sql = jjenv.from_string(self.status_topic).render(**jjenv_data)
        # in additional to MQTT payload we'll collect some extra data
        _topic_addon = f"topic() as {self.topic_field}"
        _timestamp_addon = f"timestamp() as {self.timestamp_field}"
        # --------------------
        # First thing - define the provisioning Role (to be associated with Provisioning template)
        self.add_metadataprov_template_role = aws_iam.Role(
            self, f"IoTProvTemplateRole{self.cnstrct_id}",
            assumed_by=aws_iam.ServicePrincipal("iot.amazonaws.com"),
            role_name=self.iot_provisioning_role_name,
            description=f"Provisioning Template Role {self.cnstrct_id}",
            managed_policies=[
                # aws_iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSIoTFullAccess")
                aws_iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSIoTThingsRegistration")
                # aws_iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSIoTConfigReadOnlyAccess")
            ]
        )
        # # add permission to invoke pre-provisioning hook
        # self.add_metadataprov_template_role.add_to_policy(
        #     aws_iam.PolicyStatement(
        #         resources = [ self.lambda_iot_preprov_hook.function_arn ],
        #         actions = [ "lambda:InvokeFunction" ]
        #     )
        # )
        # Next - define the provisioning template
        # EXAMPLE:
        # cfn_provisioning_template = iot.CfnProvisioningTemplate(self, "MyCfnProvisioningTemplate",
        #     provisioning_role_arn="provisioningRoleArn",
        #     template_body="templateBody",
        #     # the properties below are optional
        #     description="description",
        #     enabled=False,
        #     pre_provisioning_hook=iot.CfnProvisioningTemplate.ProvisioningHookProperty(
        #         payload_version="payloadVersion",
        #         target_arn="targetArn"
        #     ),
        #     tags=[CfnTag(
        #         key="key",
        #         value="value"
        #     )],
        #     template_name="templateName",
        #     template_type="templateType"
        # )

        # --------------------
        # Define policy for any Thing (it'll be attached to Thing certificate by provisioning template)
        self.things_policy_name = f"Thing{self.group_name}Policy{self.cnstrct_id}"
        self.things_policy = aws_iot.CfnPolicy(
            self, f"Thing{self.group_name}Policy{self.cnstrct_id}",
            policy_name=self.things_policy_name,
            policy_document={
                "Version": "2012-10-17",
                "Statement": [
                    { 
                        "Effect": "Allow", 
                        "Action": [ 
                            "iot:Connect", 
                            "iot:Publish",
                            "iot:Subscribe",
                            "iot:Receive"
                        ],
                        "Resource": [
                            f"arn:aws:iot:us-east-1:{self.proj_account}:*"
                        ]
                    }
                ] 
            }
        )
        # --------------------
        # Provisioning template will be applied for any Thing provisioned with 'fleet provisioning'
        self.provisioning_template = aws_iot.CfnProvisioningTemplate(
            self, f"IoTProvTemplate{self.group_name}{self.cnstrct_id}",
            # The role ARN for the role associated with the provisioning template. 
            # This IoT role grants permission to provision a device.
            provisioning_role_arn=self.add_metadataprov_template_role.role_arn,
            # @see https://docs.aws.amazon.com/iot/latest/developerguide/provision-template.html
            template_body=ProvisioningTemplate.templateForGroup(self.group_name, thing_policy_name=self.things_policy_name),
            description=f"Default provisional template for the things group {self.group_name}",
            enabled=True,
            # Only supports template of type FLEET_PROVISIONING
            pre_provisioning_hook=aws_iot.CfnProvisioningTemplate.ProvisioningHookProperty(
                payload_version="2020-04-01",
                # target_arn=f"arn:aws:lambda:{self.region}:{self.account}:function:{self.lambda_iot_preprov_hook.from_function_name}"
                target_arn=self.lambda_iot_preprov_hook.function_arn
            ),
            tags=[CfnTag(key=k, value=v) for k,v in self.proj_tags.items()],
            template_name=self.iot_provisioning_template_name,
            template_type="FLEET_PROVISIONING"
        )
        self.provisioning_template.add_dependency(self.things_policy)
        # self.provisioning_template.add_dependency(self.lambda_iot_preprov_hook)
        # self.provisioning_template.add_dependency(self.add_metadataprov_template_role)
        # --------------------
        # Create Log Group for Rule Errors
        _top_logger.info(f"Create Log Group for IoT Rules Errors")
        self.log_group_iot_rule_errors = aws_logs.LogGroup(
            self, f"IotRulesErrorsLogGroup{self.cnstrct_id}",
            log_group_name=f"IotRulesErrors{self.cnstrct_id}",
            retention=aws_logs.RetentionDays.ONE_WEEK,
            removal_policy=None,
            encryption_key=None
        )
        self.export_data["log_groups"].setdefault("iot", [])
        self.export_data["log_groups"]["iot"].append(self.lambda_api_ui_devices_deviceid_telemetry_get.function_name)
        # --------------------
        # Enable IoT Core logging
        # create logging role
        self.iot_logging_role = aws_iam.Role(
            self, f"IotLoggingRole{self.cnstrct_id}",
            assumed_by=aws_iam.ServicePrincipal("iot.amazonaws.com"),
            role_name=self.iot_logging_role_name,
            description=f"IoT Logging Role {self.cnstrct_id}",
            inline_policies={f"{self.iot_logging_role_name}Policy": aws_iam.PolicyDocument(
                # {
                #     "Version": "2012-10-17",
                #     "Statement": [
                #         {
                #             "Effect": "Allow",
                #             "Action": [
                #                 "logs:CreateLogGroup",
                #                 "logs:CreateLogStream",
                #                 "logs:PutLogEvents",
                #                 "logs:PutMetricFilter",
                #                 "logs:PutRetentionPolicy"
                #             ],
                #             "Resource": [
                #                 "arn:aws:logs:*:286119765097:log-group:*:log-stream:*"
                #             ]
                #         }
                #     ]
                # }
                statements=[
                    aws_iam.PolicyStatement(
                        actions=[
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                            "logs:PutMetricFilter",
                            "logs:PutRetentionPolicy"
                        ],
                        effect=aws_iam.Effect.ALLOW,
                        resources=[f"arn:aws:logs:*:{self.proj_account}:log-group:*:log-stream:*"]
                    )
                ]
            )}
        )
        #! enable logging - THIS ONE WILL FAIL IF YOU'VE ENABLED LOGGING MANUALLY !!!
        # self.iot_logging = aws_iot.CfnLogging(
        #     self, f"IotLogging{self.cnstrct_id}",
        #     account_id=self.proj_account,
        #     default_log_level="WARN",
        #     role_arn=self.iot_logging_role.role_arn
        # )
        # --------------------
        # Data injection rule
        _top_logger.info(f"Create Data Injection Rule Action")
        self.iot_telemetry_s3_action = aws_iot_actions_alpha.S3PutObjectAction(
            bucket=self.telemetry_s3,
            # The path to the file where the data is written. Supports substitution templates. Default: '${topic()}/${timestamp()}'
            # *NOTE* this key format MUST be the same as variable for Lambda functions !
            key=self.telemetry_key,   
            # The IAM role that allows access to AWS service. Default: a new role will be created
            role=None,
            # The Amazon S3 canned ACL that controls access to the object identified by the object key. Default: None
            access_control=None  
        )
        _top_logger.info(f"Create Data Injection Rule")
        self.iot_telemetry_injection_rule = aws_iot_alpha.TopicRule(
            self, f"{self.telemetry_ingest_rule_prefix}Rule{self.cnstrct_id}",
            topic_rule_name=f"{self.telemetry_ingest_rule_prefix}{self.mqtt_app_name}",
            description="Direct write of incoming telemetry to S3 Bucket",
            # A simplified SQL syntax to filter messages received on an MQTT topic and push the data elsewhere.
            sql=aws_iot_alpha.IotSql.from_string_as_ver20160323(
                # f"SELECT *, {_topic_addon}, {_timestamp_addon} FROM '{self.data_plane_name}/{_topic_subname}'"
                f"SELECT *, {_topic_addon}, {_timestamp_addon} FROM '{telemetry_rule_sql}'"
            ),
            actions=[self.iot_telemetry_s3_action],
            enabled=True,
            error_action=aws_iot_actions_alpha.CloudWatchLogsAction(self.log_group_iot_rule_errors)
        )
        self.export_data["telemetry_rule_name"] = self.iot_telemetry_injection_rule.topic_rule_name
        self.export_data["telemetry_rule_serve"] = telemetry_rule_sql
        # --------------------
        # Status injection rule
        # - status will have two actions: Lambda with reaction logic and S3 to store status messages in history bucket
        _top_logger.info(f"Create Status Injection Rule Action")
        self.iot_status_s3_action = aws_iot_actions_alpha.S3PutObjectAction(
            bucket=self.historical_s3,
            # The Amazon S3 canned ACL that controls access to the object identified by the object key. Default: None
            access_control=None,    
            # The path to the file where the data is written. Supports substitution templates. Default: '${topic()}/${timestamp()}'
            # *NOTE* this key format MUST be the same as variable for Lambda functions !
            # <plane_id>/<app_name>/<thing_type>/<thing_name>/<year>/<month>/<day>/<timestamp>
            key=self.status_key,   
            # The IAM role that allows access to AWS service. Default: a new role will be created
            role=None   
        )
        _top_logger.info(f"Create Status Injection Rule")
        self.iot_status_injection_rule = aws_iot_alpha.TopicRule(
            self, f"{self.status_ingest_rule_prefix}Rule{self.cnstrct_id}",
            topic_rule_name=f"{self.status_ingest_rule_prefix}{self.mqtt_app_name}",
            description="Trigger Lambda when Status message received",
            sql=aws_iot_alpha.IotSql.from_string_as_ver20160323(
                f"SELECT *, {_topic_addon}, {_timestamp_addon} FROM '{status_rule_sql}'"
            ),
            actions=[
                aws_iot_actions_alpha.LambdaFunctionAction(self.lambda_iot_status_received),
                self.iot_status_s3_action
            ],
            enabled=True,
            error_action=aws_iot_actions_alpha.CloudWatchLogsAction(self.log_group_iot_rule_errors)
        )
        self.export_data["status_rule_name"] = self.iot_status_injection_rule.topic_rule_name
        self.export_data["status_rule_serve"] = status_rule_sql
