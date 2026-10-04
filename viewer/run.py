"""Build the viewer dex with dexweb and publish it to viewer/ in ledgdex/ledgdex.github.io (GitHub Pages:
https://ledgdex.github.io/viewer/). The viewer page is also the dex's index.html, so the viewer is at
https://ledgdex.github.io/viewer/index.html. Run from this folder:  python run.py   (or  python run.py --build-only
to build gen/)."""
import glob, os, shutil, sys
from dexweb import dexgen, dexweb

dex = dexgen.Dexgen()
for f in glob.glob('../js/*.js') + ['../js/dexweb-template.json']:  # the modules viewer.js loads
    shutil.copy(f, 'gen')
shutil.copy(os.path.join('gen', 'viewer.html'), os.path.join('gen', 'index.html'))
open(os.path.join('gen', '.nojekyll'), 'w').close()
if '--build-only' not in sys.argv[1:] and not dexweb.Dexweb().publish():
    sys.exit('the viewer was not published')
