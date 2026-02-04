from queue import Queue
import numpy as np
import queue
import threading
import logging
import serial.tools.list_ports
from time import monotonic_ns
from typing import Callable, Any
from pydantic import ValidationError, BaseModel
from functools import partial

from pyBEEP.device import PotentiostatDevice
from pyBEEP.logger import DataLogger
from pyBEEP.measurement_modes.waveform_outputs import (
    GalvanoOutput,
    PotenOutput,
    BaseOuput,
)
from pyBEEP.measurement_modes.waveforms_ocp import ocp_waveform
from pyBEEP.utils.utils import (
    default_filename,
    convert_uint16_to_float32,
    select_folder,
)
from pyBEEP.measurement_modes.waveforms_pot import (
    constant_waveform,
    linear_sweep,
    cyclic_voltammetry,
    potential_steps,
    capacitance_from_cv,
)
from pyBEEP.measurement_modes.waveforms_gal import (
    single_point,
    linear_galvanostatic_sweep,
    cyclic_galvanostatic,
    current_steps,
)
from pyBEEP.utils.constants import (
    CMD,
    REG_READ_ADDR,
    REG_WRITE_ADDR_PID,
    REG_WRITE_ADDR_POT,
    BUSSY_DLAY_NS,
    POINT_INTERVAL,
)
from pyBEEP.measurement_modes.waveform_params import (
    ConstantWaveformParams,
    PotentialStepsParams,
    LinearSweepParams,
    CyclicVoltammetryParams,
    SinglePointParams,
    CurrentStepsParams,
    LinearGalvanostaticSweepParams,
    CyclicGalvanostaticParams,
    OCPParams,
    CapacitanceParams
)
from pyBEEP.measurement_modes.measurement_modes import (
    ModeName,
    ControlMode,
    MeasurementMode,
    MeasurementModeMap,
)

logger = logging.getLogger(__name__)


class PotentiostatController:
    def __init__(self, device: PotentiostatDevice, default_folder: str | None = None):
        """
        Initialize the PotentiostatController.

        Args:
            device (PotentiostatDevice): The hardware interface for the potentiostat.
            default_folder (str | None): Default folder for saving measurement files. If None, no default is set.
        """
        self.device = device
        self.default_folder = default_folder
        self.last_plot_path = None
        self.device_lock = threading.Lock()
        available_modes = {
            "CA": {
                "mode_type": ControlMode.POT,
                "waveform_func": constant_waveform,
                "param_class": ConstantWaveformParams,
                "pid": False,
            },
            "LSV": {
                "mode_type": ControlMode.POT,
                "waveform_func": linear_sweep,
                "param_class": LinearSweepParams,
                "pid": False,
            },
            "CV": {
                "mode_type": ControlMode.POT,
                "waveform_func": cyclic_voltammetry,
                "param_class": CyclicVoltammetryParams,
                "pid": False,
            },
            "PSTEP": {
                "mode_type": ControlMode.POT,
                "waveform_func": potential_steps,
                "param_class": PotentialStepsParams,
                "pid": False,
            },
            "CP": {
                "mode_type": ControlMode.GAL,
                "waveform_func": single_point,
                "param_class": SinglePointParams,
                "pid": True,
            },
            "GS": {
                "mode_type": ControlMode.GAL,
                "waveform_func": linear_galvanostatic_sweep,
                "param_class": LinearGalvanostaticSweepParams,
                "pid": True,
            },
            "GCV": {
                "mode_type": ControlMode.GAL,
                "waveform_func": cyclic_galvanostatic,
                "param_class": CyclicGalvanostaticParams,
                "pid": True,
            },
            "STEPSEQ": {
                "mode_type": ControlMode.GAL,
                "waveform_func": current_steps,
                "param_class": CurrentStepsParams,
                "pid": True,
            },
            "OCP": {
                "mode_type": ControlMode.OCP,
                "waveform_func": ocp_waveform,
                "param_class": OCPParams,
                "pid": False,
            },
            "CDL": {
                "mode_type": ControlMode.POT,
                "waveform_func": capacitance_from_cv,
                "param_class": CapacitanceParams,
                "pid": False,
            },
        }
        validated_map = MeasurementModeMap.model_validate(available_modes)
        self._measurement_modes = validated_map.root

    def set_default_folder(self, folder: str | None = None):
        """
        Set the default folder for saving measurement files.

        Args:
            folder (str | None): The folder path to set as default. If None, no default is set.
        """
        if folder:
            self.default_folder = folder
        else:
            self.default_folder = select_folder()
        logger.info(f"Default folder set to: {self.default_folder}")

    def get_default_folder(self) -> str | None:
        """
        Get the default folder used for saving measurement files.

        Returns:
            str: The currently set default folder path. If not set, prompts the user to select one.
        """
        if not self.default_folder:
            self.set_default_folder()
        return self.default_folder

    def get_available_modes(self) -> list[str]:
        """
        Get a list of available measurement modes supported by this controller.

        Returns:
            list[str]: A list of string keys for supported measurement modes (e.g. 'CA', 'CV', 'LSV', etc.).
        """
        return [enum.value for enum in list(self._measurement_modes.keys())]

    def get_mode_params(self, mode: str) -> dict[str, Any]:
        """
        Get the parameter names and types required for a given measurement mode.

        Args:
            mode (str): The measurement mode key (e.g. 'CA', 'CV').

        Returns:
            dict[str, type]: A dictionary mapping parameter names to their expected types.

        Raises:
            ValueError: If the mode is not recognized.
        """
        mode_config = self._get_mode(mode=mode)
        if not mode_config:
            raise ValueError(f"Unknown measurement mode: {mode}")
        param_class = mode_config.param_class
        return {
            name: field.annotation for name, field in param_class.model_fields.items()
        }

    def get_waveform_func(self, mode: str) -> Callable | None:
        """
        Retrieve the waveform generation function associated with a given mode.

        Args:
            mode (str): The measurement mode key.

        Returns:
            Callable | None: The waveform generation function, or None if the mode is not found.
        """
        return self._get_mode(mode).waveform_func

    def is_pid_active(self, mode: str) -> bool:
        """
        Check if PID control is active for the given measurement mode.

        Args:
            mode (str): The measurement mode key.

        Returns:
            bool: True if PID control is used for this mode, False otherwise.
        """
        return self._get_mode(mode).pid

    def _get_mode(self, mode: str) -> MeasurementMode:
        """
        Retrieve the validated configuration for a given measurement mode.

        Args:
            mode (str): The measurement mode key (e.g., 'CA', 'CV').

        Returns:
            MeasurementMode: The corresponding validated mode configuration.

        Raises:
            ValueError: If the mode is not recognized.
        """
        try:
            return self._measurement_modes[ModeName(mode.upper())]
        except ValueError:
            raise ValueError(
                f"Invalid measurement mode: '{mode}'. Available modes: {[m.value for m in self._measurement_modes]}"
            )

    def _setup_measurement(
        self, tia_gain: int | None, clear_fifo: bool = False, fifo_start: bool = False
    ):
        """
        Configure and initialize the potentiostat hardware for a new measurement.

        Args:
            tia_gain (int): Transimpedance amplifier gain setting.
            clear_fifo (bool, optional): Whether to clear the FIFO buffer before starting. Defaults to False.
            fifo_start (bool, optional): Whether to start the FIFO immediately. Defaults to False.
        """
        if tia_gain is not None:
            self.device.send_command(CMD["SET_TIA_GAIN"], tia_gain)
        if clear_fifo:
            self.device.send_command(CMD["CLEAR_FIFO"], 1)
        if fifo_start:
            self.device.send_command(CMD["FIFO_START"], 1)
        self.device.send_command(CMD["SET_SWITCH"], 1)

    def _run_measurement(
        self,
        write_func: Callable[[queue.Queue], None],
        filepath: str,
        waveform: BaseModel,
        sampling_interval: int | float | None,
    ):
        """
        Run the measurement  process, managing writing and saving threads.

        Args:
            write_func (Callable): Function to perform measurement and write data to a queue.
            filepath (str): Path to the file where data will be saved.
            waveform (dict): Waveform data to be used in the measurement.
            sampling_interval (int | float | None): If set, will average every N rows before saving. Defaults to None (no reduction).
        """
        data_queue = queue.Queue()
        writer = DataLogger(data_queue, waveform, filepath, sampling_interval)

        write_thread = threading.Thread(target=write_func, args=(data_queue,))
        save_thread = threading.Thread(target=writer.run)

        write_thread.start()
        save_thread.start()

        try:
            write_thread.join()
        finally:
            data_queue.put(None)
            save_thread.join()

    def _teardown_measurement(self):
        """
        Switch off potentiostat after measurement is complete.
        """
        self.device.send_command(CMD["SET_SWITCH"], 0)
        self.device.send_command(CMD["TEST_STOP"], 1)

    def apply_measurement(
        self,
        mode: str,
        params: dict,
        *,
        tia_gain: int = 0,
        sampling_interval: int | float | None = None,
        filename: str | None = None,
        folder: str | None = None,
        charge_cutoff_c: float | None = None,
    ):
        """
        Function for performing electrochemical measurements with the potentiostat. Takes electrochemical method
        and its parameters, validates them, generate waveform for running the experiment, and runs it.

        Args:
            mode (str): Measurement mode key (e.g., 'CA', 'CV', etc.).
            params (dict): Dictionary of parameters for the waveform generation.
            tia_gain (int, optional): Transimpedance amplifier gain setting. Defaults to 0.
            sampling_interval (int | float | None): If set, will average every N rows before saving. Defaults to None (no reduction).
            filename (str | None, optional): File path for storing measurement data. If None, a default is generated.
            folder (str | None, optional): Folder for storing the file. If None, a pop-up will ask for the folder.
            charge_cutoff_c (float | None): Optional absolute charge limit in Coulombs. Stops the measurement once |Q| exceeds this value.

        Raises:
            ValueError: If the mode is unknown or parameter validation fails.

        Notes:
            - Select the TIA_GAIN carefully according to you expected current range of the reaction. If the gian is
              higher than needed (lower resistance), a higher noise level will be assumed unnecessarily. But if the
              gain is set too low (higher resistance), the desired current might not be reached.
        """
        mode_config = self._get_mode(mode)
        param_class = mode_config.param_class

        try:
            # Validate and parse user input with Pydantic
            param_obj = param_class(**params)
        except ValidationError as e:
            required_fields = list(param_class.model_fields.keys())
            raise ValueError(
                f"Parameter error for mode '{mode}':\n{e}\nExpected fields: {required_fields}"
            )

        # Generate the waveform using validated parameters
        waveform = mode_config.waveform_func(**param_obj.model_dump())

        filename = filename or default_filename(mode=mode, tia_gain=tia_gain)
        folder = folder or self.get_default_folder()
        filepath = f"{folder}/{filename}"

        logger.info(
            f"Mode: {mode.upper()}\nWavefunction: {mode_config.waveform_func}\n"
            f"Gain: {tia_gain}\nFilepath: {filepath}"
        )

        match mode_config.mode_type:
            case "GAL":
                write_func = partial(
                    self._read_write_data_pid_active,
                    waveform=waveform,
                    tia_gain=tia_gain,
                    charge_cutoff_c=charge_cutoff_c,
                )
            case "POT":
                write_func = partial(
                    self._read_write_data_pid_inactive,
                    waveform=waveform,
                    tia_gain=tia_gain,
                    charge_cutoff_c=charge_cutoff_c,
                )
            case "OCP":
                write_func = partial(
                    self._read_write_ocp, waveform=waveform, tia_gain=tia_gain
                )
            case _:
                raise ValueError(f"Unknown mode type: {mode_config.mode_type}")

        with self.device_lock:
            self._run_measurement(write_func, filepath, waveform, sampling_interval)

        self.last_plot_path = filepath

        if mode.upper() == "CDL":
            try:
                from pyBEEP.utils.postprocess.CdlAnalysis import estimate_cdl_from_csv
                result = estimate_cdl_from_csv(
                    filepath,
                    vertex_a = getattr(params, "vertex_a", 0.0),
                    vertex_b = getattr(params, "vertex_a", 0.0),
                )
                logger.info(
                    f"C_dl = {result['Cdl_mF']:.3f} mF "
                    f"(slope={result['Cdl_F']:.3e} F, R²={result['R2']:.3f}); "
                    f"points={result['n_points']}  file={result['csv']}"
                )
            except Exception as e:
                logger.warning(f"CDL analysis failed: {e}")
    def _read_operation(
        self,
        st: int,
        params: dict,
        n_register: int | None,
    ) -> list | None:
        try:
            if (st - params["rd_dly_st"] * 0) > params["busy_dly_ns"]:
                rd_data = self.device.read_data(
                    REG_READ_ADDR, n_register
                )  # Collect data
                return rd_data
        except Exception as e:
            logger.debug("Reading error, retrying...")
            params["rd_dly_st"] = monotonic_ns()
            params["rd_err_cnt"] += 1
            if params["rd_err_cnt"] > 16:
                logger.error(
                    f"Reading errors exceeded the limit, potentiostat not responding. Last error: {e}"
                )
                raise
        return None

    def _read_write_ocp(
        self,
        data_queue: Queue,
        waveform: BaseOuput,
        tia_gain: int | None = 0,
        n_register: int | None = 120,
    ) -> None:
        self._setup_measurement(tia_gain=tia_gain, clear_fifo=True, fifo_start=True)
        params = {
            "busy_dly_ns": BUSSY_DLAY_NS,
            "wr_err_cnt": 0,
            "rd_err_cnt": 0,
            "wr_dly_st": 0,
            "rd_dly_st": 0,
            "rx_tx_reg": 0,
            "wr_tx_reg": 0,
            "rd_tx_reg": 0,
            "transmission_st": monotonic_ns(),
        }

        n_items = len(waveform.time) * 2
        global_start_ns = monotonic_ns()
        # Start collecting
        while params["rd_tx_reg"] < n_items:
            st = monotonic_ns()
            rd_data = self._read_operation(st, params, n_register)
            if rd_data:
                rd_list = convert_uint16_to_float32(rd_data)
                data_queue.put(rd_list)
                params["rd_tx_reg"] += len(rd_list)
                params["rd_err_cnt"] = 0

        self._teardown_measurement()
        total_time_ns = monotonic_ns() - global_start_ns
        result_tm = total_time_ns / 1e9
        data_rate = (2 * params["rx_tx_reg"]) / result_tm
        logger.info(
            f"\nTotal transmission time {result_tm:3.4} s, data rate {(data_rate / 1000):3.4} KBytes/s.\n"
        )
        logger.info(f"Failed reading: {params['rd_err_cnt']}")

    def _read_write_data_pid_active(
        self,
        data_queue: Queue,
        waveform: GalvanoOutput,
        tia_gain: int | None = 0,
        n_register: int | None = 120,
        charge_cutoff_c: float | None = None,
    ) -> None:
        """
        Perform a measurement using PID-regulated current mode. The function handles writing commands
        of the commands to the potentiostat, given the current steps given, and reading of the
        potentiostat adc output data, which is added to a queue.

        Args:
            data_queue (Queue): Queue to which acquired data is pushed.
            waveform (np.ndarray): Array of [current, duration] pairs to be applied sequentially.
            tia_gain (int | None): TIA gain setting for measurement.
            n_register (int | None): Number of data words to read per register operation.
            charge_cutoff_c (float | None): Optional absolute charge limit in Coulombs.

        Raises:
            minimalmodbus.SlaveReportedException: If serial communication with the potentiostat fails repeatedly.

        Behaviour:
            - The current input is converted from np.float32 to uint16
            - The Transimpedance amplifier gain (TIA_GAIN) is initialized to the specified resistance and the FIFO
              is cleared.
            - For each current step, the PID is activated (which will switch on the FIFO too), setting the current
              value of the corresponding step as target (converted to uint16). This is followed a a reading loop that
              keeps withdrawing data during the step duration. The data read, is converted back to np.float32 and
              added to the 'data_queue' shared with the saving thread.
            - The 'data_queue' consist of a np.ndarray: A numpy array where each element is a pair of float values:
              [potential (in V), current (in A)]
            - Once the measurement is finished, potentiostat is switched off.
        """
        self._setup_measurement(tia_gain=tia_gain, clear_fifo=True)

        params = {
            "busy_dly_ns": BUSSY_DLAY_NS,
            "wr_err_cnt": 0,
            "rd_err_cnt": 0,
            "wr_dly_st": 0,
            "rd_dly_st": 0,
            "rx_tx_reg": 0,
            "wr_tx_reg": 0,
            "rd_tx_reg": 0,
            "transmission_st": monotonic_ns(),
        }

        accumulated_charge = 0.0  # [C]
        cutoff_reached = False
        global_start_ns = monotonic_ns()

        for current, duration, length in zip(
            waveform.current_steps, waveform.duration_steps, waveform.length_steps
        ):
            if cutoff_reached:
                break
            target = np.array(
                [
                    current,
                ],
                dtype=np.float32,
            ).tobytes(order="C")
            target = np.frombuffer(target, np.uint16).tolist()

            # Activate PID and set target
            self.device.write_data(
                REG_WRITE_ADDR_PID, [CMD["PID_START"]] + target
            )  # Send data

            # Start collecting
            while (params["rd_tx_reg"] < length) and (not cutoff_reached):
                st = monotonic_ns()
                rd_data = self._read_operation(st, params, n_register)
                if rd_data:
                    rd_list = convert_uint16_to_float32(rd_data)
                    data_queue.put(rd_list)
                    params["rd_tx_reg"] += len(rd_list)
                    params["rd_err_cnt"] = 0
                    if charge_cutoff_c is not None:
                        accumulated_charge += float(
                            np.sum(rd_list[:, 0]) * POINT_INTERVAL
                        )
                        logger.debug(
                            f"Charge |Q| = {abs(accumulated_charge):.6g} C (limit {charge_cutoff_c} C)."
                        )
                        if abs(accumulated_charge) >= charge_cutoff_c:
                            cutoff_reached = True
                            break
            # reset read counter for next PID step
            params["rd_tx_reg"] = 0
        self._teardown_measurement()

        total_time_ns = monotonic_ns() - global_start_ns
        result_tm = total_time_ns / 1e9
        data_rate = (2 * params["rx_tx_reg"]) / result_tm
        logger.info(
            f"\nTotal transmission time {result_tm:3.4} s, data rate {(data_rate / 1000):3.4} KBytes/s.\n"
        )
        logger.info(f"Failed writing: {params['wr_err_cnt']}")
        logger.info(f"Failed reading: {params['rd_err_cnt']}")
        logger.info(
            f"Send: {params['wr_tx_reg']}, Read: {params['rd_tx_reg']}, Diff: {params['rd_tx_reg'] - params['wr_tx_reg'] * 2}\n"
        )
        if cutoff_reached:
            logger.info(
                f"Charge cutoff reached at |Q| = {abs(accumulated_charge):.6g} C (limit {charge_cutoff_c} C)."
            )

    def _read_write_data_pid_inactive(
        self,
        data_queue: Queue,
        waveform: PotenOutput,
        tia_gain: int | None = 0,
        n_register: int = 120,
        charge_cutoff_c: float | None = None,
    ) -> None:
        """
        Perform a measurement using standard voltage-controlled mode. The function handles writing
        commands of the commands to the potentiostat, given the current steps given, and reading of
        the potentiostat adc output data, which is added to a queue.

         Args:
            data_queue (Queue): Queue to which acquired data is pushed.
            waveform (PotenOutput): Array of potential values to be applied over time.
            tia_gain (int | None): TIA gain setting for measurement.
            n_register (int): Number of data words to read per register operation.
            charge_cutoff_c (float | None): Optional absolute charge limit in Coulombs.

        Raises:
            minimalmodbus.SlaveReportedException: If serial communication with the potentiostat fails repeatedly.

        Behaviour:
           - The Transimpedance amplifier gain (TIA_GAIN) is initialized to the specified resistance and the FIFO
             is cleared and switch on.
           - The writing and reading of data is performed in a loop until all the data list created is sent.
             In this loop, a try-except clause is used for both writing and reading. No delays for writing or reading
             are applied, it will always keep trying to send and read data. Once all input voltage list is consumed,
             it will attept to read the FIFO 3 more times, to make sure all data is collected.
           - When reading, the output data is converted back from uint16 to np.float32 and added to 'data_queue'.
           - The 'data_queue' consist of a np.ndarray: A numpy array where each element is a pair of float values:
             [potential (in V), current (in A)]
           - Once the measurement is finished, potentiostat is switched off and adc_data list is returned.

        Notes:
           - Select the TIA_GAIN carefully according to your expected potential range of the reaction. If the gain
             is higher than needed (lower resistance), a higher noise level will be assumed unnecessarily. But if the
             gain is set too low (higher resistance), the desired potential might not be reached.
           - Unexpected behaviour is sometimes observed in first iterations of the while loop: number of reading
             operations is sometimes lower than writing operations. This was solved by (1) eliminating delays on
             reading and writing attempts, and (2) Adding 3 extra attempt after writing finishes to try to not leave
             any unread data in the FIFO. Still issues arise if measurements last less than 1s.
        """

        params = {
            "busy_dly_ns": BUSSY_DLAY_NS,
            "wr_err_cnt": 0,
            "rd_err_cnt": 0,
            "wr_dly_st": 0,
            "rd_dly_st": 0,
            "rx_tx_reg": 0,
            "wr_tx_reg": 0,
            "rd_tx_reg": 0,
            "transmission_st": monotonic_ns(),
        }

        accumulated_charge = 0.0  # [C]
        cutoff_reached = False

        # Generate numpy array to send
        y_bytes = waveform.applied_potential.tobytes(order="C")
        write_list = np.frombuffer(y_bytes, np.uint16)
        logger.debug(f"Write list element count {len(write_list)}.")
        n_items = len(write_list)
        logger.info(f"Total items to write: {n_items} uint16, {n_items // 2} float32,")
        for i in waveform.model_fields:
            value = getattr(waveform, i)
            logger.debug(f"Waveform {i}: {value.shape}, {value.dtype}")
            logger.debug(f"Waveform {i} first 10 values: {value[:10]}")
        logger.debug(f"Write list first 10 values: {write_list[:10]}")

        self._setup_measurement(tia_gain=tia_gain, clear_fifo=True, fifo_start=True)

        # Send and collect data
        i = 0
        params["transmission_st"] = monotonic_ns()

        post_read_attempts = 0
        while (not cutoff_reached) and (
            (post_read_attempts < 3)
            or (
                (params["rd_tx_reg"] / max(params["wr_tx_reg"], 1) / 2)
                < 1.0
            )
        ):
            st = monotonic_ns()
            if i < n_items:  # Writing
                data = write_list[i : i + n_register].tolist()
                try:
                    if (st - params["wr_dly_st"] * 0) > params["busy_dly_ns"]:
                        self.device.write_data(REG_WRITE_ADDR_POT, data)
                        params["wr_err_cnt"] = 0
                        params["wr_tx_reg"] += n_register
                        i += n_register
                except Exception as e:
                    params["wr_dly_st"] = monotonic_ns()
                    params["wr_err_cnt"] += 1
                    if params["wr_err_cnt"] > 10:
                        logger.error(
                            f"Writing errors exceeded the limit, potentiostat not responding. Last error: {e}"
                        )
                        raise
            # We need read two times for each write time because adc push two values to FIFO
            for _ in range(0, 2):
                rd_data = self._read_operation(st, params, n_register)
                if rd_data:
                    rd_list = convert_uint16_to_float32(rd_data)
                    data_queue.put(rd_list)
                    params["rd_tx_reg"] += len(rd_data)
                    params["rd_err_cnt"] = 0
                    if charge_cutoff_c is not None:
                        accumulated_charge += float(
                            np.sum(rd_list[:, 0]) * POINT_INTERVAL
                        )
                        logger.debug(
                            f"Charge |Q| = {abs(accumulated_charge):.6g} C (limit {charge_cutoff_c} C)."
                        )
                        if abs(accumulated_charge) >= charge_cutoff_c:
                            cutoff_reached = True
                            break
            if i >= n_items:
                post_read_attempts += 1

        self._teardown_measurement()

        result_tm = (monotonic_ns() - params["transmission_st"]) / 1e9
        data_rate = (2 * params["rx_tx_reg"]) / result_tm
        logger.info(
            f"\nTotal transmission time {result_tm:3.4} s, data rate {(data_rate / 1000):3.4} KBytes/s.\n"
        )
        logger.info(
            f"Send: {params['wr_tx_reg']}, Read: {params['rd_tx_reg']}, Read/Sent/2: {params['rd_tx_reg'] / params['wr_tx_reg'] / 2}\n"
        )
        logger.info(
            f"Actual points expected to read: {2 * params['wr_tx_reg']}, actual read: {params['rd_tx_reg']}, extra read operations: {int((params['rd_tx_reg'] - params['wr_tx_reg'] * 2) / 120)}\n"
        )
        if cutoff_reached:
            logger.info(
                f"Charge cutoff reached at |Q| = {abs(accumulated_charge):.6g} C (limit {charge_cutoff_c} C)."
            )


def connect_to_potentiostat():
    ports = serial.tools.list_ports.comports()
    device = None
    if not ports:
        raise ConnectionError(
            "No ports found, verify that the device is connected (and flashed) then try again"
        )

    for port in ports:
        if (port.vid == 2022) and (port.pid == 22099):
            device = PotentiostatDevice(port=port.device, address=1)
            break

    if device is None:
        raise ConnectionError(
            "No port found for the potentiostat, verify that the device is connected (and flashed) then try again"
        )
    else:
        controller = PotentiostatController(device=device)

    return controller


def connect_to_potentiostats():
    ports = serial.tools.list_ports.comports()
    list_controller = []

    if not ports:
        raise ConnectionError(
            "No ports found, verify that the device is connected (and flashed) then try again"
        )

    for port in ports:
        if (port.vid == 2022) and (port.pid == 22099):
            try:
                device = PotentiostatDevice(port=port.device, address=1)
                list_controller.append(PotentiostatController(device=device))
            except ConnectionError:
                print(f"Failed to connect to {port.device}")

    if len(list_controller) == 0:
        raise ConnectionError(
            "No port found for the potentiostat, verify that the device is connected (and flashed) then try again"
        )

    return list_controller
