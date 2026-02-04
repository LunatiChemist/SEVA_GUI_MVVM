import csv
import numpy as np
import logging
from pydantic import BaseModel
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import _csv

from pyBEEP.utils.constants import POINT_INTERVAL

logger = logging.getLogger(__name__)


class DataLogger:
    """
    Streams data from a queue to a CSV file, with optional reduction (downsampling) by averaging every N rows.
    Handles arbitrary-sized incoming data blocks and ensures no data is lost, always averaging the specified number of points.
    """

    def __init__(
        self,
        queue,
        waveform: BaseModel,
        filepath: str,
        sampling_interval: float | int | None,
    ):
        """
        Initialize the DataLogger. And calculates the reducing factor according to the sampling interval  specified

        Args:
            queue: Queue providing data blocks (np.ndarray or list of rows).
            waveform (dict): Dictionary containing waveform metadata, e.g., applied potentials or currents.
            filepath (str): Path to the output CSV file.
            sampling interval (int | float | None): If set, will average every N rows before saving. Defaults to None (no reduction).
        """
        self.queue = queue
        self.filepath = filepath
        self.waveform = waveform
        self.metadata_keys = list(waveform.model_fields.keys())
        if sampling_interval is not None:
            if sampling_interval < POINT_INTERVAL:
                logger.warning(
                    "Introduced sampling interval is bellow maximum BEEP resolution\n"
                )
                logger.warning(f"Sampling intervalas changed to: {POINT_INTERVAL} s")
                sampling_interval = POINT_INTERVAL
            self.reducing_factor = int(round(sampling_interval / POINT_INTERVAL))
        else:
            self.reducing_factor = 1
        logger.info(f"Reducing factor applied: {self.reducing_factor}")

    def run(self) -> None:
        """
        Continuously reads data blocks from the queue and writes them to a CSV file.
        If reducing_factor is set, averages every N rows before writing.
        Handles arbitrary block sizes and ensures all data is processed without loss.
        When the queue signals completion with None, any remaining data is also written (averaged if needed).
        """
        buffer = []
        data_idx = 0
        with open(self.filepath, mode="w", newline="") as file:
            writer = csv.writer(file)
            while True:
                item = self.queue.get()
                if item is None:
                    break
                buffer.extend(item)
                if len(buffer) > 20 and len(buffer) > self.reducing_factor:
                    buffer, data_idx = self._save_batch(writer, buffer, data_idx)
                    file.flush()
            if buffer:
                self._save_batch(writer, buffer, data_idx, flush_all=True)
                file.flush()
        logger.info(f"Saved: {self.filepath}")

    def _save_batch(
        self,
        writer: "_csv._writer",
        buffer: list,
        data_idx: int,
        flush_all: bool = False,
    ) -> tuple:
        """
        Enriches the buffer with waveform metadata (if present) and writes as many reduced (averaged)
        rows as possible to the CSV file. Keeps any leftover rows (less than reducing_factor) in the
        buffer unless flush_all is True.

        Args:
            writer (csv.writer): CSV writer object used for writing rows.
            buffer (list): List of measured rows (each row is a list or np.ndarray).
            data_idx (int): Current offset into waveform arrays.
            flush_all (bool): If True, averages and writes any leftover rows (even if less than reducing_factor).

        Returns:
            tuple: (remaining buffer as list, updated data_idx)
        """
        factor = self.reducing_factor
        n = len(buffer)
        new_idx = data_idx + n
        measured = np.array(buffer)  # shape (N, 2) = [Current (A), Potential (V)]
        current = measured[:, 0].reshape(-1, 1)
        potential = measured[:, 1].reshape(-1, 1)

        skip_keys = {"current_steps", "duration_steps", "length_steps"}
        metadata = {}
        if self.waveform:
            for key in self.metadata_keys:
                if key not in skip_keys:
                    value = getattr(self.waveform, key)[data_idx:new_idx]
                    metadata[key] = np.asarray(value).reshape(-1, 1)

        # Ensure metadata and measured have same length
        min_len = (
            min(len(potential), *(len(v) for v in metadata.values()))
            if metadata
            else len(potential)
        )
        potential = potential[:min_len]
        current = current[:min_len]
        exp_num = np.ones((min_len, 1), dtype=int)
        for k in metadata:
            metadata[k] = metadata[k][:min_len]

        # Build ordered columns
        ordered_cols = []
        col_names = []
        if "time" in metadata:
            ordered_cols.append(metadata.pop("time"))
            col_names.append("Time (s)")
        ordered_cols.append(potential)
        col_names.append("Potential (V)")
        ordered_cols.append(current)
        col_names.append("Current (A)")
        if "cycle" in metadata:
            ordered_cols.append(metadata.pop("cycle"))
            col_names.append("Cycle")
        if "step" in metadata:
            ordered_cols.append(metadata.pop("step"))
            col_names.append("Step")
        ordered_cols.append(exp_num)
        col_names.append("Exp")
        if "applied_potential" in metadata:
            ordered_cols.append(metadata.pop("applied_potential"))
            col_names.append("Applied potential (V)")
        elif "applied_current" in metadata:
            ordered_cols.append(metadata.pop("applied_current"))
            col_names.append("Applied current (A)")

        enriched_buffer = np.hstack(ordered_cols)

        # Write header
        if data_idx == 0:
            writer.writerow(col_names)

        # Write to CSV
        if factor < 2:
            for row in enriched_buffer:
                writer.writerow(row)
            return [], new_idx
        else:
            idx = 0
            while len(enriched_buffer) - idx >= factor:
                chunk = enriched_buffer[idx : idx + factor]
                avg = chunk.mean(axis=0)
                avg[0] = chunk[0, 0]
                writer.writerow(avg.tolist())
                idx += factor

            if flush_all and idx < len(enriched_buffer):
                chunk = enriched_buffer[idx:]
                avg = chunk.mean(axis=0)
                avg[0] = chunk[0, 0]
                writer.writerow(avg.tolist())
                idx = len(enriched_buffer)

            return buffer[idx:], new_idx - (len(enriched_buffer) - idx)
