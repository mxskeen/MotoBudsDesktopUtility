#!/usr/bin/python3
import os
import sys

# Ensure running with system python that has dbus-python and bluetooth support
if os.path.exists("/usr/bin/python3") and sys.executable != "/usr/bin/python3":
    os.execv("/usr/bin/python3", ["/usr/bin/python3"] + sys.argv)

import time
import subprocess
import threading
import logging
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

APP_CANDIDATE_PATHS = [
    os.path.expanduser("~/.local/bin/motobudsdesktoputility"),
    os.path.expanduser("~/mot/code/builds/linux-unpacked/motobudsdesktoputility"),
    "/usr/bin/motobudsdesktoputility",
    "/opt/Moto Buds Utility/motobudsdesktoputility"
]

def find_app_binary():
    for p in APP_CANDIDATE_PATHS:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return "motobudsdesktoputility"

def is_moto_buds_device(name, mac):
    name_lower = (name or "").lower()
    if "moto" in name_lower and "buds" in name_lower:
        return True
    if mac and mac.upper() == "9C:CD:42:6E:6E:58":
        return True
    return False

def get_user_session_env():
    env = os.environ.copy()
    if "DISPLAY" not in env or "XDG_RUNTIME_DIR" not in env:
        try:
            out = subprocess.check_output(["systemctl", "--user", "show-environment"], text=True, timeout=2)
            for line in out.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    if k not in env:
                        env[k] = v
        except Exception:
            pass
    if "DISPLAY" not in env:
        env["DISPLAY"] = ":1"
    if "XDG_RUNTIME_DIR" not in env:
        env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
    return env

def trigger_app_connect(mac, name):
    """Wait for Bluetooth services to settle, then launch or signal the app with --hidden and --connect."""
    logging.info(f"Moto Buds detected connected: {mac} ({name}). Scheduling app launch/connect...")
    # Allow 1.5s for BlueZ profiles and RFCOMM socket to become ready
    time.sleep(1.5)
    
    app_bin = find_app_binary()
    logging.info(f"Launching app via {app_bin} --hidden --connect")
    
    env = get_user_session_env()

    try:
        # Spawn detached process with --hidden --connect
        subprocess.Popen(
            [app_bin, "--hidden", "--connect"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        logging.info("App launch/connect command dispatched successfully.")
    except Exception as e:
        logging.error(f"Failed to launch app: {e}")

class MotoBudsWatcher:
    def __init__(self):
        DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus()
        self.device_names = {}
        self.device_connected = {}
        self._lock = threading.Lock()

    def get_device_info(self, dev_path):
        try:
            dev_obj = self.bus.get_object("org.bluez", dev_path)
            props_iface = dbus.Interface(dev_obj, "org.freedesktop.DBus.Properties")
            props = props_iface.GetAll("org.bluez.Device1")
            name = str(props.get("Name", props.get("Alias", "")))
            mac = str(props.get("Address", ""))
            connected = bool(props.get("Connected", False))
            return name, mac, connected
        except Exception:
            return None, None, False

    def on_properties_changed(self, interface, changed, invalidated, path=None):
        if interface != "org.bluez.Device1" or not path:
            return

        if "Connected" in changed:
            connected = bool(changed["Connected"])
            name, mac, _ = self.get_device_info(path)
            if not name:
                name = self.device_names.get(path, "")
            else:
                self.device_names[path] = name

            if is_moto_buds_device(name, mac):
                prev = self.device_connected.get(path, False)
                self.device_connected[path] = connected
                if connected and not prev:
                    logging.info(f"Detected connection event for {name} ({mac})")
                    # Trigger connection in a separate thread so GLib loop isn't blocked
                    t = threading.Thread(target=trigger_app_connect, args=(mac, name), daemon=True)
                    t.start()
                elif not connected and prev:
                    logging.info(f"Detected disconnection event for {name} ({mac})")

    def check_initial_devices(self):
        try:
            manager = dbus.Interface(self.bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
            objects = manager.GetManagedObjects()
            for path, interfaces in objects.items():
                if "org.bluez.Device1" in interfaces:
                    dev = interfaces["org.bluez.Device1"]
                    name = str(dev.get("Name", dev.get("Alias", "")))
                    mac = str(dev.get("Address", ""))
                    connected = bool(dev.get("Connected", False))
                    self.device_names[path] = name
                    self.device_connected[path] = connected
                    if connected and is_moto_buds_device(name, mac):
                        logging.info(f"Moto Buds is already connected on startup: {mac} ({name})")
                        t = threading.Thread(target=trigger_app_connect, args=(mac, name), daemon=True)
                        t.start()
        except Exception as e:
            logging.error(f"Error checking initial devices: {e}")

    def run(self):
        logging.info("Starting Moto Buds Bluetooth Watcher Service...")
        self.check_initial_devices()

        self.bus.add_signal_receiver(
            self.on_properties_changed,
            signal_name="PropertiesChanged",
            dbus_interface="org.freedesktop.DBus.Properties",
            path_keyword="path"
        )
        logging.info("Listening for BlueZ Bluetooth connection events...")
        loop = GLib.MainLoop()
        try:
            loop.run()
        except (KeyboardInterrupt, SystemExit):
            logging.info("Stopping watcher...")
            loop.quit()

if __name__ == "__main__":
    watcher = MotoBudsWatcher()
    watcher.run()
