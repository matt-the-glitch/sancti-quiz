"""
Fetch real artwork data for saints from Wikidata SPARQL.

Same approach as renaissance-quiz/fetch-data.js: query Wikidata for verified
artworks depicting each saint, with real Wikimedia Commons image URLs.

Run when WDQS is available (currently rate-limited to 1 req/min during outage).
"""
import urllib.request
import urllib.parse
import urllib.error
import json
import re
import sys
import time

USER_AGENT = 'SanctiQuiz/1.0 (educational quiz, matthias.milleker@example.com)'
SPARQL = 'https://query.wikidata.org/sparql'
THUMB_WIDTH = 500
HEADERS = {'User-Agent': USER_AGENT, 'Accept': 'application/sparql-results+json'}

# Saints with Wikidata Q-IDs.
# Each entry: (qid, name_de, difficulty, attributes)
# Attributes copied from existing index.html (kept as content knowledge).
SAINTS = [
    # === HEILIGE FAMILIE / ZENTRALFIGUREN ===
    ('Q345', 'Maria (Mutter Jesu)', 1, ['Blaues Gewand','Mondsichel','Sternenkrone','Lilie','Jesuskind','Rose']),
    ('Q51666', 'Jesus Christus', 1, ['Kreuznimbus','Dornenkrone','Wunden (Stigmata)','Lamm','Brot und Wein','Hirtenstab']),
    ('Q128267', 'Hl. Joseph', 1, ['Lilie','Zimmermannswerkzeug','Stab mit Blüte','Jesuskind','Älterer Mann']),
    ('Q314700', 'Hl. Joachim', 2, ['Hirtenstab','Älterer Mann','Begegnung an der Goldenen Pforte','Lamm']),
    ('Q235812', 'Hl. Elisabeth (Mutter Johannes\' d. Täufers)', 2, ['Älterer Frauenkopf','Johannesknabe','Heimsuchung Mariens','Schwanger']),

    # === APOSTEL ===
    ('Q33923', 'Hl. Petrus', 1, ['Schlüssel','Hahn','Umgekehrtes Kreuz','Fisch','Papsttiara']),
    ('Q9200', 'Hl. Paulus', 1, ['Schwert','Buch','Hohe Stirnglatze','Langer Bart']),
    ('Q40662', 'Johannes der Täufer', 1, ['Fellgewand','Lamm Gottes','Kreuzstab','Taufschale','Wüste']),
    ('Q43669', 'Hl. Thomas (Apostel)', 2, ['Lanze','Winkelmaß','Baumeisterattribut','Finger (Ungläubiger Thomas)']),
    ('Q43999', 'Hl. Jakobus der Ältere', 2, ['Pilgermuschel','Pilgerstab','Pilgerhut','Kürbisflasche','Buch']),
    ('Q43399', 'Hl. Andreas', 2, ['Andreaskreuz (X-Kreuz)','Fisch','Buch','Strick']),
    ('Q43982', 'Hl. Bartholomäus', 2, ['Eigene Haut über dem Arm','Schindermesser','Buch']),
    ('Q44047', 'Hl. Jakobus der Jüngere', 3, ['Walkerstange','Buch','Mitra (Bischof von Jerusalem)']),
    ('Q43675', 'Hl. Philippus (Apostel)', 3, ['Kreuzstab','Buch','Drache zu Füßen']),
    ('Q43945', 'Hl. Judas Thaddäus', 3, ['Keule','Schiff','Christusmedaillon','Buch']),

    # === EVANGELISTEN (Symbole) ===
    ('Q43600', 'Hl. Matthäus (Evangelist)', 1, ['Engel als Beistand','Buch','Schreibfeder','Geldbeutel (vor Berufung)']),
    ('Q31966', 'Hl. Markus (Evangelist)', 1, ['Geflügelter Löwe','Buch','Schreibfeder','Tetraevangelist']),
    ('Q128538', 'Hl. Lukas (Evangelist)', 1, ['Geflügelter Stier','Buch','Maler-Attribute (Pinsel, Staffelei)','Marienikone']),
    ('Q44015', 'Hl. Johannes (Evangelist)', 1, ['Adler','Kelch mit Schlange','Buch','Jugendlich-Bart-los']),

    # === ERZENGEL ===
    ('Q45581', 'Erzengel Michael', 2, ['Flügel','Schwert / Flammenschwert','Waage (Seelenwäger)','Rüstung','Besiegter Teufel / Drache']),
    ('Q81989', 'Erzengel Gabriel', 2, ['Flügel','Lilie','Verkündigung an Maria','Schriftrolle']),
    ('Q56951', 'Erzengel Raphael', 3, ['Flügel','Fisch','Pilgerstab','Begleiter Tobias','Wanderhut']),

    # === KIRCHENVÄTER & GROSSE THEOLOGEN ===
    ('Q44248', 'Hl. Hieronymus', 1, ['Löwe','Kardinalstracht','Totenkopf','Stein','Buch','Kruzifix']),
    ('Q8018', 'Hl. Augustinus', 2, ['Flammendes Herz','Bischofsstab','Mitra','Buch','Kind mit Muschel']),
    ('Q43689', 'Hl. Ambrosius von Mailand', 3, ['Bienenkorb','Bischofsstab','Mitra','Buch','Geißel']),
    ('Q42827', 'Hl. Gregor der Große', 3, ['Heiliggeisttaube am Ohr','Papsttiara','Buch','Bischofsstab']),
    ('Q9438', 'Hl. Thomas von Aquin', 3, ['Sonne auf der Brust','Dominikanerkutte','Buch','Lilie','Taube']),
    ('Q70991', 'Hl. Hildegard von Bingen', 3, ['Visionen-Flammen','Buch','Bischofsstab (Äbtissin)','Benediktiner-Habit']),
    ('Q188411', 'Hl. Bernhard von Clairvaux', 3, ['Zisterzienser-Habit (weiß)','Drei Mitren zu Füßen','Bienenkorb','Schreibfeder']),

    # === ORDENSGRÜNDER & MYSTIKER ===
    ('Q676555', 'Hl. Franziskus von Assisi', 1, ['Stigmata','Braune Kutte','Strickgürtel','Kruzifix','Tiere (Vögel)','Totenkopf']),
    ('Q191107', 'Hl. Klara von Assisi', 3, ['Monstranz','Klarissen-Habit','Lilie','Kreuzstab']),
    ('Q44091', 'Hl. Dominikus', 3, ['Hund mit brennender Fackel','Stern','Rosenkranz','Lilie','Schwarz-weißes Ordensgewand']),
    ('Q44265', 'Hl. Benedikt von Nursia', 3, ['Zerbrochenes Glas / Kelch mit Schlange','Rabe mit Brot','Ordensregel (Buch)','Abtsstab','Schwarzes Ordensgewand']),
    ('Q44281', 'Hl. Ignatius von Loyola', 3, ['IHS-Monogramm','Jesuiten-Habit','Buch (Exerzitien)','Strahlennimbus']),
    ('Q174880', 'Hl. Teresa von Ávila', 3, ['Karmeliter-Habit','Pfeil ins Herz','Heiliggeisttaube','Feder']),
    ('Q170547', 'Hl. Antonius der Große', 2, ['Schwein','Tau-Kreuz (T)','Flammen','Glocke','Dämonen','Mönchsgewand']),
    ('Q167477', 'Hl. Antonius von Padua', 2, ['Jesuskind (auf dem Arm)','Lilie','Buch','Flamme','Franziskanerkutte']),

    # === MÄRTYRER UND BEKANNTE HEILIGE ===
    ('Q183332', 'Hl. Sebastian', 1, ['Pfeile','An Baum/Säule gebunden','Halbnackt','Palme']),
    ('Q48438', 'Hl. Georg', 1, ['Drache','Ritterrüstung','Lanze','Weißes Pferd','Kreuzfahne','Prinzessin']),
    ('Q179718', 'Hl. Katharina von Alexandrien', 1, ['Rad (zerbrochen)','Schwert','Krone','Buch','Ring','Palme']),
    ('Q63070', 'Hl. Maria Magdalena', 1, ['Salbgefäß','Offenes langes Haar','Totenkopf','Kruzifix','Rotes Gewand']),
    ('Q133704', 'Hl. Martin von Tours', 1, ['Geteilter Mantel','Pferd','Bettler','Gans','Bischofsstab']),
    ('Q192816', 'Hl. Barbara', 2, ['Turm mit drei Fenstern','Kelch mit Hostie','Krone','Schwert','Palme']),
    ('Q17590', 'Hl. Laurentius', 2, ['Bratrost','Dalmatika','Palme','Geldbeutel','Weihrauchgefäß']),
    ('Q44269', 'Hl. Nikolaus von Myra', 2, ['Drei Goldkugeln','Bischofsstab','Mitra','Drei Kinder im Bottich','Buch']),
    ('Q193507', 'Hl. Christophorus', 2, ['Jesuskind auf der Schulter','Baumstamm als Stab','Fluss','Riesengröße']),
    ('Q297742', 'Hl. Margareta von Antiochia', 2, ['Drache (besiegt)','Kreuz / Kreuzstab','Palme','Perlen']),
    ('Q210096', 'Hl. Agnes', 2, ['Lamm','Schwert','Langes Haar','Palme','Ring']),
    ('Q183240', 'Hl. Lucia', 2, ['Augen auf Teller','Öllampe','Schwert / Dolch','Palme']),
    ('Q80513', 'Hl. Cäcilia', 2, ['Orgel','Musikinstrumente','Rosen','Palme','Krone']),
    ('Q161775', 'Hl. Stephanus', 2, ['Steine','Dalmatika','Palme']),
    ('Q159862', 'Hl. Elisabeth von Thüringen', 2, ['Rosen','Brot','Krone','Kanne','Arme / Kranke']),
    ('Q164294', 'Hl. Anna (Mutter Mariens)', 2, ['Maria und Jesuskind (Anna Selbdritt)','Buch','Grünes / rotes Gewand','Kopftuch']),
    ('Q196653', 'Hl. Veronika', 2, ['Schweißtuch Christi (Vera Icon)','Abdruck des Antlitzes Christi','Wegkreuz','Tränen']),

    # === SPEZIALHEILIGE UND REGIONALE PATRONE ===
    ('Q369691', 'Hl. Ursula', 3, ['Pfeile','Krone','Kreuzfahne','Schützender Mantel','Offenes Haar']),
    ('Q232427', 'Hl. Apollonia', 3, ['Zange mit Zahn','Palme','Krone']),
    ('Q242274', 'Hl. Dorothea', 3, ['Korb mit Rosen und Äpfeln','Blumenkranz','Palme','Schwert']),
    ('Q170164', 'Hl. Helena', 3, ['Großes Kreuz (Kreuzauffindung)','Kaiserkrone','Nägel','Hermelinmantel','Inschriftentafel INRI']),
    ('Q152457', 'Hl. Rochus', 3, ['Pestbeule am Oberschenkel','Hund mit Brot','Pilgerstab','Pilgermuschel','Engel']),
    ('Q218921', 'Hl. Eustachius', 3, ['Hirsch mit Kreuz im Geweih','Jägergewand','Hunde','Eherner Stier']),
    ('Q159834', 'Hl. Hubertus', 3, ['Hirsch mit Kreuz im Geweih','Jagdhund','Jagdhorn','Bischofsstab']),
    ('Q298845', 'Hl. Florian', 3, ['Wassereimer','Brennendes Haus','Rüstung','Mühlstein','Fahne']),
    ('Q2142772', 'Hl. Gereon', 3, ['Ritterrüstung','Fahne','Kreuz','Schwert','Kölner Stadtpatron']),
    ('Q359878', 'Hl. Erasmus', 3, ['Winde / Spule mit Gedärmen','Bischofstracht','Mitra','Palme']),
    ('Q316599', 'Hl. Mauritius', 3, ['Ritterrüstung','Fahne','Dunkle Hautfarbe','Lanze','Schild mit Mohrenköpfen']),
    ('Q60889', 'Hl. Wolfgang von Regensburg', 3, ['Beil im Kirchendach','Kirchenmodell','Bischofsstab','Mitra']),
    ('Q76486', 'Hll. Cosmas und Damian', 3, ['Arztinstrumente','Salbentiegel','Mörser','Rotes Gewand','Palme']),
    ('Q57520', 'Hl. Hedwig von Schlesien', 3, ['Schuhe in der Hand (Barfuß)','Madonnenstatuette','Herzogskrone','Witwentracht']),
    ('Q160445', 'Hl. Bonifatius', 3, ['Gefälltes Eichenbaum (Donar-Eiche)','Bischofsstab','Mitra','Buch mit Schwert (Märtyrertod)']),
    ('Q221522', 'Hl. Johannes Nepomuk', 3, ['Fünf-Sterne-Nimbus','Brücke','Kruzifix in der Hand','Domherrentracht (Priester)']),
]

def query_artworks_for_saint(saint_qid, limit=15):
    """SPARQL: artworks depicting this saint, with images, paintings only."""
    sparql = f"""
    SELECT DISTINCT ?artwork ?artworkLabel ?image ?creator ?creatorLabel ?inception ?collectionLabel WHERE {{
      ?artwork wdt:P180 wd:{saint_qid} .
      ?artwork wdt:P18 ?image .
      ?artwork wdt:P31/wdt:P279* wd:Q3305213 .
      OPTIONAL {{ ?artwork wdt:P170 ?creator . }}
      OPTIONAL {{ ?artwork wdt:P571 ?inception . }}
      OPTIONAL {{ ?artwork wdt:P195 ?collection . }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en" . }}
    }}
    LIMIT {limit}
    """
    url = f"{SPARQL}?query={urllib.parse.quote(sparql)}&format=json"
    req = urllib.request.Request(url, headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=60)
    return json.loads(resp.read())

def commons_filename_from_image_url(url):
    """Extract filename from Wikimedia Commons URL."""
    m = re.search(r'/commons/(?:thumb/)?[a-f0-9]/[a-f0-9]{2,3}/([^/]+)', url)
    if m:
        return urllib.parse.unquote(m.group(1))
    # Already a Special:Redirect URL?
    m = re.search(r'/file/([^&?]+)', url)
    if m:
        return urllib.parse.unquote(m.group(1))
    return None

def special_redirect_url(filename, width=THUMB_WIDTH):
    """Build Special:Redirect URL."""
    encoded = urllib.parse.quote(filename.replace(' ', '_'), safe='/_.,()')
    a = "title=Special:Redirect"
    b = "/fi" + "le/"
    return f"https://commons.wikimedia.org/w/index.php?{a}{b}{encoded}&width={width}"

def js_string(s):
    """Escape for JS string literal."""
    return s.replace('\\', '\\\\').replace('"', '\\"')

def format_year(iso_date):
    """Wikidata gives dates like '+1525-00-00T00:00:00Z'. Extract year."""
    if not iso_date:
        return ''
    m = re.match(r'[+-]?(\d{1,4})', iso_date)
    return m.group(1) if m else ''

def build_painting_block(binding):
    """Build one painting JS object from a SPARQL binding."""
    img_url = binding.get('image', {}).get('value', '')
    filename = commons_filename_from_image_url(img_url)
    if not filename:
        return None
    artist = binding.get('creatorLabel', {}).get('value', 'Unbekannt')
    title = binding.get('artworkLabel', {}).get('value', '?')
    # Skip Q-IDs that didn't resolve to readable labels
    if title.startswith('Q') and title[1:].isdigit():
        title = 'Werk'
    year = format_year(binding.get('inception', {}).get('value', ''))
    museum = binding.get('collectionLabel', {}).get('value', '')
    if museum.startswith('Q') and museum[1:].isdigit():
        museum = ''
    new_url = special_redirect_url(filename)
    parts = [f'img:"{js_string(new_url)}"', f'artist:"{js_string(artist)}"', f'title:"{js_string(title)}"']
    if year:
        parts.append(f'year:"{js_string(year)}"')
    if museum:
        parts.append(f'museum:"{js_string(museum)}"')
    return '      { ' + ', '.join(parts) + ' },'

def build_saint_block(qid, name, difficulty, attributes, bindings):
    paintings = []
    seen_imgs = set()
    for b in bindings:
        img = b.get('image', {}).get('value', '')
        if img in seen_imgs:
            continue
        seen_imgs.add(img)
        line = build_painting_block(b)
        if line:
            paintings.append(line)
        if len(paintings) >= 6:
            break

    attr_str = ','.join(f'"{js_string(a)}"' for a in attributes)
    out = []
    out.append('  {')
    out.append(f'    saint: "{js_string(name)}",')
    out.append(f'    attributes: [{attr_str}],')
    out.append(f'    difficulty: {difficulty},')
    out.append('    paintings: [')
    out.extend(paintings)
    out.append('    ]')
    out.append('  },')
    return '\n'.join(out), len(paintings)

def main():
    delay = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    print(f"Fetching {len(SAINTS)} saints with {delay}s delay between requests", flush=True)
    print(f"(Bump delay to 70 if WDQS is rate-limited to 1 req/min)", flush=True)

    all_blocks = []
    total_paintings = 0
    failures = []

    for idx, (qid, name, difficulty, attrs) in enumerate(SAINTS):
        if idx > 0:
            time.sleep(delay)
        print(f"\n[{idx+1}/{len(SAINTS)}] {name} ({qid})", flush=True)
        try:
            data = query_artworks_for_saint(qid, limit=15)
            bindings = data['results']['bindings']
            block, n = build_saint_block(qid, name, difficulty, attrs, bindings)
            all_blocks.append(block)
            total_paintings += n
            print(f"  -> {n} paintings", flush=True)
            if n == 0:
                failures.append((qid, name, 'no results'))
        except urllib.error.HTTPError as e:
            print(f"  -> HTTP {e.code}: {e.reason}", flush=True)
            failures.append((qid, name, f'HTTP {e.code}'))
            # Keep saint with empty paintings so structure stays intact
            block, _ = build_saint_block(qid, name, difficulty, attrs, [])
            all_blocks.append(block)
        except Exception as e:
            print(f"  -> ERR: {e}", flush=True)
            failures.append((qid, name, str(e)))
            block, _ = build_saint_block(qid, name, difficulty, attrs, [])
            all_blocks.append(block)

    output = 'const SAINTS_DATA = [\n' + '\n'.join(all_blocks) + '\n];\n'
    out_path = 'saints_data_generated.js'
    with open(out_path, 'w') as f:
        f.write(output)

    print(f"\n=== DONE ===", flush=True)
    print(f"Saints: {len(SAINTS)} | Total paintings: {total_paintings}", flush=True)
    print(f"Failures: {len(failures)}", flush=True)
    for qid, name, why in failures:
        print(f"  - {name} ({qid}): {why}", flush=True)
    print(f"\nOutput: {out_path}", flush=True)

if __name__ == '__main__':
    main()
