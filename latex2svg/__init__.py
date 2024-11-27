#!/usr/bin/env python3
"""latex2svg

Read LaTeX code from stdin and render a SVG using LaTeX, dvisvgm and scour.

Returns a minified SVG with `width`, `height` and `style="vertical-align:"`
attribues whose values are in `em` units. The SVG will have (pseudo-)unique
IDs in case more than one is used on the same HTML page.

Based on [original work](https://github.com/tuxu/latex2svg) by Tino Wagner.
"""

VERSION = "0.0.4"
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

# Modify SVG attributes, to a get a self-contained, scaling SVG
from lxml import etree

# Run optimizer to get a minified oneliner with (pseudo-)unique Ids
# generate random prefix using ASCII letters (ID may not start with a digit)
import random, string

import pyperclip
import argparse

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



    # read SVG, discarding all comments ("<-- Generated by… -->")
    parser = etree.XMLParser(remove_comments=True)
    xml = etree.parse(os.path.join(working_directory, "code.svg"), parser)
    svg = xml.getroot()
    svg.set("width", f"{width:.6f}em")
    svg.set("height", f"{height:.6f}em")
    svg.set("style", f"vertical-align:{-depth:.6f}em")
    xml.write(os.path.join(working_directory, "code.svg"))

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

def ui():
    # Generated thanks to ChatGPT
    import tkinter as tk
    import re
    import idlelib.colorizer as ic
    import idlelib.percolator as ip

    # Function to clear the text box
    def clear_text():
        latex_input.delete("1.0", tk.END)
        latex_input.insert("1.0", DEFAULT_MATH)
        latex_input.mark_set("insert", "%d.%d" % (2, 1))

    def call_latex2svg():
        latex_code = latex_input.get("1.0", tk.END).strip()
        font_size = int(font_size_input.get())
        preamble = default_preamble

        try:
            params = default_params.copy()
            params["preamble"] = preamble
            # Changing the font size in the latex preamble does not impact math size
            # so we need to scale the output SVG instead
            params["scale"] = font_size / 10

            out = latex2svg(latex_code, params)

            pyperclip.copy(out["svg"])
            convert_button.config(text="Copied!", bg="green")
            root.after(500, lambda: convert_button.config(text="Copy", bg="grey"))

        except subprocess.CalledProcessError as exc:
            e = exc.output.decode("utf-8") + exc.stderr.decode("utf-8")

            if latex_code == DEFAULT_MATH:
                e = "Empty math!"

            error_window = tk.Toplevel(root)
            error_window.title("Error")
            
            # Create a frame for the Text widget and scrollbar
            frame = tk.Frame(error_window)
            frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)

            title_label = tk.Label(frame, text="Error!", font=("Arial", 14, "bold"), fg="red")
            title_label.pack(pady=10)

            # Create a Text widget to display the error message
            error_text = tk.Text(frame, wrap=tk.WORD, height=10, width=50, font=("Arial", 12))
            error_text.insert(tk.END, f"Error: {str(e)}")  # Insert the error message
            error_text.config(state=tk.DISABLED)  # Make the text box read-only
            error_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # Create a Scrollbar and link it to the Text widget
            scrollbar = tk.Scrollbar(frame, command=error_text.yview)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            error_text.config(yscrollcommand=scrollbar.set)

            # Create an "OK" button to close the error window
            ok_button = tk.Button(error_window, text="OK", command=error_window.destroy, bg="red", fg="white", font=("Arial", 12))
            ok_button.pack(pady=10)

            # Ensure the error window is modal (blocks interaction with the main window until closed)
            error_window.grab_set()
            error_window.transient(root)
            error_window.mainloop()

    DEFAULT_MATH = """$$

$$"""

    # Create the main window
    root = tk.Tk()
    root.title("Latex to SVG")

    # Add components
    frame = tk.Frame(root, bg="lightgray", padx=10, pady=10)
    frame.grid(row=0, column=0, sticky="nsew")

    # Grid weight configuration to make components scale properly
    root.grid_rowconfigure(0, weight=1)  # Make the main row resizable
    root.grid_columnconfigure(0, weight=1)  # Make the main column resizable

    # Label for title
    title_label = tk.Label(frame, text="LaTeX to SVG", font=("Arial", 24), bg="lightgray")
    title_label.grid(row=0, column=0, pady=10, sticky="nsew")

    # Text box for LaTeX input
    latex_input = tk.Text(frame, height=10, width=40, font=("Courier", 14))
    latex_input.insert("1.0", DEFAULT_MATH)
    latex_input.grid(row=1, column=0, pady=10, sticky="nsew")

    # Frame for font size and clear button
    input_frame = tk.Frame(frame, bg="lightgray")
    input_frame.grid(row=2, column=0, pady=5, sticky="ew")

    # Font Size section
    font_size_label = tk.Label(input_frame, text="Font Size:", bg="lightgray", font=("Arial", 14))
    font_size_label.grid(row=0, column=0, padx=5, sticky="w")

    font_size_input = tk.Entry(input_frame, width=5)
    font_size_input.config(font=("Arial", 14))
    font_size_input.insert(0, "12")
    font_size_input.grid(row=0, column=1, padx=5, sticky="ew")

    # Clear button
    clear_button = tk.Button(input_frame, text="Clear", command=clear_text, bg="grey", fg="white", font=("Arial", 14))
    clear_button.grid(row=0, column=2, padx=5, sticky="ew")

    # Convert button (spans the width of Font Size and Clear buttons)
    convert_button = tk.Button(frame, text="Copy", command=call_latex2svg, bg="grey", fg="white", font=("Arial", 14))
    convert_button.grid(row=3, column=0, pady=5, padx=10, sticky="ew")

    # Configure row and column weight distribution for scaling
    frame.grid_rowconfigure(1, weight=1)  # Allow text box to expand vertically
    frame.grid_rowconfigure(2, weight=0)  # Fixed height for input frame
    frame.grid_rowconfigure(3, weight=0)  # Fixed height for convert button

    # Make columns expand properly for the buttons and inputs
    frame.grid_columnconfigure(0, weight=1)  # Make the main column (text box and buttons) scale horizontally
    input_frame.grid_columnconfigure(0, weight=0)  # Font size label does not scale
    input_frame.grid_columnconfigure(1, weight=1)  # Font size input expands horizontally
    input_frame.grid_columnconfigure(2, weight=1)  # Clear button expands horizontally

    # Run the application
    root.mainloop()

def cli():
    """Simple command line interface to latex2svg.

    - Read LaTeX code from `stdin`.
    - Write SVG to `stdout`.
    - On error: write error messages to `stderr` and return with error code.
    """
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

def main():
    if len(sys.argv) == 1:
        ui()
    else:
        cli()

if __name__ == "__main__":
    main()