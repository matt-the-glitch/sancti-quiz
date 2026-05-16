# Quiz-Skill

Patterns und Lessons Learned aus drei Quiz-Projekten:
- `renaissance-quiz` — Künstler/Werk-Erkennung der Nordischen Renaissance
- `boxing-quiz` — Boxer/Fights aus der Schwergewichts-Ära
- `sancti-quiz` — Heilige in der Kunst erkennen

Ziel: Beim nächsten Quiz nicht die gleichen Fehler nochmal machen.

---

## 1. Datenquelle: das wichtigste Thema

**Regel Nr. 1: Niemals KI/App halluzinierte Daten ohne Verifikation übernehmen.**

Im Sancti-Quiz wurden 78% der Wikimedia-Bild-URLs von der Mobile-App halluziniert (plausibel klingende Dateinamen, die nicht existieren). Genau so habe ich beim Q-ID-Lookup zunächst aus dem Gedächtnis falsche Q-IDs eingesetzt. Beides nur erkannt nachdem User sich beschwerte.

### Verlässliche Quellen (in dieser Reihenfolge)

1. **Wikidata SPARQL** — strukturierte Datenbankabfrage, beste Quelle
   - Renaissance: `?artwork wdt:P170 wd:<artist>` (Werke nach Künstler)
   - Sancti: `?artwork wdt:P180 wd:<saint>` (Werke nach Motiv/Heiliger)
   - Liefert garantiert echte Werke mit echten Wikimedia-Bildern
   - **Achtung:** Service hat regelmäßig Outages (aggressives Rate-Limit auf 1 req/min)

2. **Wikipedia Action API** — pageprops für Wikidata-Q-ID-Lookup
   - `action=query&titles=<artikel>&prop=pageprops&ppprop=wikibase_item`
   - Liefert verifizierte Q-IDs aus echtem Wikipedia-Artikel
   - Höhere Rate-Limits als WDQS, oft up wenn SPARQL down ist

3. **Wikipedia pageimages** — für Personenbilder (Boxing)
   - `action=query&titles=<artikel>&prop=pageimages&pithumbsize=400`
   - Liefert das Hauptbild der Wikipedia-Seite, immer echt

### Anti-Pattern

- Mobile-Apps die "Quiz-Daten generieren" → meist halluzinierte URLs, IMMER verifizieren
- Q-IDs/URLs aus dem Gedächtnis schreiben → **immer** programmatisch lookuppen
- Generic Search statt strukturierter Query → schlechte Trefferqualität

---

## 2. Wikimedia Commons Bild-URLs

**Nur dieses Format nutzen:**
```
https://commons.wikimedia.org/w/index.php?title=Special:Redirect/file/FILENAME&width=NNN
```

Direkte `upload.wikimedia.org/wikipedia/commons/thumb/X/XX/...` URLs sind unzuverlässig (Hotlink-Blocking, fehlende Thumbnails).

`Special:Redirect/file/` macht 302-Redirect zur korrekten Datei, generiert Thumbnails on-demand, funktioniert von jedem Drittanbieter aus.

### URL-Transformation aus Wikidata-Response

Wikidata gibt URLs der Form `http://commons.wikimedia.org/wiki/Special:FilePath/X.jpg` zurück. Filename extrahieren und in `Special:Redirect`-Format überführen (siehe `renaissance-quiz/fetch-data.js` Zeile 105-111).

### Bild-Tag Best Practices

```html
<img referrerpolicy="no-referrer"
     onload="this.style.display='block';loading.style.display='none'"
     onerror="handleImageError(this)"
     style="display:none">
```

- `referrerpolicy="no-referrer"`: defensiv gegen Hotlink-Blocking
- Initial `display:none`, beim `onload` einblenden → kein leerer Rahmen während Ladezeit
- `onerror`-Handler: Fallback-Text zeigen

### Preconnect-Hint

```html
<link rel="preconnect" href="https://commons.wikimedia.org">
```

Im `<head>`. Browser baut TCP/TLS-Verbindung schon vor dem ersten Bild auf.

---

## 3. Architektur

### Single-File vs Multi-File

| Quiz | Setup | Wann |
|---|---|---|
| Sancti | Single-File HTML | Klein, schneller Setup, Mobile-App-Generierung |
| Renaissance | Multi-File (index.html + quiz.js + style.css + data/*.json) | Größer, sauber trennbar, Cache-friendly |
| Boxing | Multi-File | Wie Renaissance |

**Empfehlung:** Multi-File ab 200+ Datensätzen oder wenn Build-Schritt nötig.

### Data Loading

- **Inline JS-Konstante** (Sancti): einfach, kein Async, aber HTML wird groß
- **Externe JSON via fetch** (Renaissance, Boxing): clean, separater Build-Schritt

### Build-Skript Convention

```
fetch-data.js  # Node, holt aus Wikidata, schreibt public/data/artworks.json
```

Vom Quiz selbst aus referenziert: `fetch('data/artworks.json').then(...)`.

---

## 4. Fragetypen

### Aus dem Sancti-Quiz

1. **`image_saint`** — Bild zeigen, "Welcher Heilige?"
2. **`image_artist`** — Bild zeigen, "Welcher Künstler?"
3. **`attr_to_saint`** — Attribut nennen, "Welcher Heilige hat das?"
4. **`saint_to_attr`** — Heiligen nennen, "Welches Attribut?"

### Aus dem Renaissance-Quiz

Ähnlich, plus:
- Style/Schule-Fragen ("Welche Schule?")
- Era-Fragen ("Aus welcher Zeit?")

### Generische Patterns

- **Forward** (X → Eigenschaft): "Wer hat das gemalt?"
- **Reverse** (Eigenschaft → X): "Welches Werk hat dieses Attribut?"
- **Multiple-Choice** mit 1 richtig + 3 falsch ist Standard

### Falsche Antworten generieren — Vorsicht!

**Bug-Falle:** Wenn das gefragte Attribut von mehreren Heiligen geteilt wird (z.B. "Palme" haben 13 Heilige), kann eine "falsche" Antwort in Wahrheit richtig sein.

**Lösung:** Falsche Antworten dürfen das Attribut **nicht** haben.
```js
function getWrongSaintsWithoutAttr(attr, correctSaint, count) {
  return shuffleArray(
    SAINTS_DATA
      .filter(s => s.saint !== correctSaint && !s.attributes.includes(attr))
      .map(s => s.saint)
  ).slice(0, count);
}
```

Wenn nicht genug Heilige ohne das Attribut existieren (< count): Frage skippen, nächste generieren.

### Wiederholungsschutz

```js
const usedQuestions = new Set();
const qKey = type + ':' + uniqueIdentifier; // z.B. type+image-url oder type+attr+saint
if (usedQuestions.has(qKey)) continue;
usedQuestions.add(qKey);
```

Bei `attr_to_saint`: key sollte `attr` sein (jedes Attribut nur 1x), nicht `saint+attr` (sonst zu viele Wiederholungen).

### Symmetrie-Check

Jeder Heilige, der als "wrong"-Option erscheinen kann, muss auch als korrekte Antwort vorkommen können. Praktisch:
- Heiliger braucht Attribute → kann in `saint_to_attr` korrekt sein
- Heiliger braucht Werke → kann in `image_*` korrekt sein
- Heiliger braucht Attribute die nicht von zu vielen geteilt werden → `attr_to_saint`

Schwache Heilige (≤3 Attribute) erscheinen statistisch viel zu selten als korrekt → mind. 5 Attribute pro Heiliger ist gute Untergrenze.

### Schwierigkeitsstufen

Sancti nutzt 3 Stufen, freigeschaltet nach Score:
```js
let maxDiff = 1;
if (score >= 5) maxDiff = 2;
if (score >= 10) maxDiff = 3;
```

**Falle:** Wenn Diff-1-Pool zu klein (z.B. 10 Heilige), gibt's am Anfang viele Wiederholungen. → Genug Diff-1-Einträge sicherstellen oder Schwellen anpassen.

---

## 5. UI-Patterns

### HUD (Head-Up Display)

Drei Elemente, oben am Rand:
- Links: `Frage 1` (Fortschritt)
- Mitte: Lives als Herzen `♥ ♥ ♥`
- Rechts: Score-Zahl + Label "richtig"

### Image-Frame mit Loading

```html
<div class="image-frame" id="imageFrame">
  <span class="img-loading" id="imgLoading">Bild wird geladen…</span>
  <img id="quizImage" style="display:none"
       onload="this.style.display='block';imgLoading.style.display='none'"
       onerror="handleImageError(this)">
</div>
```

CSS für `.image-frame`:
- `min-height: 200px` damit Layout nicht springt
- `display: flex; align-items: center; justify-content: center` für zentriertes Loading
- Border + Background für Frame-Look

### Feedback nach Antwort

- **Antwort einfärben:** richtige Option grün, falsche rot
- **Werkinfo unter den Options:** "Künstler – Titel, Jahr · Museum"
- **Status-Zeile:** "Richtig! – Hl. Sebastian" oder "Falsch – Die richtige Antwort: ..."
- **Bonus-Bild:** zusätzliches Werk des Heiligen → vertieft das Lernen

### Weiter-Knopf, NICHT Auto-Advance

**Lesson learned:** Auto-Advance per `setTimeout(endGame, 2000)` ist schlecht — Bilder können noch laden, User wird vor Aha-Moment weitergerissen.

→ Immer manuelles **"Weiter"** (bzw. **"Zur Bestenliste"** beim letzten Leben).

### Bestenliste

Drei Spalten: Rank, Name, Punkte. Highlight für den eigenen Eintrag.

---

## 6. Persistence

### LocalStorage (lokal pro Browser)

```js
const KEY = 'quiz-leaderboard';
let lb = JSON.parse(localStorage.getItem(KEY) || '[]');
lb.push({ name, score, total, date: new Date().toISOString().slice(0,10) });
lb.sort((a,b) => b.score - a.score);
localStorage.setItem(KEY, JSON.stringify(lb.slice(0, 50)));
```

Limit: 50 Einträge sortiert nach Score absteigend.

### Shared Leaderboard (für später)

Wenn Leaderboard zwischen Spielern geteilt werden soll, **drei** realistische Optionen:

1. **Firebase Realtime Database** — kostenlose Spark-Plan, Pure-JS-SDK, Security Rules nötig
2. **Supabase** — PostgreSQL + REST, etwas komplexer
3. **Netlify Functions + KV-Store** — wenn schon auf Netlify

**Nicht** jsonbin.io oder ähnliches: keine Race-Condition-Safety.

---

## 7. Deployment auf Netlify

```toml
# netlify.toml
[build]
  publish = "public"
```

Kein Build-Step nötig wenn pure HTML/CSS/JS. Wenn Build-Skript für Daten nötig (Wikidata-Fetch), separat lokal laufen lassen und committen.

### Setup-Steps

1. GitHub-Repo
2. Netlify-Account: "Import from Git" → Repo wählen
3. Build-Settings: publish dir = `public`, kein build command
4. Done

---

## 8. Häufige Fallen (Pitfalls)

### 8.1 Mobile-App-Daten halluziniert

Wenn Quiz-Daten von einer Mobile-App / KI generiert wurden: **Alle URLs verifizieren** bevor man darauf vertraut. Pattern: über alle URLs iterieren, HEAD-Request, dead ones markieren.

### 8.2 En-dash in CSS-Custom-Properties

Mobile-Tastaturen mit Autocorrect ersetzen `--` durch `–` (en-dash). Resultat: `var(--gold)` wird zu `var(–gold)` und das Quiz hat keine Farben. Visuell schwer zu erkennen.

→ Beim Empfangen von KI/Mobile-generierten CSS-Code immer Suche-und-Ersetze durchführen.

### 8.3 Wikidata SPARQL Outages

`query.wikidata.org` ist regelmäßig down oder aggressiv rate-limited (1 req/min). 
→ Build-Skripte mit Retry + Backoff bauen (siehe `renaissance-quiz/fetch-data.js` Zeile 168-173).
→ Wenn SPARQL down: Wikipedia Action API funktioniert oft weiter.

### 8.4 Doppelt zugeordnete Bilder

Sancti-Quiz hatte ein Gemälde "Begegnung Erasmus + Mauritius" zugeordnet zu BEIDEN Heiligen. Bei Bildfrage uneindeutig.
→ Pre-Check: ein Bild darf nur zu einem Heiligen gehören.

### 8.5 Attribut-Mehrdeutigkeit

13 Heilige haben "Palme" als Attribut. Frage "Welcher Heilige wird mit Palme dargestellt?" mit 4 Optionen — wenn unter den 3 falschen Antworten ein weiterer Palme-Heiliger ist, ist sie unfair.
→ Wrong-Picker filtert nach Attribut-Abwesenheit.

### 8.6 Generische statt ikonografische Attribute

"Junge Frau", "Älterer Mann", "Pestpatron" sind keine bildlichen Attribute, sondern Beschreibungen/Rollen.
→ Attribute müssen visuell erkennbar sein im Bild.

### 8.7 Pfad-Encoding bei Special:Redirect

`Special:Redirect/file/X` akzeptiert sowohl `_` als auch `%20` für Spaces. Bei automatisierten Pipelines die echte Wikimedia-Filename-Konvention nutzen (mit `_`).

---

## 9. Build-Skript-Template (Wikidata-Quiz)

Siehe `renaissance-quiz/fetch-data.js` als Referenz-Implementation. Kernschritte:

1. Liste mit Q-IDs der "Subjects" (Künstler, Heilige, …)
2. SPARQL pro Subject:
   - `?work P170 wd:<artist>` oder `?work P180 wd:<subject>`
   - `?work P18 ?image`
   - `?work P31/P279* wd:Q3305213` (filter auf paintings)
   - Optional: P571 (Datum), P195 (Museum)
3. URL transformieren: `Special:FilePath/` → `Special:Redirect/file/`
4. Output: `public/data/works.json`

**Q-IDs zuerst verifizieren** via Wikipedia Action API (siehe `sancti-quiz/find_qids.py`).

---

## 10. Code-Templates

Konkrete Code-Snippets siehe Referenz-Projekte:

- **Wikidata-Fetch (Node):** `renaissance-quiz/fetch-data.js`
- **Wikidata-Fetch (Python):** `sancti-quiz/fetch-saints.py`
- **Q-ID-Verifikation:** `sancti-quiz/find_qids.py`
- **Wikipedia-pageimages (Personen):** `boxing-quiz/fetch-images.js`
- **Multi-file Quiz:** `renaissance-quiz/public/`
- **Single-file Quiz:** `sancti-quiz/public/index.html`

---

## 11. Checkliste für neues Quiz

- [ ] Datenquelle gewählt (Wikidata SPARQL vs Wikipedia pageimages vs hardcoded)
- [ ] Q-IDs / Wikipedia-Titel der Subjects verifiziert
- [ ] Fetch-Skript geschrieben mit Retry/Backoff
- [ ] Architektur entschieden (single- vs multi-file)
- [ ] Fragetypen definiert
- [ ] Wrong-Answer-Logik prüft auf Mehrdeutigkeit
- [ ] Wiederholungsschutz (usedQuestions Set)
- [ ] Schwierigkeitsstufen mit genug Pool pro Stufe
- [ ] HUD + Image-Frame + Loading-State
- [ ] Manuelle "Weiter"-Buttons, kein Auto-Advance
- [ ] Symmetrie-Check: jeder Heilige als korrekt + als falsch möglich
- [ ] Mind. 5 Attribute / Eigenschaften pro Subject
- [ ] localStorage-Bestenliste (oder shared wenn nötig)
- [ ] netlify.toml mit `publish = "public"`
- [ ] Preconnect für Bilder-Host

---

**Version:** 1.0
**Letztes Update:** 2026-05-14
