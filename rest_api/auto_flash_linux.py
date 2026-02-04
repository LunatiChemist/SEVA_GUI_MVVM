"""Linux firmware flashing helper used by the REST API.

The `/firmware/flash` route in `rest_api.app` stores an uploaded `.bin` file and
then invokes this script as a subprocess. The script switches the controller to
DFU mode (USB bootloader mode), flashes the binary via `dfu-util`, and waits
until the CDC serial interface is available again.
"""

import os
import subprocess
import sys
import time

import serial
import serial.tools.list_ports

# Runtime constants must match the firmware bootloader configuration.
BAUD_RATE = 115200
BOOT_COMMAND = b"BOOT_DFU_MODE"
DFU_VENDOR = 2022
DFU_PRODUCT = 22099


def find_com_port() -> str:
    """Locate the CDC serial device for the configured VID/PID pair.

    Returns
    -------
    str
        Device path (for example `/dev/ttyACM0`).

    Raises
    ------
    ValueError
        If no ports are available or none match the configured USB IDs.
    """
    ports = serial.tools.list_ports.comports()

    if not ports:
        raise ValueError(
            "No ports found, verify that the device is connected (and flashed once) then try again"
        )

    for port in ports:
        if (port.vid == DFU_VENDOR) and (port.pid == DFU_PRODUCT):
            return port.device

    raise ValueError(
        "No compatible port found, verify that the device is connected (and flashed once) then try again"
    )


def send_command(command: bytes) -> None:
    """Send a binary command over CDC serial.

    Parameters
    ----------
    command : bytes
        Bootloader control command. The REST API passes `BOOT_DFU_MODE`.

    Side Effects
    ------------
    Opens the serial port, writes a command, and prints optional response bytes.

    Raises
    ------
    SystemExit
        Exits with status code 1 when the serial port cannot be opened.
    """
    try:
        com_port = find_com_port()
        print(f"[USB CDC] Sending {command} command to {com_port}...")
        with serial.Serial(com_port, BAUD_RATE, timeout=2) as ser:
            ser.reset_input_buffer()
            ser.write(command)
            print("[USB CDC] Command sent.")

            timeout = time.time() + 3
            while time.time() < timeout:
                if ser.in_waiting:
                    response = ser.read(ser.in_waiting).decode(errors="ignore")
                    print(f"[USB CDC] Received: {response.strip()}")
                    break
            else:
                print("[USB CDC] No response received.")

    except (serial.SerialException, ValueError):
        print("[!] Error opening COM port")
        sys.exit(1)


def wait_for_dfu(timeout: int = 10) -> bool:
    """Wait until a DFU device appears on USB.

    Parameters
    ----------
    timeout : int, default=10
        Maximum wait time in seconds.

    Returns
    -------
    bool
        `True` when DFU mode is detected.

    Raises
    ------
    SystemExit
        If `dfu-util` is missing or no DFU device appears before timeout.
    """
    print(f"[DFU] Waiting for STM32 DFU device to appear on USB ({timeout}s)...")
    for _ in range(timeout):
        try:
            result = subprocess.run(["dfu-util", "-l"], capture_output=True, text=True)
            if "Found DFU" in result.stdout:
                print("[DFU] DFU device detected.")
                return True
        except FileNotFoundError:
            print("[!] dfu-util not found in PATH.")
            sys.exit(1)
        time.sleep(1)
    print("[!] DFU device not found in time.")
    sys.exit(1)


def flash_firmware() -> None:
    """Flash the firmware binary with `dfu-util`.

    Side Effects
    ------------
    Runs an external process and writes firmware bytes to the controller.

    Raises
    ------
    SystemExit
        If `dfu-util` reports a critical error.
    """
    print("[DFU] Flashing firmware via USB...")
    flash_cmd = [
        "dfu-util",
        "-a",
        "0",
        "-d",
        f"{DFU_VENDOR:04x}:{DFU_PRODUCT:04x}",
        "-s",
        "0x08000000:leave",
        "-D",
        BIN_FILE_PATH,
    ]
    result = subprocess.run(flash_cmd, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)

    # Ignore known non-fatal dfu-util warnings; fail only on critical lines.
    critical_errors = []
    for line in result.stderr.splitlines():
        if not (
            "Invalid DFU suffix signature" in line
            or "Error during download get_status" in line
            or "A valid DFU suffix will be required in a future dfu-util release" in line
        ):
            critical_errors.append(line)

    if result.returncode != 0 and critical_errors:
        print("[!] Flashing failed with critical error(s):")
        for err in critical_errors:
            print(err)
        sys.exit(1)

    print("[DFU] Flashing complete")


def wait_for_cdc(timeout: int = 10) -> bool:
    """Wait for CDC serial re-enumeration after flashing.

    Parameters
    ----------
    timeout : int, default=10
        Maximum wait time in seconds.

    Returns
    -------
    bool
        `True` when the serial port is available again.

    Raises
    ------
    RuntimeError
        If the CDC interface does not come back in time.
    """
    print("[USB CDC] Waiting for new firmware to appear...")
    for _ in range(timeout):
        try:
            com_port = find_com_port()
            with serial.Serial(com_port, BAUD_RATE, timeout=1):
                print("[USB CDC] Device is back.")
                return True
        except (serial.SerialException, ValueError):
            time.sleep(1)
    raise RuntimeError("New firmware did not enumerate CDC")


if __name__ == "__main__":
    if len(sys.argv) == 2:
        BIN_FILE_PATH = sys.argv[1].replace("/", os.sep)
    else:
        print("[!] Arg not found")
        sys.exit(1)

    if not os.path.exists(BIN_FILE_PATH):
        print(f"[!] File not found: {BIN_FILE_PATH}")
        sys.exit(1)

    send_command(BOOT_COMMAND)
    wait_for_dfu()
    flash_firmware()
    wait_for_cdc()
