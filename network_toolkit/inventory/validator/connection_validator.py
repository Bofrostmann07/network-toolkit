import logging
import re
import socket
from concurrent.futures import ThreadPoolExecutor

from alive_progress import alive_bar

import network_toolkit.config as config
from network_toolkit.ssh_connection import run_command_on_switch


def wrapper_check_for_ssh_reachability(validated_switch_data):
    if config.GLOBAL_CONFIG.skip_ssh_reachability_check:
        logging.info("Skip: SSH reachability check. [4/5]")
        for switch_element in validated_switch_data:
            switch_element.reachable = True
        return validated_switch_data

    ssh_reachability_results = check_switch_reachability(validated_switch_data)
    reachable_switch_data = manipulate_networkswitches_reachability(validated_switch_data, ssh_reachability_results)
    return reachable_switch_data


def check_switch_reachability(validated_switch_data):
    logging.info(f"Starting SSH reachability check on TCP port {config.GLOBAL_CONFIG.ssh_port} for {len(validated_switch_data)} switches...")
    results = {}

    with alive_bar(total=len(validated_switch_data)) as bar:
        with ThreadPoolExecutor(max_workers=config.GLOBAL_CONFIG.number_of_worker_threads) as executor:
            futures = [executor.submit(check_reachability, switch_element.ip, config.GLOBAL_CONFIG.ssh_port) for switch_element in validated_switch_data]
            for future in futures:
                ip, reachable = future.result()
                results[ip] = reachable
                bar()

    logging.debug(results)
    return results


def check_reachability(ip, port):
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
    return ip, reachable


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
    first_three_switches = switch_data[:3]

    for switch_element in first_three_switches:
        raw_cli_output = run_command_on_switch(switch_element, "show privilege")
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
