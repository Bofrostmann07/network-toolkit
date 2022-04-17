import re
import socket
import logging
from threading import Event, Thread
from queue import Queue, Empty
from time import sleep
from alive_progress import alive_bar
from network_toolkit import fetch_switch_config
import network_toolkit.config as config

# Global variables
worker_threads = []


def wrapper_check_for_ssh_reachability(validated_switch_data):
    if config.GLOBAL_CONFIG.skip_ssh_reachability_check:
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
    logging.info(f"Starting SSH reachability check on TCP port {config.GLOBAL_CONFIG.ssh_port} for {len(validated_switch_data)} switches...")
    with alive_bar(total=len(validated_switch_data)) as bar:
        stop_event, input_queue, output_queue = start_workers(num_workers=config.GLOBAL_CONFIG.number_of_worker_threads, bar=bar)
        for switch_element in validated_switch_data:
            if switch_element.reachable is False:
                ip = switch_element.ip
                input_queue.put((ip, config.GLOBAL_CONFIG.ssh_port))

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
                socket.setdefaulttimeout(config.GLOBAL_CONFIG.ssh_timeout)
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
    if config.GLOBAL_CONFIG.skip_ssh_authentication_check:
        logging.info("Skip: SSH authentication check. [5/5]")
        return
    check_ssh_authentication(reachable_switch_data)
    return


def check_ssh_authentication(switch_data):
    """Check if the provided user has privilege 15"""
    logging.info(f"Starting to check if SSH session gets established and user gets authenticated. Trying the first 3 switches...")

    counter_failed_logins = 0
    priv_re_pattern = re.compile(r"\d{1,2}")
    first_three_switches = switch_data[:2]

    for switch_element in first_three_switches:
        raw_cli_output = fetch_switch_config(switch_element, "show privilege")
        logging.debug(raw_cli_output)
        login_success_check = (priv_re_pattern.findall(raw_cli_output))

        if len(login_success_check) == 0:
            counter_failed_logins += 1
            continue

        elif int(login_success_check[0]) != 15:
            counter_failed_logins += 1
            logging.error(f"Insufficent privileges for {switch_element.ip}: priv {login_success_check[0]}")
            continue

        logging.debug(f"Authencation successful for {switch_element.ip}")

    if counter_failed_logins >= 1:
        logging.error(f"Authentication failed for {counter_failed_logins} switches")
        print(f"Check if user '{config.GLOBAL_CONFIG.ssh_username}' is available, has privilege 15 and the password is correct. Press [enter] to retry.")
        input("[ENTER]")
        return check_ssh_authentication(switch_data)

    logging.info("SSH login check is successfuly completed. [5/5]")


def check_ssh_connection(validated_switch_data):
    reachable_switch_data = wrapper_check_for_ssh_reachability(validated_switch_data)
    wrapper_check_ssh_authentication(reachable_switch_data)
    logging.info("All prerequisites are fullfilled.")
    return reachable_switch_data
