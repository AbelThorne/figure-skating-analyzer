import pdfplumber
import re
import glob
import sys
import os
from pathlib import Path
from parsers.common import EmptyResultsException
from parsers.standard import parse_page as parse_standard

def parse_page(page, context=None):
    """
    This function takes a page object, checks whether there
    are any score sheets on the page, and the parsed out the 
    structured score data from each score sheet
    """

    try:
        text = page.extract_text()

    # If pdfplumber cannot read the page, we note it in the parsing log.
    except Exception:
        sys.stderr.write("*** CANNOT READ ***")
        return None

    # For some pages -- often the graphical cover pages -- pdfplumber
    # can't find any text. We skip over those, and note them in
    # the parsing log.
    if text is None or len(text) == 0:
        sys.stderr.write("*** CANNOT FIND ANY TEXT ***")
        return None

    # All the score sheets should have "JUDGES DETAILS PER SKATER"
    # on the page. If a page doesn't, we continue to the next page.
    if "JUDGES DETAILS PER SKATER" not in text:
        sys.stderr.write("-")
        return None

    parser = parse_standard

    try:
        parsed = parser(page)

    # A few pages of the protocol PDFs have headers that make it
    # look like they'd contain score sheets, but don't. You can
    # check the parsing log to see which these are.
    except EmptyResultsException:
        sys.stderr.write("*** CAN'T FIND PERFORMANCES ON PAGE ***")
        return None

    # If we got this far, we've been able to locate, and parse the
    # score sheets on this page.
    sys.stderr.write("+")

    # Here, we extract the competition and program names,
    # and add them to the parsed data.
    program = text.split("\n")[0]
    program = re.sub(r"\s+JUDGES DETAILS PER SKATER", "", program).strip()

    if context is not None:
        for result in parsed:
            result["metadata"]["season"] = context["season"]
            result["metadata"]["competition"] = context["competition"]
            result["metadata"]["city"] = context["city"]
            result["metadata"]["type"] = context["type"]
            result["metadata"]["start"] = context["start"]
            result["metadata"]["end"] = context["end"]
            result["metadata"]["program"] = program

    return parsed

def parse_pdf(pdf, context=None):
    """
    This function takes a PDF object, iterates through
    each page, and returns structured data representing for 
    each score sheet it has found.
    """
    performances = []
    for i, page in enumerate(pdf.pages):
        sys.stderr.flush()
        sys.stderr.write("\nPage {:03d}: ".format(i + 1))
        parsed = parse_page(page, context)
        if parsed is None: continue
        performances += parsed

    sys.stderr.write("\n")
    return performances

def parse_pdf_from_path(path, context=None):
    try:
        with pdfplumber.open(path) as pdf:
            return {
                "performances": parse_pdf(pdf, context),
                "pdf": path.name
            }

    except pdfplumber.pdfminer.pdfparser.PDFSyntaxError as e:
            sys.stderr.write("*** IS REAL PDF?: {}\n".format(path))

if __name__ == "__main__":
    import json
    dest_dir = Path("output/json")
    # args = sys.argv[1:]
    args = ["/Users/julien/Library/Mobile Documents/com~apple~CloudDocs/Patin/Compétitions/Saison 2021-2022"]
    season_path = Path(args[0])
    context = {}
    context["season"] = season_path.name
    competitions = [f for f in Path(args[0]).iterdir() if f.is_dir()]
    for i, comp in enumerate(competitions):
        paths = comp.glob("*.pdf")
        with open(comp.joinpath("infos.json"), "r") as f:
            infos = json.load(f)
            context["competition"] = infos["competition"]
            context["city"] = infos["city"]
            context["type"] = infos["type"]
            context["start"] = infos["start"]
            context["end"] = infos["end"]

        if not dest_dir.joinpath(comp.name).is_dir():
            Path.mkdir(dest_dir.joinpath(comp.name), parents=True)
        for path in paths:
            fname = path.name
            sys.stderr.write("\n--- {} ---\n".format(fname))
            parsed = parse_pdf_from_path(path, context)
            dest = dest_dir.joinpath(path.parents[0].name, fname[:-4] + ".json")
            with open(dest, "w") as f:
                json.dump(parsed, f, sort_keys=True, indent=2)
