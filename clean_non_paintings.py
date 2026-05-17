"""Remove non-painting images from SAINTS_DATA.

Wikimedia-Kategorien enthalten oft Bilder die keine Gemälde sind:
Bücher (Vita di X), Statuen-Fotos, Manuskripte, Drucke, etc.
Filter anhand des Dateinamens/Titels."""
import re

# Wenn diese Strings im Dateinamen ODER Titel vorkommen → kein Gemälde
BAD_PATTERNS = [
    r'\bvita\s+d[ie]\b',     # "Vita di santa..."
    r'\blibro\b',
    r'\bbuch\b',
    r'_book_',
    r'cover\.',
    r'_cover',
    r'title[\s_]?page',
    r'\bspine\b',
    r'manuscript',
    r'handschrift',
    r'frontispiece',
    r'stained[\s_-]?glass',
    r'glasfenster',
    r'kirchenfenster',
    r'mosaic',
    r'mosaik',
    r'statue[\s_-]of',
    r'_statue',
    r'\bbust\b',
    r'\bbüste\b',
    r'sculpture',
    r'skulptur',
    r'relief',
    r'reliquary',
    r'reliquar',
    r'coin',
    r'medal\b',
    r'medaille',
    r'engraving',
    r'kupferstich',
    r'_stamp_',
    r'briefmarke',
    r'wallpaper',
    r'\bflag\b',
    r'\bflagge\b',
    r'coat[\s_-]of[\s_-]arms',
    r'wappen',
    r'_arms_',
    r'altar\s*(piece|panel)?\s*\(',  # eher "Foto eines Altars"
    r'church\s*of',
    r'kirche\s+',
    r'kapelle',
    r'pfarrkirche',
    r'kathedrale',
    r'cathedral',
    r'basilica',
    r'monastery',
    r'kloster',
    r'plaque',
    r'gedenktafel',
    r'\bsign\b',
    r'\bschild\b',
    r'_logo',
    r'cdgg2009',  # Wikimedia-spezifische ID-Codes
    r'wga\d+_',   # Auch nicht alle Gemälde
    r'\.gif',     # Animationen
    r'\.svg',     # Vektor-Logos
    r'\.tif',
]

bad_re = re.compile('|'.join(BAD_PATTERNS), re.IGNORECASE)

def is_likely_painting(img_url, title):
    """Heuristik: ist das wahrscheinlich ein Gemälde?"""
    # Test gegen URL + Titel
    combined = (img_url + ' ' + title).lower()
    if bad_re.search(combined):
        return False
    return True

def clean():
    with open('public/index.html') as f:
        html = f.read()
    m = re.search(r'const SAINTS_DATA = \[(.*?)\];', html, re.DOTALL)
    block = m.group(1)
    new_lines = []
    removed = 0
    kept = 0
    examples = []
    for line in block.split('\n'):
        pm = re.search(r'\{\s*img:"([^"]+)",\s*artist:"([^"]+)",\s*title:"([^"]+)"', line)
        if pm:
            img, artist, title = pm.groups()
            if is_likely_painting(img, title):
                new_lines.append(line)
                kept += 1
            else:
                removed += 1
                if len(examples) < 20:
                    examples.append(f"{title[:50]} ({img.split('file/')[-1].split('&')[0][:40]})")
        else:
            new_lines.append(line)
    new_html = html[:m.start(1)] + '\n'.join(new_lines) + html[m.end(1):]
    with open('public/index.html', 'w') as f:
        f.write(new_html)
    print(f"Kept: {kept}")
    print(f"Removed (non-paintings): {removed}")
    print("Examples removed:")
    for e in examples:
        print(f"  - {e}")

if __name__ == '__main__':
    clean()
