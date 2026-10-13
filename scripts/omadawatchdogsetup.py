#!/usr/bin/env python3

"""Omada watchdog setup script.

This script will guide the user through gathering the required identifiers for input into the omadawatchdog.py script.

Usage: run chmod +x and execute.
Script will prompt for Omada controller details and credentials and allow a user to

Requirements:
- Prior to running you must have enabled API access to your controller and have set up API client Credentials
-
"""

from ast import match_case
import logging
import requests
import subprocess
import platform
import time
import sys
from pathlib import Path
import urllib3

VERIFY_SSL = False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

global API
# =============================================================================
# API CLIENT
# =============================================================================

class OmadaAPI:
    """Simple Omada Open API client for authenticated controller actions."""

    def __init__(self):
        self.session = requests.Session()
        self.session.verify = VERIFY_SSL
        self.token = None

        self.omada_host = None
        self.omadac_id = None
        self.omada_client_id=None
        self.client_secret = None
        self.site_id = None
        self.site_name = None
        self.ssid = None

    # ---------------- AUTH ----------------

    def login(self):
        """Authenticate with the Omada controller and store an access token."""

        url = f"{self.omada_host}/openapi/authorize/token?grant_type=client_credentials"

        payload = {
            "omadacId": self.omadac_id,
            "client_id": self.omada_client_id,
            "client_secret": self.client_secret
        }

        r = self.session.post(url, json=payload)

        #print("[DEBUG AUTH]", r.text)

        r.raise_for_status()

        data = r.json()

        if data.get("errorCode") != 0:
            raise Exception(data)

        self.token = data["result"]["accessToken"]

        self.session.headers.update({
            "Authorization": f"AccessToken={self.token}",
            "Content-Type": "application/json"
        })

        print("[+] Authenticated")

    # ---------------- CLIENTS ----------------

    def get_clients(self):
        """Retrieve the list of clients from the configured Omada site."""
        url = (
            f"{self.omada_host}/openapi/v2/"
            f"{self.omadac_id}/sites/{self.site_id}/clients"
        )
        payload = {
            "page": 1,
            "pageSize": 1000
        }

        r = self.session.post(url, json=payload)

        r.raise_for_status()

        data = r.json()

        if data.get("errorCode") != 0:
            raise Exception(data)

        return data["result"]["data"]

    def get_sites(self):
        """Retrieve the list of clients from the configured Omada server."""

        url = (
            f"{self.omada_host}/openapi/v1/"
            f"{self.omadac_id}/sites"
        )

        payload = {
            "page": 1,
            "pageSize": 100
        }

        r = self.session.get(url, params=payload)
        r.raise_for_status()

        data = r.json()

        if data.get("errorCode") != 0:
            raise Exception(data)

        return data["result"]["data"]

    def get_ssids(self):
        """Retrieve the list of SSIDs from the configured Omada site."""

        url = (
            f"{self.omada_host}/openapi/v2/"
            f"{self.omadac_id}/sites/"
            f"{self.site_id}/wireless-network/ssids"
        )

        payload = {
            "page": 1,
            "pageSize": 100
        }

        r = self.session.get(url, params=payload)
        r.raise_for_status()
        data = r.json()

        if data.get("errorCode") != 0:
            raise Exception(data)

        return data["result"]["data"]

# =============================================================================
# HELPERS
# =============================================================================

def filter_clients(clients, ssid):
    """Return only the client entries that match the configured SSID and VLAN.

    The Omada API returns all clients for the site, so this function narrows the
    list to the targeted wireless network segment that this watchdog manages.
    """

    out = []

    for c in clients:

        if c.get("ssid") == ssid:
            out.append(c)

    return out

# =============================================================================
# Helper functions
# =============================================================================

def authenticate(api: OmadaAPI):
    api.omada_host = input("Enter hostname or IP Address of Omada Controller (https://hostname:port): ").strip().lower()
    api.omadac_id = input("Enter Omadac ID: ").strip().lower()
    api.omada_client_id= input("Enter Omada Client ID: ").strip().lower()
    api.client_secret = input("Enter Omada Client Secret: ").strip().lower()

    api.login()


def get_site_ids(api: OmadaAPI):
    sites = api.get_sites()
    print(f"{'Index':<5} | {'ID':<20}     | {'Name':<20}")
    print("--------------------------------------------")

    for index, s in enumerate(sites):
        name = s["name"]
        id = s["siteId"]
        print(f" {index:<3}  | {id:<20} | {name:<20}")

    print()

    selection = int(input("Select Site ID: ").strip().lower())
    if (selection < len(sites)):
        api.site_id = sites[selection].get("siteId")
        api.site_name = sites[selection].get("name")
        print(f"{sites[selection].get("name")} (Site ID: {sites[selection].get("siteId")}) selected")
    else:
        print("Bad selection")
        print()


def get_ssids(api: OmadaAPI):
    api.get_ssids()
    ssids = api.get_ssids()
    print(f"{'Index':<5} | {'ID':<20}     | {'Name':<20}")
    print("--------------------------------------------")

    for index, s in enumerate(ssids):
        name = s["name"]
        id = s["id"]
        print(f" {index:<3}  | {id:<20} | {name:<20}")

    selection = int(input("Select SSID: ").strip().lower())
    if (selection < len(ssids)):
        api.ssid = ssids[selection].get("name")
        print(f"{ssids[selection].get("name")} (SSID ID: {ssids[selection].get("id")}) selected")
    else:
        print("Bad selection")
        print()

def get_clients(api: OmadaAPI):
    clients = api.get_clients()
    print(f"{'Index':<5} | {'IP':<20} | {'Name':<30} | {'SSID':<20}")
    print("------------------------------------------------------------------------------------------------")

    filtered = filter_clients(clients,api.ssid)
    for index, c in enumerate(filtered):
        name = c.get("name") #["name"]
        ip = c.get("ip") #["id"]
        ssid = ""
        if c.get("ssid"):
            ssid = c.get("ssid")
        print(f" {index:<3}  | {ip:<20} | {name:<30} | {ssid:<20}")



def mainmenu(api):
    print()
    print(f"Current Omada Host: {api.omada_host}")
    print(f"Connected: {api.token != None}")
    print()

    print(f"Current selected site: {api.site_name} (ID: {api.site_id})")
    print(f"Current target SSID: {api.ssid}")


    print()
    print("1. Authenticate to the server")
    print("2. Get available Site IDs")
    print("3. Get SSIDs available for a given site")
    print("4. Retrieve wireless clients for a given SSID")
    print("5. Print config for omadawatchdog.py")
    print("q. Exit")

    return  input("Please select: ").strip().lower()

def print_config(api):
    print("\n\n\n")
    print("Enter the following into the configuration section of omadawatchdog.py")
    print()
    print(f"OMADA_HOST = \"{api.omada_host}\"")
    print(f"OMADAC_ID = \"{api.omadac_id}\"")
    print(f"CLIENT_ID = \"{api.omada_client_id}\"")
    print(f"CLIENT_SECRET = \"{api.client_secret}\"")
    print(f"SITE_ID = \"{api.site_id}\"")
    print(f"TARGET_SSID = \"{api.ssid}\" (note: Enter SSID Name as shown here)")

    handle_exit(api)

def handle_exit(api):
    print("Good bye.")
    return False
# =============================================================================
# Dictionaries
# =============================================================================\
global MENU_ACTIONS
MENU_ACTIONS =  {
    "1" : authenticate,
    "2" : get_site_ids,
    "3" : get_ssids,
    "4" : get_clients,
    "5" : print_config,
    "q" : handle_exit
}

def main():

    print("Omada watchdog script setup.\nThis script will help set up your own instance of the omadawatchdog script by gathering required IDs from the controller. \nPrior to using this script, you must will need to set up a Client ID, Client secret and get your Omada ID on the target controller. \nThese are located in global settings > Platform Integration > OpenAPI")
    print()
    api = OmadaAPI()
    is_running = True;

    while is_running:
        choice = mainmenu(api)
        action = MENU_ACTIONS.get(choice)
        if action:
            result = action(api)
            if result==False:
                is_running=False
        else:
            print("")
            print("Invalid selection. Please try again")

if __name__ == "__main__":
    main()
