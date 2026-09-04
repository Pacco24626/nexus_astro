"""Button: riallineamento immediato."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, KEY_RIALLINEA
from .controller import AstroController
from .entity import AstroEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    controller: AstroController = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RiallineaButton(controller)])


class RiallineaButton(AstroEntity, ButtonEntity):
    """Porta subito le luci nello stato che la programmazione prevede adesso.

    Utile dopo un intervento manuale, o in fase di collaudo per verificare la
    programmazione senza aspettare il tramonto.
    """

    _attr_name = "Riallinea adesso"
    _attr_icon = "mdi:autorenew"

    def __init__(self, controller: AstroController) -> None:
        super().__init__(controller, KEY_RIALLINEA)

    async def async_press(self) -> None:
        await self.controller.async_riallinea()
