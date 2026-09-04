"""Config flow: un gruppo per voce, con editor degli eventi a elenco.

L'elenco degli eventi non si ridichiara da capo: si sceglie la riga da
toccare e si modifica quella. E' la differenza fra una configurazione che si
puo' correggere fra sei mesi e una che si rifa' ogni volta.
"""

from __future__ import annotations

import uuid
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    AZIONE_ACCENDI,
    AZIONE_INTENSITA,
    AZIONI,
    CONF_EVENTI,
    CONF_GIORNI,
    CONF_NOME,
    CONF_RITENTATIVI,
    CONF_SONDA,
    CONF_SPAZIATURA,
    DEFAULT_GIORNI,
    DEFAULT_INTENSITA,
    DEFAULT_RITENTATIVI,
    DEFAULT_SPAZIATURA,
    DOMAIN,
    EV_AZIONE,
    EV_ENTITA,
    EV_ID,
    EV_INTENSITA,
    EV_NON_DOPO,
    EV_NON_PRIMA,
    EV_OFFSET,
    EV_ORARIO,
    EV_TIPO,
    GIORNI,
    TIPI,
    TIPO_ORARIO,
    TIPO_TRAMONTO,
)

SCELTA_AGGIUNGI = "__aggiungi__"
SCELTA_FINE = "__fine__"


def _schema_gruppo(defaults: dict[str, Any], con_nome: bool) -> vol.Schema:
    campi: dict[Any, Any] = {}
    if con_nome:
        campi[vol.Required(CONF_NOME, default=defaults.get(CONF_NOME, "Luci esterne"))] = str

    campi.update(
        {
            vol.Required(
                CONF_GIORNI, default=defaults.get(CONF_GIORNI, list(DEFAULT_GIORNI))
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=GIORNI,
                    multiple=True,
                    translation_key="giorni",
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Optional(
                CONF_SONDA, description={"suggested_value": defaults.get(CONF_SONDA)}
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["binary_sensor", "input_boolean"])
            ),
            vol.Required(
                CONF_SPAZIATURA, default=defaults.get(CONF_SPAZIATURA, DEFAULT_SPAZIATURA)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=30, step=0.5, unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_RITENTATIVI, default=defaults.get(CONF_RITENTATIVI, DEFAULT_RITENTATIVI)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=10, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
        }
    )
    return vol.Schema(campi)


def _schema_evento(defaults: dict[str, Any], con_rimozione: bool = False) -> vol.Schema:
    campi: dict[Any, Any] = {
        vol.Required(EV_TIPO, default=defaults.get(EV_TIPO, TIPO_TRAMONTO)): (
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=TIPI, translation_key="tipo_evento",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        ),
        vol.Optional(EV_OFFSET, default=defaults.get(EV_OFFSET, 0)): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=-120, max=120, step=5, unit_of_measurement="min",
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        vol.Optional(
            EV_ORARIO, description={"suggested_value": defaults.get(EV_ORARIO)}
        ): selector.TimeSelector(),
        vol.Optional(
            EV_NON_PRIMA, description={"suggested_value": defaults.get(EV_NON_PRIMA)}
        ): selector.TimeSelector(),
        vol.Optional(
            EV_NON_DOPO, description={"suggested_value": defaults.get(EV_NON_DOPO)}
        ): selector.TimeSelector(),
        vol.Required(EV_AZIONE, default=defaults.get(EV_AZIONE, AZIONE_ACCENDI)): (
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=AZIONI, translation_key="azione",
                    mode=selector.SelectSelectorMode.LIST,
                )
            )
        ),
        vol.Optional(
            EV_INTENSITA, default=defaults.get(EV_INTENSITA, DEFAULT_INTENSITA)
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=100, step=1, unit_of_measurement="%",
                mode=selector.NumberSelectorMode.SLIDER,
            )
        ),
        vol.Required(
            EV_ENTITA, default=defaults.get(EV_ENTITA, [])
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=["light", "switch", "input_boolean"], multiple=True
            )
        ),
    }
    if con_rimozione:
        campi[vol.Optional("rimuovi", default=False)] = bool
    return vol.Schema(campi)


def _valida_evento(dati: dict[str, Any]) -> dict[str, str]:
    if dati[EV_TIPO] == TIPO_ORARIO and not dati.get(EV_ORARIO):
        return {EV_ORARIO: "orario_mancante"}
    if not dati.get(EV_ENTITA):
        return {EV_ENTITA: "entita_mancanti"}
    return {}


def _normalizza_evento(dati: dict[str, Any], id_esistente: str | None = None) -> dict[str, Any]:
    evento = {
        EV_ID: id_esistente or uuid.uuid4().hex[:8],
        EV_TIPO: dati[EV_TIPO],
        EV_AZIONE: dati[EV_AZIONE],
        EV_ENTITA: list(dati.get(EV_ENTITA) or []),
        EV_OFFSET: int(dati.get(EV_OFFSET) or 0),
    }
    for chiave in (EV_ORARIO, EV_NON_PRIMA, EV_NON_DOPO):
        if dati.get(chiave):
            evento[chiave] = dati[chiave]
    if dati[EV_AZIONE] == AZIONE_INTENSITA:
        evento[EV_INTENSITA] = int(dati.get(EV_INTENSITA) or DEFAULT_INTENSITA)
    return evento


def _etichetta(evento: dict[str, Any]) -> str:
    quando = {
        "sunset": "Tramonto",
        "sunrise": "Alba",
        "time": evento.get(EV_ORARIO, "orario"),
        "dusk_dark": "Sonda: buio",
        "dusk_light": "Sonda: luce",
    }.get(evento[EV_TIPO], evento[EV_TIPO])

    offset = evento.get(EV_OFFSET) or 0
    if offset and evento[EV_TIPO] in ("sunset", "sunrise"):
        quando = f"{quando} {offset:+d}min"

    azione = {
        "on": "accendi",
        "off": "spegni",
        "brightness": f"{evento.get(EV_INTENSITA, '')}%",
    }.get(evento[EV_AZIONE], evento[EV_AZIONE])

    return f"{quando} → {azione} · {len(evento.get(EV_ENTITA) or [])} entità"


class NexusAstroConfigFlow(ConfigFlow, domain=DOMAIN):
    """Creazione di un gruppo."""

    VERSION = 1

    def __init__(self) -> None:
        self._dati: dict[str, Any] = {}
        self._eventi: list[dict[str, Any]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._async_abort_entries_match({CONF_NOME: user_input[CONF_NOME]})
            self._dati = dict(user_input)
            self._dati[CONF_SPAZIATURA] = float(user_input[CONF_SPAZIATURA])
            self._dati[CONF_RITENTATIVI] = int(user_input[CONF_RITENTATIVI])
            return await self.async_step_evento()

        return self.async_show_form(step_id="user", data_schema=_schema_gruppo({}, True))

    async def async_step_evento(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _valida_evento(user_input)
            if not errors:
                self._eventi.append(_normalizza_evento(user_input))
                if user_input.pop("ancora", False):
                    return await self.async_step_evento()
                self._dati[CONF_EVENTI] = self._eventi
                return self.async_create_entry(title=self._dati[CONF_NOME], data=self._dati)

        schema = _schema_evento(user_input or {}).extend(
            {vol.Optional("ancora", default=True): bool}
        )
        return self.async_show_form(
            step_id="evento",
            data_schema=schema,
            errors=errors,
            description_placeholders={"numero": str(len(self._eventi) + 1)},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NexusAstroOptionsFlow()


class NexusAstroOptionsFlow(OptionsFlow):
    """Modifica del gruppo: impostazioni e singoli eventi."""

    def __init__(self) -> None:
        self._in_modifica: str | None = None
        # Copia di lavoro: le modifiche agli eventi si accumulano qui e
        # vengono scritte solo alla conferma finale. Cosi' la voce non viene
        # ricaricata a ogni singola correzione, e chi chiude il dialogo a
        # meta' non lascia una configurazione monca.
        self._lavoro: list[dict[str, Any]] | None = None

    @property
    def _corrente(self) -> dict[str, Any]:
        return {**self.config_entry.data, **self.config_entry.options}

    @property
    def _eventi(self) -> list[dict[str, Any]]:
        if self._lavoro is None:
            self._lavoro = [dict(e) for e in (self._corrente.get(CONF_EVENTI) or [])]
        return self._lavoro

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="init", menu_options=["generale", "eventi"])

    # --- impostazioni del gruppo ---------------------------------------------
    async def async_step_generale(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            dati = dict(user_input)
            dati[CONF_SPAZIATURA] = float(dati[CONF_SPAZIATURA])
            dati[CONF_RITENTATIVI] = int(dati[CONF_RITENTATIVI])
            if not dati.get(CONF_SONDA):
                dati[CONF_SONDA] = None
            return self._salva(dati)

        return self.async_show_form(
            step_id="generale", data_schema=_schema_gruppo(self._corrente, False)
        )

    # --- elenco degli eventi --------------------------------------------------
    async def async_step_eventi(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            scelta = user_input["scelta"]
            if scelta == SCELTA_FINE:
                return self._salva({CONF_EVENTI: self._eventi})
            if scelta == SCELTA_AGGIUNGI:
                self._in_modifica = None
                return await self.async_step_evento()
            self._in_modifica = scelta
            return await self.async_step_evento()

        opzioni = [
            selector.SelectOptionDict(value=e[EV_ID], label=_etichetta(e))
            for e in self._eventi
        ]
        opzioni.append(
            selector.SelectOptionDict(value=SCELTA_AGGIUNGI, label="➕ Aggiungi un evento")
        )
        opzioni.append(
            selector.SelectOptionDict(value=SCELTA_FINE, label="✓ Ho finito")
        )

        return self.async_show_form(
            step_id="eventi",
            data_schema=vol.Schema(
                {
                    vol.Required("scelta", default=SCELTA_AGGIUNGI): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=opzioni, mode=selector.SelectSelectorMode.LIST
                        )
                    )
                }
            ),
            description_placeholders={"quanti": str(len(self._eventi))},
        )

    # --- singolo evento -------------------------------------------------------
    async def async_step_evento(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        eventi = self._eventi
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input.pop("rimuovi", False) and self._in_modifica:
                self._lavoro = [e for e in eventi if e[EV_ID] != self._in_modifica]
                self._in_modifica = None
                return await self.async_step_eventi()

            errors = _valida_evento(user_input)
            if not errors:
                nuovo = _normalizza_evento(user_input, self._in_modifica)
                if self._in_modifica:
                    self._lavoro = [
                        nuovo if e[EV_ID] == self._in_modifica else e for e in eventi
                    ]
                else:
                    self._lavoro = eventi + [nuovo]
                self._in_modifica = None
                return await self.async_step_eventi()

        precedente: dict[str, Any] = {}
        if self._in_modifica:
            precedente = next((e for e in eventi if e[EV_ID] == self._in_modifica), {})

        return self.async_show_form(
            step_id="evento",
            data_schema=_schema_evento(user_input or precedente, con_rimozione=bool(self._in_modifica)),
            errors=errors,
        )

    # -------------------------------------------------------------------------
    def _salva(self, modifiche: dict[str, Any]) -> ConfigFlowResult:
        """Le opzioni contengono sempre la configurazione completa."""
        unito = {**self._corrente, **modifiche}
        unito.pop(CONF_NOME, None)
        return self.async_create_entry(title="", data=unito)
