# -*- coding: UTF-8 -*-
import csv
import logging
from threading import Event, Thread
from queue import Queue, Empty
from time import sleep
from alive_progress import alive_bar
# from ssh_connection import ssh_connect_only_one_show_command_singlethreaded # TODO wieder aktivieren
from .validator.connection_validator import check_ssh_connection

from .network_switch import NetworkSwitch
from .validator.csv_validator import get_csv_path_and_validate_header, validate_switch_data


def read_and_validate_csv(csv_file_path):
    while True:
        switch_data = read_switch_data_from_csv(csv_file_path)
        data_valid = validate_switch_data(switch_data)

        if data_valid:
            return switch_data

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


def import_switches_from_csv():
    """Read data from csv file and validate its contents"""
    validated_csv_file_path = get_csv_path_and_validate_header()
    validated_switch_data = read_and_validate_csv(validated_csv_file_path)
    return validated_switch_data
