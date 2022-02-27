import re
import socket
import logging
from threading import Event, Thread
from queue import Queue, Empty
from time import sleep
from alive_progress import alive_bar


# Global variables
worker_threads = []
global_config = {}


def get_global_config():
    config = global_config
    return config


def wrapper_check_for_ssh_reachability(validated_switch_data):
    if global_config.skip_ssh_reachability_check:
        reachable_switch_data = skip_check_ssh_reachability(validated_switch_data)
        return reachable_switch_data
    results_from_ssh_reachability_checker = fill_input_queue_start_worker_fill_output_queue(validated_switch_data)
    reachable_switch_data = manipulate_networkswitches_reachability(validated_switch_data, results_from_ssh_reachability_checker)
    return reachable_switch_data


def skip_check_ssh_reachability(validated_switch_data):
    for switch_element in validated_switch_data:
        switch_element.reachable = True
    logging.info("Skip: SSH reachability check. [4/5]")
    return validated_switch_data


def fill_input_queue_start_worker_fill_output_queue(validated_switch_data):
    logging.info(f"Starting SSH reachability check on TCP port {global_config.ssh_port} for {len(validated_switch_data)} switches...")
    with alive_bar(total=len(validated_switch_data)) as bar:
        stop_event, input_queue, output_queue = start_workers(num_workers=global_config.number_of_worker_threads, bar=bar)
        for switch_element in validated_switch_data:
            if switch_element.reachable is False:
                ip = switch_element.ip
                input_queue.put((ip, global_config.ssh_port))

        # Wait for the input queue to be emptied
        while not input_queue.empty():
            sleep(0.1)
        # Stop the workers
        stop_event.set()
        # Wait until all worker threads are done
        for w in worker_threads:
            w.join()

    results = {}
    # Wait for the output queue to be emptied
    while not output_queue.empty() and len(validated_switch_data) != len(results):
        try:
            ip, reachable = output_queue.get(block=False)
        except Empty:
            pass
        else:
            results[ip] = reachable
    logging.debug(results)
    return results


def worker(stop_event, input_queue, output_queue, bar):
    while not (stop_event.is_set() and input_queue.empty()):
        try:
            ip, port = input_queue.get(block=True, timeout=1)
        except Empty:
            continue
        try:
            # Open TCP Socket for SSH reachability check
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                socket.setdefaulttimeout(global_config.ssh_timeout)
                result = sock.connect_ex((ip, port))
            if result == 0:
                reachable = True
            else:
                reachable = False
        except Exception as e:
            reachable = False
            print(e)
        output_queue.put((ip, reachable))
        bar()


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


def manipulate_networkswitches_reachability(validated_switch_data, results_from_ssh_reachability_checker):
    for switch_element in validated_switch_data:
        for result_ip, result_reachable in results_from_ssh_reachability_checker.items():
            if switch_element.ip == result_ip:
                switch_element.reachable = result_reachable
        if not switch_element.reachable:
            if switch_element.hostname == "No Hostname":
                logging.warning(f"{switch_element.ip} is not reachable")
            else:
                logging.warning(f"{switch_element.hostname} @ {switch_element.ip} is not reachable")
    logging.debug(validated_switch_data)
    logging.info("SSH reachability check is successfuly completed. [4/5]")
    return validated_switch_data


def wrapper_check_ssh_authentication(reachable_switch_data):
    if global_config.skip_ssh_authentication_check:
        logging.info("Skip: SSH authentication check. [5/5]")
        return
    check_ssh_authentication(reachable_switch_data)
    return


def check_ssh_authentication(switch_data):  # TODO this is super ugly, please clean me up in the future :(
    logging.info(f"Starting to check if SSH session gets established and user gets authenticated. Trying the first 3 switches...")
    # Expected output from 'show privilege' is 'Current privilege level is [priv level]'
    cli_show_command = "show privilege"
    priv_re_pattern = re.compile(r"\d{1,2}")
    counter_failed_logins = 0
    first_three_switches = switch_data[:2]
    config = get_global_config()
    # raw_cli_output = ssh_connect_only_one_show_command_singlethreaded(first_three_switches, cli_show_command, config)
    raw_cli_output = {}
    for ip, cli_output in raw_cli_output.items():
        logging.debug(cli_output)
        login_success_check = (re.findall(priv_re_pattern, cli_output))
        if len(login_success_check) == 0:
            counter_failed_logins += 1
        elif int(login_success_check[0]) != 15:
            counter_failed_logins += 1
            logging.error(f"Insufficent privileges for {ip}: priv {login_success_check[0]}")
        else:
            logging.debug(f"Authencation successful for {ip}")

    if counter_failed_logins >= 1:
        logging.error(f"Authentication failed for {counter_failed_logins} switches")
        print(f"Check if user '{global_config.ssh_username}' is available, has privilege 15 and the password is correct. Press [enter] to retry.")
        input("[ENTER]")
        return check_ssh_authentication(first_three_switches)
    else:
        logging.info("SSH login check is successfuly completed. [5/5]")
        return


def check_ssh_connection(validated_switch_data, config):
    set_global_config(config)
    reachable_switch_data = wrapper_check_for_ssh_reachability(validated_switch_data)
    wrapper_check_ssh_authentication(reachable_switch_data)
    logging.info("All prerequisites are fullfilled.")
    return reachable_switch_data


def set_global_config(config):
    global global_config
    global_config = config
    return
