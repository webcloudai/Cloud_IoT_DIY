from pathlib import Path
from aws_cdk import (
    aws_s3 as _s3,
    aws_cloudfront as _cloudfront,
    aws_cloudfront_origins as _origins,
    aws_certificatemanager as _acm,
    aws_route53 as _route53,
    aws_route53_targets as _targets,
    aws_logs as _logs,
    aws_iam as _iam,
    aws_ssm as _ssm,
    RemovalPolicy,
    aws_s3_deployment as _s3_deploy,
    Duration
)
from constructs import Construct


class WebSitePrivateBucketConstructL3(Construct):
    ''' '''

    def __init__(self, scope:Construct, construct_id:str,
            site_bucket:_s3.IBucket,
            site_domain_name:str,
            hosted_zone:_route53.IHostedZone,

            #======================================================
            # Optional parameters
            #* You should clearly understand what you are doing before changing these parameters!
            content_location:Path=Path("../Cloud_IoT_DIT_website/web"),
            site_index_html:str="index.html",
            upload_content:bool=True,
            site_domain_certificate_arn:str=None

        ) -> None:
        ''' '''
        super().__init__(scope, construct_id)

        self.construct_id = construct_id,
        self.bucket = site_bucket
        self.site_domain_name = site_domain_name
        self.hosted_zone = hosted_zone
        #
        self.site_index_html = site_index_html
        self.content_location:Path = content_location
        self.upload_content = upload_content
        self.site_domain_certificate_arn = site_domain_certificate_arn

        #################################################################################
        #
        # Build Static Web-Site
        #
        # --------------------
        # 1. Create certificate for API domain
        if self.site_domain_certificate_arn:
            # If certificate arn is provided, import the certificate
            self.certificate = _acm.Certificate.from_certificate_arn(
                self,
                "site_certificate",
                certificate_arn=self.site_domain_certificate_arn,
            )
        else:
            # If certificate arn is not provided, create a new one.
            # ACM certificates that are used with CloudFront must be in
            # the us-east-1 region.
            # self.certificate = _acm.Certificate(
            #     self, f"site_certificate{self.construct_id}",
            #     domain_name=self.site_domain_name,
            #     certificate_name=f"site{self.construct_id}",
            #     validation=_acm.CertificateValidation.from_dns(self.hosted_zone)
            # )
            self.certificate = _acm.DnsValidatedCertificate(
                self, f"site_certificate{self.construct_id}",
                domain_name=self.site_domain_name,
                hosted_zone=self.hosted_zone,
                region="us-east-1",
            )
        # --------------------
        # 2. Define a cloudfront distribution with a private bucket as the origin
        # This is actually where the site delivery is defined
        self.cloud_formation_distribution = _cloudfront.Distribution(
            self,
            f"CloudFrontDistribution{self.construct_id}",
            default_behavior=_cloudfront.BehaviorOptions(
                origin=_origins.S3Origin(self.bucket),
                viewer_protocol_policy=_cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            domain_names=[self.site_domain_name],
            certificate=self.certificate,
            default_root_object=self.site_index_html,
        )
        # --------------------
        # 3. Define A-Record in Route53 zone for site domain name
        self.a_record = _route53.ARecord(
            self, f"WebSiteARecord{self.construct_id}",
            target=_route53.RecordTarget.from_alias(_targets.CloudFrontTarget(self.cloud_formation_distribution)),
            zone=self.hosted_zone,
            delete_existing=True,
            record_name=self.site_domain_name,
            ttl=Duration.minutes(30)
        )
        # --------------------
        # 4. Upload site-content
        if self.upload_content:
            _s3_deploy.BucketDeployment(
                self, f"WebSiteDeployment{self.construct_id}",
                destination_bucket=self.bucket,
                sources=[_s3_deploy.Source.asset(str(self.content_location))],
                distribution=self.cloud_formation_distribution,
                distribution_paths=["/*"],
                log_retention=_logs.RetentionDays.ONE_WEEK,
                prune=True, # If this is set to false, files in the destination bucket that do not exist in the asset, will NOT be deleted during deployment (create/update). Default: true
                # *NOTE* Multiple AWS CDK defaults are in use !
                # @see https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_s3_deployment/BucketDeployment.html
                # access_control=None, cache_control=None,
                # content_disposition=None, content_encoding=None,
                # content_language=None, content_type=None,
                # destination_key_prefix=None, ephemeral_storage_size=None,
                # exclude=None, expires=None, memory_limit=None, metadata=None,
                # retain_on_delete=None, role=None,
                # server_side_encryption=None, server_side_encryption_aws_kms_key_id=None,
                # server_side_encryption_customer_algorithm=None,
                # storage_class=None, use_efs=None, vpc=None, vpc_subnets=None,
                # website_redirect_location=None
            )        
