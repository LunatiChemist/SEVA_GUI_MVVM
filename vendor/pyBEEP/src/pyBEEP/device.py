import minimalmodbus
from typing import List
import logging

logger = logging.getLogger(__name__)


class PotentiostatDevice:
    def __init__(
        self, port: str, address: int, baudrate: int = 1500000, timeout: float = 0.03
    ):
        self.device = minimalmodbus.Instrument(port, address)
        if self.device.serial is not None:
            self.device.serial.baudrate = baudrate
            self.device.serial.timeout = timeout
        else:
            raise ConnectionError("No device found")

    def send_command(self, command: int, parameter: int = 0) -> None:
        """
        Sends a specific command and its associated parameter to the potentiometer device
        via Modbus communication using the MinimalModbus library.

        Parameters:
        command (int): The command to be sent to the device, represented as an integer value.
                       This can be one of the predefined constants in the PotentiometerCommand class.
        parameter (int): The parameter associated with the command, represented as an integer value.
                         The meaning of the parameter depends on the specific command.

        Raises:
        minimalmodbus.SlaveReportedException: If the device responds with an error, an exception will be raised.

        Example:
        pot_command.SenPotentiometerCommand(PotentiometerCommand.CMD_SET_TIA_GAIN, PotentiometerCommand.GAIN_10K)
        """
        try:
            self.device.write_registers(0x4F00, [command, parameter])
        except minimalmodbus.SlaveReportedException as e:
            logger.debug(f"[Error] Command {command:#X}: {e}")
            exit()

    def write_data(self, address: int, data: List[int]) -> None:
        """Write a list of register values to the device."""
        self.device.write_registers(address, data)

    def read_data(self, address: int, count: int | None) -> List[int]:
        """Read a list of register values from the device."""
        if count is not None:
            return self.device.read_registers(address, count)
        else:
            return []
