import logging
import json
import re
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

logging.getLogger("paramiko.transport").setLevel(logging.WARNING)
logging.getLogger("netmiko").setLevel(logging.WARNING)

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
    for i in range(num_workers):
        w = Thread(target=worker, args=(i, stop_event, input_queue, output_queue, bar))
        w.daemon = True
        w.start()
        worker_threads.append(w)
    return stop_event, input_queue, output_queue


def construct_ssh_parameter(switch_data, global_config):
    ssh_parameter_list = []
    for switch_element in switch_data:
        if switch_element.reachable is True:
            ssh_parameter = {
                'device_type': switch_element.os,
                'host': switch_element.ip,
                'username': global_config.ssh_username,
                'password': global_config.ssh_password,
                'port': global_config.ssh_port
            }
            ssh_parameter_list.append(ssh_parameter)
    return ssh_parameter_list


def fill_input_queue_start_worker_fill_output_queue(ssh_parameter_list, cli_show_command, global_config):
    logging.info(f"Starting to execute CLI commands for {len(ssh_parameter_list)} switches...")
    with alive_bar(total=len(ssh_parameter_list)) as bar:
        stop_event, input_queue, output_queue = start_workers(num_workers=global_config.number_of_worker_threads, bar=bar)
        for ssh_parameter in ssh_parameter_list:
            command = "show derived-config | begin interface"
            input_queue.put((ssh_parameter, command))

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
    while not output_queue.empty() and len(ssh_parameter_list) != len(combined_cli_output):
    # while not output_queue.empty():
        try:
            cli_output = output_queue.get(block=False)
        except Empty:
            pass
        else:
            combined_cli_output.update(cli_output)
    logging.debug(json.dumps(combined_cli_output))
    return combined_cli_output


def worker(i, stop_event, input_queue, output_queue, bar):
    while not (stop_event.is_set() and input_queue.empty()):
        try:
            ssh_parameter, command = input_queue.get(block=True, timeout=1)
        except Empty:
            continue
        captured_cli_output = {}
        try:
            with ConnectHandler(**ssh_parameter) as ssh_connection:
                raw_cli_output = ssh_connection.send_command(command)
                captured_cli_output = parse_show_run(ssh_parameter, raw_cli_output)
                if captured_cli_output is not None:
                    converted_cli_output = convert_captured_output_to_dict(ssh_parameter, captured_cli_output) #####
                # captured_cli_output = parse_output(platform="cisco_ios", command="show vlan", data=raw_cli_output)
        except AuthenticationException:
            captured_cli_output = {"status": "error - authentication failed"}
            logging.warning(f"Authentication failed for {ssh_parameter['host']}")
        except NetMikoTimeoutException:
            captured_cli_output = {"status": "error - timeout"}
            logging.warning(f"SSH timeout for {ssh_parameter['host']}")
        except SSHException:
            captured_cli_output = {"status": "error - not enabled / not negotiated"}
            logging.warning(f"SSH not enabled or could not be negotiated for {ssh_parameter['host']}")
        except Exception:
            traceback.print_exc()
            quit()
        output_queue.put(converted_cli_output) ####
        bar()


def parse_show_run(ssh_parameter, raw_cli_output):
    final_cli_output = {}
    if raw_cli_output is None:
        error_note = {"status": "error - did not receive cli output"}
        final_cli_output[ssh_parameter["host"]] = error_note
        logging.warning(f"{ssh_parameter['host']} - Did not receive CLI output.")
        return final_cli_output
    re_pattern = re.compile(r"^(interface.*)\n((?:.*\n)+?)!", re.MULTILINE)  # there is a bug when regex is not matching. Issue #16
    captured_cli_output = re.findall(re_pattern, raw_cli_output)
    if captured_cli_output is None:
        error_note = {"status": "error - regex capture didnt match anything"}
        final_cli_output[ssh_parameter["host"]] = error_note
        logging.warning(f"{ssh_parameter['host']} - RegEx capture didnt match anything.")
        return final_cli_output
    return captured_cli_output


def convert_captured_output_to_dict(ssh_parameter, captured_cli_output):
    parsed_interface_data = {}
    final_cli_output = {}
    for element in captured_cli_output:
        interface_name = element[0]
        interface_config = element[1]
        interface_config_list = interface_config.split("\n ")
        interface_config_list = [x.strip() for x in interface_config_list]  # Remove leading blanks
        parsed_interface_data[interface_name] = interface_config_list
        final_cli_output[ssh_parameter["host"]] = parsed_interface_data
    final_cli_output[ssh_parameter["host"]]["status"] = "succeeded"
    return final_cli_output


def wrapper_send_show_command_to_switches(switch_data, cli_show_command, global_config):
    ssh_parameter_list = construct_ssh_parameter(switch_data, global_config)
    unparsed_cli_output = fill_input_queue_start_worker_fill_output_queue(ssh_parameter_list, cli_show_command, global_config)
    # print("wrapper output:", unparsed_cli_output)

    # vlan_parsed = parse_output(platform="cisco_ios", command="show vlan", data=vlan_output)
    # json_vlan_parsed = (json.dumps(vlan_parsed))
