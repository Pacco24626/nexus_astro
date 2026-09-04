"""Sensori: prossimo evento e ultimo eseguito.

Il sensore del prossimo evento porta negli attributi la scaletta della
giornata: e' l'anteprima che serve in fase di collaudo per verificare la
programmazione senza aspettare il tramonto, e la base per una futura card.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, KEY_PROSSIMO, KEY_ULTIMO
from .controller import AstroController
from .entity import AstroEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    controller: AstroController = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ProssimoEventoSensor(controller), UltimoEventoSensor(controller)])


class ProssimoEventoSensor(AstroEntity, SensorEntity):
    """Quando scatta il prossimo evento a orario."""

    _attr_name = "Prossimo evento"
    _attr_icon = "mdi:clock-star-four-points-outline"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, controller: AstroController) -> None:
        super().__init__(controller, KEY_PROSSIMO)

    @property
    def native_value(self) -> datetime | None:
        return self.controller.prossimo_orario

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        controller = self.controller
        return {
            "descrizione": controller.prossima_descrizione,
            "giorni_attivi": controller.giorni,
            "sonda": controller.sonda,
            "spaziatura_s": controller.spaziatura,
            "ritentativi": controller.ritentativi,
            "scaletta_oggi": controller.scaletta_oggi(),
        }


class UltimoEventoSensor(AstroEntity, SensorEntity):
    """Quando e' stato applicato l'ultimo evento."""

    _attr_name = "Ultimo evento"
    _attr_icon = "mdi:history"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, controller: AstroController) -> None:
        super().__init__(controller, KEY_ULTIMO)

    @property
    def native_value(self) -> datetime | None:
        return self.controller.ultimo_evento

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"descrizione": self.controller.ultimo_nome}
