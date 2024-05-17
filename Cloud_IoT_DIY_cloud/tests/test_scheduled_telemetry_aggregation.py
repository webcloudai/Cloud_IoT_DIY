''' Unit tests for scheduled_telemetry_aggregation implementation 
    LocalFolder datasource will be used for unit tests
'''
import unittest

from pathlib import Path
import asyncio
import re

import sys
sys.path.insert(1, "../src")
sys.path.insert(1, "./src")

from _objects_datasource import ObjectsDatasource, ObjectsDatasourceFactory, ObjectsDatasourceType
from scheduled_telemetry_aggregation.lambda_code import telemetry_key_grouping_components, aggregate_telemetry_to_annual_history

class TestScheduledTelemetryAggregation(unittest.TestCase):

    def setUp(self):
        self.telemetry_key:str = "${topic(1)}/${topic(2)}/${topic(6)}/${topic(7)}/${parse_time('yyyy',timestamp())}/${parse_time('MM',timestamp())}/${parse_time('dd',timestamp())}/${timestamp()}"
        self.handler_loop = asyncio.get_event_loop()

        # TODO: we need to create known telemetry
        pass

    def test_key_grouping(self):
        ''' test groping prefix extraction '''
        self.assertEqual(
            "(?P<part00>[^/]*)/(?P<part01>[^/]*)/(?P<part02>[^/]*)/(?P<part03>[^/]*)/(?P<part04>[^/]*)/(?P<part05>[^/]*)/(?P<year>[0-9]+)",
            telemetry_key_grouping_components("1/2/3/4/5/6/yyyy/7/8/8/9")
        )
        example_key = "dt/diyiot/DiyThing01/2023/05/09/1683599820642"
        with self.assertRaises(ValueError):
            telemetry_key_grouping_components(example_key)
        result = re.match(
            # r"^(?P<part00>[^/]*)/(?P<part01>[^/]*)/(?P<part02>[^/]*)/(?P<year>[0-9]+)/.+$",
            "^"+telemetry_key_grouping_components(example_key.replace("2023", "yyyy"))+"/.+$",
            example_key
        )
        self.assertEqual(int(result["year"]),2023)
        self.assertEqual(len(result.groups()),4)    # 4 is because we've added a year !

    def test_aggregate_telemetry_to_annual_history(self):
        '''  '''
        grouping_key_prefix = telemetry_key_grouping_components(self.telemetry_key)
        # 1. Datasource for telemetry (to get the data and removed handled data)
        test_telemetry_ds = ObjectsDatasourceFactory.create(
            provider_name=ObjectsDatasourceType.LocalFolder.value, 
            config={"folder_path": Path("tests/telemetry_data")})
        # 2. Datasource for historical data (to get current history and update it)
        test_history_ds = ObjectsDatasourceFactory.create(
            provider_name=ObjectsDatasourceType.LocalFolder.value, 
            config={"folder_path": Path("tests/history_data")})
        # 3. Create context
        invocation_context:dict = {
            "group_prefix": grouping_key_prefix
        }

        # Now we are ready to proceed with logic invocation
        # Our microservice logic is async so we need 
        if self.handler_loop.is_closed():
            self.handler_loop = asyncio.new_event_loop()
        result:dict = self.handler_loop.run_until_complete(
            aggregate_telemetry_to_annual_history(test_telemetry_ds, test_history_ds, **invocation_context)
        )
        
        # TODO: we need to create known telemetry in setup and assert aggregation results here
        self.assertEqual(1,1)


    def test_cloud_aggregate_telemetry_to_annual_history(self):
        '''  '''
        grouping_key_prefix = telemetry_key_grouping_components(self.telemetry_key)
        historical_s3_bucket_name = "iotdiyuseast1historicaldata"
        telemetry_s3_bucket_name = "iotdiyuseast1telemetrydata"
        # 1. Datasource for telemetry (to get the data and removed handled data)
        test_telemetry_ds = ObjectsDatasourceFactory.create(
            provider_name=ObjectsDatasourceType.S3Bucket.value, 
            config={"bucket_name": telemetry_s3_bucket_name, "key_prefix": ""})
        # 2. Datasource for historical data (to get current history and update it)
        test_history_ds = ObjectsDatasourceFactory.create(
            provider_name=ObjectsDatasourceType.S3Bucket.value, 
            config={"bucket_name": historical_s3_bucket_name, "key_prefix": ""})
        # 3. Create context
        invocation_context:dict = {
            "group_prefix": grouping_key_prefix
        }

        # Now we are ready to proceed with logic invocation
        # Our microservice logic is async so we need
        if self.handler_loop.is_closed():
            self.handler_loop = asyncio.new_event_loop()
        result:dict = self.handler_loop.run_until_complete(
            aggregate_telemetry_to_annual_history(test_telemetry_ds, test_history_ds, **invocation_context)
        )
        
        # TODO: we need to create known telemetry in setup and assert aggregation results here
        self.assertEqual(1,1)



    def tearDown(self):
        # TODO: cleanup create test telemetry and history data
        if not self.handler_loop.is_closed():
            self.handler_loop.close()
