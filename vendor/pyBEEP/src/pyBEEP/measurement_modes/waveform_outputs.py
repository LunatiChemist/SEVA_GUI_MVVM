from pydantic import BaseModel, Field
from typing import Annotated
import numpy as np

NDArrayFloat = Annotated[np.ndarray, "float32"]
NDArrayInt = Annotated[np.ndarray, "int32"]


class BaseOuput(BaseModel):
    time: NDArrayFloat = Field(..., description="Time (s), shape (N,)")

    class Config:
        arbitrary_types_allowed = True


class PotenOutput(BaseOuput):
    applied_potential: NDArrayFloat = Field(
        ..., description="Applied Potential (V), shape (N,)"
    )


class SteppedPotenOutput(PotenOutput):
    step: NDArrayInt = Field(..., description="Step, shape (N,)")


class CyclicPotenOutput(PotenOutput):
    cycle: NDArrayInt = Field(..., description="Cycle, shape (N,)")


class GalvanoOutput(BaseOuput):
    applied_current: NDArrayFloat = Field(
        ..., description="Applied Current (A), shape (N,)"
    )
    current_steps: NDArrayFloat = Field(
        ..., description="Current steps (A), shape (S,)"
    )
    duration_steps: NDArrayFloat = Field(
        ..., description="Duration of each step (s), shape(S,)"
    )
    length_steps: NDArrayInt = Field(
        ..., description="Length (in points) of each step, shape(S,)"
    )


class CyclicGalvanoOutput(GalvanoOutput):
    cycle: NDArrayInt = Field(..., description="Cycle, shape(N,)")
