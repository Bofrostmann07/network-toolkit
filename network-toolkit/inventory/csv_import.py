# -*- coding: UTF-8 -*-
import csv
import re
import socket
import logging
from threading import Event, Thread
from queue import Queue, Empty
from time import sleep
from alive_progress import alive_bar
# from ssh_connection import ssh_connect_only_one_show_command_singlethreaded # TODO wieder aktivieren
from .validator.csv_validator import get_csv_path_and_validate_header, validate_raw_csv_switch_data  # TODO . weg
from .network_switch import NetworkSwitch
from .validator.connection_validator import check_ssh_connection

# Global variables
global_config = {}


def get_global_config():
    config = global_config
    return config


def wrapper_read_csv_and_validate_switch_data(csv_file_path):
    while True:
        raw_switch_data = import_csv_fill_class_networkswitch(csv_file_path)
        is_data_valid = validate_raw_csv_switch_data(raw_switch_data)
        if is_data_valid:
            break
    return raw_switch_data


def import_csv_fill_class_networkswitch(path_to_csv):
    switches_data = []
    with open(path_to_csv, mode="r", encoding="utf-8") as csv_switch_file:
        raw_csv_data = csv.DictReader(csv_switch_file)
        for line_number, row in enumerate(raw_csv_data, start=2):
            hostname = row.get("hostname") or "No Hostname"
            ip = row.get("ip") or "No IP"
            os = row.get("os") or "No OS"
            switch_data = NetworkSwitch(hostname=hostname, ip=ip, os=os, reachable=False, line_number=line_number)
            switches_data.append(switch_data)
    logging.info(f"Read {len(switches_data)} rows from CSV. [2/5]")
    return switches_data


def import_switches_from_csv(config):
    set_global_config(config)
    validated_csv_file_path = get_csv_path_and_validate_header(config)
    validated_switch_data = wrapper_read_csv_and_validate_switch_data(validated_csv_file_path)
    reachable_switch_data = check_ssh_connection(validated_switch_data, config)
    return reachable_switch_data


def set_global_config(config):
    global global_config
    global_config = config
    return
