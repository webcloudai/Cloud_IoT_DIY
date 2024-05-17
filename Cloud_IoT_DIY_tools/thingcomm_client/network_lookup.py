'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
from typing import Union, List, Tuple, Dict
import socket
from scapy.all import *
from scapy.layers.inet import Ether, TCP, IP
from scapy.layers.l2 import ARP
from ipaddress import IPv4Network
import asyncio
from multiprocessing.pool import ThreadPool
# import requests   # aiohttp is used instead of requests
import aiohttp
#-------------------------
import logging
_top_logger = logging.getLogger(__name__)

async def get_one_url(url, session):
    ''' '''
    # thanks to
    # https://stackoverflow.com/questions/55259755/maximize-number-of-parallel-requests-aiohttp
    try:
        async with session.get(
            url, 
            ssl = False, 
            timeout = aiohttp.ClientTimeout(total=2)
        ) as response:
            content = await response.text()
            print("*",end="")
            return (url, content)
    except Exception as e:
        _top_logger.debug(f"http scan failed for {url} with exception {e}")
        print(".",end="")
        return (url, None)

async def async_get(url_list):
    ''' '''
    tasks = []
    conn = aiohttp.TCPConnector(limit=min(255,len(url_list)), verify_ssl=False)
    async with aiohttp.ClientSession(connector=conn) as session:
        for url in url_list:
            task = asyncio.ensure_future(get_one_url(url, session))
            tasks.append(task)
        responses = asyncio.gather(*tasks)
        await responses
    return responses


def test_port_number(host, port, host_details)->Tuple[str, str]:
    ''' returns True if a connection can be made, False otherwise '''
    host_name = None
    # create and configure the socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        # set a timeout of a few seconds
        sock.settimeout(3)
        # connecting may fail
        try:
            # attempt to connect
            sock.connect((host, port))
            # a successful connection was made
            # _top_logger.info(f"Host {host} with TCP {port} --- OPEN")
            try:
                host_name = socket.gethostbyaddr(host)[0]
            except Exception as host_name_e:
                host_name = None
            return (True, host_name)
        except:
            # ignore the failure
            # _top_logger.info(f"Host {host} with TCP {port} --- CLOSED")
            return (False, host_name)

class AppLayer(Enum):
    HTTP = "HTTP"
    SSH = "SSH"
    FTP = "FTP"

class NetworkLookup:
    
    def collect_all_local_ips(self):
        # scan network if no IP address provided
        # 1. Identify my network address and mask
        self.my_ip = get_if_addr(conf.iface)
        self.my_gw_ip = conf.route.route("0.0.0.0")[2]
        # we'll pick up Netmask from route table with route network for 0 
        # This is questionable but working in most cases (depending from masks )
        self.ip_myrange0 = ".".join(self.my_ip.split(".")[:-1]+["0"])
        self.myrange0 = struct.unpack("!L", socket.inet_aton(self.ip_myrange0))[0]
        nmask = None
        max_deep = 16
        while nmask is None and max_deep>0:
            try:
                nmask=[(nw,nmask,gw,iface,out,metric) for (nw,nmask,gw,iface,out,metric) in conf.route.routes if nw==self.myrange0][0]
            except:
                max_deep -=1
                myrange0 -=256
        if nmask:
            self.netmask = socket.inet_ntoa(struct.pack('!L', nmask[1]))
            self.ip_subnet1 = socket.inet_ntoa(struct.pack('!L', self.myrange0))
            self.netrange = IPv4Network(f"0.0.0.0/{self.netmask}").prefixlen
            _top_logger.info(f"Subnet to scan is {self.ip_subnet1}/{self.netrange}({self.netmask})")
        else:
            _top_logger.critical(f"Fail to identify subnet to scan")
            exit(-1)

        # we have network (subnet) ip and mask so we can start arp_scan
        self.mySubnet = f"{self.ip_subnet1}/{self.netrange}"
        # the full range of ip addresses in our subnet
        self.full_ip_range = {str(ip): {"MAC": "??:??:??:??:??:??"} for ip in IPv4Network(self.mySubnet)}
        _ = self.full_ip_range.pop(self.my_gw_ip, None)
        _ = self.full_ip_range.pop(self.ip_subnet1, None)

    def arp_scan(self)->Dict[str, Dict[str,str]]:
        ''' '''
        try:
            request = ARP()
            request.pdst = self.mySubnet
            broadcast = Ether()
            broadcast.dst = "ff:ff:ff:ff:ff:ff"
            cleints_l = srp( broadcast / request, timeout = 3)
            self.disc_nwdev = {el[1].psrc: {"MAC": el[1].hwsrc} for el in cleints_l[0]}
        except Exception as e:
            _top_logger.warning(f"FAIL to perform ARP scan with exception {e}")
            _top_logger.warning("Will continue with full ip range")
            disc_nwdev = {}
        # let's exclude our GW
        _ = disc_nwdev.pop(self.my_gw_ip, None)
        if len(disc_nwdev)==0:
            _top_logger.warning("ARP found no devices in network. We'll be using full range")
            self.disc_nwdev = self.full_ip_range

    def tcp_scan(self, ports_to_test:Union[int,List[int],Tuple[int]]=80)->Dict[str,Dict]:
        ''' 
            ports_to_test - tuple will be the range of ports, list is specific ports
        '''
        self.tcp_dev = {}
        ports = ports_to_test if isinstance(ports_to_test, (list, tuple)) else [ports_to_test]
        # create a thread pool with 512 threads (number of concurrent socket open attempts)
        with ThreadPool(512) as pool:
            # prepare the arguments - we'll use host port and host details (the last one for convenience only)
            args = [
                (dev_ip, port, dev_det) 
                    for dev_ip, dev_det in self.disc_nwdev.items() 
                        for port in ports]
            # dispatch all tasks
            results = pool.starmap(test_port_number, args)
            # report results in order
            for (dev_ip, port, dev_det),(is_open, host_name) in zip(args,results):
                self.tcp_dev[dev_ip] = {"MAC":dev_det["MAC"], str(port):is_open, "host": host_name or "???"}
                if is_open:
                    _top_logger.info(f"Host {dev_ip} has TCP {port} OPEN")
        

        if len(self.tcp_dev)==0:
            _top_logger.warning(f"No devices with port {ports_to_test} open found. This maybe an error so we'll continue with full list")
            self.tcp_dev = {k:{**v, **{str(port):"UNKNOWN" for port in ports}} for k,v in self.disc_nwdev.items()}
        return self.tcp_dev

    def http_scan(self)->Dict[str,Dict]:
        ''' '''
        self.url_list = [f"http://{v}" for v in self.tcp_dev.keys()]
        self.responses = asyncio.run(async_get(self.url_list)).result()
        self.responses = {v[0]:v[1] for v in self.responses if v[1]!=None}
        self.tcp_dev_with_http = {k:v for k,v in self.tcp_dev.items() if f"http://{k}" in self.responses}
        self.found_i = -1
        for i,(dev_ip, dev_det) in enumerate(self.tcp_dev_with_http.items()):
            try:
                resp_text = self.responses[f"http://{dev_ip}"]
                resp_split = resp_text.split("<title")
                resp_descr:string = ""
                # resp_split = resp_split if len(resp_split)>1 else resp_text.split('itle">')
                if len(resp_split)>0:
                    resp_descr = resp_split[1].split("</title")[0][:20].strip()
                    resp_descr = resp_descr[1:] if resp_descr.startswith(">") else resp_descr
                if len(resp_descr)==0:
                    # no meaningful title found - lets' try to collect the beginning of body
                    resp_split = resp_text.split("<body")
                    resp_descr = resp_split[1][1:21].strip() if len(resp_split)>1 else resp_descr
                self.tcp_dev_with_http[dev_ip] = {**dev_det,"Title":resp_descr}
                if "Thing Configuration Form" in resp_text:
                    self.found_i = i
            except Exception as e:
                _top_logger.debug(f"{dev_ip} no http response")

        return self.tcp_dev_with_http

    def ssh_scan(self)->Dict[str,Dict]:
        ''' '''
        raise ValueError(f"NOT SUPPORTED YET")

    def collect_ip_addresses(self, tcp_port=80, app_layer=AppLayer.HTTP )->Dict[str,Dict]:
        ''' '''
        result = []
        print(f"Collect full ip range of the local subnet")
        self.collect_all_local_ips()
        print(f"Start ARP scan")
        self.arp_scan()
        print(f"Start TCP scan")
        self.tcp_scan(tcp_port)
        self.found_i = -1
        if app_layer==AppLayer.HTTP:
            print("Start http scan", end="")
            self.http_scan()
            result = self.tcp_dev_with_http
        elif app_layer==AppLayer.SSH:
            print("Start ssh scan", end="")
            result = self.tcp_dev
        elif app_layer==AppLayer.FTP:
            print("Start ftp scan", end="")
        else:
            raise ValueError(f"Not supported application layer request {app_layer}")

        print("")
        return result


