from pydantic import BaseModel
from typing import List, Optional

# --- Potentiostatic waveform parameters ---


class ConstantWaveformParams(BaseModel):
    potential: float
    duration: float


class PotentialStepsParams(BaseModel):
    potentials: List[float]
    step_duration: float


class LinearSweepParams(BaseModel):
    start: float
    end: float
    scan_rate: float


class CyclicVoltammetryParams(BaseModel):
    start: float
    vertex1: float
    vertex2: float
    end: float
    scan_rate: float
    cycles: int


# --- Galvanostatic waveform parameters ---


class SinglePointParams(BaseModel):
    current: float
    duration: float


class CurrentStepsParams(BaseModel):
    currents: List[float]
    step_duration: float


class LinearGalvanostaticSweepParams(BaseModel):
    start: float
    end: float
    num_steps: int
    step_duration: float


class CyclicGalvanostaticParams(BaseModel):
    start: float
    vertex1: float
    vertex2: float
    end: float
    num_steps: int
    step_duration: float
    cycles: int


# --- OCP waveform parameters ---
class OCPParams(BaseModel):
    duration: float

# --- Capacitance (Cdl) parameters ---
class CapacitanceParams(BaseModel):
    vertex_a: float
    vertex_b: float
    scan_rates: List[float]
    rest_time: float = 0.0
    start: Optional[float] = None
    end: Optional[float] = None
