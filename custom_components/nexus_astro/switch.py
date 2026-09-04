"""Switch: abilitazione del gruppo."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, KEY_ABILITATO
from .controller import AstroController
from .entity import AstroEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    controller: AstroController = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AbilitazioneSwitch(controller)])


class AbilitazioneSwitch(AstroEntity, SwitchEntity, RestoreEntity):
    """Spento, il gruppo non comanda piu' nulla.

    Serve per la vacanza, per il cantiere, o per escludere una zona senza
    disfare la programmazione.
    """

    _attr_name = "Abilitato"
    _attr_icon = "mdi:sun-clock"

    def __init__(self, controller: AstroController) -> None:
        super().__init__(controller, KEY_ABILITATO)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (ultimo := await self.async_get_last_state()) is not None:
            self.controller.set_abilitato(ultimo.state == "on")

    @property
    def is_on(self) -> bool:
        return self.controller.abilitato

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.controller.set_abilitato(True)
        # Riaccendendo il gruppo si rimette subito tutto nello stato previsto,
        # invece di aspettare il prossimo evento.
        await self.controller.async_riallinea()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.controller.set_abilitato(False)
