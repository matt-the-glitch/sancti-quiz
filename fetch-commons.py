"""
Fallback fetcher: Wikimedia Commons Categories statt Wikidata SPARQL.

Funktioniert auch wenn WDQS/SPARQL gedrosselt ist, weil es die normale
Wikipedia Action API benutzt (war heute getestet zuverlässig).

Für jeden Heiligen werden mehrere Kategorie-Pattern probiert:
  - "Paintings of <name>"
  - "<name> in art"
  - "Iconography of <name>"
  - "Saint <name>"

Aus Dateinamen extrahieren wir Künstler + Werktitel (Konvention:
"Künstler - Werktitel.jpg" auf Wikimedia Commons).
"""
import urllib.request
import urllib.parse
import urllib.error
import json
import re
import time
import sys

HEADERS = {'User-Agent': 'SanctiQuiz/1.0 (educational quiz)'}

# Saints: (qid, de_name, difficulty, attributes, commons_search_names)
# commons_search_names: Liste englischer Bezeichnungen für Kategorie-Suche
SAINTS_COMMONS = [
    # Heilige Familie
    ('Q345', 'Maria (Mutter Jesu)', 1,
     ['Blaues Gewand','Mondsichel','Sternenkrone','Lilie','Jesuskind','Rose'],
     ['Mary, mother of Jesus', 'Virgin Mary', 'Madonna']),
    ('Q51666', 'Jesus Christus', 1,
     ['Kreuznimbus','Dornenkrone','Wunden (Stigmata)','Lamm','Brot und Wein','Hirtenstab'],
     ['Jesus Christ', 'Jesus']),
    ('Q128267', 'Hl. Joseph', 1,
     ['Lilie','Zimmermannswerkzeug','Stab mit Blüte','Jesuskind','Älterer Mann'],
     ['Saint Joseph', 'Joseph of Nazareth']),
    ('Q314700', 'Hl. Joachim', 2,
     ['Hirtenstab','Älterer Mann','Begegnung an der Goldenen Pforte','Lamm'],
     ['Saint Joachim', 'Joachim of Nazareth']),
    ('Q235849', "Hl. Elisabeth (Mutter Johannes' d. Täufers)", 2,
     ['Älterer Frauenkopf','Johannesknabe','Heimsuchung Mariens','Schwanger'],
     ['Saint Elizabeth, mother of John the Baptist', 'Elizabeth, mother of John the Baptist']),
    # Apostel
    ('Q33923', 'Hl. Petrus', 1,
     ['Schlüssel','Hahn','Umgekehrtes Kreuz','Fisch','Papsttiara'],
     ['Saint Peter', 'Saint Peter the Apostle']),
    ('Q9200', 'Hl. Paulus', 1,
     ['Schwert','Buch / Briefe','Hohe Stirnglatze','Langer Bart','Schriftrolle','Pferd (Bekehrung vor Damaskus)'],
     ['Paul the Apostle', 'Saint Paul']),
    ('Q40662', 'Johannes der Täufer', 1,
     ['Fellgewand','Lamm Gottes','Kreuzstab','Taufschale','Wüste'],
     ['John the Baptist', 'Saint John the Baptist']),
    ('Q43669', 'Hl. Thomas (Apostel)', 2,
     ['Lanze','Winkelmaß / Baumeister','Finger berührt Christuswunde','Buch','Gürtel Mariens (Mariä Himmelfahrt)'],
     ['Thomas the Apostle', 'Saint Thomas the Apostle']),
    ('Q43999', 'Hl. Jakobus der Ältere', 2,
     ['Pilgermuschel','Pilgerstab','Pilgerhut','Kürbisflasche','Buch'],
     ['James, son of Zebedee', 'James the Great', 'Saint James the Great']),
    ('Q43399', 'Hl. Andreas', 2,
     ['Andreaskreuz (X-Kreuz)','Fisch','Buch','Strick'],
     ['Andrew the Apostle', 'Saint Andrew']),
    ('Q43982', 'Hl. Bartholomäus', 2,
     ['Eigene Haut über dem Arm','Schindermesser','Buch'],
     ['Bartholomew the Apostle', 'Saint Bartholomew']),
    ('Q44047', 'Hl. Jakobus der Jüngere', 3,
     ['Walkerstange','Buch','Mitra (Bischof von Jerusalem)'],
     ['James, son of Alphaeus', 'James the Less', 'Saint James the Less']),
    ('Q43675', 'Hl. Philippus (Apostel)', 3,
     ['Kreuzstab','Buch','Drache zu Füßen'],
     ['Philip the Apostle', 'Saint Philip the Apostle']),
    ('Q43945', 'Hl. Judas Thaddäus', 3,
     ['Keule','Schiff','Christusmedaillon','Buch'],
     ['Jude the Apostle', 'Saint Jude', 'Jude Thaddaeus']),
    # Evangelisten
    ('Q43600', 'Hl. Matthäus (Evangelist)', 1,
     ['Engel als Beistand','Buch','Schreibfeder','Geldbeutel (vor Berufung)'],
     ['Matthew the Apostle', 'Saint Matthew', 'Matthew the Evangelist']),
    ('Q31966', 'Hl. Markus (Evangelist)', 1,
     ['Geflügelter Löwe','Buch','Schreibfeder','Tetraevangelist'],
     ['Mark the Evangelist', 'Saint Mark']),
    ('Q128538', 'Hl. Lukas (Evangelist)', 1,
     ['Geflügelter Stier','Buch','Maler-Attribute (Pinsel, Staffelei)','Marienikone'],
     ['Luke the Evangelist', 'Saint Luke']),
    ('Q44015', 'Hl. Johannes (Evangelist)', 1,
     ['Adler','Kelch mit Schlange','Buch','Jugendlich-Bart-los'],
     ['John the Evangelist', 'Saint John the Evangelist', 'John the Apostle']),
    # Erzengel
    ('Q45581', 'Erzengel Michael', 2,
     ['Flügel','Schwert / Flammenschwert','Waage (Seelenwäger)','Rüstung','Besiegter Teufel / Drache'],
     ['Archangel Michael', 'Michael (archangel)']),
    ('Q81989', 'Erzengel Gabriel', 2,
     ['Flügel','Lilie','Verkündigung an Maria','Schriftrolle'],
     ['Archangel Gabriel', 'Gabriel (archangel)']),
    ('Q56951', 'Erzengel Raphael', 3,
     ['Flügel','Fisch','Pilgerstab','Begleiter Tobias','Wanderhut'],
     ['Archangel Raphael', 'Raphael (archangel)']),
    # Kirchenväter und Theologen
    ('Q44248', 'Hl. Hieronymus', 1,
     ['Löwe','Kardinalstracht','Totenkopf','Stein','Buch','Kruzifix'],
     ['Jerome', 'Saint Jerome']),
    ('Q8018', 'Hl. Augustinus', 2,
     ['Flammendes Herz','Bischofsstab','Mitra','Buch','Kind mit Muschel'],
     ['Augustine of Hippo', 'Saint Augustine']),
    ('Q43689', 'Hl. Ambrosius von Mailand', 3,
     ['Bienenkorb','Bischofsstab','Mitra','Buch','Geißel'],
     ['Ambrose', 'Ambrose of Milan', 'Saint Ambrose']),
    ('Q42827', 'Hl. Gregor der Große', 3,
     ['Heiliggeisttaube am Ohr','Papsttiara','Buch','Bischofsstab'],
     ['Pope Gregory I', 'Gregory the Great', 'Saint Gregory the Great']),
    ('Q9438', 'Hl. Thomas von Aquin', 3,
     ['Sonne auf der Brust','Dominikanerkutte','Buch','Lilie','Taube'],
     ['Thomas Aquinas', 'Saint Thomas Aquinas']),
    ('Q70991', 'Hl. Hildegard von Bingen', 3,
     ['Visionen-Flammen','Buch','Bischofsstab (Äbtissin)','Benediktiner-Habit'],
     ['Hildegard of Bingen']),
    ('Q188411', 'Hl. Bernhard von Clairvaux', 3,
     ['Zisterzienser-Habit (weiß)','Drei Mitren zu Füßen','Bienenkorb','Schreibfeder'],
     ['Bernard of Clairvaux']),
    # Ordensgründer
    ('Q676555', 'Hl. Franziskus von Assisi', 1,
     ['Stigmata','Braune Kutte','Strickgürtel','Kruzifix','Tiere (Vögel)','Totenkopf'],
     ['Francis of Assisi', 'Saint Francis of Assisi']),
    ('Q191107', 'Hl. Klara von Assisi', 3,
     ['Monstranz','Klarissen-Habit','Lilie','Kreuzstab'],
     ['Clare of Assisi', 'Saint Clare']),
    ('Q44091', 'Hl. Dominikus', 3,
     ['Hund mit brennender Fackel','Stern','Rosenkranz','Lilie','Schwarz-weißes Ordensgewand'],
     ['Saint Dominic', 'Dominic de Guzman']),
    ('Q44265', 'Hl. Benedikt von Nursia', 3,
     ['Zerbrochenes Glas / Kelch mit Schlange','Rabe mit Brot','Ordensregel (Buch)','Abtsstab','Schwarzes Ordensgewand'],
     ['Benedict of Nursia', 'Saint Benedict']),
    ('Q44281', 'Hl. Ignatius von Loyola', 3,
     ['IHS-Monogramm','Jesuiten-Habit','Buch (Exerzitien)','Strahlennimbus'],
     ['Ignatius of Loyola']),
    ('Q174880', 'Hl. Teresa von Ávila', 3,
     ['Karmeliter-Habit','Pfeil ins Herz','Heiliggeisttaube','Feder'],
     ['Teresa of Avila']),
    ('Q170547', 'Hl. Antonius der Große', 2,
     ['Schwein','Tau-Kreuz (T)','Flammen','Glocke','Dämonen','Mönchsgewand'],
     ['Anthony the Great', 'Saint Anthony the Great', 'Anthony of Egypt']),
    ('Q167477', 'Hl. Antonius von Padua', 2,
     ['Jesuskind (auf dem Arm)','Lilie','Buch','Flamme','Franziskanerkutte'],
     ['Anthony of Padua']),
    # Märtyrer
    ('Q183332', 'Hl. Sebastian', 1,
     ['Pfeile','An Baum/Säule gebunden','Halbnackt (Lendentuch)','Palme','Märtyrerkrone'],
     ['Saint Sebastian']),
    ('Q48438', 'Hl. Georg', 1,
     ['Drache','Ritterrüstung','Lanze','Weißes Pferd','Kreuzfahne','Prinzessin'],
     ['Saint George']),
    ('Q179718', 'Hl. Katharina von Alexandrien', 1,
     ['Rad (zerbrochen)','Schwert','Krone','Buch','Ring','Palme'],
     ['Catherine of Alexandria']),
    ('Q63070', 'Hl. Maria Magdalena', 1,
     ['Salbgefäß','Offenes langes Haar','Totenkopf','Kruzifix','Rotes Gewand'],
     ['Mary Magdalene', 'Saint Mary Magdalene']),
    ('Q133704', 'Hl. Martin von Tours', 1,
     ['Geteilter Mantel','Pferd','Bettler','Gans','Bischofsstab'],
     ['Martin of Tours', 'Saint Martin of Tours']),
    ('Q192816', 'Hl. Barbara', 2,
     ['Turm mit drei Fenstern','Kelch mit Hostie','Krone','Schwert','Palme'],
     ['Saint Barbara', 'Barbara the Great Martyr']),
    ('Q17590', 'Hl. Laurentius', 2,
     ['Bratrost','Dalmatika','Palme','Geldbeutel','Weihrauchgefäß'],
     ['Lawrence of Rome', 'Saint Lawrence']),
    ('Q44269', 'Hl. Nikolaus von Myra', 2,
     ['Drei Goldkugeln','Bischofsstab','Mitra','Drei Kinder im Bottich','Buch'],
     ['Saint Nicholas', 'Nicholas of Myra']),
    ('Q193507', 'Hl. Christophorus', 2,
     ['Jesuskind auf der Schulter','Baumstamm als Stab','Fluss','Riesengröße','Eremitenlampe am Ufer'],
     ['Saint Christopher']),
    ('Q297742', 'Hl. Margareta von Antiochia', 2,
     ['Drache (besiegt)','Aus Drachenbauch hervorkommend','Kreuz / Kreuzstab','Palme','Krone','Perlen'],
     ['Margaret the Virgin', 'Margaret of Antioch']),
    ('Q210096', 'Hl. Agnes', 2,
     ['Lamm','Schwert','Langes Haar','Palme','Ring'],
     ['Agnes of Rome', 'Saint Agnes']),
    ('Q183240', 'Hl. Lucia', 2,
     ['Augen auf Teller','Öllampe','Schwert / Dolch','Palme','Krone','Brennende Kerze'],
     ['Lucy of Syracuse', 'Saint Lucy']),
    ('Q80513', 'Hl. Cäcilia', 2,
     ['Orgel','Musikinstrumente','Rosen','Palme','Krone'],
     ['Saint Cecilia']),
    ('Q161775', 'Hl. Stephanus', 2,
     ['Steine','Dalmatika (Diakontracht)','Palme','Märtyrerkrone','Buch (Evangelium)','Weihrauchgefäß'],
     ['Saint Stephen', 'Stephen the Protomartyr']),
    ('Q159862', 'Hl. Elisabeth von Thüringen', 2,
     ['Rosen','Brot','Krone','Kanne','Arme / Kranke'],
     ['Elizabeth of Hungary']),
    ('Q164294', 'Hl. Anna (Mutter Mariens)', 2,
     ['Maria und Jesuskind (Anna Selbdritt)','Buch','Grünes / rotes Gewand','Kopftuch','Lehrt Maria das Lesen','Goldene Pforte (Begegnung mit Joachim)'],
     ['Saint Anne', 'Anne, mother of Mary']),
    ('Q196653', 'Hl. Veronika', 2,
     ['Schweißtuch Christi (Vera Icon)','Abdruck des Antlitzes Christi','Begegnung am Kreuzweg','Kopftuch'],
     ['Saint Veronica', 'Veronica']),
    # Spezialheilige
    ('Q369691', 'Hl. Ursula', 3,
     ['Pfeile','Krone','Kreuzfahne','Schützender Mantel','Offenes Haar'],
     ['Saint Ursula', 'Ursula of Cologne']),
    ('Q232427', 'Hl. Apollonia', 3,
     ['Zange mit Zahn','Palme','Krone','Buch','Scheiterhaufen'],
     ['Apollonia', 'Saint Apollonia']),
    ('Q242274', 'Hl. Dorothea', 3,
     ['Korb mit Rosen und Äpfeln','Blumenkranz im Haar','Palme','Schwert','Krone','Engelsbote mit Blumen'],
     ['Dorothea of Caesarea', 'Saint Dorothea']),
    ('Q170164', 'Hl. Helena', 3,
     ['Großes Kreuz (Kreuzauffindung)','Kaiserkrone','Nägel','Hermelinmantel','Inschriftentafel INRI'],
     ['Helena, mother of Constantine I', 'Saint Helena']),
    ('Q152457', 'Hl. Rochus', 3,
     ['Pestbeule am Oberschenkel','Hund mit Brot','Pilgerstab','Pilgermuschel','Engel'],
     ['Saint Roch', 'Roch of Montpellier']),
    ('Q218921', 'Hl. Eustachius', 3,
     ['Hirsch mit Kreuz im Geweih','Jägergewand','Hunde','Eherner Stier (Martyrium)','Pferd','Soldatenrüstung'],
     ['Saint Eustace']),
    ('Q159834', 'Hl. Hubertus', 3,
     ['Hirsch mit Kreuz im Geweih','Jagdhund','Jagdhorn','Bischofsstab','Mitra','Kniende Pose (Karfreitags-Vision)'],
     ['Hubertus', 'Saint Hubert']),
    ('Q298845', 'Hl. Florian', 3,
     ['Wassereimer','Brennendes Haus','Rüstung','Mühlstein','Fahne'],
     ['Saint Florian']),
    ('Q2142772', 'Hl. Gereon', 3,
     ['Ritterrüstung','Fahne','Kreuz','Schwert','Kölner Stadtpatron'],
     ['Gereon of Cologne', 'Saint Gereon']),
    ('Q359878', 'Hl. Erasmus', 3,
     ['Winde / Spule mit Gedärmen','Bischofstracht','Mitra','Palme','Schiff / Anker','Buch'],
     ['Saint Erasmus', 'Erasmus of Formia']),
    ('Q316599', 'Hl. Mauritius', 3,
     ['Ritterrüstung','Fahne','Dunkle Hautfarbe','Lanze','Schild mit Mohrenköpfen'],
     ['Saint Maurice', 'Maurice (saint)']),
    ('Q60889', 'Hl. Wolfgang von Regensburg', 3,
     ['Beil im Kirchendach','Kirchenmodell','Bischofsstab','Mitra','Teufel (hilft beim Hausbau)','Buch'],
     ['Wolfgang of Regensburg', 'Saint Wolfgang']),
    ('Q76486', 'Hll. Cosmas und Damian', 3,
     ['Arztinstrumente','Salbentiegel','Mörser','Rotes Gewand','Palme'],
     ['Saints Cosmas and Damian']),
    ('Q57520', 'Hl. Hedwig von Schlesien', 3,
     ['Schuhe in der Hand (Barfuß)','Madonnenstatuette','Herzogskrone','Witwentracht'],
     ['Hedwig of Andechs', 'Hedwig of Silesia']),
    ('Q160445', 'Hl. Bonifatius', 3,
     ['Gefälltes Eichenbaum (Donar-Eiche)','Bischofsstab','Mitra','Buch mit Schwert (Märtyrertod)'],
     ['Saint Boniface', 'Boniface']),
    ('Q221522', 'Hl. Johannes Nepomuk', 3,
     ['Fünf-Sterne-Nimbus','Brücke','Kruzifix in der Hand','Domherrentracht (Priester)'],
     ['John of Nepomuk']),
]

CAT_PATTERNS = [
    "Paintings of {name}",
    "{name} in art",
    "Iconography of {name}",
    "{name}",
]

def api_request(params, delay_on_429=10):
    """Make Wikipedia/Commons API request with retry."""
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    delays = [0, delay_on_429, delay_on_429*3]
    for d in delays:
        if d > 0:
            time.sleep(d)
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            r = urllib.request.urlopen(req, timeout=20)
            return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and d != delays[-1]:
                continue
            return None
    return None

def find_category(search_names):
    """Try multiple category patterns; return first that exists."""
    for name in search_names:
        for pattern in CAT_PATTERNS:
            cat = pattern.format(name=name)
            data = api_request({
                'action': 'query',
                'list': 'categorymembers',
                'cmtitle': f'Category:{cat}',
                'cmtype': 'file',
                'cmlimit': '1',
                'format': 'json',
            })
            if data and data.get('query', {}).get('categorymembers'):
                return cat
    return None

def get_files_in_category(category, limit=15):
    data = api_request({
        'action': 'query',
        'list': 'categorymembers',
        'cmtitle': f'Category:{category}',
        'cmtype': 'file',
        'cmlimit': str(limit),
        'format': 'json',
    })
    if not data:
        return []
    return [m['title'] for m in data.get('query', {}).get('categorymembers', [])]

def parse_filename(filename):
    """Extract artist + title from Commons filename.
    Convention: 'Artist - Title.ext' or 'Title.ext'
    """
    if filename.startswith('File:'):
        filename = filename[5:]
    # Strip extension
    base = re.sub(r'\.(jpg|jpeg|png|gif|tif|tiff|webp)$', '', filename, flags=re.IGNORECASE)
    # Split on " - "
    parts = base.split(' - ')
    if len(parts) >= 2:
        artist = parts[0].strip()
        title = ' - '.join(parts[1:]).strip()
        # Strip WGA prefixes etc.
        title = re.sub(r'\s*-?\s*WGA\d+', '', title)
        title = re.sub(r'\s*Google Art Project.*$', '', title)
        return artist, title
    return 'Unbekannt', base

def special_redirect_url(filename, width=400):
    """Wikimedia Special:Redirect URL."""
    if filename.startswith('File:'):
        filename = filename[5:]
    encoded = urllib.parse.quote(filename.replace(' ', '_'), safe='/_.,()')
    return f"https://commons.wikimedia.org/w/index.php?title=Special:Redirect/fi{'le/'}{encoded}&width={width}"

def js_escape(s):
    return s.replace('\\', '\\\\').replace('"', '\\"')

def build_painting(filename):
    artist, title = parse_filename(filename)
    url = special_redirect_url(filename)
    return f'      {{ img:"{js_escape(url)}", artist:"{js_escape(artist)}", title:"{js_escape(title)}" }},'

def build_saint(qid, name, diff, attrs, paintings):
    attr_str = ','.join(f'"{js_escape(a)}"' for a in attrs)
    lines = [
        '  {',
        f'    saint: "{js_escape(name)}",',
        f'    attributes: [{attr_str}],',
        f'    difficulty: {diff},',
        '    paintings: [',
    ]
    lines.extend(paintings)
    lines.append('    ]')
    lines.append('  },')
    return '\n'.join(lines)

def main():
    delay = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    print(f"Wikimedia Commons fetch for {len(SAINTS_COMMONS)} saints (delay {delay}s)", flush=True)
    print(f"Strategy: find category, list files, extract artist/title from filename\n", flush=True)

    all_blocks = []
    total = 0
    fails = []
    for idx, (qid, name, diff, attrs, search_names) in enumerate(SAINTS_COMMONS):
        if idx > 0:
            time.sleep(delay)
        print(f"[{idx+1:3}/{len(SAINTS_COMMONS)}] {name}", flush=True)
        cat = find_category(search_names)
        if not cat:
            print(f"  -> no category found", flush=True)
            fails.append(name)
            all_blocks.append(build_saint(qid, name, diff, attrs, []))
            continue
        print(f"  category: {cat}", flush=True)
        files = get_files_in_category(cat, limit=12)
        if not files:
            print(f"  -> empty", flush=True)
            fails.append(name)
            all_blocks.append(build_saint(qid, name, diff, attrs, []))
            continue
        # Build painting blocks
        paintings = [build_painting(f) for f in files[:8]]
        print(f"  -> {len(paintings)} paintings", flush=True)
        total += len(paintings)
        all_blocks.append(build_saint(qid, name, diff, attrs, paintings))

    output = 'const SAINTS_DATA = [\n' + '\n'.join(all_blocks) + '\n];\n'
    with open('saints_data_generated.js', 'w') as f:
        f.write(output)

    print(f"\n=== DONE ===", flush=True)
    print(f"Saints: {len(SAINTS_COMMONS)} | Total paintings: {total}", flush=True)
    print(f"No-category-found: {len(fails)}", flush=True)
    for n in fails:
        print(f"  - {n}", flush=True)

if __name__ == '__main__':
    main()
