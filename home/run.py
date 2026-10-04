"""Build the home dex with dexweb and publish it to the root of ledgdex/ledgdex.github.io (GitHub Pages:
https://ledgdex.github.io): the home page, Live Markets and About. The viewer is in viewer/ there (../viewer), and the
docs in docs/ (../guide/dex). Run from this folder:  python run.py   (or  python run.py --build-only  to build gen/)."""
import os, sys
from dexweb import dexgen, dexweb

dex = dexgen.Dexgen()
open(os.path.join('gen', '.nojekyll'), 'w').close()
if '--build-only' not in sys.argv[1:] and not dexweb.Dexweb().publish():
    sys.exit('the home dex was not published')
