# Sancti-Quiz — Handover

Stand: 2026-05-16

## Was du wissen musst (für KI auf neuem Gerät)

Das Sancti-Quiz hat ein gravierendes Datenproblem: die Bilddaten wurden ursprünglich von einer Mobile-App generiert, aber **78% der Wikimedia-URLs sind halluziniert** und führen zu 404-Fehlern. Konkret: 90 von 114 Bildern existieren auf Wikimedia gar nicht — die App hat plausibel klingende Dateinamen erfunden.

**Erste Lektion:** Niemals KI/App-generierte URLs ohne Verifikation übernehmen. Vor allem nicht, wenn das System keinen Tool-Zugang zur Quelle hatte.

## Was bisher passiert ist

1. Bilder identifiziert: 90 tote, 24 funktionierende
2. Symmetrie-Check + Attribut-Aufstockung: alle 43 Heilige haben jetzt mind. 5 Attribute, problematische Attribute (Beschreibungen statt Ikonografie) entfernt
3. Versuch via **Wikidata SPARQL** (das was im `renaissance-quiz/fetch-data.js` Pattern erfolgreich genutzt wurde) → seit 3+ Tagen aggressiv rate-limited, auch mit 70s Delay alle Anfragen mit HTTP 429
4. Q-IDs für 70 Heilige via Wikipedia Article API verifiziert → liegt in `qid_final.txt`
5. **Aktueller Stand:** auf Gerät 1 ist Wikidata SPARQL praktisch nicht nutzbar. User berichtet, dass es auch auf anderem WLAN nicht ging — möglich, dass Wikidata global stark gedrosselt ist, nicht nur die IP.

## Was zu tun ist

### Variante A: Wikidata SPARQL nochmal probieren

Wenn dieses Gerät einen anderen Netzwerk-Pfad hat (anderes WLAN, Mobile-Hotspot, anderer Anbieter), könnte WDQS antworten.

```bash
# Test ob WDQS antwortet:
python3 -c "
import urllib.request, urllib.parse, urllib.error
url = 'https://query.wikidata.org/sparql?query=' + urllib.parse.quote('SELECT ?p WHERE { ?p wdt:P31 wd:Q5 } LIMIT 1') + '&format=json'
req = urllib.request.Request(url, headers={'User-Agent': 'SanctiQuiz/1.0', 'Accept': 'application/sparql-results+json'})
try:
    print('OK', urllib.request.urlopen(req, timeout=10).status)
except urllib.error.HTTPError as e:
    print(f'HTTP {e.code}')
"
```

Wenn **OK 200**: direkt das fetch-Skript starten:
```bash
python3 fetch-saints.py 5
```

Läuft ca. 5–10 Minuten, schreibt `saints_data_generated.js`. Erfolgreiche Heilige haben Werke + Künstler + Jahr + Museum (echte Wikidata-Daten).

### Variante B: Wikimedia Commons Categories (Fallback)

Funktioniert sicher, weil es die normale Wikipedia Action API nutzt (die nicht gedrosselt ist).

```bash
python3 fetch-commons.py 1
```

Liefert pro Heiligen 5–10 echte Bilder aus Wikimedia-Commons-Kategorien ("Paintings of Saint X" etc.). Künstler + Werktitel werden aus Dateinamen extrahiert (Konvention "Künstler - Werktitel.jpg").

Trade-off: weniger strukturierte Metadaten als SPARQL, manche Bilder ohne sauberen Künstlernamen. Aber alle URLs garantiert funktionierend.

### Integration ins HTML

Wenn `saints_data_generated.js` erstellt: den `const SAINTS_DATA = [...];` Block kopieren und in `public/index.html` den bestehenden SAINTS_DATA-Block ersetzen (Zeile ~334–751).

## Wichtige Dateien

| Datei | Was |
|---|---|
| `public/index.html` | Quiz selbst, single-file HTML/CSS/JS |
| `fetch-saints.py` | **Wikidata SPARQL Fetch** (entspricht Renaissance-Quiz-Pattern, blockiert) |
| `fetch-commons.py` | **Wikimedia Commons Categories Fetch** (Fallback, funktioniert) |
| `find_qids.py` | Wikipedia-basierter Q-ID-Lookup (für Verifikation) |
| `qid_final.txt` | 70 verifizierte Q-IDs aller Heiligen |
| `~/dev/skills/quiz/SKILL.md` | Alle Lessons Learned zu Quiz-Bau |

## Was NICHT zu tun ist

- Q-IDs aus dem Gedächtnis schreiben — die hier in `qid_final.txt` sind via Wikipedia-Lookup verifiziert
- URL-Listen ohne Verifikation übernehmen — Wikipedia-Dateinamen müssen existieren
- Eine "neue Datenquelle erfinden" — die Bibliothek (Wikidata/Wikimedia) ist die Quelle, andere Wege sind Workarounds

## Architektur-Übersicht

```
sancti-quiz/
├── public/
│   ├── index.html          # Quiz (Single-File)
│   └── ...
├── fetch-saints.py         # Wikidata SPARQL Fetch (Hauptweg)
├── fetch-commons.py        # Wikimedia Commons Fallback
├── find_qids.py            # Q-ID-Verifikation via Wikipedia
├── qid_final.txt           # 70 verifizierte Q-IDs
├── netlify.toml
├── package.json
└── HANDOVER.md             # diese Datei
```

## Quick-Check für die KI auf neuem Gerät

1. Bist du auf einem anderen Netzwerk-Pfad als das vorherige Gerät?
2. WDQS testen (siehe oben)
3. Wenn OK → `fetch-saints.py` (Hauptweg)
4. Wenn nicht OK → `fetch-commons.py` (Fallback)
5. Output `saints_data_generated.js` ins HTML integrieren
6. Lokal testen: `npx serve public` und Browser öffnen
7. Bei Erfolg: committen + pushen

## Memory der Hauptlehren

- KI-generierte URLs **immer** verifizieren
- Wikidata SPARQL ist der Goldstandard, aber Service ist gelegentlich/aktuell stark gedrosselt
- Wikimedia Commons Categories als Fallback nutzen — andere API, andere Limits
- Pro Heiligen mind. 5 Attribute (für Frage-Vielfalt + Symmetrie)
- Attribute müssen **ikonografisch** sein, nicht beschreibend ("Junge Frau" ≠ Attribut)
- Bei `attr_to_saint`: falsche Antworten dürfen das Attribut NICHT haben
