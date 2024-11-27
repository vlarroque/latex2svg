# latex2svg

Python wrapper and CLI utility to convert LaTeX math to Affinity Designer compatible SVG using
[dvisvgm](https://dvisvgm.de/) and [scour](https://github.com/scour-project/scour).

Based on the [original work](https://github.com/Moonbase59/latex2svg) by Matthias C. Hormann, this version directly copies a Affinity Designer compatible svg to clipboard.

## Installation

Install directly from this repository:

```bash
pip3 install git+https://github.com/vlarroque/latex2svg.git#egg=latex2svg
```

### CLI utility

```
$ latex2svg --help
usage: latex2svg [-h] [-fs FONT_SIZE] latex_code [latex_code ...]

This script converts LaTeX code to SVG using LaTeX, dvisvgm and scour. The resulting SVG is copied to the clipboard.

positional arguments:
  latex_code

options:
  -h, --help            show this help message and exit
  -fs FONT_SIZE, --font-size FONT_SIZE
                        Latex font size (default: 12.000000)
```

Exemples:
```
$ latex2svg "$$L_o = L_e + \int_{\Omega} L_i \cdot f_r \cdot \cos \theta \, \text{d}\omega$$"
$ latex2svg "$H(X) = - \sum_{x \in \mathcal{X}} p(x) \log_2 p(x)$" -fs 16
```

## Requirements

- Python 3
- A working LaTeX installation, like _Tex Live_
- [dvisvgm](https://dvisvgm.de/) (likely installed with LaTeX)
- [ghostscript](https://www.ghostscript.com/) version < [`10.01.0`](https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/tag/gs1000)

dvisvgm as an [issue](https://dvisvgm.de/Manpage/) on version > `10.01.0` when using the `--pdf` option.

## Licence

This project is based on work originally created by Matthias C. Hormann and licensed under the MIT license. See [LICENSE](LICENSE) for details.

Contributions and modifications made by vlarroque are dedicated to the public domain. You may use, modify, and distribute them freely, without restriction.

Copyright © 2022 Matthias C. Hormann
Additional contributions © 2024 vlarroque
