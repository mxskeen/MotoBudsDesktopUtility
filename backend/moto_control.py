import os
import sys
import socket

# Re-exec with system python if current Python lacks AF_BLUETOOTH (e.g. mise/pyenv/asdf)
if sys.platform == "linux" and not hasattr(socket, "AF_BLUETOOTH"):
    for system_python in ["/usr/bin/python3", "/bin/python3"]:
        if os.path.exists(system_python) and sys.executable != system_python:
            os.execv(system_python, [system_python] + sys.argv)

import binascii
import struct
import time
import argparse
import json
import subprocess

CLASSIC_MAC = "AUTO"
RFCOMM_PORT = 16

HEAD = b"HEAD"
TAIL = b"TAIL"

def discover_moto_device():
    """Dynamically discover connected or paired Moto Buds MAC address and responsive RFCOMM port."""
    detected_mac = None
    detected_port = None

    if sys.platform == "linux":
        import re
        # 1. Check currently connected devices via bluetoothctl
        try:
            out = subprocess.check_output(["bluetoothctl", "devices", "Connected"], text=True, timeout=3)
            for line in out.strip().splitlines():
                m = re.match(r"^Device\s+([0-9A-Fa-f:]{17})\s+(.*)$", line.strip())
                if m:
                    mac, name = m.group(1), m.group(2)
                    if any(kw in name.lower() for kw in ["moto", "buds"]):
                        detected_mac = mac
                        break
        except Exception:
            pass

        # 2. Fallback to paired devices
        if not detected_mac:
            try:
                out = subprocess.check_output(["bluetoothctl", "devices"], text=True, timeout=3)
                for line in out.strip().splitlines():
                    m = re.match(r"^Device\s+([0-9A-Fa-f:]{17})\s+(.*)$", line.strip())
                    if m:
                        mac, name = m.group(1), m.group(2)
                        if any(kw in name.lower() for kw in ["moto", "buds"]):
                            detected_mac = mac
                            break
            except Exception:
                pass

        # 3. Probe candidate RFCOMM ports (28 for Moto Buds 2, 16 for Moto Buds / Buds+)
        if detected_mac:
            candidate_ports = [28, 16, 13, 17, 1, 2, 3]
            for port in candidate_ports:
                s = None
                try:
                    s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
                    s.settimeout(0.8)
                    s.connect((detected_mac, port))
                    detected_port = port
                    break
                except Exception:
                    pass
                finally:
                    if s:
                        try:
                            s.close()
                        except Exception:
                            pass

            # Ensure Linux trust protocol is satisfied
            try:
                subprocess.run(["bluetoothctl", "trust", detected_mac], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    elif sys.platform == "win32":
        import re
        try:
            ps_cmd = 'Get-PnpDevice -Class Bluetooth | Where-Object { $_.FriendlyName -match "moto buds" } | Select-Object -ExpandProperty DeviceID'
            out = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps_cmd], text=True, timeout=4)
            for line in out.strip().splitlines():
                m = re.search(r"DEV_([0-9A-Fa-f]{12})", line)
                if m:
                    raw_mac = m.group(1)
                    detected_mac = ":".join(raw_mac[i:i+2] for i in range(0, 12, 2))
                    break
        except Exception:
            pass

        if detected_mac:
            candidate_ports = [28, 16, 13, 17, 1, 2, 3]
            for port in candidate_ports:
                s = None
                try:
                    s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
                    s.settimeout(0.8)
                    s.connect((detected_mac, port))
                    detected_port = port
                    break
                except Exception:
                    pass
                finally:
                    if s:
                        try:
                            s.close()
                        except Exception:
                            pass

    return detected_mac, detected_port

class MotoBudsController:
    def __init__(self, mac_address=CLASSIC_MAC, port=RFCOMM_PORT, output_json=False, is_daemon=False):
        self.mac_address = mac_address
        self.port = port
        self.sock = None
        self.output_json = output_json
        self.is_daemon = is_daemon
        
    def log(self, msg):
        if self.is_daemon:
            print(json.dumps({"type": "log", "message": msg}), flush=True)
        elif not self.output_json:
            print(msg)

    def connect(self):
        # Resolve auto mac/port if needed
        if self.mac_address in ("AUTO", None, "") or self.port in (16, None):
            auto_mac, auto_port = discover_moto_device()
            if auto_mac and self.mac_address in ("AUTO", None, ""):
                self.mac_address = auto_mac
            if auto_port:
                self.port = auto_port

        self.log(f"[*] Connecting to {self.mac_address} on Port {self.port}...")

        for attempt in range(5):
            if self.mac_address == "127.0.0.1":
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            else:
                self.sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            self.sock.settimeout(3.0)

            try:
                self.sock.connect((self.mac_address, self.port))
                self.log("[+] Connected successfully!")
                self._initialization_handshake()
                return True
            except Exception as e:
                self.log(f"[-] Connection attempt {attempt+1} failed: {e}")
                if self.sock:
                    try:
                        self.sock.close()
                    except Exception:
                        pass
                    self.sock = None
                time.sleep(0.5)
                
        self.log("[-] Failed to connect after all attempts.")
        self.sock = None
        return False

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.sock = None
            self.log("[*] Disconnected.")

    def _create_packet(self, opcode: int, payload: bytes) -> bytes:
        packet = bytearray()
        packet.extend(HEAD)
        
        total_len = 8 + len(payload)
        packet.extend(total_len.to_bytes(2, byteorder='little'))
        
        packet.extend(opcode.to_bytes(2, byteorder='big'))
        packet.append(128)  
        packet.append(0)    
        packet.extend(len(payload).to_bytes(2, byteorder='little'))
        packet.extend(int(0).to_bytes(2, byteorder='little')) 
        
        packet.extend(payload)
        
        crc = binascii.crc32(packet) & 0xFFFFFFFF
        packet.extend(struct.pack('<I', crc))
        
        packet.extend(TAIL)
        return bytes(packet)

    def send_command(self, opcode: int, payload: bytes):
        if not self.sock:
            return
        packet = self._create_packet(opcode, payload)
        self.sock.send(packet)

    def _send_and_receive(self, opcode: int, payload: bytes, wait_for_response=True):
        if not self.sock:
            self.log("[-] Not connected.")
            return None
            
        self.send_command(opcode, payload)
        
        # In daemon mode, we must not synchronously wait for responses because the 
        # main thread is actively polling the socket. Doing so causes race conditions 
        # and thread deadlocks.
        if self.is_daemon or not wait_for_response:
            return None
            
        try:
            self.sock.settimeout(0.5)
            all_data = bytearray()
            chunk = self.sock.recv(4096)
            if chunk:
                all_data.extend(chunk)
                self.sock.settimeout(0.2)
                while True:
                    try:
                        more = self.sock.recv(4096)
                        if not more: break
                        all_data.extend(more)
                    except socket.timeout:
                        break
            self.sock.settimeout(3.0)
            return bytes(all_data) if all_data else None
        except socket.timeout:
            self.log(f"[-] Timeout waiting for response to opcode {hex(opcode)}")
            return None
        except Exception as e:
            self.log(f"[-] Error communicating: {e}")
            return None

    def _initialization_handshake(self):
        self.log("[*] Performing initialization handshake...")
        self._send_and_receive(0x0000, b"")
        time.sleep(0.2)
        self._send_and_receive(0x000B, b"\xfc\xff\x05\x00")
        time.sleep(0.2)
        self._send_and_receive(0x0010, b"")
        time.sleep(0.2)

    def _get_bluez_battery(self):
        if sys.platform != "linux" or self.mac_address in ("127.0.0.1", "AUTO", None):
            return None
        try:
            out = subprocess.check_output(["bluetoothctl", "info", self.mac_address], text=True, timeout=2)
            import re
            m = re.search(r"Battery Percentage:\s+0x[0-9a-fA-F]+\s+\((\d+)\)", out)
            if m:
                return int(m.group(1))
        except Exception:
            pass
        return None

    def read_battery(self):
        self.log("[*] Reading Battery Level...")
        resp = None
        if not self.is_daemon:
            resp = self._send_and_receive(0x0005, b"")
        else:
            self.send_command(0x0005, b"")

        # Fallback to BlueZ battery info on Linux if SPP doesn't return battery levels
        if not resp:
            bluez_bat = self._get_bluez_battery()
            if bluez_bat is not None:
                # Opcode 9 Battery notification: Left, Right, Case=0xFF (unknown/not in case)
                resp = self._create_packet(0x0009, bytes([bluez_bat, bluez_bat, 0xFF]))

        if resp:
            self.log(f"[+] Raw Battery Response: {resp.hex()}")
        return resp.hex() if resp else None

    def get_hardware_info(self):
        self.log("[*] Reading Hardware Info...")
        resp = self._send_and_receive(0x0004, b"")
        if resp:
            self.log(f"[+] Raw Hardware Info: {resp.hex()}")
        return resp.hex() if resp else None

    def toggle_anc(self, mode: int, sub_mode: int):
        self.log(f"[*] Setting ANC Mode: {mode}, Sub-Mode: {sub_mode}")
        payload = bytes([mode, sub_mode])
        resp = self._send_and_receive(0x0201, payload)
        if resp:
            self.log(f"[+] Response: {resp.hex()}")
        return resp.hex() if resp else None

    def toggle_game_mode(self, enabled: int):
        self.log(f"[*] Setting Game Mode: {enabled}")
        resp = self._send_and_receive(0x030F, bytes([enabled]))
        return resp.hex() if resp else None

    def toggle_inear(self, enabled: int):
        self.log(f"[*] Setting In-Ear Detection: {enabled}")
        resp = self._send_and_receive(0x0403, bytes([enabled]))
        return resp.hex() if resp else None

    def toggle_volboost(self, enabled: int):
        self.log(f"[*] Setting Volume Boost: {enabled}")
        resp = self._send_and_receive(0x0314, bytes([enabled]))
        return resp.hex() if resp else None

    def toggle_hires(self, enabled: int):
        self.log(f"[*] Setting Hi-Res Mode: {enabled}")
        resp = self._send_and_receive(0x030D, bytes([enabled]))

        # The earbuds will internally reboot to renegotiate the LDAC codec.
        # We must bounce the adapter unconditionally because in daemon mode, _send_and_receive returns None.
        if self.mac_address != "127.0.0.1":
            import subprocess
            # We use disconnect and connect to force the Linux A2DP stack to renegotiate
            # the codec successfully without taking down the entire bluetooth adapter.
            subprocess.Popen(
                f"sleep 1 ; bluetoothctl disconnect {self.mac_address} ; sleep 2 ; bluetoothctl connect {self.mac_address}", 
                shell=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        return resp.hex() if resp else None

    def toggle_fit(self, start: int):
        self.log(f"[*] Setting Fit Test: {start}")
        resp = self._send_and_receive(0x0400, bytes([start]))
        return resp.hex() if resp else None

    def toggle_fmd(self, left: int, right: int):
        self.log(f"[*] Setting FMD: Left={left}, Right={right}")
        resp = self._send_and_receive(0x0405, bytes([left, right]))
        return resp.hex() if resp else None

    def set_custom_eq(self, bands):
        import struct
        self.log(f"[*] Setting Custom EQ")
        # 173 bytes payload for opcode 774 (0x0306)
        payload = bytearray([0x3F])
        payload.extend(struct.pack('<f', 0.0)) # Pre-amp
        payload.extend(struct.pack('<f', 0.0)) # Post-amp
        payload.extend(struct.pack('<i', 10))  # Num bands
        
        freqs = [32.0, 64.0, 125.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0, 16000.0]
        for i in range(10):
            gain = float(bands[i]) if i < len(bands) else 0.0
            payload.extend(struct.pack('<i', 0)) # Filter type
            payload.extend(struct.pack('<f', gain))
            payload.extend(struct.pack('<f', freqs[i]))
            payload.extend(struct.pack('<f', 0.75)) # Q Factor
            
        resp = self._send_and_receive(0x0306, bytes(payload))
        return resp.hex() if resp else None

    def set_gesture(self, earbud: int, gesture_type: int, function_id: int):
        self.log(f"[*] Setting Gesture: Earbud={earbud}, Type={gesture_type}, Func={function_id}")
        resp = self._send_and_receive(0x0102, bytes([earbud, gesture_type, function_id]))
        return resp.hex() if resp else None

def main():
    parser = argparse.ArgumentParser(description="Moto Buds Controller")
    parser.add_argument("--battery", action="store_true", help="Read battery levels")
    parser.add_argument("--info", action="store_true", help="Read hardware info")
    parser.add_argument("--anc", type=int, choices=[0, 1, 2], help="Set ANC Mode (0=Off, 1=ANC, 2=Transparency)")
    parser.add_argument("--game", type=int, choices=[0, 1], help="Set Game Mode")
    parser.add_argument("--inear", type=int, choices=[0, 1], help="Set In-Ear Detection")
    parser.add_argument("--volboost", type=int, choices=[0, 1], help="Set Volume Boost")
    parser.add_argument("--hires", type=int, choices=[0, 1], help="Set Hi-Res/LDAC")
    parser.add_argument("--fit", type=int, choices=[0, 1], help="Set Fit Test (0=Stop, 1=Start)")
    parser.add_argument("--fmd", type=int, choices=[0, 1, 2, 3], help="Set Find My Device Mode")
    parser.add_argument("--daemon", action="store_true", help="Run as a long-lived bidirectional daemon using stdin/stdout")
    parser.add_argument("--keepalive", type=int, help="Keep SPP connection alive for N seconds to capture async events")
    parser.add_argument("--sync", action="store_true", help="Sync startup states (ANC, HiRes, Game, InEar)")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--mac", type=str, default=CLASSIC_MAC, help="MAC address or 127.0.0.1 for mock")
    parser.add_argument("--port", type=int, default=RFCOMM_PORT, help="Port")
    
    args = parser.parse_args()
    
    if not any([args.battery, args.info, args.anc is not None, args.game is not None, args.inear is not None, args.volboost is not None, args.hires is not None, args.fit is not None, args.fmd is not None, args.sync, args.daemon]):
        parser.print_help()
        sys.exit(1)

    # If this is a UI command (not a keepalive polling script), we must preemptively 
    # kill the background keepalive script, otherwise the RFCOMM socket is locked 
    # and we'll get a 'Device or resource busy' error.
    if args.keepalive is None:
        try:
            import subprocess
            # Kill any running moto_control.py that has --keepalive
            subprocess.run(["pkill", "-f", "moto_control.py.*--keepalive"], stderr=subprocess.DEVNULL)
            time.sleep(0.2) # Give the OS a tiny moment to release the RFCOMM port
        except Exception:
            pass

    target_mac = args.mac
    target_port = args.port
    if target_mac in ("AUTO", "54:84:50:92:78:AE", None):
        auto_mac, auto_port = discover_moto_device()
        if auto_mac:
            target_mac = auto_mac
        if auto_port and target_port in (16, None):
            target_port = auto_port

    controller = MotoBudsController(mac_address=target_mac, port=target_port, output_json=args.json, is_daemon=args.daemon)
    
    if args.daemon:
        if not controller.connect():
            print(json.dumps({"type": "error", "message": "Failed to connect to earbuds"}))
            sys.exit(1)
            
        print(json.dumps({"type": "status", "status": "connected"}), flush=True)
        # Emit initial battery state
        init_bat = controller.read_battery()
        if init_bat:
            print(json.dumps({"type": "battery", "data": init_bat}), flush=True)
        
        import subprocess
        subprocess.Popen("killall -q mpris-proxy ; sleep 0.5 ; mpris-proxy &", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        
        import threading
        
        def stdin_listener():
            for line in sys.stdin:
                line = line.strip()
                if not line: continue
                try:
                    cmd = json.loads(line)
                    op = cmd.get("op")
                    if op == "anc":
                        mode = cmd.get("mode")
                        sub_mode = 1 if mode == 1 else 0
                        controller.toggle_anc(mode, sub_mode)
                        anc_pkt = controller._create_packet(0x0204, bytes([mode, sub_mode]))
                        print(json.dumps({"type": "event", "data": anc_pkt.hex()}), flush=True)
                    elif op == "game":
                        en = 1 if cmd.get("enabled") else 0
                        controller.toggle_game_mode(en)
                        game_pkt = controller._create_packet(0x0312, bytes([en]))
                        print(json.dumps({"type": "event", "data": game_pkt.hex()}), flush=True)
                    elif op == "inear":
                        en = 1 if cmd.get("enabled") else 0
                        controller.toggle_inear(en)
                        inear_pkt = controller._create_packet(1027, bytes([en]))
                        print(json.dumps({"type": "event", "data": inear_pkt.hex()}), flush=True)
                    elif op == "volboost":
                        en = 1 if cmd.get("enabled") else 0
                        controller.toggle_volboost(en)
                        vb_pkt = controller._create_packet(789, bytes([en]))
                        print(json.dumps({"type": "event", "data": vb_pkt.hex()}), flush=True)
                    elif op == "hires":
                        en = 1 if cmd.get("enabled") else 0
                        controller.toggle_hires(en)
                        hires_pkt = controller._create_packet(785, bytes([en]))
                        print(json.dumps({"type": "event", "data": hires_pkt.hex()}), flush=True)
                    elif op == "fit":
                        controller.toggle_fit(cmd.get("enabled"))
                    elif op == "fmd":
                        controller.toggle_fmd(int(cmd.get("left", 0)), int(cmd.get("right", 0)))
                    elif op == "eq":
                        controller.set_custom_eq(cmd.get("bands"))
                    elif op == "gesture":
                        eb = cmd.get("earbud")
                        gt = cmd.get("gesture")
                        fn = cmd.get("func")
                        controller.set_gesture(eb, gt, fn)
                        g_pkt = controller._create_packet(0x0105, bytes([eb, gt, fn]))
                        print(json.dumps({"type": "event", "data": g_pkt.hex()}), flush=True)
                    elif op == "sync":
                        res_anc = controller._send_and_receive(0x0200, b"")
                        res_hires = controller._send_and_receive(0x030C, b"")
                        res_game = controller._send_and_receive(0x030E, b"")
                        res_inear = controller._send_and_receive(0x0402, b"")
                        res_gestures = controller._send_and_receive(0x0100, b"")
                        sync_data = {}
                        if res_anc: sync_data["anc_raw"] = res_anc.hex()
                        if res_hires: sync_data["hires_raw"] = res_hires.hex()
                        if res_game: sync_data["game_raw"] = res_game.hex()
                        if res_inear: sync_data["inear_raw"] = res_inear.hex()
                        if res_gestures: sync_data["gestures_raw"] = res_gestures.hex()
                        print(json.dumps({"type": "sync", "data": sync_data}), flush=True)
                    elif op == "battery":
                        res = controller.read_battery()
                        print(json.dumps({"type": "battery", "data": res}), flush=True)
                    elif op == "info":
                        res = controller.get_hardware_info()
                        print(json.dumps({"type": "info", "data": res}), flush=True)
                except Exception as e:
                    controller.log(f"[-] Daemon JSON command error: {e}")
            # Exit daemon immediately when stdin reaches EOF (parent Electron closed)
            controller.disconnect()
            os._exit(0)
        
        # Start the thread that listens to commands from Electron
        t = threading.Thread(target=stdin_listener, daemon=True)
        t.start()
        
        # Main thread acts as the async event polling loop
        controller.sock.settimeout(0.5)
        last_battery_poll = time.time()
        while True:
            try:
                # Periodic battery update every 15 seconds
                now = time.time()
                if now - last_battery_poll > 15:
                    last_battery_poll = now
                    b_hex = controller.read_battery()
                    if b_hex:
                        print(json.dumps({"type": "battery", "data": b_hex}), flush=True)

                if not controller.sock:
                    break
                data = controller.sock.recv(1024)
                if data:
                    print(json.dumps({"type": "event", "data": data.hex()}), flush=True)
            except socket.timeout:
                continue
            except Exception as e:
                print(json.dumps({"type": "error", "message": f"Connection dropped, attempting to reconnect... ({e})"}), flush=True)
                
                # The earbuds often momentarily reboot their Bluetooth stack to renegotiate
                # codecs (e.g., when toggling LDAC Hi-Res). Instead of crashing the daemon, 
                # we wait and attempt to gracefully reconnect.
                controller.disconnect()
                
                # Give the OS-level bluetoothctl script 4 seconds to fully bounce
                # the connection (disconnect -> connect) before we aggressively 
                # try to grab the RFCOMM serial port again.
                time.sleep(4)
                
                reconnected = False
                for attempt in range(10):
                    time.sleep(2)
                    if controller.connect():
                        reconnected = True
                        print(json.dumps({"type": "status", "status": "connected"}), flush=True)
                        import subprocess
                        subprocess.Popen("killall -q mpris-proxy ; sleep 0.5 ; mpris-proxy &", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        break
                        
                if not reconnected:
                    print(json.dumps({"type": "error", "message": "Failed to reconnect after device reset."}), flush=True)
                    break
                
        controller.disconnect()
        sys.exit(0)

    results = {"status": "success", "data": {}}
    
    if controller.connect():
        if args.battery:
            res = controller.read_battery()
            results["data"]["battery_raw"] = res
        if args.info:
            res = controller.get_hardware_info()
            results["data"]["hardware_raw"] = res
        if args.anc is not None:
            sub_mode = 1 if args.anc == 1 else 0
            res = controller.toggle_anc(args.anc, sub_mode)
            results["data"]["anc_response"] = res
        if args.game is not None:
            res = controller.toggle_game_mode(args.game)
            results["data"]["game_response"] = res
        if args.inear is not None:
            res = controller.toggle_inear(args.inear)
            results["data"]["inear_response"] = res
        if args.volboost is not None:
            res = controller.toggle_volboost(args.volboost)
            results["data"]["volboost_response"] = res
        if args.hires is not None:
            res = controller.toggle_hires(args.hires)
            results["data"]["hires_response"] = res
        if args.fit is not None:
            res = controller.toggle_fit(args.fit)
            results["data"]["fit_response"] = res
        if args.fmd is not None:
            res = controller.toggle_fmd(args.fmd)
            results["data"]["fmd_response"] = res

        if args.sync:
            # Opcode 512, 780, 782, 1026
            res_anc = controller._send_and_receive(0x0200, b"")
            res_hires = controller._send_and_receive(0x030C, b"")
            res_game = controller._send_and_receive(0x030E, b"")
            res_inear = controller._send_and_receive(0x0402, b"")
            res_gestures = controller._send_and_receive(0x0100, b"")
            if res_anc: results["data"]["anc_raw"] = res_anc.hex()
            if res_hires: results["data"]["hires_raw"] = res_hires.hex()
            if res_game: results["data"]["game_raw"] = res_game.hex()
            if res_inear: results["data"]["inear_raw"] = res_inear.hex()
            if res_gestures: results["data"]["gestures_raw"] = res_gestures.hex()

        if args.keepalive:
            controller.log(f"[*] Keeping connection alive for {args.keepalive} seconds...")
            start_t = time.time()
            async_events = []
            try:
                controller.sock.settimeout(1.0)
                while time.time() - start_t < args.keepalive:
                    try:
                        data = controller.sock.recv(1024)
                        if data:
                            async_events.append(data.hex())
                            controller.log(f"[+] Async Event: {data.hex()}")
                    except socket.timeout:
                        continue
            except Exception as e:
                controller.log(f"[-] Keepalive error: {e}")
            finally:
                if controller.sock:
                    try:
                        controller.sock.settimeout(2.0)
                    except Exception:
                        pass
            results["data"]["async_events"] = async_events
            
        controller.disconnect()
    else:
        results["status"] = "error"
        results["message"] = "Failed to connect to earbuds"

    if args.json:
        print(json.dumps(results))

if __name__ == "__main__":
    main()
