import logging
import json
from netmiko import ConnectHandler
from netmiko.ssh_exception import NetMikoTimeoutException
from paramiko.ssh_exception import SSHException
from netmiko.ssh_exception import AuthenticationException
from ntc_templates.parse import parse_output
import traceback
from alive_progress import alive_bar
from threading import Event, Thread
from queue import Queue, Empty
from time import sleep
from datetime import datetime


logging.getLogger("paramiko.transport").setLevel(logging.WARNING)
logging.getLogger("netmiko").setLevel(logging.WARNING)

tool_config = None
worker_threads = []


# need to get rid of ot that function, as soon as multithreading code is reliable
def ssh_connect_only_one_show_command_singlethreaded(switch_data, cli_show_command, global_config):
    output_data = {}
    logging.info(f"Starting to connect to {len(switch_data)} switches and enter show command...")
    for switch_element in switch_data:
        ssh_parameter = {
            'device_type': switch_element.os,
            'host': switch_element.ip,
            'username': global_config.ssh_username,
            'password': global_config.ssh_password,
            'port': global_config.ssh_port
        }
        try:
            with ConnectHandler(**ssh_parameter) as ssh_connection:
                output = ssh_connection.send_command(cli_show_command)
                output_data[switch_element.ip] = output
        except AuthenticationException:
            logging.warning(f"Authentication failed for {switch_element.hostname} @ {switch_element.ip}")
            output_data[switch_element.ip] = "failed"
        except NetMikoTimeoutException:
            logging.warning(f"SSH timeout for {switch_element.hostname} @ {switch_element.ip}")
            output_data[switch_element.ip] = "timeout"
        except SSHException:
            logging.warning(
                f"SSH not enabled or could not be negotiated for {switch_element.hostname} @ {switch_element.ip}")
            output_data[switch_element.ip] = "failed"
        except Exception:
            traceback.print_exc()
    return output_data


def start_workers(num_workers, bar):
    stop_event = Event()
    input_queue = Queue()
    output_queue = Queue()
    for _ in range(num_workers):
        w = Thread(target=worker, args=(stop_event, input_queue, output_queue, bar))
        w.daemon = True
        w.start()
        worker_threads.append(w)
    return stop_event, input_queue, output_queue


def fill_input_queue_start_worker_fill_output_queue(switches, cli_show_command, global_config):
    logging.info(f"Starting to execute '{cli_show_command}' on {len(switches)} switches...")
    with alive_bar(total=len(switches)) as bar:
        stop_event, input_queue, output_queue = start_workers(num_workers=global_config.number_of_worker_threads, bar=bar)

        for switch_element in switches:
            input_queue.put((switch_element, cli_show_command))

        # Wait for the input queue to be emptied
        while not input_queue.empty():
            sleep(0.1)
        # Stop workers from taking from the input queue
        stop_event.set()
        # Wait until all worker threads are done
        for w in worker_threads:
            w.join()

    # Wait for the output queue to be emptied
    combined_cli_output = {}
    while not output_queue.empty() and len(switches) != len(combined_cli_output):
        try:
            switch_element = output_queue.get(block=False)
        except Empty:
            pass
        else:
            final_interface_eth_config = switch_element.config_to_dict()
            combined_cli_output.update(final_interface_eth_config)
    return combined_cli_output


def fetch_switch_config(switch_element, command):
    global tool_config
    ssh_parameter = {
        'device_type': switch_element.os,
        'host': switch_element.ip,
        'username': tool_config.ssh_username,
        'password': tool_config.ssh_password,
        'port': tool_config.ssh_port
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


# Worker thread for fetching ssh config from switch
def worker(stop_event, input_queue, output_queue, bar):
    while not (stop_event.is_set() and input_queue.empty()):
        try:
            switch_element, command = input_queue.get(block=True, timeout=1)
        except Empty:
            continue

        if switch_element.reachable:
            raw_cli_output = fetch_switch_config(switch_element, command)
            switch_element.parse_cli_output(raw_cli_output)

        output_queue.put(switch_element)
        bar()


def create_json_file(parsed_cli_output):
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


def wrapper_send_show_command_to_switches(switch_data, cli_show_command, global_config):
    global tool_config
    tool_config = global_config

    cli_show_command = "show derived-config | begin interface"
    parsed_cli_output = fill_input_queue_start_worker_fill_output_queue(switch_data, cli_show_command, global_config)
    create_json_file(parsed_cli_output)
    return parsed_cli_output

    # vlan_parsed = parse_output(platform="cisco_ios", command="show vlan", data=vlan_output)
    # json_vlan_parsed = (json.dumps(vlan_parsed))
