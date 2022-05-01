import re
import logging
import requests
import time
import json
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from alive_progress import alive_bar

from network_toolkit.config.mac_lookup_config import load_mac_lookup_config

path_to_cache = Path.cwd() / "raw_output/mac_address_lookup/mac_address_cache.json"


@dataclass(frozen=True)
class MacAddress:
    raw_mac: str
    formatted_mac: str
    oui: str


def _prompt_user():
    logging.info("Enter/Paste your content. Ctrl-D/Ctrl-Z(Windows) or type 'end' in a new line to save it.")
    user_input = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "end":
            break
        else:
            user_input.append(line)
    user_input = '\n'.join(user_input)
    return user_input


def _filter_mac_addresses(user_input):
    mask_pattern = re.compile(r"(?:[a-fA-F\d]{2}[-:.]){5}[a-fA-F\d]{2}|(?:[a-fA-F\d]{4}.){2}[a-fA-F\d]{4}|[a-fA-F\d]{12}")
    mac_list = mask_pattern.findall(user_input)

    if not mac_list:
        logging.error("No MAC addresses found in user input.")
        quit()

    logging.info(f"Parsed {len(mac_list)} MAC addresses from user input. [1/4]")
    logging.debug(mac_list)
    return mac_list


def _format_mac_addresses(raw_mac_list):
    formatted_mac_list = []
    characters_to_remove = re.compile(r"[.:-]")

    for raw_mac in raw_mac_list:
        formatted_mac = characters_to_remove.sub("", raw_mac).upper()
        oui = formatted_mac[:6]
        mac_address_obj = MacAddress(raw_mac, formatted_mac, oui)
        formatted_mac_list.append(mac_address_obj)

    return formatted_mac_list


def _lookup_cache(formatted_mac_list):
    resolved_mac_list = {}
    unresolved_mac_list = []
    logging.info(f"Trying to resolve from cache...")

    with open(path_to_cache, mode="r", encoding="utf-8") as file:
        mac_cache = (json.load(file))

    for mac_entity in formatted_mac_list:
        mac_found = False
        organisation = None

        for cache_entity in mac_cache:
            if mac_entity.oui == cache_entity["oui"]:
                mac_found = True
                organisation = cache_entity["organisation"]

                date_today = datetime.now().strftime("%Y-%m-%d")
                cache_entity["last_update"] = date_today
                break

        if not mac_found:
            unresolved_mac_list.append(mac_entity)
            continue

        resolved_mac_list[mac_entity.raw_mac] = organisation

    logging.info(f"Resolved {len(resolved_mac_list)} MAC addresses via cache. [2/4]  (this saved you {len(resolved_mac_list) * 0.6}s)")
    if not unresolved_mac_list:
        logging.info("Resolved all addresses via cache. Skipping webAPI lookup.")
    return unresolved_mac_list, resolved_mac_list, mac_cache


def _lookup_webapi(unresolved_mac_list, resolved_mac_list, mac_cache, config):
    url_base = "https://api.macvendors.com/v1/lookup/"
    # token = "Bearer " + config.api_token_macvendors
    headers = {'Authorization': ("Bearer " + config.api_token_macvendors)}
    date_today = datetime.now().strftime("%Y-%m-%d")
    logging.info(f"Resolving {len(unresolved_mac_list)} MAC addresses via {url_base}...")

    with alive_bar(len(unresolved_mac_list)) as bar:
        for mac_entity in unresolved_mac_list:
            url = url_base + mac_entity.formatted_mac

            try:
                response = requests.get(url, verify=True, timeout=5, headers=headers)
            except requests.exceptions.ConnectionError:
                logging.critical(f"Timeout - Please check address({url_base}) and reachability")
                quit()
            except Exception as e:
                print(e)
            if response.status_code == 404:
                resolved_mac_list[mac_entity.raw_mac] = "Unknown"
                new_cache_entity = {"organisation": "Unknown", "oui": mac_entity.oui, "last_update": date_today}
                mac_cache.append(new_cache_entity)
                bar()
                continue
            elif response.status_code != 200:
                logging.error(f"HTTP {response.status_code} - Please check your API token in 'global_config.yml'")

            response_text = response.json()
            new_cache_entity = {"organisation": response_text["data"]["organization_name"], "oui": mac_entity.oui, "last_update": date_today}
            mac_cache.append(new_cache_entity)
            resolved_mac_list[mac_entity.raw_mac] = response_text["data"]["organization_name"]
            bar()
            time.sleep(0.6)

    logging.info(f"Resolved {len(unresolved_mac_list)} MAC addresses via webAPI. [3/4]")
    return resolved_mac_list, mac_cache


def _update_cache(mac_cache):
    with open(path_to_cache, "w") as json_file:
        json.dump(mac_cache, json_file, indent=2)

    logging.info("Updated MAC address cache. [4/4]")


def _print_lookup(mac_list):
    print("____________________________________________________________________________________")
    for mac_address, organisation in mac_list.items():
        print(f"{mac_address} - {organisation}")


def mac_address_batch_lookup():
    mac_lookup_config = load_mac_lookup_config()
    user_input = _prompt_user()
    raw_mac_list = _filter_mac_addresses(user_input)
    formatted_mac_list = _format_mac_addresses(raw_mac_list)
    unresolved_mac_list, resolved_mac_list, mac_cache = _lookup_cache(formatted_mac_list)

    if unresolved_mac_list:
        resolved_mac_list, mac_cache = _lookup_webapi(unresolved_mac_list, resolved_mac_list, mac_cache, mac_lookup_config)

    _update_cache(mac_cache)
    _print_lookup(resolved_mac_list)
