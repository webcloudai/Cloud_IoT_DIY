'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
import sys
import argparse
from pathlib import Path
import json
import logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from thingcomm_client.network_lookup import NetworkLookup, AppLayer

def parse_arguments():
    parser = argparse.ArgumentParser(
        description='''Scan local subnet for Thing IP addresses'''
    )
    parser.add_argument("--output", "-o", dest="output_file", required=False, default=None, help="Location of generated json file")
    # parser.add_argument("--tcp", "-t", dest="tcp_port", required=False, default=22, help="TCP port to scan")
    parser.add_argument("--tcp", "-t", dest="tcp_port", required=False, default=80, help="TCP port to scan")

    args = parser.parse_args()
    return args


if __name__=="__main__":
    my_args = parse_arguments()
    output_file = None if my_args.output_file is None else Path(my_args.output_file)    
    tcp_port = int(my_args.tcp_port)    
    print("\n==============================================")
    print("Start network scanning")
    lookup = NetworkLookup()
    collected_data = lookup.collect_ip_addresses(
        tcp_port=tcp_port,
        app_layer=AppLayer.HTTP if tcp_port==80 else AppLayer.SSH)
    print("\n\n==============================================")
    print(f"Network scan results for port {tcp_port}")
    print("==============================================")
    print("##   ip address         host name         MAC address       http response")
    for i,(dev_ip, dev_det) in enumerate(collected_data.items()):
        if not dev_det.get(str(tcp_port), False):
            continue
        print(f"{'>>>' if i==lookup.found_i else ''}{i:2d}: {dev_ip:15s} {dev_det['host']:17s} {dev_det['MAC'] or '':17s}  {dev_det.get('Title','')}")
    result = {
        f"{'>>>' if i==lookup.found_i else ''}{dev_ip:15s} {dev_det['host']:17s}  {dev_det['MAC'] or '':17s}  {dev_det.get('Title','')}":
            {"ip_address":dev_ip}
                for i,(dev_ip, dev_det) in enumerate(collected_data.items())
                    if dev_det.get(str(tcp_port), False)
    }
    if not output_file is None:
        with open(output_file, "w") as f:
            json.dump(result, f)
