class SwitchingLossError(Exception):
    """Base exception for calculation failures."""


class InputValidationError(SwitchingLossError, ValueError):
    """An operating point or parasitic value is outside the supported domain."""


class DeviceNotFoundError(SwitchingLossError, KeyError):
    """Requested device id is not registered."""


class CalibrationError(SwitchingLossError, ValueError):
    """A calibration profile is missing, malformed, or incompatible."""


class SolverConvergenceError(SwitchingLossError, RuntimeError):
    """The transient solver did not reach a physical terminal state."""

