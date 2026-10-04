"""Build the viewer dex with dexweb and publish it to the root of ledgdex/ledgdex.github.io (GitHub Pages:
https://ledgdex.github.io). Run from this folder:  python run.py   (or  python run.py --build-only  to build gen/)."""
import glob, os, shutil, sys
from dexweb import dexgen, dexweb

dex = dexgen.Dexgen()
for f in glob.glob('../js/*.js') + ['../js/dexweb-template.json']:  # the modules viewer.js loads
    shutil.copy(f, 'gen')
open(os.path.join('gen', '.nojekyll'), 'w').close()
if '--build-only' not in sys.argv[1:] and not dexweb.Dexweb().publish():
    sys.exit('the viewer was not published')
