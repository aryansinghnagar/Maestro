import pytest
from unittest.mock import MagicMock
from gesture_controller.core.capabilities import Tier, CapabilitySet
from gesture_controller.core.event_bus import EventBus
from gesture_controller.core.tier_manager import TierManager


@pytest.fixture
def mock_config_manager() -> MagicMock:
    cm = MagicMock()
    cm.get_config.return_value = {
        "performance": {
            "tier": "auto",
            "override_capabilities": {},
        }
    }
    return cm


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


def test_tier_manager_initial_state(mock_config_manager: MagicMock, event_bus: EventBus) -> None:
    tm = TierManager(mock_config_manager, event_bus)
    assert isinstance(tm.active_tier, Tier)
    assert isinstance(tm.capabilities, CapabilitySet)
    assert tm.hardware_profile is not None


def test_tier_manager_manual_override(mock_config_manager: MagicMock, event_bus: EventBus) -> None:
    mock_config_manager.get_config.return_value = {
        "performance": {
            "tier": Tier.ULTRA.value,
            "override_capabilities": {},
        }
    }
    tm = TierManager(mock_config_manager, event_bus)
    assert tm.active_tier == Tier.ULTRA


def test_tier_manager_reevaluate(mock_config_manager: MagicMock, event_bus: EventBus) -> None:
    tm = TierManager(mock_config_manager, event_bus)
    new_tier = tm.reevaluate(force_immediate=True)
    assert isinstance(new_tier, Tier)


def test_tier_manager_set_override(mock_config_manager: MagicMock, event_bus: EventBus) -> None:
    tm = TierManager(mock_config_manager, event_bus)
    tm.set_manual_override(Tier.MINIMAL.value)
    assert tm.active_tier == Tier.MINIMAL

    tm.set_manual_override(None)
    assert isinstance(tm.active_tier, Tier)
