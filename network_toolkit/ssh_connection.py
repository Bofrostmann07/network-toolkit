import json
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from alive_progress import alive_bar
from netmiko import ConnectHandler
from netmiko.ssh_exception import NetMikoTimeoutException, AuthenticationException
from paramiko.ssh_exception import SSHException

import network_toolkit.config as config

logging.getLogger("paramiko.transport").setLevel(logging.WARNING)
logging.getLogger("netmiko").setLevel(logging.WARNING)


def run_show_command(switches, cli_show_command):
    """Runs the cli command on all the switches"""
    logging.info(f"Starting to execute '{cli_show_command}' on {len(switches)} switches...")
    combined_cli_output = {}

    with alive_bar(total=len(switches)) as bar:
        with ThreadPoolExecutor(max_workers=config.GLOBAL_CONFIG.number_of_worker_threads) as executor:
            futures = [executor.submit(worker, switch_element, cli_show_command) for switch_element in switches]
            for future in futures:
                switch_element = future.result()
                combined_cli_output[switch_element.ip] = switch_element.interface_eth_config
                bar()

    return combined_cli_output


def run_command_on_switch(switch_element, command):
    """Connects via ssh to the switch and runs the given command"""
    ssh_parameter = {
        'device_type': switch_element.os,
        'host': switch_element.ip,
        'username': config.GLOBAL_CONFIG.ssh_username,
        'password': config.GLOBAL_CONFIG.ssh_password,
        'port': config.GLOBAL_CONFIG.ssh_port
        }

    raw_cli_output = ""
    try:
        with ConnectHandler(**ssh_parameter) as ssh_connection:
            raw_cli_output = ssh_connection.send_command(command)
    except AuthenticationException:
        logging.warning(f"Authentication failed for {switch_element.ip}")
    except NetMikoTimeoutException:
        logging.warning(f"SSH timeout for {switch_element.ip}")
    except SSHException:
        logging.warning(f"SSH not enabled or could not be negotiated for {switch_element.ip}")
    except Exception:
        traceback.print_exc()
        quit()

    return raw_cli_output


def worker(switch_element, command):
    raw_cli_output = run_command_on_switch(switch_element, command)
    switch_element.parse_interface_cli_output(raw_cli_output)
    return switch_element


def save_parsed_cli_output_as_json(parsed_cli_output):
    local_time = datetime.now()
    timestamp_url_safe = (local_time.strftime("%Y-%m-%dT%H-%M-%S"))
    file_path = "raw_output/interface_eth_config/" + timestamp_url_safe + ".json"
    try:
        with open(file_path, "x") as json_file:
            json.dump(parsed_cli_output, json_file, indent=2)
            logging.info(f"Created result file @ {file_path}")
    except Exception:
        logging.error("Could not create result file")
    return


def wrapper_send_show_command_to_switches(switch_data, cli_show_command):
    cli_show_command = "show derived-config | begin interface"
    parsed_cli_output = run_show_command(switch_data, cli_show_command)
    save_parsed_cli_output_as_json(parsed_cli_output)
    return parsed_cli_output

    # vlan_parsed = parse_output(platform="cisco_ios", command="show vlan", data=vlan_output)
    # json_vlan_parsed = (json.dumps(vlan_parsed))
