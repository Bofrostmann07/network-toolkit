# -*- coding: UTF-8 -*-
import logging
import requests

from network_toolkit.config.input_source_config import load_input_config
import network_toolkit.config as config



# response = requests.get(
#     'https://10.9.8.9/webacs/api/v4/data/Devices.json?.full=true&.sort=deviceName&reachability=REACHABLE&adminStatus=MANAGED&productFamily=startsWith(Switches)',
#     verify=False, auth=('prime-nbi-read', 'APItest123')).json()
#
# print(response)




def _verify_prime_connection(url, prime_config):
    request = "/webacs/api/v4/op/info/version.json"
    url = "https://" + prime_config.address + request
    try:
        response = requests.get(url, verify=False, auth=(prime_config.username, prime_config.password)).json()
    except requests.exceptions.ConnectionError:
        print("timeout")
    print(response)


def import_switches_from_prime():
    prime_config = load_input_config()
    url = "https://" + prime_config.address + "/webacs/api/v4/data/"
    while True:
        url = _verify_prime_connection(url, prime_config)
