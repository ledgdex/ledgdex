"""Build the viewer dex with dexweb and publish it to ../docs (GitHub Pages). Run from this folder."""
import glob, os, shutil
from dexweb import dexgen, dexweb

dex = dexgen.Dexgen()
for f in glob.glob('../js/*.js') + ['../js/dexweb-template.json']:  # the modules viewer.js loads
    shutil.copy(f, 'gen')
open(os.path.join('gen', '.nojekyll'), 'w').close()
dexweb.Dexweb().publish()
