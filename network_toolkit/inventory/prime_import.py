# -*- coding: UTF-8 -*-
import logging
import requests

from network_toolkit.config.input_source_config import load_input_config
from .network_switch import NetworkSwitch

requests.packages.urllib3.disable_warnings()


def _query_switch_data(prime_config):
    if prime_config.group is None:
        request = "/webacs/api/v4/data/Devices.json?.full=true&.maxResults=1000&.sort=deviceName&reachability=REACHABLE&adminStatus=MANAGED&productFamily" \
                  "=startsWith(Switches) "
    else:
        request = "/webacs/api/v4/data/Devices.json?.full=true&.maxResults=1000&.group=" + prime_config.group + "&.sort=deviceName&reachability" \
                  "=REACHABLE&adminStatus=MANAGED&productFamily=startsWith(Switches)"
    url = "https://" + prime_config.address + request

    try:
        response = requests.get(url, verify=False, timeout=5, auth=(prime_config.username, prime_config.password))
    except requests.exceptions.ConnectionError:
        logging.error(f"Timeout - Please check address({prime_config.address}) and reachability")
        quit()
    except Exception as e:
        print(e)

    if response.status_code == 401:
        logging.error("HTTP 401 Unauthorized - Please check username, password and role('NBI Read')")
        quit()
    elif response.status_code == 404:
        logging.critical("HTTP 404 Not found - Can´t access API v4. Update Prime Infrastructure or use CSV import")
        quit()
    elif response.status_code == 500:
        logging.critical(f"HTTP 500 Internal Server Error - Invalid group. Check your group('{prime_config.group}")
        quit()
    elif response.status_code == 503:
        logging.critical(f"HTTP 503 Service Unavailable - Rate limited / Requestes more then 1000 devices at once")
        quit()
    elif response.status_code != 200:
        logging.critical(f"HTTP {response.status_code} - Unknown Error")
        quit()

    response_data = response.json()

    if response_data["queryResponse"]["@count"] == 0:
        logging.critical(f"Found no devices. Check your group('{prime_config.group}')")
        quit()

    logging.info("Connected to Prime Infrastructure API. [1/5]")
    return response_data


def _build_switch_data(response):
    switches_data = []
    logging.info("Valid response to device query received. [2/5]")

    for switch in response["queryResponse"]["entity"]:
        hostname = switch["devicesDTO"]["deviceName"]
        ip = switch["devicesDTO"]["ipAddress"]
        if switch["devicesDTO"]["softwareType"] == "IOS-XE":
            os = "cisco_xe"
        else:
            os = "cisco_ios"

        switch_data = NetworkSwitch(hostname=hostname, ip=ip, os=os, reachable=False, line_number=0)
        switches_data.append(switch_data)

    logging.info(f"Read {response['queryResponse']['@count']} devices from Prime. [3/5]")
    return switches_data


def import_switches_from_prime():
    logging.info("Connecting to Prime Infrastructure...")
    prime_config = load_input_config()
    response = _query_switch_data(prime_config)
    switch_data = _build_switch_data(response)
    return switch_data
