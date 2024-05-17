# Cloud-IoT DiY Tools
There are three main tools in this folder:
- `bootstrap.py` - project bootstrapping/installation tool
- `mqtt.py` - MQTT testing tool (test fleet provisioning and/or simulate device MQTT activity)
- `prov.py` - device provisioning tool to be used when/if '_claim certificate_' is not installed on device
Main tool in this folder is `prov.py` - fully functional Device provisioning tool with UI

It was not an easy choice to create UI-based tool instead of command-line.
But provisioning process seems too complicated for command-line.

## Bootstrapping Tool Usage
Tools are developed in Python (one of the reason is great boto3 library to communicated with AWS).

So you'll need to have Python3 (3.9+) installed on your laptop.

Recommended steps after that:
- Create and activate venv
    - `python3 -m venv .venv`
    - Mac/Linux: `source .venv/bin/activate`
    - Windows: `.venv\scripts\activate.bat`
        
- Install dependencies in that venv
    - `pip install -r requirements.txt`

- Run the tool from activated venv `python bootstrap.py`

## MQTT Client Tool Usage

- Run the tool from activated venv `python mqtt.py`
