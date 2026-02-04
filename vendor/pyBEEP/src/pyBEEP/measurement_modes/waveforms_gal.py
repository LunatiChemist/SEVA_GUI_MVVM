import numpy as np

from pyBEEP.measurement_modes.waveform_outputs import (
    GalvanoOutput,
    CyclicGalvanoOutput,
)
from pyBEEP.utils.constants import POINT_INTERVAL


def single_point(current: float, duration: float) -> GalvanoOutput:
    """
    Generates a single galvanostatic step.

    Args:
        current (float): Constant current to apply (in Amperes).
        duration (float): Duration of the step (in seconds).

    Returns:
        GalvanoOutput:
            - applied_current (np.ndarray): Constant applied current, shape (N,)
            - time (np.ndarray): Time array in seconds, shape (N,)
            - current_steps (np.ndarray): Single current step, shape (1,)
            - duration_steps (np.ndarray): Step duration, shape (1,)
            - length_steps (np.ndarray): Number of points in step, shape (1,)
    """
    num_points = int(duration / POINT_INTERVAL)
    applied_current = np.full(num_points, current, dtype=np.float32)
    time = np.arange(num_points) * POINT_INTERVAL

    return GalvanoOutput(
        applied_current=applied_current,
        time=time,
        current_steps=np.array([current], dtype=np.float32),
        duration_steps=np.array([duration], dtype=np.float32),
        length_steps=np.array([num_points], dtype=np.int32),
    )


def current_steps(currents: list[float], step_duration: float) -> GalvanoOutput:
    """
    Generates a sequence of galvanostatic steps, each with the same duration.

    Args:
        currents (list[float]): List of current values (in Amperes) to apply.
        step_duration (float): Duration (in seconds) for each step.

    Returns:
        GalvanoOutput:
            - applied_current (np.ndarray): Repeated current values, shape (N,)
            - time (np.ndarray): Time array in seconds, shape (N,)
            - current_steps (np.ndarray): Current step values, shape (n_steps,)
            - duration_steps (np.ndarray): Step durations, shape (n_steps,)
            - length_steps (np.ndarray): Points per step, shape (n_steps,)
    """
    num_points_per_step = int(step_duration / POINT_INTERVAL)
    applied_current = np.repeat(currents, num_points_per_step).astype(np.float32)
    total_points = len(applied_current)
    time = np.arange(total_points) * POINT_INTERVAL

    return GalvanoOutput(
        applied_current=applied_current,
        time=time,
        current_steps=np.array(currents, dtype=np.float32),
        duration_steps=np.full(len(currents), step_duration, dtype=np.float32),
        length_steps=np.full(len(currents), num_points_per_step, dtype=np.int32),
    )


def linear_galvanostatic_sweep(
    start: float, end: float, num_steps: int, step_duration: float
) -> GalvanoOutput:
    """
    Generates a linear sweep of current from start to end in equal steps.

    Args:
        start (float): Starting current (in Amperes).
        end (float): Ending current (in Amperes).
        num_steps (int): Number of discrete current steps.
        step_duration (float): Duration (in seconds) of each step.

    Returns:
        GalvanoOutput:
            - applied_current (np.ndarray): Linearly spaced current steps, repeated, shape (N,)
            - time (np.ndarray): Time array in seconds, shape (N,)
            - current_steps (np.ndarray): Current step values, shape (num_steps,)
            - duration_steps (np.ndarray): Step durations, shape (num_steps,)
            - length_steps (np.ndarray): Points per step, shape (num_steps,)
    """
    currents = np.linspace(start, end, num_steps, dtype=np.float32)
    points_per_step = int(step_duration / POINT_INTERVAL)
    applied_current = np.repeat(currents, points_per_step)
    time = np.arange(len(applied_current)) * POINT_INTERVAL

    return GalvanoOutput(
        applied_current=applied_current,
        time=time,
        current_steps=currents,
        duration_steps=np.full(num_steps, step_duration, dtype=np.float32),
        length_steps=np.full(num_steps, points_per_step, dtype=np.int32),
    )


def cyclic_galvanostatic(
    start: float,
    vertex1: float,
    vertex2: float,
    num_steps: int,
    step_duration: float,
    cycles: int,
    end: float | None = None,
) -> CyclicGalvanoOutput:
    """
    Generates a cyclic galvanostatic waveform with two vertex currents.

    Each cycle consists of:
        start → vertex1 → vertex2 → start

    Optionally, a final sweep from start to `end` is added if specified.

    Args:
        start (float): Starting current (in Amperes).
        vertex1 (float): First vertex current.
        vertex2 (float): Second vertex current.
        num_steps (int): Number of steps per segment.
        step_duration (float): Duration (in seconds) of each step.
        cycles (int): Number of full cycles.
        end (float, optional): Final current (if different from start).

    Returns:
        CyclicGalvanoOutput:
            - applied_current (np.ndarray): All current points, shape (N,)
            - time (np.ndarray): Time array in seconds, shape (N,)
            - cycle (np.ndarray): Cycle number label for each point, shape (N,)
            - current_steps (np.ndarray): All step current values, shape (M,)
            - duration_steps (np.ndarray): Durations per step, shape (M,)
            - length_steps (np.ndarray): Points per step, shape (M,)
    """
    current_steps_list = []
    duration_steps_list = []
    length_steps_list = []
    applied_current_segments = []
    cycle_segments = []

    points_per_step = int(step_duration / POINT_INTERVAL)

    for cycle_num in range(1, cycles + 1):
        for i_start, i_end in [(start, vertex1), (vertex1, vertex2), (vertex2, start)]:
            step_currents = np.linspace(i_start, i_end, num_steps, dtype=np.float32)
            segment = np.repeat(step_currents, points_per_step)
            applied_current_segments.append(segment)
            current_steps_list.extend(step_currents.tolist())
            duration_steps_list.extend([step_duration] * num_steps)
            length_steps_list.extend([points_per_step] * num_steps)
            cycle_segments.append(np.full_like(segment, cycle_num, dtype=np.int32))

    # Optional final segment
    if end is not None and end != start:
        step_currents = np.linspace(start, end, num_steps, dtype=np.float32)
        segment = np.repeat(step_currents, points_per_step)
        applied_current_segments.append(segment)
        current_steps_list.extend(step_currents.tolist())
        duration_steps_list.extend([step_duration] * num_steps)
        length_steps_list.extend([points_per_step] * num_steps)
        cycle_segments.append(np.full_like(segment, cycles + 1, dtype=np.int32))

    applied_current = np.concatenate(applied_current_segments)
    cycle_array = np.concatenate(cycle_segments)
    time = np.arange(len(applied_current)) * POINT_INTERVAL

    return CyclicGalvanoOutput(
        applied_current=applied_current,
        time=time,
        cycle=cycle_array,
        current_steps=np.array(current_steps_list, dtype=np.float32),
        duration_steps=np.array(duration_steps_list, dtype=np.float32),
        length_steps=np.array(length_steps_list, dtype=np.int32),
    )
