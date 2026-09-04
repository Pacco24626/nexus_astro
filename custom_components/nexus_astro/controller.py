"""Controller di un gruppo dell'orologio astronomico.

Tre idee reggono tutto il file:

1. Un evento e' una *regola*, non un innesco: da essa si calcola a che ora
   deve scattare oggi, ieri e domani. Questo permette il riallineamento.

2. Il riallineamento e' per entita', non per gruppo: all'avvio, per ogni
   entita' si cerca l'ultimo evento passato che la riguarda e si applica
   quello. Senza, un riavvio a mezzanotte lascia le luci come capita fino
   al giorno dopo.

3. I comandi vengono distanziati e verificati. Due entita' sullo stesso
   ricevitore radio comandate nello stesso istante fanno eseguire un comando
   solo: il difetto si manifesta a intermittenza ed e' inspiegabile finche'
   non lo si e' visto.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util import dt as dt_util

from .const import (
    ATTESA_CONFERMA,
    AZIONE_ACCENDI,
    AZIONE_INTENSITA,
    AZIONE_SPEGNI,
    CONF_EVENTI,
    CONF_GIORNI,
    CONF_NOME,
    CONF_RITENTATIVI,
    CONF_SONDA,
    CONF_SPAZIATURA,
    DEFAULT_GIORNI,
    DEFAULT_RITENTATIVI,
    DEFAULT_SPAZIATURA,
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
    ORE_RIALLINEAMENTO,
    TIPI_SONDA,
    TIPO_ALBA,
    TIPO_ORARIO,
    TIPO_SONDA_BUIO,
    TIPO_SONDA_LUCE,
    TIPO_TRAMONTO,
)

_LOGGER = logging.getLogger(__name__)


def _ora(testo: str | None) -> time | None:
    """Converte "HH:MM" o "HH:MM:SS" in un orario."""
    if not testo:
        return None
    parti = str(testo).split(":")
    try:
        return time(int(parti[0]), int(parti[1]), int(parti[2]) if len(parti) > 2 else 0)
    except (ValueError, IndexError):
        return None


@dataclass
class Evento:
    """Una regola oraria del gruppo."""

    id: str
    tipo: str
    azione: str
    entita: list[str]
    offset: int = 0
    orario: str | None = None
    non_prima: str | None = None
    non_dopo: str | None = None
    intensita: int | None = None

    @staticmethod
    def da_config(dati: dict[str, Any]) -> "Evento":
        return Evento(
            id=dati[EV_ID],
            tipo=dati[EV_TIPO],
            azione=dati[EV_AZIONE],
            entita=list(dati.get(EV_ENTITA) or []),
            offset=int(dati.get(EV_OFFSET) or 0),
            orario=dati.get(EV_ORARIO),
            non_prima=dati.get(EV_NON_PRIMA),
            non_dopo=dati.get(EV_NON_DOPO),
            intensita=dati.get(EV_INTENSITA),
        )

    @property
    def da_sonda(self) -> bool:
        return self.tipo in TIPI_SONDA


class AstroController:
    """Programma e applica gli eventi di un gruppo."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        cfg = {**entry.data, **entry.options}
        self.nome: str = cfg.get(CONF_NOME, entry.title)
        self.giorni: list[str] = list(cfg.get(CONF_GIORNI) or DEFAULT_GIORNI)
        self.sonda: str | None = cfg.get(CONF_SONDA)
        self.spaziatura: float = float(cfg.get(CONF_SPAZIATURA, DEFAULT_SPAZIATURA))
        self.ritentativi: int = int(cfg.get(CONF_RITENTATIVI, DEFAULT_RITENTATIVI))
        self.eventi: list[Evento] = [
            Evento.da_config(e) for e in (cfg.get(CONF_EVENTI) or [])
        ]

        self.abilitato: bool = True
        self.ultimo_evento: datetime | None = None
        self.ultimo_nome: str | None = None

        self._unsub: list[CALLBACK_TYPE] = []
        self._programmati: list[CALLBACK_TYPE] = []
        self._listeners: list[CALLBACK_TYPE] = []
        self._prossimo: tuple[datetime, Evento] | None = None

    # -------------------------------------------------------------------------
    # Ciclo di vita
    # -------------------------------------------------------------------------
    async def async_setup(self) -> None:
        # Ricalcolo giornaliero: le ore solari cambiano ogni giorno.
        self._unsub.append(
            async_track_time_change(self.hass, self._async_nuovo_giorno, hour=0, minute=0, second=30)
        )

        if self.sonda:
            self._unsub.append(
                async_track_state_change_event(self.hass, [self.sonda], self._async_sonda)
            )

        if self.hass.is_running:
            await self._async_avvia()
        else:
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self._async_avvio_ritardato)

    async def _async_avvio_ritardato(self, _event: Event) -> None:
        await self._async_avvia()

    async def _async_avvia(self) -> None:
        self.pianifica()
        await self.async_riallinea()

    async def async_shutdown(self) -> None:
        for annulla in self._unsub + self._programmati:
            annulla()
        self._unsub.clear()
        self._programmati.clear()

    @callback
    def async_add_listener(self, update: CALLBACK_TYPE) -> CALLBACK_TYPE:
        self._listeners.append(update)

        @callback
        def _rimuovi() -> None:
            self._listeners.remove(update)

        return _rimuovi

    @callback
    def notify(self) -> None:
        for update in list(self._listeners):
            update()

    @callback
    def set_abilitato(self, valore: bool) -> None:
        self.abilitato = valore
        self.pianifica()

    # -------------------------------------------------------------------------
    # Calcolo degli orari
    # -------------------------------------------------------------------------
    def _giorno_attivo(self, giorno: date) -> bool:
        return GIORNI[giorno.weekday()] in self.giorni

    def orario_di(self, evento: Evento, giorno: date) -> datetime | None:
        """A che ora scatta questo evento in quel giorno, o None."""
        if evento.da_sonda:
            return None  # dipende dalla sonda, non dall'orologio

        if evento.tipo in (TIPO_TRAMONTO, TIPO_ALBA):
            chiave = "sunset" if evento.tipo == TIPO_TRAMONTO else "sunrise"
            base = get_astral_event_date(self.hass, chiave, giorno)
            if base is None:
                return None
            quando = dt_util.as_local(base) + timedelta(minutes=evento.offset)
        elif evento.tipo == TIPO_ORARIO:
            ora = _ora(evento.orario)
            if ora is None:
                return None
            quando = dt_util.start_of_local_day(giorno).replace(
                hour=ora.hour, minute=ora.minute, second=ora.second
            )
        else:
            return None

        return self._applica_limiti(quando, evento, giorno)

    def _applica_limiti(self, quando: datetime, evento: Evento, giorno: date) -> datetime:
        """Tetti orari.

        Fra dicembre e giugno il tramonto si sposta di ore: senza un limite,
        d'estate le luci esterne si accenderebbero alle nove e un quarto.
        """
        inizio = dt_util.start_of_local_day(giorno)

        prima = _ora(evento.non_prima)
        if prima is not None:
            minimo = inizio.replace(hour=prima.hour, minute=prima.minute, second=prima.second)
            quando = max(quando, minimo)

        dopo = _ora(evento.non_dopo)
        if dopo is not None:
            massimo = inizio.replace(hour=dopo.hour, minute=dopo.minute, second=dopo.second)
            quando = min(quando, massimo)

        return quando

    def scaletta(self, giorno: date | None = None) -> list[tuple[datetime, Evento]]:
        """Gli eventi a orario di un giorno, ordinati. Utile anche alla card."""
        giorno = giorno or dt_util.now().date()
        if not self._giorno_attivo(giorno):
            return []

        righe = []
        for evento in self.eventi:
            quando = self.orario_di(evento, giorno)
            if quando is not None:
                righe.append((quando, evento))
        return sorted(righe, key=lambda r: r[0])

    # -------------------------------------------------------------------------
    # Pianificazione
    # -------------------------------------------------------------------------
    @callback
    def pianifica(self) -> None:
        """Riarma i timer di oggi e di domani."""
        for annulla in self._programmati:
            annulla()
        self._programmati.clear()
        self._prossimo = None

        if not self.abilitato:
            self.notify()
            return

        adesso = dt_util.now()
        prossimi: list[tuple[datetime, Evento]] = []
        for scarto in (0, 1):
            giorno = (adesso + timedelta(days=scarto)).date()
            prossimi += [r for r in self.scaletta(giorno) if r[0] > adesso]

        prossimi.sort(key=lambda r: r[0])
        for quando, evento in prossimi[:12]:
            self._programmati.append(
                async_track_point_in_time(
                    self.hass, self._crea_scatto(evento), quando
                )
            )

        self._prossimo = prossimi[0] if prossimi else None
        self.notify()

    def _crea_scatto(self, evento: Evento):
        async def _scatta(_now: datetime) -> None:
            await self.async_esegui(evento)
            # Dopo ogni evento si ripianifica: cosi' la lista resta corta e
            # il passaggio di mezzanotte non lascia buchi.
            self.pianifica()

        return _scatta

    async def _async_nuovo_giorno(self, _now: datetime) -> None:
        self.pianifica()

    # -------------------------------------------------------------------------
    # Sonda crepuscolare
    # -------------------------------------------------------------------------
    async def _async_sonda(self, event: Event) -> None:
        nuovo = event.data.get("new_state")
        vecchio = event.data.get("old_state")
        if nuovo is None or vecchio is None:
            return
        if nuovo.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        if nuovo.state == vecchio.state:
            return

        cercato = TIPO_SONDA_BUIO if nuovo.state == STATE_ON else TIPO_SONDA_LUCE
        adesso = dt_util.now()

        for evento in self.eventi:
            if evento.tipo != cercato:
                continue
            if not self.abilitato or not self._giorno_attivo(adesso.date()):
                continue
            # I limiti orari valgono anche qui: una sonda coperta da una
            # tenda puo' scattare a mezzogiorno.
            if not self._entro_limiti(adesso, evento):
                _LOGGER.debug("%s: evento da sonda fuori dai limiti orari", self.nome)
                continue
            await self.async_esegui(evento)

    def _entro_limiti(self, adesso: datetime, evento: Evento) -> bool:
        prima = _ora(evento.non_prima)
        dopo = _ora(evento.non_dopo)
        if prima is not None and adesso.time() < prima:
            return False
        if dopo is not None and adesso.time() > dopo:
            return False
        return True

    # -------------------------------------------------------------------------
    # Esecuzione
    # -------------------------------------------------------------------------
    async def async_esegui(self, evento: Evento) -> None:
        if not self.abilitato:
            return

        _LOGGER.debug("%s: eseguo %s su %s", self.nome, evento.azione, evento.entita)
        for indice, entity_id in enumerate(evento.entita):
            if indice:
                # Il respiro fra un comando e il successivo: e' cio' che
                # evita che due canali dello stesso ricevitore radio si
                # annullino a vicenda.
                await asyncio.sleep(self.spaziatura)
            await self._async_comanda(entity_id, evento)

        self.ultimo_evento = dt_util.now()
        self.ultimo_nome = self.descrizione(evento)
        self.notify()

    async def _async_comanda(self, entity_id: str, evento: Evento) -> None:
        """Comanda e verifica, con ritentativo."""
        for tentativo in range(1, max(1, self.ritentativi) + 1):
            await self._async_chiama(entity_id, evento)

            if await self._async_conferma(entity_id, evento):
                if tentativo > 1:
                    _LOGGER.info(
                        "%s: %s ha risposto al tentativo %s", self.nome, entity_id, tentativo
                    )
                return

        _LOGGER.warning(
            "%s: %s non ha confermato dopo %s tentativi",
            self.nome,
            entity_id,
            self.ritentativi,
        )

    async def _async_chiama(self, entity_id: str, evento: Evento) -> None:
        dominio = entity_id.split(".", 1)[0]
        try:
            if evento.azione == AZIONE_SPEGNI:
                await self.hass.services.async_call(
                    "homeassistant", "turn_off", {"entity_id": entity_id}, blocking=True
                )
            elif evento.azione == AZIONE_INTENSITA and dominio == "light":
                await self.hass.services.async_call(
                    "light",
                    "turn_on",
                    {"entity_id": entity_id, "brightness_pct": evento.intensita or 0},
                    blocking=True,
                )
            else:
                await self.hass.services.async_call(
                    "homeassistant", "turn_on", {"entity_id": entity_id}, blocking=True
                )
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("%s: comando su %s fallito: %s", self.nome, entity_id, err)

    async def _async_conferma(self, entity_id: str, evento: Evento) -> bool:
        """Attende che l'entita' riporti lo stato voluto."""
        atteso_acceso = evento.azione != AZIONE_SPEGNI
        scadenza = self.hass.loop.time() + ATTESA_CONFERMA

        while self.hass.loop.time() < scadenza:
            stato = self.hass.states.get(entity_id)
            if stato is not None and stato.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                if (stato.state == STATE_ON) == atteso_acceso:
                    return True
            await asyncio.sleep(0.5)
        return False

    # -------------------------------------------------------------------------
    # Riallineamento
    # -------------------------------------------------------------------------
    async def async_riallinea(self) -> None:
        """Porta ogni entita' nello stato che la programmazione prevede adesso.

        Si guarda indietro fino a 24 ore e, per ogni entita', si applica
        l'ultimo evento passato che la riguarda. Gli eventi da sonda non
        entrano nel conto: non hanno un orario da cui dedurre nulla.
        """
        if not self.abilitato or not self.eventi:
            return

        adesso = dt_util.now()
        passati: list[tuple[datetime, Evento]] = []
        for scarto in (-1, 0):
            giorno = (adesso + timedelta(days=scarto)).date()
            passati += [
                r for r in self.scaletta(giorno)
                if r[0] <= adesso and (adesso - r[0]) <= timedelta(hours=ORE_RIALLINEAMENTO)
            ]

        if not passati:
            _LOGGER.debug("%s: nessun evento passato da riallineare", self.nome)
            return

        passati.sort(key=lambda r: r[0])

        # L'ultimo evento che tocca ciascuna entita' vince.
        per_entita: dict[str, Evento] = {}
        for _quando, evento in passati:
            for entity_id in evento.entita:
                per_entita[entity_id] = evento

        _LOGGER.info("%s: riallineo %s entita'", self.nome, len(per_entita))
        primo = True
        for entity_id, evento in per_entita.items():
            if not primo:
                await asyncio.sleep(self.spaziatura)
            primo = False
            await self._async_comanda(entity_id, evento)

        self.notify()

    # -------------------------------------------------------------------------
    # Descrizioni, per entita' e card
    # -------------------------------------------------------------------------
    def descrizione(self, evento: Evento) -> str:
        quando = {
            TIPO_TRAMONTO: "tramonto",
            TIPO_ALBA: "alba",
            TIPO_ORARIO: evento.orario or "orario",
            TIPO_SONDA_BUIO: "sonda: buio",
            TIPO_SONDA_LUCE: "sonda: luce",
        }.get(evento.tipo, evento.tipo)

        if evento.tipo in (TIPO_TRAMONTO, TIPO_ALBA) and evento.offset:
            quando = f"{quando} {evento.offset:+d} min"

        azione = {
            AZIONE_ACCENDI: "accendi",
            AZIONE_SPEGNI: "spegni",
            AZIONE_INTENSITA: f"intensita' {evento.intensita}%",
        }.get(evento.azione, evento.azione)

        return f"{quando} → {azione} ({len(evento.entita)})"

    @property
    def prossimo_orario(self) -> datetime | None:
        return self._prossimo[0] if self._prossimo else None

    @property
    def prossima_descrizione(self) -> str | None:
        return self.descrizione(self._prossimo[1]) if self._prossimo else None

    def scaletta_oggi(self) -> list[dict[str, Any]]:
        righe = [
            {
                "ora": quando.isoformat(),
                "descrizione": self.descrizione(evento),
                "azione": evento.azione,
                "entita": evento.entita,
                "passato": quando <= dt_util.now(),
            }
            for quando, evento in self.scaletta()
        ]
        righe += [
            {
                "ora": None,
                "descrizione": self.descrizione(evento),
                "azione": evento.azione,
                "entita": evento.entita,
                "passato": False,
            }
            for evento in self.eventi
            if evento.da_sonda
        ]
        return righe
