"""Integrazione Nexus Astro: orologio astronomico per gruppi di luci.

Una voce di configurazione per gruppo: aggiungere, modificare, disattivare o
cancellare un gruppo usa l'interfaccia che Home Assistant offre gia' per
qualunque integrazione, invece di un elenco costruito a mano.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, PLATFORMS
from .controller import AstroController

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configura un gruppo."""
    controller = AstroController(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = controller

    await controller.async_setup()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_ricarica))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Scarica un gruppo, disarmando i suoi timer."""
    scaricato = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if scaricato:
        controller: AstroController = hass.data[DOMAIN].pop(entry.entry_id)
        await controller.async_shutdown()
    return scaricato


async def _async_ricarica(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
