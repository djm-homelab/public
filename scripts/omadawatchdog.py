#!/usr/bin/env python3

"""Omada watchdog script.

This script queries the Omada controller API for clients on a specific SSID
and VLAN, checks whether each device is currently reachable via ICMP ping, and
attempts to reconnect any unreachable clients through the Omada controller.

After issuing reconnect commands, the script confirms each previously unreachable
device is again responsive by retrying ping for a configurable number of
attempts before exiting.

Intended usage:
- Run as a cron job every 5 minutes
- Uses the Omada Open API client credentials configured below
"""

import logging
import requests
import subprocess
import platform
import time
import sys
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================

OMADA_HOST = "https://[controlleripaddress]:[port]"

# Open API settings
OMADAC_ID = "aaaaaa"
CLIENT_ID = "aaaaaa"
CLIENT_SECRET = "aaaaaa"

# Site ID from Omada
SITE_ID = "aaaaa"

TARGET_SSID = "SSID Name"
TARGET_VLAN = 00 # Numeric value

VERIFY_SSL = False
PING_TIMEOUT = 2
RECONNECT_DELAY = 2
RECONNECT_CONFIRMATION_ATTEMPTS = 5
LOG_FILE = Path(__file__).resolve().parent / "omadawatchdog.log"

logger = logging.getLogger(__name__)

# =============================================================================
# LOGGING
# =============================================================================

def setup_logging() -> None:
    """Configure file-based logging for each run."""
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)

    logger.addHandler(file_handler)

    logger.info("\n=== Starting new omadawatchdog run ===")
    logger.info("Log file: %s", LOG_FILE)

# =============================================================================
# API CLIENT
# =============================================================================

class OmadaAPI:
    """Simple Omada Open API client for authenticated controller actions."""

    def __init__(self):
        self.session = requests.Session()
        self.session.verify = VERIFY_SSL
        self.token = None

    # ---------------- AUTH ----------------

    def login(self):
        """Authenticate with the Omada controller and store an access token."""

        url = f"{OMADA_HOST}/openapi/authorize/token?grant_type=client_credentials"

        payload = {
            "omadacId": OMADAC_ID,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET
        }

        r = self.session.post(url, json=payload)

        print("[DEBUG AUTH]", r.text)

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
            f"{OMADA_HOST}/openapi/v2/"
            f"{OMADAC_ID}/sites/{SITE_ID}/clients"
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

    # ---------------- RECONNECT (FIXED) ----------------

    def reconnect_clients(self, macs):
        """Attempt to trigger a reconnect for the given client MAC addresses."""

        if not macs:
            return



        payload = {
            "mac": macs
        }

        last_error = None
        for mac in macs:
            endpoints = [
            f"{OMADA_HOST}/openapi/v1/{OMADAC_ID}/sites/{SITE_ID}/clients/{mac}/reconnect",
            #f"{OMADA_HOST}/openapi/v2/{OMADAC_ID}/sites/{SITE_ID}/cmd/reconnect-client",
            ]
            for url in endpoints:

                logger.debug("Trying reconnect endpoint: %s", url)

                try:
                    r = self.session.post(url) #, json=payload)

                    # IMPORTANT: don't crash immediately
                    if r.status_code == 404:
                        last_error = r.text
                        continue

                    r.raise_for_status()

                    data = r.json()

                    if data.get("errorCode") == 0:
                        logger.info("Reconnected %d device(s)", len(macs))
                        return True

                    last_error = data

                except Exception as e:
                    last_error = str(e)
                    logger.error("Reconnect request failed for %s: %s", mac, last_error)

            logger.error("All reconnect endpoints failed for %s: %s", mac, last_error)
            return False

# =============================================================================
# HELPERS
# =============================================================================

def ping(ip: str) -> bool:
    """Send a single ICMP ping to the given IP address and return True if it succeeds."""

    if not ip:
        return False

    if platform.system().lower() == "windows":
        cmd = ["ping", "-n", "1", "-w", "2000", ip]
    else:
        cmd = ["ping", "-c", "1", "-W", "2", ip]

    return subprocess.run(cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    ).returncode == 0


def confirm_ping(ip: str, attempts: int = RECONNECT_CONFIRMATION_ATTEMPTS, interval: int = RECONNECT_DELAY) -> bool:
    """Retry ICMP ping until the host becomes responsive or attempts are exhausted."""

    if not ip:
        return False

    for attempt in range(1, attempts + 1):
        if ping(ip):
            if attempt > 1:
                print(f"        ✔ reachable after {attempt} attempt(s)")
            return True

        print(f"        ⟳ waiting for {ip} (attempt {attempt}/{attempts})")
        time.sleep(interval)

    return False


def filter_clients(clients):
    """Return only the client entries that match the configured SSID and VLAN.

    The Omada API returns all clients for the site, so this function narrows the
    list to the targeted wireless network segment that this watchdog manages.
    """

    out = []

    for c in clients:

        if c.get("ssid") != TARGET_SSID:
            continue

        if c.get("vid") != TARGET_VLAN:
            continue

        if not c.get("ip") or not c.get("mac"):
            continue

        out.append(c)

    return out


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run the watchdog workflow.

    1. Authenticate with the Omada controller.
    2. Fetch clients for the configured site.
    3. Filter clients by SSID/VLAN.
    4. Ping each client and reconnect any that are offline.
    5. Confirm reconnected clients are responsive before exiting.
    """

    setup_logging()

    api = OmadaAPI()
    api.login()

    clients = api.get_clients()
    clients = filter_clients(clients)

    print(f"[+] Monitoring {len(clients)} clients")

    to_reconnect = []

    for c in clients:

        ip = c["ip"]
        mac = c["mac"]
        name = c.get("name", "unknown")

        print(f"[*] {name} ({ip})")

        if ping(ip):
            print("    ✔ reachable")
        else:
            print("    ✖ unreachable")
            logger.warning("Unreachable device: %s (%s) [%s]", name, ip, mac)
            to_reconnect.append((mac, name, ip))

    if to_reconnect:

        print("\n[!] Reconnecting devices...")

        macs = [m[0] for m in to_reconnect]

        success = api.reconnect_clients(macs)

        if not success:
            print("[✖] Reconnect failed, skipping post-reconnect validation")
            logger.error("Reconnect action failed for %d device(s)", len(macs))
            sys.exit(1)

        print("\n[!] Confirming reconnected devices are responsive...")
        logger.info("Confirming reconnected devices are responsive")
        failed_confirmations = 0

        for m, name, ip in to_reconnect:
            print(f"    ↻ reconnected: {name} ({ip}) [{m}]")
            logger.info("Post-reconnect validation started for %s (%s)", name, ip)
            if confirm_ping(ip):
                print(f"        ✔ {ip} is now responsive")
                logger.info("Device %s (%s) responded to ping after reconnect", name, ip)
            else:
                print(f"        ✖ {ip} still unreachable after reconnect")
                logger.error("Device %s (%s) still unreachable after reconnect", name, ip)
                failed_confirmations += 1
            time.sleep(RECONNECT_DELAY)

        if failed_confirmations:
            print(f"\n[✖] {failed_confirmations} device(s) failed post-reconnect validation")
            logger.error("%d device(s) failed post-reconnect validation", failed_confirmations)
            sys.exit(2)

        print("\n[+] All reconnected devices are now responsive")
        logger.info("All reconnected devices are now responsive")


if __name__ == "__main__":
    main()
