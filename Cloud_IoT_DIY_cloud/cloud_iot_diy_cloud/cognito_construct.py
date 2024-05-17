from __future__ import annotations
from enum import Enum
from typing import List
from dataclasses import asdict, dataclass, field
# from uuid import uuid4
import logging
_top_logger = logging.getLogger(__name__)

from aws_cdk import (
    Duration,
    aws_route53,
    aws_route53_targets as targets,
    aws_certificatemanager as acm,
    aws_cognito as cognito,
    SecretValue
)
from constructs import Construct


class SupportedProviders(Enum):
    AMAZON = cognito.UserPoolClientIdentityProvider.AMAZON
    COGNITO = cognito.UserPoolClientIdentityProvider.COGNITO
'''
Dataclass with Cognito UserPool Client parameters
NOTE: it has a bunch of mutable fields which is NOT good 
      maybe replaced with tuples/named tuples but will require set of getters/setters as CDK doesn't like tuples
'''
@dataclass
class CognitoClient:
    name:str
    ''''''
    callback_urls:list = field(default_factory=list)
    ''''''
    logout_urls:list = field(default_factory=list)
    ''' '''
    auth_flows:dict= field(default_factory=lambda: {"admin_user_password":False, "custom":True, "user_srp":True, "user_password":True})
    ''' '''
    oauth_flows:dict= field(default_factory=lambda: { "authorization_code_grant":True, "client_credentials":False, "implicit_code_grant":False})   # see cognito.OAuthFlows for details
    ''' '''
    identity_providers:list= field( default_factory= lambda: [cognito.UserPoolClientIdentityProvider.AMAZON, cognito.UserPoolClientIdentityProvider.COGNITO])
    ''' '''
    scopes:list= field( default_factory= lambda: [cognito.OAuthScope.OPENID] )  #! NOTE that list element type is CDK custom !
    ''' '''
    enable_token_revocation:bool=True
    id_token_validity:Duration=Duration.minutes(5)
    access_token_validity:Duration=Duration.minutes(60)
    refresh_token_validity:Duration=Duration.minutes(60)
    ''' '''
    write_attributes=None
    ''' '''
    read_attributes=None
    ####################################################
    cognito_client:cognito.UserPoolClient=None
    client_secret:SecretValue=None

    def update_with_partial_dict(self, props:dict={}):
        ''' create new instance with updated properties with values from dict provided '''
        res_dict = asdict(self)
        for k,v in props.items():
            if k in res_dict:
                res_dict[k] = v
            else:
                _top_logger.warning(f"{k} is not a valid field for CognitoClient. Ignored.")
        return CognitoClient(**res_dict)

class CognitoConstructL3(Construct):
    '''
    Implements Cognito User Pool and Client with some assumptions
    - authentication URL will be <auth_subdomain>.<parent_domain_name>
    - auth URL certificate will be always located in us-east-1 (AWS restriction)
    - user verification delivered with e-mails only (not SMS)
    - new 
    '''

    def __init__(
            self,
            scope:Construct,
            construct_id,
            *,
            hosted_zone:aws_route53.IHostedZone,
            client_callback_urls:List[str],
            client_logout_urls:List[str],
            parent_domain_name:str,
            auth_subdomain:str="auth",
            user_pool_name:str="main",
            auth_subdomain_certificate_arn:str=None,
            resource_server_id:str=None,
            client_scopes:list=None,
            create_default_client:bool=True,
            identity_providers:List[SupportedProviders]=[i for i in SupportedProviders],
            **kwargs,
        ):
        '''
        @param parent_domain_name is used to assemble cognito url and for auto-generate user communication
        @param client_callback_urls:
        @param client_logout_urls: standard parameters for oAuth flow
        @param parent_domain_name: is used in verification email templates
        @param auth_subdomain: subdomain of parent_domain_name. NOTE: subdomain.parent_domain_name will be attached to Cognito.
        @param identity_providers: list of identity providers to be added w/o extra configuration (see SupportedProviders enum)
        @param client_scopes: TODO created client will have these scopes defined
        @param create_default_client: Cognito client will be created if True
        @param auth_subdomain_certificate_arn: will be used (if provided). Otherwise new cert will be created
        '''
        super().__init__(scope, construct_id, **kwargs)

        self.certificate = None
        self.cognito_user_pool = None
        self.construct_id = construct_id
        self.identity_providers = identity_providers
        self.create_default_client = create_default_client
        
        self.cognito_user_pool_name = f"UserPool-{user_pool_name}-{self.construct_id}"
        
        self.parent_domain_name = parent_domain_name
        self.resource_server_id = resource_server_id or self.parent_domain_name
        if not isinstance(auth_subdomain, str) or len(auth_subdomain)==0:
            raise ValueError(f"auth_subdomain should not be empty!")
        self.cognito_domain = f"{auth_subdomain}.{parent_domain_name}"

        self.__auth_subdomain_certificate_arn = auth_subdomain_certificate_arn
        self.hosted_zone = hosted_zone

        # NOTE: multiple clients are supported for UserPool !
        self.clients:dict = {}

        ######################
        # To support simplified "one-client-flow" default instance value will be updated
        self.default_client = CognitoClient(
            callback_urls=client_callback_urls,
            logout_urls=client_logout_urls,
            name = f"DefaultClient-{self.construct_id}",
            identity_providers=[i.value for i in self.identity_providers],
        )
        if isinstance(client_scopes, list):
            self.default_client.scopes = [cognito.ResourceServerScope(scope_name=v, scope_description=f"Description - {v}") for v in client_scopes]
        else:
            self.default_client.scopes = [
                f"{self.parent_domain_name}/{self.parent_domain_name}",
                f"{self.parent_domain_name}/read",
                f"{self.parent_domain_name}/*"
            ]
        # pre-initiate future single client values
        self.cognito_user_pool_client = None
        self.cognito_user_pool_client_secret = None

        ##################################################
        # Do stuff
        _top_logger.debug("Create certificate")
        self._create_certificate(hosted_zone=self.hosted_zone)
        self._create_cognito_user_pool()
        if self.create_default_client:
            self.create_cognito_client()
        ##################################################


    def _create_certificate(self, hosted_zone):
        if self.__auth_subdomain_certificate_arn:
            # If certificate arn is provided, import the certificate
            self.certificate = acm.Certificate.from_certificate_arn(
                self,
                f"auth_url_certificate{self.construct_id}",
                certificate_arn=self.__auth_subdomain_certificate_arn,
            )
        else:
            # If certificate arn is not provided, create a new one.
            # ACM certificates that are used with CloudFront must be in
            # the us-east-1 region.
            # self.certificate = acm.Certificate(
            #     self, f"auth_url_certificate{self.construct_id}",
            #     domain_name=self.cognito_domain,
            #     validation=acm.CertificateValidation.from_dns(
            #         hosted_zone=hosted_zone
            #     )
            # )
            self.certificate = acm.DnsValidatedCertificate(
                self, f"auth_url_certificate{self.construct_id}",
                domain_name=self.cognito_domain,
                hosted_zone=hosted_zone,
                region="us-east-1",
            )

    def _create_cognito_user_pool(self, props:dict=None):
        ''' 
        see details on https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cognito/README.html
        '''
        self.cognito_user_pool = cognito.UserPool(
            self, f"UserPool{self.construct_id}",
            user_pool_name=self.cognito_user_pool_name,
            self_sign_up_enabled=True,
            deletion_protection=False,
            user_verification=cognito.UserVerificationConfig(
                    email_subject=f"Verify your email for {self.parent_domain_name}",
                    email_body=(f"Thanks for signing up to {self.parent_domain_name}!" + " Your verification code is {####}"),
                    email_style=cognito.VerificationEmailStyle.CODE,
                    sms_message=(f"Thanks for signing up to {self.parent_domain_name}!" + " Your verification code is {####}")
            ),
            user_invitation=cognito.UserInvitationConfig(
                email_subject=f"Invite to join {self.parent_domain_name}!",
                email_body=("Hello {username}, you have been invited to join " + f"{self.parent_domain_name}!" + " Your temporary password is {####}"),
                sms_message=("Hello {username}, your temporary password for " + f"{self.parent_domain_name} is" + " {####}")
            ),
            sign_in_aliases=cognito.SignInAliases(
                # username=True,
                email=True
            ),
            auto_verify=cognito.AutoVerifiedAttrs(email=True, phone=True),
            sign_in_case_sensitive=False,
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(
                    required=True,
                    mutable=True
                ),
                fullname=cognito.StandardAttribute(
                    required=False,
                    mutable=True
                ),
                phone_number=cognito.StandardAttribute(
                    required=False,
                    mutable=True
                ),
                address=cognito.StandardAttribute(
                    required=False,
                    mutable=True
                ),
                profile_picture=cognito.StandardAttribute(
                    required=False,
                    mutable=True
                ),
                preferred_username=cognito.StandardAttribute(
                    required=False,
                    mutable=True
                )
            ),
            custom_attributes={
                "unique_id": cognito.StringAttribute(mutable=False)
            },
            keep_original=cognito.KeepOriginalAttrs(
                email=True,
                phone=True
            ),
            account_recovery=cognito.AccountRecovery.PHONE_AND_EMAIL,
            # For typical production environments, the default email limit is below the required delivery volume. 
            # To enable a higher delivery volume, you can configure the UserPool to send emails through Amazon SES.
            # SMS configuration required https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-sms-settings.html
            # email=cognito.UserPoolEmail.with_sES( ...
        )


        # The default set up for the user pool is configured such that only administrators will be allowed to create users. 
        # Features such as Multi-factor authentication (MFAs) and Lambda Triggers are not configured by default.
        
        # Register Amazon providers
        self.amazon_provider = cognito.UserPoolIdentityProviderAmazon(self, f"AmazonIdP{self.construct_id}",
            client_id="amzn-client-id",
            client_secret="amzn-client-secret",
            user_pool=self.cognito_user_pool,
            attribute_mapping=cognito.AttributeMapping( # ALL REQUIRED ATTRIBUTES MUST BE MAPPED !!!
                email=cognito.ProviderAttribute.AMAZON_EMAIL,
                fullname=cognito.ProviderAttribute.AMAZON_NAME,
                website=cognito.ProviderAttribute.other("url"),  # use other() when an attribute is not pre-defined in the CDK
                custom={
                    # custom user pool attributes go here
                    "unique_id": cognito.ProviderAttribute.AMAZON_USER_ID
                }
            )
        )
        
        # Add resource servers
        #  - add default scopes (if self.default_client.scopes is None)
        # useful link about scopes: https://repost.aws/knowledge-center/cognito-custom-scopes-api-gateway
        self.user_scope = cognito.ResourceServerScope(scope_name=self.parent_domain_name, scope_description="some app")
        self.mobile_scope = cognito.ResourceServerScope(scope_name="mobile", scope_description="mobile app")
        self.web_scope = cognito.ResourceServerScope(scope_name="web", scope_description="web app")
        self.desktop_scope = cognito.ResourceServerScope(scope_name="desktop", scope_description="desktop app")
        #  - add resource server to control API access with custom scopes
        # scopes limit access per TYPE of application (i.e. we can disable sending commands from web app)
        self.api_resource = self.cognito_user_pool.add_resource_server("ResourceServer",
            identifier=self.resource_server_id,
            scopes=self.default_client.scopes if self.create_default_client else [self.user_scope, self.mobile_scope, self.web_scope, self.desktop_scope]
        )

        # Add Domain
        self.cognito_user_pool_domain = self.cognito_user_pool.add_domain(f"CognitoDomain{self.construct_id}",
            custom_domain=cognito.CustomDomainOptions(
                domain_name=self.cognito_domain,
                certificate=self.certificate
            )
        )
        # Add Route53 record for assigned domain
        self.cognito_domain_dns_record = aws_route53.ARecord(
            self,f"UserPoolCloudFrontA{self.construct_id}",
            record_name=self.cognito_domain,
            zone=self.hosted_zone,
            target=aws_route53.RecordTarget.from_alias( targets.UserPoolDomainTarget(self.cognito_user_pool_domain) ),
            delete_existing=True
        )

    def create_cognito_client( self, client_name:str=None, client_props:dict={} ):
        ''' 
        client_props will be expanded with values from default client
        see details on https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cognito/README.html
        for read and write attributes this can be helpful:
            client_write_attributes = (cognito.ClientAttributes()).with_standard_attributes(
            fullname=True, email=True, address=True, profile_picture=True, preferred_username=True,
            birthdate=True, family_name=True).with_custom_attributes("favoritePizza", "favoriteBeverage")

            client_read_attributes = client_write_attributes.with_standard_attributes(email_verified=True, phone_number_verified=True)#.with_custom_attributes("pointsEarned")

        '''
        if not isinstance(client_props, dict):
            client_conf = self.default_client
        else:
            client_conf = self.default_client.update_with_partial_dict(client_props) # client_props has an advantage over default !
        
        if client_name:
            client_conf.name = client_name
        elif isinstance(client_props, dict) and isinstance(client_props.get("client_name", None), str):
            # already assigned
            pass
        elif len(self.clients) == 0:
            # this is first client - can go with default name
            pass
        else:
            raise ValueError(f"An attempt to create second client with default name as unique name was not provided!")

        
        '''
        :param access_token_validity: Validity of the access token. Values between 5 minutes and 1 day are valid. The duration can not be longer than the refresh token validity. Default: Duration.minutes(60)
        :param auth_flows: The set of OAuth authentication flows to enable on the client. Default: - all auth flows disabled
        :param disable_o_auth: Turns off all OAuth interactions for this client. Default: false
        :param enable_token_revocation: Enable token revocation for this client. Default: true for new user pool clients
        :param generate_secret: Whether to generate a client secret. Default: false
        :param id_token_validity: Validity of the ID token. Values between 5 minutes and 1 day are valid. The duration can not be longer than the refresh token validity. Default: Duration.minutes(60)
        :param o_auth: OAuth settings for this client to interact with the app. An error is thrown when this is specified and ``disableOAuth`` is set. Default: - see defaults in ``OAuthSettings``. meaningless if ``disableOAuth`` is set.
        :param prevent_user_existence_errors: Whether Cognito returns a UserNotFoundException exception when the user does not exist in the user pool (false), or whether it returns another type of error that doesn't reveal the user's absence. Default: false
        :param read_attributes: The set of attributes this client will be able to read. Default: - all standard and custom attributes
        :param refresh_token_validity: Validity of the refresh token. Values between 60 minutes and 10 years are valid. Default: Duration.days(30)
        :param supported_identity_providers: The list of identity providers that users should be able to use to sign in using this client. Default: - supports all identity providers that are registered with the user pool. If the user pool and/or identity providers are imported, either specify this option explicitly or ensure that the identity providers are registered with the user pool using the ``UserPool.registerIdentityProvider()`` API.
        :param user_pool_client_name: Name of the application client. Default: - cloudformation generated name
        :param write_attributes: The set of attributes this client will be able to write. Default: - all standard and custom attributes
        '''
        client_conf.cognito_client = self.cognito_user_pool.add_client(f"app-client-{self.construct_id}", 
            user_pool_client_name=client_conf.name,
            auth_flows=client_conf.auth_flows,
            supported_identity_providers=client_conf.identity_providers,
            enable_token_revocation=client_conf.enable_token_revocation,
            id_token_validity=client_conf.id_token_validity,
            access_token_validity=client_conf.access_token_validity,
            refresh_token_validity=client_conf.refresh_token_validity,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows( **client_conf.oauth_flows ),
                scopes=[
                    #! WE ARE RELYING on resource server (self.api_resource) created earlier
                    cognito.OAuthScope.resource_server(self.api_resource, v) for v in client_conf.scopes
                ] + [cognito.OAuthScope.OPENID],
                callback_urls=client_conf.callback_urls,
                logout_urls=client_conf.logout_urls,
            ),
            read_attributes=client_conf.read_attributes,    # self.client_read_attributes,        # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
            write_attributes=client_conf.write_attributes,  # self.client_write_attributes,      # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
            prevent_user_existence_errors=True,              # hardcoded config
            generate_secret=True                             # hardcoded config
        )
        client_conf.client_secret = client_conf.cognito_client.user_pool_client_secret
        if SupportedProviders.AMAZON in self.identity_providers:
            _top_logger.debug(f"Add explicit dependency of client on Amazon IdP")
            client_conf.cognito_client.node.add_dependency(self.amazon_provider)
        else:
            _top_logger.debug(f"Identity providers: {[v.name for v in client_conf.identity_providers]}")
        
        # add latest client info as current to the instance
        self.cognito_user_pool_client = client_conf.cognito_client
        self.cognito_user_pool_client_secret = client_conf.client_secret

        # finally add client to the dict
        self.clients[client_conf.name] = client_name


    def add_identity_provider(self):
        ''' to be used for SSO with 3rd party '''
        raise RuntimeError(f"add_identity_provider not available yet")