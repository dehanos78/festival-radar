# Festival Radar

Vik's shortlist van intieme/underground festivals — gesorteerd op reisafstand, met live
ticket-tracking. Statische single-page site (GitHub Pages) met een gedeelde events-database
(Firebase Firestore) waar vrienden zelf evenementen aan kunnen toevoegen.

- **Live site:** <https://dehanos78.github.io/festival-radar/>
- **Toevoegen:** knop **+ Evenement** rechtsboven → verschijnt live voor iedereen
- **Agenda (ICS):** abonneer op <https://dehanos78.github.io/festival-radar/festival-radar.ics>

## Functies

- **Overzicht** — curated shortlist per zone (voor de deur / roadtrip / bucketlist)
- **Zoeken & filteren** — zoekbalk + chips op zone en status
- **Kalender** — tijdlijn incl. community-tips met datum
- **Kaart** — alle locaties op een Leaflet/OSM-kaart, gekleurd per zone, met per stip een geverifieerde link naar de officiële festivalsite
- **+ Evenement / verwijderen** — gedeelde tips via Firestore, met verwijder-knop
- **🙌 Ik ga** — RSVP per festival, met zichtbare namen/initialen van wie er gaat
- **★ Review** — score 1–5 per onderdeel (🎵 muziek · ✨ sfeer · 👥 publiek · 📍 setting) + toelichting; kaarten tonen het gemiddelde **én per persoon wie welke score gaf** (smaak verschilt). Je eigen review kun je verwijderen (Firestore `reviews`)
- **Top (ranglijst)** — beoordeelde festivals gerangschikt op totaal- of onderdeelscore, met medailles; schakel tussen **Iedereen** (groepsgemiddelde) en **Alleen ik** (jouw eigen ranglijst)
- **🎤 Line-up** — toont wie er speelt zodra bekend (uit `lineup`), anders "Line-up nog niet bekend"; de scheduler checkt tweewekelijks de officiële site
- **♫ Spotify / ☁ Live sets** — Spotify-zoeklink (bij bekende artiesten) + SoundCloud-zoeklink voor live DJ-sets, om te luisteren
- **Deel-preview** — Open-Graph `og.png` voor mooie link-previews (WhatsApp/social)
- **ICS-agenda** — abonneerbaar, met kaartverkoop-meldingen (zie hieronder)

De deel-afbeelding regenereren (na een tekstwijziging in `scripts/og.html`):
```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new \
  --window-size=1200,630 --screenshot="og.png" "file://$(pwd)/scripts/og.html"
```

---

## Agenda in je telefoon/laptop (ICS-abonnement)

Er wordt een `festival-radar.ics` gegenereerd met alle festivals mét datum + losse
kaartverkoop-meldingen. **Abonneer** je erop (niet importeren — dan blijft 'ie automatisch
bijwerken):

- **iPhone/iPad:** Instellingen → Agenda → Accounts → Voeg account toe → Andere →
  Agenda-abonnement → plak de ICS-URL.
- **macOS Agenda:** Archief → Nieuw agenda-abonnement → plak de URL → interval "elke dag".
- **Google Calendar:** Andere agenda's → Via URL → plak de URL.

De agenda ververst dagelijks. Als de scheduler een kaartverkoop-datum vindt, verschijnt er
automatisch een **🎟️ Kaartverkoop start**-item met melding (1 dag + 1 uur ervoor).

Handmatig opnieuw genereren:
```bash
python3 scripts/build_ics.py
```

---

## Firebase koppelen (eenmalig, ~5 min)

De site werkt meteen als statische pagina, maar de **+ Evenement**-knop heeft een gratis
Firebase-database nodig. Zo zet je die op:

### 1. Project aanmaken
1. Ga naar <https://console.firebase.google.com> en log in met je Google-account.
2. Klik **Add project** → geef 'm een naam (bv. `festival-radar`) → **Continue**.
3. Google Analytics mag je **uitzetten** (niet nodig) → **Create project**.

### 2. Firestore database aanzetten
1. Linkermenu → **Build → Firestore Database** → **Create database**.
2. Kies een **locatie** in Europa (bv. `eur3` of `europe-west`).
3. Start in **production mode** (rules zetten we hieronder goed) → **Enable**.

### 3. Beveiligingsregels instellen
Ga naar **Firestore → Rules**, vervang alles door onderstaande en klik **Publish**.
Dit staat lezen toe voor iedereen en toevoegen van nette events, maar géén wijzigen/verwijderen:

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /events/{doc} {
      allow read: if true;
      allow create: if request.resource.data.name is string
                    && request.resource.data.name.size() > 0
                    && request.resource.data.name.size() < 100;
      allow delete: if true;
      allow update: if false;
    }
    // "Ik ga"-RSVP's
    match /rsvps/{doc} {
      allow read: if true;
      allow create: if request.resource.data.eid is string
                    && request.resource.data.name is string
                    && request.resource.data.name.size() > 0
                    && request.resource.data.name.size() < 60;
      allow delete: if true;
      allow update: if false;
    }
    // reviews met scores (muziek / sfeer / publiek / setting)
    match /reviews/{doc} {
      allow read: if true;
      allow create: if request.resource.data.eid is string
                    && request.resource.data.name is string
                    && request.resource.data.name.size() > 0
                    && request.resource.data.name.size() < 60;
      allow delete: if true;
      allow update: if false;
    }
  }
}
```

> `allow delete: if true;` zet de **verwijder-knop** op elke community-kaart aan (iedereen
> mag events weghalen — trust-based, prima voor vrienden). Wil je dat alleen jij kunt
> wissen, zet 'm op `if false;` en verwijder events via de Firestore-console (tab **Data**).
> Bewerken blijft altijd uit.

### 4. Web-app registreren en config kopiëren
1. **Project settings** (tandwiel linksboven) → tab **General** → onderaan **Your apps**.
2. Klik het **web-icoon `</>`** → geef een bijnaam (bv. `web`) → **Register app**
   (Firebase Hosting mag je overslaan).
3. Je krijgt een `firebaseConfig`-blok te zien. Kopieer de waarden.

### 5. Config in de site plakken
Open `index.html`, zoek het blok `const firebaseConfig = { ... }` (onderaan, in de
`<script type="module">`) en vervang de `PASTE_...`-waarden door die van jou:

```js
const firebaseConfig = {
  apiKey: "AIza...",
  authDomain: "festival-radar-xxxx.firebaseapp.com",
  projectId: "festival-radar-xxxx",
  storageBucket: "festival-radar-xxxx.appspot.com",
  messagingSenderId: "1234567890",
  appId: "1:1234567890:web:abcdef123456"
};
```

> Deze waarden zijn **niet geheim** — ze horen in client-code en mogen gewoon op GitHub staan.
> De beveiliging zit in de Firestore-rules uit stap 3.

### 6. Committen en pushen
```bash
git add index.html
git commit -m "Firebase-config gekoppeld"
git push
```
Na ~1 minuut is de live site bijgewerkt en werkt **+ Evenement**.

---

## Datamodel

Collection **`events`**, per document:

| Veld        | Type    | Voorbeeld                        |
|-------------|---------|----------------------------------|
| `name`      | string  | "Boothstock Festival"            |
| `zone`      | string  | `near` \| `road` \| `bucket`     |
| `status`    | string  | `go` \| `watch` \| `gone`        |
| `where`     | string  | "Kraggenburg · ~40 min"          |
| `when`      | string  | "9–12 jul 2026"                  |
| `tickets`   | string  | "verkoop opent 28 jan"           |
| `tags`      | string  | "techno, bos, 18+"               |
| `by`        | string  | "Viktor"                         |
| `createdAt` | timestamp | (automatisch)                  |

## Lokaal bekijken
Open `index.html` in de browser, of start een simpele server:
```bash
python3 -m http.server 8000
# → http://localhost:8000
```
