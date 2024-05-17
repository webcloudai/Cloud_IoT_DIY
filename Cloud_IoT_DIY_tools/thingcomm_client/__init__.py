'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
from typing import Dict, List, Any, Tuple, Union, Callable
from time import sleep, time
from datetime import datetime
import io
import json
from abc import ABC, abstractmethod
from enum import Enum
# Serial client
from serial import Serial
from serial.tools import list_ports
from dataclasses import dataclass
# IP-client
import asyncio
import aiohttp
import paramiko

#-------------------------
import logging
_top_logger = logging.getLogger(__name__)


class ThingCommType(Enum):
    IP = "IP"
    IP_SSH = "IP-SSH"
    BLE = "BLE"
    SERIAL = "Serial"


class ThingCommClient(ABC):
    COMM_TYPE = None
    #! NOTE that these SESSION parameters will be overwritten with values from project_config.json
    CONFIG_SESSION_REQUEST = "Request config over Serial"
    CONFIG_SESSION_CONFIRM = "Serial confirmed"
    CONFIG_SESSION_CLOSE = "Config over Serial completed"
    CONFIG_SESSION_START_DATA = "Start data transmission"
    SERIAL_COMM_TIMEOUT_MS = 3000
    
    @property
    def connected(self)->bool:
        return self._connected

    def __init__(self, **kwargs) -> None:
        ''' '''
        self._client_error:str = ""
        self._logs:List[str] = []
        self.log_callback:Callable = None
        self.available:bool = False
        self._connected:bool = False
        self.comm_id:str = None
        self.project_config:dict = kwargs.get("project_config",{})
        self.CONFIG_SESSION_REQUEST = self.project_config.get("CONFIG_SESSION_REQUEST", self.CONFIG_SESSION_REQUEST)
        self.CONFIG_SESSION_CONFIRM = self.project_config.get("CONFIG_SESSION_CONFIRM", self.CONFIG_SESSION_CONFIRM)
        self.CONFIG_SESSION_CLOSE = self.project_config.get("CONFIG_SESSION_CLOSE", self.CONFIG_SESSION_CLOSE)
        self.CONFIG_SESSION_START_DATA = self.project_config.get("CONFIG_SESSION_START_DATA", self.CONFIG_SESSION_START_DATA)
        self.SERIAL_COMM_TIMEOUT_MS = int(self.project_config.get("SERIAL_COMM_TIMEOUT_MS", self.SERIAL_COMM_TIMEOUT_MS))

    def logs_append(self, message:str):
        self._logs.append(message)
        if isinstance(self.log_callback, Callable):
            self.log_callback()
            return

    @abstractmethod
    def get_comm_options(self)->Dict[str, Any]:
        ''' '''
    @abstractmethod
    def connect(self, **kwargs)->str:
        ''' '''
    @abstractmethod
    async def disconnect(self)->bool:
        ''' '''
    @abstractmethod
    def send_form_data(self, data:Dict[str, any], log_callable:Callable=None)->str:
        ''' '''
    @abstractmethod
    def get_data(self, **kwargs)->str:
        ''' '''
    @abstractmethod
    def test_connection(self, **kwargs)->str:
        ''' '''

class ThingCommFactory:
    @staticmethod
    def client_with(comm_type:ThingCommType, options:Dict)->ThingCommClient:
        ''' '''
        if comm_type == ThingCommType.SERIAL:
            return SerialCommClient(**options)
        if comm_type == ThingCommType.IP:
            return IpCommClient(**options)
        if comm_type == ThingCommType.BLE:
            return BleCommClient(**options)
        if comm_type == ThingCommType.IP_SSH:
            return SshCommClient(**options)

@dataclass
class SerialDevice:
    port:str
    name:str
    description:str
    hardware:str

class SerialCommClient(ThingCommClient):
    COMM_TYPE = ThingCommType.SERIAL

    def get_comm_options(self)->Dict[str,Dict[str,SerialDevice]]:
        ''' '''
        return {
            p.name:{"device":SerialDevice(name=p.name, port=p.device, hardware=p.hwid, description=p.description)}
                for p in sorted(list_ports.comports())}

    def _start_session(self)->str:
        ''' Serial specific method to start comm session '''
        self.retry_attempts = 5
        i = 0
        self.ser.reset_input_buffer()
        while i<self.retry_attempts and not self.config_session:
            i+=1
            try:
                self.ser.write(f"{self.CONFIG_SESSION_REQUEST}".encode(encoding="utf-8"))
                # resp = [v.decode(encoding="utf-8").replace("\n","").replace("\r","") for v in self.ser.readlines()]
                resp = [v.decode(encoding="utf-8").replace("\r\n","") for v in self.ser.readlines()]
                for v in resp:
                    # print(v)
                    self.logs_append(v)
                    self.config_session = v == self.CONFIG_SESSION_CONFIRM#.encode(encoding="utf-8")
                    if self.config_session:
                        break
            except Exception as e:
                resp = f"FAIL to start config session with exception {e}"
                _top_logger.error(resp)
                self.logs_append(resp)
            if not self.config_session:
                sleep(1)
        return "\n".join(self._logs)+"\nSUCCESS starting comm session\n" if self.config_session else f"FAIL TO START A SESSION\nTry to RESTART your Thing and use 'Test connection'"

    def connect(self, device:SerialDevice, baudr:int=115200, timeout=0.3) -> str:
        result = ""
        self.dev = device
        self.comm_id = self.dev.port
        self.ser = getattr(self, "ser", Serial(port=self.dev.port, timeout=timeout, baudrate=baudr, dsrdtr=False))
        self.config_session:bool = False
        return self.test_connection()

    def _close_session(self)->str:
        ''' '''
        self.ser.write(self.CONFIG_SESSION_CLOSE.encode(encoding="utf-8"))
        # responses = [v.decode(encoding="utf-8").replace("\n","").replace("\r","") for v in self.ser.readlines()]
        responses = [v.decode(encoding="utf-8").replace("\r\n","") for v in self.ser.readlines()]
        for v in responses:
            self.logs_append(v)
        return "\n".join(responses)


    async def disconnect(self)->bool:
        try:
            self.ser.close()
        except Exception as e:
            _top_logger.warning(f"FAIL to close serial connection with exception {e}")
            return False
        return True

    def _collect_expected_data_with_optional_send(self, 
            expected_responses: Union[str,List[str]], 
            retry_attempts:int = 0, 
            send_data:str=None)->Tuple[Dict[str,bool],List[str]]:
        ''' 
            send the data and wait for confirmation
            for example: send_data "<a>:::<b>" expect ["<a>", "<b>"]
            expected response will be waited until timeout at self.SERIAL_COMM_TIMEOUT_MS/100
            retry_attempts defines how many time data send will be retried 
        '''
        exp_responses:List[str] = expected_responses if isinstance(expected_responses,list) else [expected_responses]
        resp_found:Dict[str,bool] = { v:False for v in exp_responses}
        encoded_mapping = {f"{v}\r\n".encode(encoding="utf-8"):v for v in exp_responses}
        for i in range(retry_attempts+1):
            try:
                if isinstance(send_data, str):
                    message = f"([{i}] {datetime.now()}) Send over serial '{send_data[:40]}'"
                    self.logs_append(message)
                    _top_logger.debug(message)
                    self.ser.write(send_data.encode(encoding="utf-8"))
                start_time = time()
                while time()-start_time < self.SERIAL_COMM_TIMEOUT_MS/100 and not all(resp_found.values()):
                    for v in self.ser.readlines():
                        try:
                            dec_v = v.decode(encoding="utf-8").replace("\r\n","")
                        except Exception as dec_e:
                            # fail to decode
                            _top_logger.debug(f"FAIL TO DECODE:\n{v}"[:50])
                            dec_v = None
                        self.logs_append(dec_v[:40] or f"unable to decode value {v}"[:40])
                        if dec_v in resp_found or v in encoded_mapping:
                            resp_found[dec_v or encoded_mapping[v]] = True
                            self.logs_append(f"{(dec_v or encoded_mapping[v])[:40]} CONFIRMED")
                            if all(resp_found.values()):
                                break
                        if dec_v == self.CONFIG_SESSION_CLOSE:
                            # we have session closure from the Thing
                            raise ConnectionAbortedError("Session closed by Thing")
                    sleep(0.3)
            except ConnectionAbortedError as e:
                # connection closed by Thing
                resp = f"([{i}] {datetime.now()}) CONNECTION FAILURE with exception '{e}'"
                _top_logger.error(resp)
                self.logs_append(f"{resp}")
                break
            except Exception as e:
                resp = f"([{i}] {datetime.now()}) FAIL to collect responses '{exp_responses}' with exception {e}"
                _top_logger.error(resp)
                self.logs_append(f"{resp}")
            if all(resp_found.values()):
                if isinstance(send_data, str):
                    self.logs_append(f"{send_data[:40]} sent with confirmation received")
                break
        return (all(resp_found.values()), self._logs, resp_found)

    def send_form_data(self, data:Dict[str, any], log_callable:Callable=None)->str:
        ''' '''
        # self.form = aiohttp.F
        self.log_callback = log_callable
        self._logs = []
        self._start_session()
        if not self.config_session:
            self.logs_append("FAIL TO START SESSION")
            return "\n".join(self._logs)
        send_success = True
        # self.ser.flush()
        self.ser.reset_input_buffer()
        # 1. Build dict to send
        # send_data = [
        #     f"{k}\n{type(v)}\n{str(v) if isinstance(v, (str, int, float, bool)) else json.dumps(v)}\n\n".encode(encoding="utf-8")
        #         for k,v in data.items()
        # ]
        # 2. Send 
        # self.ser.write(f"{self.CONFIG_SESSION_START_DATA}".encode(encoding="utf-8"))
        (confirmed, conf_logs, conf_details) = self._collect_expected_data_with_optional_send(
            expected_responses=self.CONFIG_SESSION_START_DATA,
            retry_attempts=3,
            send_data=self.CONFIG_SESSION_START_DATA
        )
        _top_logger.debug(f"Start data transition details: {conf_details}")
        # result.extend(conf_logs)
        if not confirmed:
            self.logs_append("FAIL get a confirmation of data transfer")
            return "\n".join(self._logs)
        else:
            self.logs_append("Data transfer confirmed")

        # to avoid errors on serial transmission we'll send line by line and control confirmation
        for data_k,data_v in data.items():
            confirmed = False
            value_2_send = f"{str(data_v) if isinstance(data_v, (str, int, float, bool)) else json.dumps(data_v)}"
            line_2_send = f"{data_k}:::{value_2_send}"#.encode(encoding="utf-8")
            (confirmed, conf_logs, conf_details) = self._collect_expected_data_with_optional_send(
                expected_responses=[data_k, value_2_send],
                retry_attempts=3,
                send_data=line_2_send
            )
            _top_logger.debug(f"Confirmation  details: {conf_details}")
            if not confirmed:
                # we fail to send the data
                self.logs_append(f"FAIL to confirm data send for {line_2_send[:30]}")
                send_success = False
                break
        if send_success:
            self.ser.write(self.CONFIG_SESSION_CLOSE.encode(encoding="utf-8"))
            self.logs_append("SUCCESSFULLY SENT DATA OVER SERIAL CONNECTION")
            # (confirmed, conf_logs, _) = self._collect_expected_data_with_optional_send(
            #     expected_responses=self.CONFIG_SESSION_CLOSE,
            #     retry_attempts=0,
            #     send_data=self.CONFIG_SESSION_CLOSE
            # )
            # result.extend(conf_logs)
        else:
            self.logs_append("FAIL TO SEND DATA OVER SERIAL CONNECTION")
        
        self.ser.reset_input_buffer()
        return "\n".join(self._logs)
        # 3. Validate data transmission
        # for i, resp in enumerate(responses):
        #     if i==0:
        #         if resp != self.CONFIG_SESSION_CONFIRM.encode(encoding="utf-8"):
        #             raise ConnectionError(f"Fail to send data - confirmation was not received")
        #         else:
        #             continue
        #     elif i<len(responses)-1:
        #         # we have data lines
        #         if resp!=send_data[i-1]:
        #             # we have a problem
        #             raise ConnectionError(f"Fail to send data - value was corrupted")
        #     else:
        #         # last message should be confirmation that session closed
        #         if resp != self.CONFIG_SESSION_CLOSE.encode(encoding="utf-8"):
        #             raise ConnectionError(f"Fail to send data - config session was not closed")
        #         else:
        #             continue
        # we're good to go

    # def send_form_data(self, data: Dict[str,any])->str:
    #     ''' '''
    #     return "MOCKED "
    def get_data(self, **kwargs)->str:
        ''' '''

    def test_connection(self, **kwargs)->str:
        ''' '''
        result = self._start_session()
        sleep(0.3)
        result += self._close_session()
        return result

class IpCommClient(ThingCommClient):
    ''' '''
    COMM_TYPE = ThingCommType.IP

    async def session(self):
        if self._session and not self._session.closed:
            if self._conn and not self._conn.closed and self._session.loop.is_running():
                return self._session
        try:
            await self.disconnect()
        except:
            pass
        self._conn:aiohttp.TCPConnector = aiohttp.TCPConnector(verify_ssl=False)
        self._session:aiohttp.ClientSession = aiohttp.ClientSession(connector=self._conn)
        return self._session
        
    async def get_one_url(self, url):
        ''' '''
        try:
            session = await self.session()
            async with session.get( url, ssl = False ) as response:
                content = await response.text()
                return content
        except Exception as e:
            self._client_error = f"http get failed for {url} with exception {e}"
            _top_logger.debug(self._client_error)
            return None

    async def post_to_url(self, url:str, payload:Union[dict,str]):
        ''' '''
        try:
            session = await self.session()
            data_2_send = payload.encode(encoding="utf-8") if isinstance(payload,str) else payload
            async with session.post( url, data=data_2_send, ssl = False ) as response:
                http_resp = response.status
                if http_resp!=200:
                    reason = response.reason or "N/A"
                    raise ConnectionError(f"HTTP response {http_resp} with reason '{reason}'")
                content = await response.text()
                return content
        except Exception as e:
            self._client_error = f"http post failed for {url} with exception {e}"
            _top_logger.debug(self._client_error)
            return None

    def get_comm_options(self)->Dict[str, Any]:
        ''' '''
        raise RuntimeError(f"IpCommClient does not support 'get_comm_options'. Use scan_ip.py instead!")

    def connect(self, ip_address, **kwargs)->str:
        ''' '''
        self.comm_id = ip_address
        self.ip_address = ip_address
        self.url = f"http://{ip_address}"
        self._conn = None
        self._session = None
        return "Connection configured. Use 'Test connection' to verify"

    async def disconnect(self)->bool:
        ''' '''
        try:
            await self._session.close()
            self._session = None
            self._conn = None
        except Exception as e:
            self._client_error = f"FAIL to close aiohttp session with exception {e}"
            _top_logger.debug(self._client_error)
            return False
        return True

    def send_form_data(self, data: Dict[str,any], log_callable:Callable=None)->str:
        ''' use data to generate standard html-form submit POST 
        NOTE that expected method is POST
        Content-Type: application/x-www-form-urlencoded
        and payload is ThingName=Name&ThingGroup=diyiot&ThingType=DiyThing&ThingBuilding=BuildingID...
        '''
        self.log_callback = log_callable
        self._logs = []
        self._client_error = ""
        # see https://docs.aiohttp.org/en/stable/client_quickstart.html
        # "More complicated POST requests" part
        converted_data = data
        try:
            #! !!!!!!!! /submittedForm - PROJECT CONST !!!!
            self.response = asyncio.run(self.post_to_url(f"{self.url}/submittedForm", payload=converted_data))
            if self.response is None:
                if len(self._client_error)>0:
                    raise ConnectionError(self._client_error)
                else:
                    self.response = "EMPTY"
        except Exception as e:
            message = f"FAIL to place a request with exception {e}"
            self.logs_append(message)
            _top_logger.error(message)
            return message
        self.logs_append(self.response)
        # validate response

        return self.response

    def get_data(self, path:str="", **kwargs)->str:
        ''' '''
        self._client_error = ""
        try:
            self.response = asyncio.run(self.get_one_url(f"{self.url}/{path}"))
            # task = asyncio.ensure_future(self.get_one_url(f"{self.url}/{path}"))
            # self.response = asyncio.run(asyncio.gather([task]))
            # self.response = asyncio.run(asyncio.gather([task])).result()
            if self.response is None:
                if len(self._client_error)>0:
                    raise ConnectionError(self._client_error)
                else:
                    self.response = "EMPTY"
        except Exception as e:
            message = f"FAIL to place a request with exception {e}"
            _top_logger.error(message)
            return message
        return self.response

    def test_connection(self, **kwargs)->str:
        ''' '''
        return self.get_data()
        

class SshCommClient(ThingCommClient):
    ''' '''
    COMM_TYPE = ThingCommType.IP_SSH
    FIRMWARE_DIR_ON_THING = "RPi_firmware"

    async def session(self):
        if self._session and not self._session.closed:
            if self._conn and not self._conn.closed and self._session.loop.is_running():
                return self._session
        try:
            await self.disconnect()
        except:
            pass
        self._conn:aiohttp.TCPConnector = aiohttp.TCPConnector(verify_ssl=False)
        self._session:aiohttp.ClientSession = aiohttp.ClientSession(connector=self._conn)
        return self._session
        
    async def get_one_url(self, url):
        ''' '''
        try:
            session = await self.session()
            async with session.get( url, ssl = False ) as response:
                content = await response.text()
                return content
        except Exception as e:
            self._client_error = f"http get failed for {url} with exception {e}"
            _top_logger.debug(self._client_error)
            return None

    async def post_to_url(self, url:str, payload:Union[dict,str]):
        ''' '''
        try:
            session = await self.session()
            data_2_send = payload.encode(encoding="utf-8") if isinstance(payload,str) else payload
            async with session.post( url, data=data_2_send, ssl = False ) as response:
                http_resp = response.status
                if http_resp!=200:
                    reason = response.reason or "N/A"
                    raise ConnectionError(f"HTTP response {http_resp} with reason '{reason}'")
                content = await response.text()
                return content
        except Exception as e:
            self._client_error = f"http post failed for {url} with exception {e}"
            _top_logger.debug(self._client_error)
            return None

    def get_comm_options(self)->Dict[str, Any]:
        ''' for ssh communication two options are required - user name AND password '''
        return {
            "user_name": "Please provide user name for this SSH connection",
            "user_pass": "Please provide password for this user name to connect over SSH"
        }

    def connect(self, ip_address:str, user_name:str, user_pass:str, **kwargs)->str:
        ''' '''
        self.comm_id = ip_address
        self.ip_address = ip_address
        self.ssh_user = user_name
        self.ssh_pass = user_pass
        self._ssh_client = paramiko.SSHClient()
        self._ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # self.ssh_command = f"ssh {self.ssh_user}:{self.ssh_pass}@{ip_address}"
        self._conn = self._ssh_client.connect(
            hostname=self.ip_address,
            username=self.ssh_user,
            password=self.ssh_pass
        )
        # self._session = None
        return "Connection configured. Use 'Test connection' to verify"

    async def disconnect(self)->bool:
        ''' '''
        try:
            await self._session.close()
            self._session = None
            self._conn = None
        except Exception as e:
            self._client_error = f"FAIL to close aiohttp session with exception {e}"
            _top_logger.debug(self._client_error)
            return False
        return True

    def send_form_data(self, data: Dict[str,any], log_callable:Callable=None)->str:
        ''' use data to generate standard html-form submit POST 
        NOTE that expected method is POST
        Content-Type: application/x-www-form-urlencoded
        and payload is ThingName=Name&ThingGroup=diyiot&ThingType=DiyThing&ThingBuilding=BuildingID...
        '''
        self.log_callback = log_callable
        self._logs = []
        self._client_error = ""
        # see https://docs.aiohttp.org/en/stable/client_quickstart.html
        # "More complicated POST requests" part
        converted_data = data
        try:
            #! !!!!!!!! /submittedForm - PROJECT CONST !!!!
            self.response = asyncio.run(self.post_to_url(f"{self.url}/submittedForm", payload=converted_data))
            if self.response is None:
                if len(self._client_error)>0:
                    raise ConnectionError(self._client_error)
                else:
                    self.response = "EMPTY"
        except Exception as e:
            message = f"FAIL to place a request with exception {e}"
            self.logs_append(message)
            _top_logger.error(message)
            return message
        self.logs_append(self.response)
        # validate response

        return self.response

    def get_data(self, path:str="", **kwargs)->str:
        ''' '''
        self._client_error = ""
        try:
            self.response = asyncio.run(self.get_one_url(f"{self.url}/{path}"))
            # task = asyncio.ensure_future(self.get_one_url(f"{self.url}/{path}"))
            # self.response = asyncio.run(asyncio.gather([task]))
            # self.response = asyncio.run(asyncio.gather([task])).result()
            if self.response is None:
                if len(self._client_error)>0:
                    raise ConnectionError(self._client_error)
                else:
                    self.response = "EMPTY"
        except Exception as e:
            message = f"FAIL to place a request with exception {e}"
            _top_logger.error(message)
            return message
        return self.response

    def test_connection(self, **kwargs)->str:
        ''' '''
        result = "Testing connection ...\n"
        commands = [
            "pwd", 
            "ls", 
            f"mkdir {self.FIRMWARE_DIR_ON_THING} ; ls"
        ]
        #
        for command in commands:
            if f"mkdir {self.FIRMWARE_DIR_ON_THING}" in command:
                _stdin, _stdout,_stderr = self._ssh_client.exec_command(command)
                ls_command_stdout = _stdout.read().decode()
                if self.FIRMWARE_DIR_ON_THING in ls_command_stdout:
                    # we have FIRMWARE_DIR_ON_THING already
                    # we should either delete it or just skip mkdir command
                    # we'll skip
                    continue
            result += f">>> {command}\n"
            _stdin, _stdout,_stderr = self._ssh_client.exec_command(command)
            command_stdout = _stdout.read().decode()
            result += command_stdout + "\n"
            

        return result

        

class BleCommClient(ThingCommClient):
    COMM_TYPE = ThingCommType.BLE

    def get_comm_options(self)->Dict[str, Any]:
        ''' '''
        return {"Not supported": {"device_id": None}}

    def connect(self, **kwargs)->str:
        ''' '''
        return "BLE NOT SUPPORTED FOR NOW !!!"

    async def disconnect(self)->bool:
        ''' '''

    def send_form_data(self, data: Dict[str,any], log_callable:Callable=None)->str:
        ''' '''

    def get_data(self, **kwargs)->str:
        ''' '''

    def test_connection(self, **kwargs)->str:
        ''' '''


if __name__=="__main__":
    print("\n\n")
    scomm = SerialCommClient()
    s_devices = scomm.get_comm_options()
    for n, (name, sd) in enumerate(s_devices.items()):
        print(f"{name:20}")
        print(f"        port: {sd['device'].port}")
        print(f" description: {sd['device'].description}")
        print(f"        hwid: {sd['device'].hardware}")
        print("\n")
    print("\n\n")
    port_to_use = s_devices["cu.usbserial-10"]["device"]
    scomm.connect(port_to_use)
    if scomm.ser.is_open:
        # scomm.ser.close()
        scomm.ser.reset_input_buffer()
        # send "<<RESET SERIAL>>"
        # sleep(2)
        # scomm.ser.write("<<RESET SERIAL>>".encode("utf-8"))
        i=0
        while True:
            resp, resp_b = None, None
            try:
                # resp_b = scomm.ser.readline()
                # resp = resp_b.decode("utf-8")
                resp = scomm.sio.readline().replace("\n","")
            except UnicodeDecodeError:
                # resp = scomm.ser.readline().decode("utf-8")
                pass
            except Exception as e:
                pass
            if resp and resp!="":
                i+=1
                print(f"\n{i}> '{resp}'") #/r or /n a the end of line ???
                # print(resp_b)
                if resp=="quit":
                    break
                if i==55:
                    scomm.ser.write(f"quit".encode("utf-8"))
                elif i%10==0:
                    scomm.ser.write(f"<<<{i}>>".encode("utf-8"))
            else:
                print(".",end="")
    
    scomm.ser.close()