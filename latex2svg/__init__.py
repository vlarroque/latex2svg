#!/usr/bin/env python3
"""latex2svg

Read LaTeX code from stdin and render a SVG using LaTeX, dvisvgm and scour.

Returns a minified SVG with `width`, `height` and `style="vertical-align:"`
attribues whose values are in `em` units. The SVG will have (pseudo-)unique
IDs in case more than one is used on the same HTML page.

Based on [original work](https://github.com/tuxu/latex2svg) by Tino Wagner.
"""

VERSION = "0.0.2"
__version__ = VERSION
__author__ = "vlarroque"
__email__ = ""
__license__ = "No License / Public Domain"
__copyright__ = "Contributions (c) 2024, vlarroque"

import os
import sys
import subprocess
import shlex
import re
from tempfile import TemporaryDirectory
from ctypes.util import find_library

default_template = r"""
\documentclass[preview]{standalone}
\usepackage{amsmath}
\usepackage{amsfonts}
{{ preamble }}
\begin{document}
\begin{preview}
{{ code }}
\end{preview}
\end{document}
"""

default_preamble = r"""
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{amsmath}
"""

latex_cmd = "pdflatex -interaction nonstopmode -halt-on-error"
dvisvgm_cmd = "dvisvgm --pdf --no-fonts --exact-bbox"
scour_cmd = (
    'scour --shorten-ids --shorten-ids-prefix="{{ prefix }}" '
    "--no-line-breaks --remove-metadata --enable-comment-stripping "
    "--strip-xml-prolog -i {{ infile }} -o {{ outfile }}"
)

default_params = {
    "fontsize": 12,  # TeX pt
    "template": default_template,
    "preamble": default_preamble,
    "latex_cmd": latex_cmd,
    "dvisvgm_cmd": dvisvgm_cmd,
    "scale": 1.0,  # default extra scaling (done by dvisvgm)
    "scour_cmd": scour_cmd,
    "optimizer": "scour",
    "libgs": None,
}


def latex2svg(code, params=default_params, working_directory=None):
    """Convert LaTeX to SVG using dvisvgm and scour (or svgo).

    Parameters
    ----------
    code : str
        LaTeX code to render.
    params : dict
        Conversion parameters.
    working_directory : str or None
        Working directory for external commands and place for temporary files.

    Returns
    -------
    dict
        Dictionary of SVG output and output information:

        * `svg`: SVG data
        * `width`: image width in *em*
        * `height`: image height in *em*
        * `valign`: baseline offset in *em*
    """
    if working_directory is None:
        with TemporaryDirectory() as tmpdir:
            return latex2svg(code, params, working_directory=tmpdir)

    # Caution: TeX & dvisvgm work with TeX pt (1/72.27"), but we need DTP pt (1/72")
    # so we need a scaling factor for correct output sizes
    # dvisvgm will produce a viewBox in DTP pt but SHOW TeX pt in its output.
    scaling = 1.00375  # (1/72)/(1/72.27)

    fontsize = params["fontsize"]
    document = (
        params["template"]
        .replace("{{ preamble }}", params["preamble"])
        .replace("{{ fontsize }}", str(fontsize))
        .replace("{{ code }}", code)
    )

    with open(os.path.join(working_directory, "code.tex"), "w") as f:
        f.write(document)

    # Run LaTeX and create DVI file
    try:
        ret = subprocess.run(
            shlex.split(params["latex_cmd"] + " code.tex"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=working_directory,
        )
        ret.check_returncode()
    except FileNotFoundError:
        raise RuntimeError("latex not found")

    # Add LIBGS to environment if supplied
    env = os.environ.copy()

    # Convert DVI to SVG
    dvisvgm_cmd = params["dvisvgm_cmd"] + " --scale=%f" % params["scale"]
    dvisvgm_cmd += " code.pdf"
    try:
        ret = subprocess.run(
            shlex.split(dvisvgm_cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=working_directory,
            env=env,
        )
        ret.check_returncode()
    except FileNotFoundError:
        raise RuntimeError("dvisvgm not found")

    # Parse dvisvgm output for size and alignment
    def get_size(output):
        regex = r"\b([0-9.]+)pt x ([0-9.]+)pt"
        match = re.search(regex, output)
        if match:
            return (
                float(match.group(1)) / fontsize * scaling,
                float(match.group(2)) / fontsize * scaling,
            )
        else:
            return None, None

    def get_measure(output, name):
        regex = r"\b%s=([0-9.e-]+)pt" % name
        match = re.search(regex, output)
        if match:
            return float(match.group(1)) / fontsize * scaling
        else:
            return None

    output = ret.stderr.decode("utf-8")
    width, height = get_size(output)
    depth = get_measure(output, "depth")
    # no baseline offset if depth not found
    if depth is None:
        depth = 0.0

    # Modify SVG attributes, to a get a self-contained, scaling SVG
    from lxml import etree

    # read SVG, discarding all comments ("<-- Generated by… -->")
    parser = etree.XMLParser(remove_comments=True)
    xml = etree.parse(os.path.join(working_directory, "code.svg"), parser)
    svg = xml.getroot()
    svg.set("width", f"{width:.6f}em")
    svg.set("height", f"{height:.6f}em")
    svg.set("style", f"vertical-align:{-depth:.6f}em")
    xml.write(os.path.join(working_directory, "code.svg"))

    # Run optimizer to get a minified oneliner with (pseudo-)unique Ids
    # generate random prefix using ASCII letters (ID may not start with a digit)
    import random, string

    prefix = "".join(random.choice(string.ascii_letters) for n in range(3))
    # with scour, input & output files must be different
    scour_cmd = (
        params["scour_cmd"]
        .replace("{{ prefix }}", prefix + "_")
        .replace("{{ infile }}", "code.svg")
        .replace("{{ outfile }}", "optimized.svg")
    )

    # optimize SVG using scour (default)
    try:
        ret = subprocess.run(
            shlex.split(scour_cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=working_directory,
            env=env,
        )
        ret.check_returncode()
    except FileNotFoundError:
        print("scour not found, using unoptimized SVG", file=sys.stderr)
        with open(os.path.join(working_directory, "code.svg"), "r") as f:
            svg = f.read()

    with open(os.path.join(working_directory, "optimized.svg"), "r") as f:
        svg = f.read()

    return {
        "svg": svg,
        "valign": round(-depth, 6),
        "width": round(width, 6),
        "height": round(height, 6),
    }


def main():
    """Simple command line interface to latex2svg.

    - Read LaTeX code from `stdin`.
    - Write SVG to `stdout`.
    - On error: write error messages to `stderr` and return with error code.
    """
    import pyperclip
    import argparse

    parser = argparse.ArgumentParser(
        description="""
    This script converts LaTeX code to SVG using LaTeX, dvisvgm and scour. The resulting SVG is copied to the clipboard.
    """
    )
    parser.add_argument(
        "-fs",
        "--font-size",
        type=int,
        default=12,
        help="Latex font size (default: %(default)f)",
    )
    parser.add_argument("latex_code", nargs="+")

    args = parser.parse_args()
    preamble = default_preamble
    latex = " ".join(args.latex_code)
    try:
        params = default_params.copy()
        params["preamble"] = preamble
        # Changing the font size in the latex preamble does not impact math size
        # so we need to scale the output SVG instead
        params["scale"] = args.font_size / 10

        out = latex2svg(latex, params)

        pyperclip.copy(out["svg"])
        print("SVG copied to clipboard")

    except subprocess.CalledProcessError as exc:
        # LaTeX prints errors on stdout instead of stderr (stderr is empty),
        # dvisvgm to stderr, so print both (to stderr)
        print(exc.output.decode("utf-8"), file=sys.stderr)
        print(exc.stderr.decode("utf-8"), file=sys.stderr)
        sys.exit(exc.returncode)


if __name__ == "__main__":
    main()
