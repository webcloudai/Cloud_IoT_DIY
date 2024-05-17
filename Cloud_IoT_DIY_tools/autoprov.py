'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
import sys
import argparse
from pathlib import Path
import logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_top_logger = logging.getLogger(__name__)
if not _top_logger.hasHandlers():
        _top_logger.addHandler(logging.StreamHandler(stream=sys.stderr))

from thingcomm_client.network_lookup import NetworkLookup
#--- we'll add path to PATH to enable import of common_project_config
sys.path.append("../Cloud_IoT_DIY_cloud")
from common_project_config import ProjectConfig


def parse_arguments():
    parser = argparse.ArgumentParser(
        description='''Push properties required for Thing 'fleet provisioning' including latest claim certificate and keys
NOTE that if you will run without IP address /network scan option/ you have to run with admin privileges!''',
        usage='''
Run with known IP address:
python3 autoprov.py --ip 192.168.1.87 --name MyThing005 --type AirSensor --buildingId b001 --locationId l005
Run in network scanning mode:
sudo python3 autoprov.py --name MyThing005 --type AirSensor --buildingId b001 --locationId l005
'''
    )
    parser.add_argument("--name", "-n", dest="thing_name", required=True, help="[REQUIRED] Unique name of your Thing")
    parser.add_argument("--group", "-g", dest="thing_group", required=True, help="[REQUIRED] Your Thing group")    
    parser.add_argument("--type", "-t", dest="thing_type", required=True, help="[REQUIRED] Your Thing type")    
    parser.add_argument("--buildingId", "-b", dest="building_id", required=True, help="[REQUIRED] Your Thing building id")    
    parser.add_argument("--locationId", "-l", dest="location_id", required=True, help="[REQUIRED] Your Thing location id")
    parser.add_argument("--ip", "-i", dest="ip_address", required=False, default=None, help="[OPTIONAL] IP address of your thing. Scan will be executed if not provided.")

    args = parser.parse_args()
    return args

if __name__=="__main__":
    #################################################################################
    # Collect Project Configuration
    pr_config = ProjectConfig.create_from_file()
    newest_cert_p:Path = sorted([v for v in Path(pr_config.bootstrapcert_local_folder).glob("*.cert.pem")], key=lambda x: x.stat().st_mtime)[-1]
    newest_keys_p:Path = newest_cert_p.with_stem(newest_cert_p.stem.replace(".cert",".keys"))

    # parse and collect command line arguments
    my_args = parse_arguments()
    _top_logger.debug(f"Will be executed with parameters:\nCert: {newest_cert_p}\nKeys: {newest_keys_p}\nArguments:\n{my_args}")

    # we need an IP address
    ip_address = my_args.ip_address
    ip_address = "192.168.1.118"
    if ip_address is None:
        print("\n==============================================")
        print("Start network scanning")
        lookup = NetworkLookup()
        lookup.collect_ip_addresses()
        print("\n\n==============================================")
        print(f"Network scan results")
        print("==============================================")
        print("##   ip address         MAC address       http response")
        for i,(dev_ip, dev_det) in enumerate(lookup.tcp_dev_with_http.items()):
            if not dev_det.get("80", False):
                continue
            print(f"{'>>>' if i==lookup.found_i else ''}{i:2d}: {dev_ip:15s}  {dev_det['MAC'] or '':20s} {dev_det.get('Title','')}")
        print(f"{'>>>' if lookup.found_i==-1 else ''} Enter IP address manually")
        while ip_address is None:
            try:
                resp = input("Choose or enter ip address: ")
                if len(resp) < 5:
                    j = int(resp)
                    ip_address = list(lookup.tcp_dev_with_http.keys())[j]
                else:
                    ip_address = resp
            except:
                if lookup.found_i >= 0:
                    ip_address = list(lookup.tcp_dev_with_http.keys())[lookup.found_i]
    
    # we now have all required parameters to push to thing for fleet provisioning
    # assemble http POST payload
    with open(newest_cert_p, "r") as f:
        claim_cert = f.read()
    with open(newest_keys_p, "r") as f:
        claim_keys = f.read()
    form_data = {
        "ThingName": my_args.thing_name,
        "ThingGroup": my_args.thing_group,
        "ThingType": my_args.thing_type,
        "ThingBuilding": my_args.building_id,
        "ThingLocation": my_args.location_id,
        "ClaimCert": claim_cert,
        "ClaimKeys": claim_keys
    }

    pass