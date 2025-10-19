from seva.adapters.relay_mock import RelayMock
from seva.usecases.set_electrode_mode import SetElectrodeMode
from seva.usecases.test_relay import TestRelay


def test_test_relay_returns_true():
    uc = TestRelay(relay=RelayMock())
    assert uc("127.0.0.1", 9000) is True


def test_set_electrode_mode_noop():
    uc = SetElectrodeMode(relay=RelayMock())
    uc("3E")  # should not raise

