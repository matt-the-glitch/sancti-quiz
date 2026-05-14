"""Find Wikidata Q-IDs by looking up the German Wikipedia article for each saint.

Each Wikipedia article has a Wikidata link (page_props.wikibase_item) — this is
the authoritative way to find Q-IDs without hallucination.
"""
import urllib.request
import urllib.parse
import urllib.error
import json
import time
import re

HEADERS = {'User-Agent': 'SanctiQuiz/1.0'}

# (de_name, wikipedia_article_title_de)
# These article titles are the actual German Wikipedia URLs.
SAINTS_WIKI = [
    # Heilige Familie
    ('Maria (Mutter Jesu)', 'Maria (Mutter Jesu)'),
    ('Jesus Christus', 'Jesus von Nazaret'),
    ('Hl. Joseph', 'Josef von Nazaret'),
    ('Hl. Joachim', 'Joachim (Heiliger)'),
    ('Hl. Elisabeth (Mutter Johannes\' d. Täufers)', 'Elisabet (Mutter Johannes des Täufers)'),
    # Apostel
    ('Hl. Petrus', 'Simon Petrus'),
    ('Hl. Paulus', 'Paulus von Tarsus'),
    ('Johannes der Täufer', 'Johannes der Täufer'),
    ('Hl. Thomas (Apostel)', 'Thomas (Apostel)'),
    ('Hl. Jakobus der Ältere', 'Jakobus der Ältere'),
    ('Hl. Andreas', 'Andreas (Apostel)'),
    ('Hl. Bartholomäus', 'Bartholomäus (Apostel)'),
    ('Hl. Jakobus der Jüngere', 'Jakobus der Jüngere'),
    ('Hl. Philippus (Apostel)', 'Philippus (Apostel)'),
    ('Hl. Judas Thaddäus', 'Judas Thaddäus'),
    # Evangelisten
    ('Hl. Matthäus (Evangelist)', 'Matthäus (Apostel)'),
    ('Hl. Markus (Evangelist)', 'Markus (Evangelist)'),
    ('Hl. Lukas (Evangelist)', 'Lukas (Evangelist)'),
    ('Hl. Johannes (Evangelist)', 'Johannes (Apostel)'),
    # Erzengel
    ('Erzengel Michael', 'Michael (Erzengel)'),
    ('Erzengel Gabriel', 'Gabriel (Erzengel)'),
    ('Erzengel Raphael', 'Raphael (Erzengel)'),
    # Kirchenväter / Theologen
    ('Hl. Hieronymus', 'Hieronymus (Kirchenvater)'),
    ('Hl. Augustinus', 'Augustinus von Hippo'),
    ('Hl. Ambrosius von Mailand', 'Ambrosius von Mailand'),
    ('Hl. Gregor der Große', 'Gregor der Große'),
    ('Hl. Thomas von Aquin', 'Thomas von Aquin'),
    ('Hl. Hildegard von Bingen', 'Hildegard von Bingen'),
    ('Hl. Bernhard von Clairvaux', 'Bernhard von Clairvaux'),
    # Ordensgründer / Mystiker
    ('Hl. Franziskus von Assisi', 'Franz von Assisi'),
    ('Hl. Klara von Assisi', 'Klara von Assisi'),
    ('Hl. Dominikus', 'Dominikus'),
    ('Hl. Benedikt von Nursia', 'Benedikt von Nursia'),
    ('Hl. Ignatius von Loyola', 'Ignatius von Loyola'),
    ('Hl. Teresa von Ávila', 'Teresa von Ávila'),
    ('Hl. Antonius der Große', 'Antonius der Große'),
    ('Hl. Antonius von Padua', 'Antonius von Padua'),
    # Märtyrer
    ('Hl. Sebastian', 'Sebastian (Heiliger)'),
    ('Hl. Georg', 'Georg (Heiliger)'),
    ('Hl. Katharina von Alexandrien', 'Katharina von Alexandrien'),
    ('Hl. Maria Magdalena', 'Maria Magdalena'),
    ('Hl. Martin von Tours', 'Martin von Tours'),
    ('Hl. Barbara', 'Barbara von Nikomedien'),
    ('Hl. Laurentius', 'Laurentius von Rom'),
    ('Hl. Nikolaus von Myra', 'Nikolaus von Myra'),
    ('Hl. Christophorus', 'Christophorus'),
    ('Hl. Margareta von Antiochia', 'Margareta von Antiochia'),
    ('Hl. Agnes', 'Agnes von Rom'),
    ('Hl. Lucia', 'Lucia von Syrakus'),
    ('Hl. Cäcilia', 'Cäcilia von Rom'),
    ('Hl. Stephanus', 'Stephanus'),
    ('Hl. Elisabeth von Thüringen', 'Elisabeth von Thüringen'),
    ('Hl. Anna (Mutter Mariens)', 'Anna (Heilige)'),
    ('Hl. Veronika', 'Veronika (Heilige)'),
    # Spezialheilige
    ('Hl. Ursula', 'Ursula (Heilige)'),
    ('Hl. Apollonia', 'Apollonia von Alexandria'),
    ('Hl. Dorothea', 'Dorothea von Caesarea'),
    ('Hl. Helena (Mutter Konstantins)', 'Helena (Mutter Konstantins des Großen)'),
    ('Hl. Rochus', 'Rochus von Montpellier'),
    ('Hl. Eustachius', 'Eustachius (Heiliger)'),
    ('Hl. Hubertus', 'Hubertus von Lüttich'),
    ('Hl. Florian', 'Florian von Lorch'),
    ('Hl. Gereon', 'Gereon von Köln'),
    ('Hl. Erasmus', 'Erasmus von Antiochia'),
    ('Hl. Mauritius', 'Mauritius (Heiliger)'),
    ('Hl. Wolfgang von Regensburg', 'Wolfgang von Regensburg'),
    ('Hll. Cosmas und Damian', 'Cosmas und Damian'),
    ('Hl. Hedwig von Schlesien', 'Hedwig von Andechs'),
    ('Hl. Bonifatius', 'Bonifatius'),
    ('Hl. Johannes Nepomuk', 'Johannes Nepomuk'),
]

def lookup_qid(article_title):
    """Get Wikidata Q-ID via pageprops.wikibase_item, with redirect following + retry."""
    delays = [0, 3, 10, 30]
    for d in delays:
        if d > 0:
            time.sleep(d)
        try:
            url = (
                f"https://de.wikipedia.org/w/api.php?action=query"
                f"&titles={urllib.parse.quote(article_title)}"
                f"&prop=pageprops&ppprop=wikibase_item"
                f"&redirects=1&format=json"
            )
            req = urllib.request.Request(url, headers=HEADERS)
            resp = urllib.request.urlopen(req, timeout=20)
            data = json.loads(resp.read())
            pages = data.get('query', {}).get('pages', {})
            for page_id, page in pages.items():
                if page_id == '-1' or 'missing' in page:
                    return None, page.get('title', article_title)
                qid = page.get('pageprops', {}).get('wikibase_item')
                resolved_title = page.get('title', article_title)
                return qid, resolved_title
            return None, article_title
        except urllib.error.HTTPError as e:
            if e.code == 429 and d != delays[-1]:
                continue
            return None, f"HTTP {e.code}"
        except Exception as e:
            return None, f"ERR {e}"
    return None, "max retries"

def main():
    print(f"Looking up {len(SAINTS_WIKI)} saints via German Wikipedia...\n")
    results = []
    for idx, (de_name, article) in enumerate(SAINTS_WIKI):
        if idx > 0:
            time.sleep(1.5)
        qid, resolved = lookup_qid(article)
        if qid:
            print(f"[{idx+1:3}/{len(SAINTS_WIKI)}] OK   {qid:<10} {de_name[:42]:<42} (article: {resolved})", flush=True)
            results.append((qid, de_name, resolved))
        else:
            print(f"[{idx+1:3}/{len(SAINTS_WIKI)}] FAIL ???        {de_name[:42]:<42} ({resolved})", flush=True)
            results.append((None, de_name, resolved))

    # Save
    with open('qid_final.txt', 'w') as f:
        for qid, de_name, article in results:
            f.write(f"{qid or 'MISSING'}\t{de_name}\t{article}\n")

    ok = sum(1 for r in results if r[0])
    print(f"\n=== {ok}/{len(SAINTS_WIKI)} resolved ===", flush=True)
    print(f"Saved to qid_final.txt", flush=True)

if __name__ == '__main__':
    main()
