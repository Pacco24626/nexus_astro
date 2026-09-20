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
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

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


class UltimoEventoSensor(AstroEntity, SensorEntity, RestoreEntity):
    """Quando e' stato applicato l'ultimo evento.

    Il valore vive nel controller, che riparte vuoto a ogni avvio: senza
    ripristino l'ultimo evento spariva a ogni riavvio di Home Assistant, anche
    se le luci erano state comandate poche ore prima.
    """

    _attr_name = "Ultimo evento"
    _attr_icon = "mdi:history"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, controller: AstroController) -> None:
        super().__init__(controller, KEY_ULTIMO)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self.controller.ultimo_evento is not None:
            return
        ultimo = await self.async_get_last_state()
        if ultimo is None or ultimo.state in (None, "unknown", "unavailable"):
            return
        quando = dt_util.parse_datetime(ultimo.state)
        if quando is None:
            return
        self.controller.ultimo_evento = quando
        self.controller.ultimo_nome = ultimo.attributes.get("descrizione")

    @property
    def native_value(self) -> datetime | None:
        return self.controller.ultimo_evento

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"descrizione": self.controller.ultimo_nome}
