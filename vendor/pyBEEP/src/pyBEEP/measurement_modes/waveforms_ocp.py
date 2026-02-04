import numpy as np

from pyBEEP.measurement_modes.waveform_outputs import BaseOuput
from pyBEEP.utils.constants import POINT_INTERVAL


def ocp_waveform(duration: float) -> BaseOuput:
    """
    Generates a single ocp step.

    Args:
        duration (float): Duration of the step (in seconds).

    Returns:
        BaseOuput:
            - time (np.ndarray): Time array in seconds, shape (N,)
    """
    num_points = int(duration / POINT_INTERVAL)
    time = np.arange(num_points) * POINT_INTERVAL

    return BaseOuput(
        time=time,
    )
