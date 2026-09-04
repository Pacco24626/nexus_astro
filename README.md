<img src="icons/logo.png" alt="Nexus Astro" width="360">

# Nexus Astro

Orologio astronomico per Home Assistant: programma gruppi di luci su alba, tramonto,
orari fissi e sonda crepuscolare, configurabile interamente dall'interfaccia.

È l'equivalente software dell'interruttore orario astronomico da quadro, con tre cose che
quello non ha: sa **rimettersi in pari dopo un riavvio**, **distanzia i comandi** e
**verifica che siano andati a segno**.

## Un gruppo per voce

Ogni gruppo è una voce dell'integrazione. Aggiungerne uno è *Aggiungi voce*, modificarlo
apre solo quel gruppo, disattivarlo per la stagione è l'interruttore che Home Assistant
mette su ogni voce. Nessun elenco da ridichiarare, nessun menu costruito a mano.

## Installazione

1. HACS → menu ⋮ → **Repository personalizzate**
2. URL `https://github.com/Pacco24626/nexus_astro`, categoria **Integration**
3. Installa, poi **riavvia Home Assistant**
4. **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → Nexus Astro**

Requisiti: Home Assistant 2024.12 o superiore.

## Configurazione del gruppo

| Campo | Default | Note |
|---|---|---|
| Nome | — | diventa il nome del dispositivo |
| Giorni attivi | tutti | selezione multipla |
| Sonda crepuscolare | nessuna | `binary_sensor` o `input_boolean`, facoltativa |
| Intervallo fra comandi | 1 s | vedi *Perché la spaziatura* |
| Tentativi per comando | 3 | verifica dello stato e ripetizione |

## Gli eventi

Un evento è una regola, e se ne possono mettere quanti se ne vuole:

| Campo | Valori |
|---|---|
| Quando | tramonto · alba · orario fisso · sonda buio · sonda luce |
| Scarto | da −120 a +120 minuti rispetto all'ora solare |
| Mai prima delle / Mai dopo le | tetti orari, facoltativi |
| Cosa fare | accendi · spegni · **imposta intensità** |
| Su quali entità | `light`, `switch`, `input_boolean`, quante servono |

I **tetti orari** sono la funzione che ogni orologio astronomico da quadro ha e che si
dimentica sempre quando lo si rifà in software: alle nostre latitudini il tramonto si
sposta di circa tre ore fra dicembre e giugno, e senza un limite d'estate le luci esterne
si accendono alle nove e un quarto di sera. Con *mai dopo le 20:30* il problema sparisce.

Gli eventi si modificano uno per uno da **Configura → Eventi**: si sceglie la riga
dall'elenco, si corregge, si torna indietro. Le modifiche vengono scritte quando confermi
con *Ho finito*.

## Le tre cose che lo distinguono da un'automazione

**Riallineamento.** Un'automazione a trigger è cieca ai riavvii: se Home Assistant riparte
alle 23, nessun evento scatta più e le luci restano come capita fino al giorno dopo.
Nexus Astro all'avvio calcola, **per ogni entità**, qual è l'ultimo evento passato che la
riguarda, e applica quello. Lo stesso fa il pulsante *Riallinea adesso*, utile dopo un
intervento manuale o in collaudo per verificare la programmazione senza aspettare il buio.

**Spaziatura fra i comandi.** Due entità che stanno sullo stesso ricevitore radio,
comandate nello stesso istante, ne eseguono una sola: il modulo riceve due trame a
millisecondi di distanza e ne lascia cadere una. Il guasto è intermittente e sembra un
comando perso a caso. Nexus Astro attende un intervallo configurabile fra un comando e il
successivo, così il problema non può presentarsi.

**Verifica e ritentativo.** Dopo ogni comando si attende che l'entità confermi lo stato
voluto; se non arriva entro tre secondi, si ripete. Nel log resta traccia di quale entità
ha avuto bisogno di più tentativi — che è il modo per accorgersi che un attuatore sta
peggiorando prima che smetta del tutto.

## Entità generate

| Entità | Descrizione |
|---|---|
| `switch.<gruppo>_abilitato` | Spento, il gruppo non comanda nulla |
| `button.<gruppo>_riallinea_adesso` | Porta subito le luci nello stato previsto |
| `sensor.<gruppo>_prossimo_evento` | Timestamp, con la scaletta della giornata negli attributi |
| `sensor.<gruppo>_ultimo_evento` | Timestamp dell'ultimo evento applicato |

La scaletta negli attributi del sensore è l'anteprima della giornata: ora per ora, cosa
verrà fatto e su cosa, con l'indicazione di ciò che è già passato.

## Sonda crepuscolare

Facoltativa, e non alternativa all'ora solare: un gruppo può avere eventi al tramonto
**e** eventi da sonda. I tetti orari valgono anche per la sonda, il che serve più di
quanto sembri — una fotocellula coperta da una tenda o sporcata dalla pioggia può
scattare a mezzogiorno.

## Licenza

Apache 2.0 — Copyright 2026 Automatic Systems. Vedi [LICENSE](LICENSE).
