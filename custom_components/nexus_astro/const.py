"""Costanti dell'integrazione Nexus Astro."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "nexus_astro"
MANUFACTURER = "Nexus-T"
MODEL = "Orologio astronomico"

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.SENSOR, Platform.SWITCH]

# --- Configurazione del gruppo ------------------------------------------------
CONF_NOME = "name"
CONF_GIORNI = "days"
CONF_SONDA = "dusk_sensor"
CONF_SPAZIATURA = "spacing"
CONF_RITENTATIVI = "retries"
CONF_EVENTI = "events"

# --- Campi di un evento -------------------------------------------------------
EV_ID = "id"
EV_TIPO = "type"
EV_OFFSET = "offset"
EV_ORARIO = "at"
EV_NON_PRIMA = "not_before"
EV_NON_DOPO = "not_after"
EV_AZIONE = "action"
EV_INTENSITA = "brightness"
EV_ENTITA = "entities"

# --- Tipi di evento -----------------------------------------------------------
TIPO_TRAMONTO = "sunset"
TIPO_ALBA = "sunrise"
TIPO_ORARIO = "time"
TIPO_SONDA_BUIO = "dusk_dark"
TIPO_SONDA_LUCE = "dusk_light"

TIPI = [TIPO_TRAMONTO, TIPO_ALBA, TIPO_ORARIO, TIPO_SONDA_BUIO, TIPO_SONDA_LUCE]
TIPI_SOLARI = [TIPO_TRAMONTO, TIPO_ALBA]
TIPI_SONDA = [TIPO_SONDA_BUIO, TIPO_SONDA_LUCE]

# --- Azioni -------------------------------------------------------------------
AZIONE_ACCENDI = "on"
AZIONE_SPEGNI = "off"
AZIONE_INTENSITA = "brightness"
AZIONI = [AZIONE_ACCENDI, AZIONE_SPEGNI, AZIONE_INTENSITA]

# --- Giorni -------------------------------------------------------------------
# now().weekday(): 0 = lunedi
GIORNI = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# --- Chiavi delle entita' -----------------------------------------------------
KEY_ABILITATO = "enabled"
KEY_RIALLINEA = "realign"
KEY_PROSSIMO = "next_event"
KEY_ULTIMO = "last_event"

# --- Valori predefiniti -------------------------------------------------------
DEFAULT_GIORNI = GIORNI
# Un secondo fra un comando e il successivo. Non e' prudenza generica: due
# entita' sullo stesso ricevitore radio comandate nello stesso istante fanno
# eseguire un comando solo, ed e' un difetto che si manifesta a intermittenza.
DEFAULT_SPAZIATURA = 1.0
DEFAULT_RITENTATIVI = 3
DEFAULT_INTENSITA = 50
DEFAULT_OFFSET = 0

# Quanto attendere la conferma di stato prima di ritentare.
ATTESA_CONFERMA = 3.0

# Finestra entro cui cercare l'ultimo evento passato quando si riallinea.
ORE_RIALLINEAMENTO = 24
