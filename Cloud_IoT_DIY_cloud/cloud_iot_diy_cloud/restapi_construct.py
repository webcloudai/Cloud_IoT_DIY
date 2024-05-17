from __future__ import annotations
from audioop import add
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union, Any
import json
from pathlib import Path
from uuid import uuid4
import logging
_top_logger = logging.getLogger(__name__)

from aws_cdk import (
    Duration,
    aws_apigateway as _apigw_v1,
    aws_route53 as _route53,
    aws_route53_targets as _targets,
    aws_certificatemanager as _acm,
    aws_cognito as _cognito,
    aws_s3 as _s3
)
from constructs import Construct

from .cognito_construct import CognitoClient, CognitoConstructL3


class RestApiConstructL3(Construct):
    ''' 
    Implements REST API and other required constructs. Some restrictions:
    - Proxy Integration only
    - Cognito Authorizer only
    - One Stage only
    - No Model/Validators
    '''

    def __init__(self, 
            scope: Construct, 
            construct_id:str, *, 
            hosted_zone:_route53.IHostedZone,
            # REST API Required Options
            api_name:str,
            api_description:str,
            parent_domain_name:str,
            api_subdomain:str,
            #------------------------------
            # REST API optional
            mtls_bucket:_s3.IBucket=None,
            mtls_truststore_key:str=None,

            # Stages Options
            # One stage parameters - MAIN option (and the only for now)
            base_path:str = "api",
            stage_name:str = "api",
            stage_variables:dict = None,
            stage_options:_apigw_v1.StageOptions = None,

            # CORS Options
            cors_allow_origins:list=None,
            cors_options:_apigw_v1.CorsOptions = _apigw_v1.CorsOptions(
                allow_origins=[""],
                allow_credentials=True,
                allow_headers=_apigw_v1.Cors.DEFAULT_HEADERS,
                allow_methods=_apigw_v1.Cors.ALL_METHODS),

            # AuthN/Z
            cognito_userpools:Union[_cognito.UserPool, List[_cognito.UserPool]]=None,   # If provided integration with Cognito for AuthN will be deployed
            cognito_client:_cognito.UserPoolClient=None,    # If provided client info will be added

            # Other options
            custom_api_options:_apigw_v1.RestApiProps = None,
            api_domain_certificate_arn:str=None,

            **kwargs) -> None:
        '''
            REST API:
            Integration PassThrough is enforced !!!
            @param custom_api_options: if provided will be used.
            @param cognito_userpools: if provided Cognito authorizer will be added (resource servers and scopes are not supported for now)
            @param cognito_client: cognito client with permissions to be used by API
            CORS:
                if cors_options is None -> CORS disabled
                if cors_options is default and cors_allow_origins provided - it'll be used
                if cors_options is default and cors_allow_origins not provided - parent domain name will be added as allowed origin
        '''

        super().__init__(scope, construct_id, **kwargs)

        self.scope = scope
        self.construct_id = construct_id
        self.uuid = str(uuid4()).replace("-","")
        self.api_name = api_name
        self.api_description = api_description
        self.api_domain_name = f"{api_subdomain}.{parent_domain_name}"
        self.api_domain_certificate_arn = api_domain_certificate_arn
        self.mtls_truststore_key = mtls_truststore_key
        self.mtls_bucket = mtls_bucket
        self.is_mtls:bool = not ((mtls_bucket is None) or (mtls_truststore_key is None))
        # Authorization ####
        self.cognito_authorizer:_apigw_v1.CognitoUserPoolsAuthorizer = None
        self.authorizers:Dict[_apigw_v1.AuthorizationType, _apigw_v1.Authorizer] = {_apigw_v1.AuthorizationType.IAM: None}
        if cognito_userpools:
            _top_logger.debug(f"Will add COGNITO authorizer")
            self.cognito_userpools:Union[_cognito.UserPool, List[_cognito.UserPool]] = cognito_userpools
            self.cognito_client:_cognito.UserPoolClient = cognito_client
            # Create Cognito authorizer
            self.cognito_authorizer = self.add_cognito_authorizer()
            self.authorizers[_apigw_v1.AuthorizationType.COGNITO]


        # Handle different CORS parameters
        self.cors_options:_apigw_v1.CorsOptions = None
        if isinstance(cors_options, _apigw_v1.CorsOptions):
            if len(cors_options.allow_origins)==1 and len(cors_options.allow_origins[0])==0:
                # we have a default cors_options - let's add allow origins
                if isinstance(cors_allow_origins, list):
                    # cors_allow_origins was provided
                    self.cors_options = _apigw_v1.CorsOptions(
                        allow_origins=cors_allow_origins,
                        allow_credentials=cors_options.allow_credentials,
                        allow_headers=cors_options.allow_headers,
                        allow_methods=cors_options.allow_methods
                    )
                else:
                    # add subdomain of api_domain with https protocol as allowed origin
                    self.cors_options = _apigw_v1.CorsOptions(
                        allow_origins=[f"https://{parent_domain_name}"],
                        allow_credentials=cors_options.allow_credentials,
                        allow_headers=cors_options.allow_headers,
                        allow_methods=cors_options.allow_methods
                    )
            else:
                self.cors_options = cors_options
        else:
            self.cors_options = None
        
        # Handle different STAGE parameters and assemble StageOptions
        if isinstance(stage_options, _apigw_v1.StageOptions):
            self.stage_options = stage_options
        else:
            # Assemble stage variables first
            stage_vars = {
                    #! NOTE that variables keys MUST be alphanumeric
                    #! Variables values can have alphanumeric characters and the symbols ' ', -', '.', '_', ':', '/', '?', '&', '=', ','
                    #! NOTE that NOT ALLOWED characters include [,],{,},*
                    **(stage_variables or {}),
                    **{ # ADD CORS PARAMETERS TO STAGE VARs
                        "AccessControlAllowOrigin": ",".join(self.cors_options.allow_origins).replace("*","&&:&&"),
                        # "AccessControlAllowMethods": json.dumps(self.cors_options.allow_methods),
                        # "AccessControlAllowHeaders": json.dumps(self.cors_options.allow_headers),
                        # "AccessControlAllowCredentials": json.dumps(self.cors_options.allow_credentials),
                    }
                }
            _top_logger.info(f"STAGE VARIABLES:\n{json.dumps(stage_vars,indent=3)}")
            self.stage_options = _apigw_v1.StageOptions(
                stage_name=stage_name,
                variables=stage_vars,
                logging_level=_apigw_v1.MethodLoggingLevel.INFO,    # Specifies the logging level for this method, which effects the log entries pushed to Amazon CloudWatch Logs. Default: - Off
                # *NOTE* we do not enable Access Logging !
            )

        # base_paths_and_stages_options dict is for future use when multiple stage will be supported
        self.base_paths_and_stages_options:Dict[str:_apigw_v1.StageOptions] = {
            base_path or self.stage_options.stage_name: self.stage_options
        }
        
        #! NOTE: defining deploy_options here informs RestApi what our "default" stage will be
        self.deploy_options = self.stage_options
        # Assemble RestApi options
        options_values = {
            **{k:getattr(self,v) for k,v in {
                    "rest_api_name": "api_name",
                    "description": "api_description",
                    "default_cors_preflight_options": "cors_options",
                    "deploy_options": "deploy_options"
                }.items()
            },
            **{
                "retain_deployments":True,
                "binary_media_types":[], # ["*/*"], NOTE: This parameter WILL AFFECT PAYLOAD VALIDATION!!! I.e. if content-type will be of binary type body validation will be skipped and always Ok
                "minimum_compression_size":0,
                "endpoint_types":[_apigw_v1.EndpointType.REGIONAL if self.is_mtls else _apigw_v1.EndpointType.EDGE],
                "endpoint_configuration":None,    #* Only one of the RestApi props, endpointTypes or endpointConfiguration, is allowed
            },
            **(custom_api_options._values if isinstance(custom_api_options, _apigw_v1.ResourceProps) else {}),
            **{
                "cloud_watch_role":True,  # to avoid dependency on value of "@aws-cdk/aws-apigateway:usagePlanKeyOrderInsensitiveId" in cdk.json
                "deploy":True,            # will be deployed separately if Resource Group implemented !!!
                "disable_execute_api_endpoint":True,    # aws proprietary endpoint will be disabled
                "fail_on_warnings":True,  # just good API will be deployed 
                "clone_from":None,
                "default_method_options":None,  # Use inheritance from defined parent instead !!!
                "default_integration":None,     # Use inheritance from defined parent instead !!!
            }
        }
        self.rest_api_props = _apigw_v1.RestApiProps(**options_values)

        #################################################################################
        #
        # Build API
        #
        # 1 Get hosted zone
        self.hosted_zone = hosted_zone
        #
        # 2. Create certificate for API domain
        if self.api_domain_certificate_arn:
            # If certificate arn is provided, import the certificate
            self.certificate = _acm.Certificate.from_certificate_arn(
                self,
                "site_certificate",
                certificate_arn=self.api_domain_certificate_arn,
            )
        else:
            # If certificate arn is not provided, create a new one.
            # ACM certificates that are used with CloudFront must be in
            # the us-east-1 region.
            # self.certificate = _acm.Certificate(
            #     self, f"restapi_{self.api_name}_certificate{self.construct_id}",
            #     domain_name=self.api_domain_name,
            #     validation=_acm.CertificateValidation.from_dns(
            #         hosted_zone=hosted_zone
            #     )
            # )
            self.certificate = _acm.DnsValidatedCertificate(
                self, f"restapi_{self.api_name}_certificate{self.construct_id}",
                domain_name=self.api_domain_name,
                hosted_zone=self.hosted_zone,
                region="us-east-1",
            )
        #
        # 3. Define domain name
        self.api_domain=_apigw_v1.DomainName(
                self, f"CustomDomain{self.construct_id}",
                domain_name=self.api_domain_name, 
                certificate=self.certificate,
                security_policy=_apigw_v1.SecurityPolicy.TLS_1_2,
                mtls=_apigw_v1.MTLSConfig(
                    bucket=self.mtls_bucket,
                    key=self.mtls_truststore_key
                ) if self.is_mtls else None,
                endpoint_type=_apigw_v1.EndpointType.REGIONAL if self.is_mtls else getattr(self.rest_api_props, "endpoint_types",[_apigw_v1.EndpointType.REGIONAL])[0],    # this will resolve the issue of different endpoint types!
                # base_path=self.api_base_path
            )
        #
        # 4. Define API
        # *NOTE* that proxy=False to be defined here as it's not a RestApiOptions !
        self.api = _apigw_v1.RestApi( self, f"RestAPI{self.construct_id}", 
            **self.rest_api_props._values 
        )
        # # add explicit dependencies
        # for authn in self.authorizers.values():
        #     if authn:
        #         self.api.node.add_dependency(authn)
        #
        # 5. Add Route53 record for API GW custom domain
        _route53.ARecord(self, f"CustomDomainAliasRecord{self.construct_id}",
            zone=self.hosted_zone,
            record_name=self.api_domain_name,
            target=_route53.RecordTarget.from_alias(_targets.ApiGatewayDomain(self.api_domain))
        )
        #
        # 6. Define deployments, stages and base paths
        # add deployment
        self.stage = self.api.deployment_stage
        # add base path mapping
        self.api_domain.add_base_path_mapping(self.api, base_path=base_path, stage=self.stage)


    def add_cognito_authorizer(self, authorizer_properties:_apigw_v1.CognitoUserPoolsAuthorizerProps=None):
        ''' add Cognito Authorizer to self.authorizers with (when authorizer_properties not provided)
            - User Pools info from self.cognito_userpools
            - Authorizer options from ApiDefaultOptions.COGNITO_AUTHORIZER_DICT
        '''
        _top_logger.debug("add_cognito_authorizer")
        c_id = f"CognitoAuthorizer{self.construct_id}"
        if isinstance(authorizer_properties, _apigw_v1.CognitoUserPoolsAuthorizerProps):
            self.authorizers[_apigw_v1.AuthorizationType.COGNITO] = _apigw_v1.CognitoUserPoolsAuthorizer(
                self, c_id, 
                **authorizer_properties._values)
            return self.authorizers[_apigw_v1.AuthorizationType.COGNITO]

        # if not isinstance(self.cognito_userpools, _cognito.UserPool):
        #     _top_logger.debug(f"No Cognito User Pool found - Cognito AuthN will not be available")
        #     return None
        
        _top_logger.debug("Create Cognito User Pools Authorizer")
        cognito_authorizer = _apigw_v1.CognitoUserPoolsAuthorizer(
            self, c_id,
            cognito_user_pools=self.cognito_userpools if isinstance(self.cognito_userpools,list) else [self.cognito_userpools],
            authorizer_name=f"{self.api_name}CognitoAuthorizer",
            identity_source=_apigw_v1.IdentitySource.header("Authorization"),
            results_cache_ttl=Duration.minutes(0)
        )
        self.authorizers[_apigw_v1.AuthorizationType.COGNITO] = cognito_authorizer
        return cognito_authorizer