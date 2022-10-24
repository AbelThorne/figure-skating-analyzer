import pdfplumber
import pandas as pd
import numpy as np
from parsers.common import EmptyResultsException, dictify, snake_case

def parse_upper_rect(page, rect):
    header_words = ["Rank", "Name", "Nation", "Starting", "Segment", "Element", "Program", "Deductions"]
    cropped = page.crop(pdfplumber.utils.objects_to_bbox([rect]))
    words = cropped.extract_words()
    v_lines = [rect["x0"]] + [[w for w in words if w["text"] == header][0]["x0"] - 5 for header in header_words[1:]] + [rect["x1"]]
    h_lines = [ [w for w in words if w["text"] == "Score"][0]["bottom"] + 1, rect["bottom"] ]
    rows = cropped.extract_table({
        "explicit_vertical_lines": v_lines,
        "explicit_horizontal_lines": h_lines, 
        "vertical_strategy": "explicit",        
        "horizontal_strategy": "explicit",        
    })
    assert len(rows) == 1
    bonification = False
    try:
        rows[0][4] = float(rows[0][4])
        rows[0][6] = float(rows[0][6])
        rows[0][7] = float(rows[0][7])
        rows[0][5] = float(rows[0][5])        
    except ValueError:
        if rows[0][5][-1] == 'B':
            rows[0][5] = float(rows[0][5][:-1])
            bonification = True
        else:
            raise

    # Bonification column
    rows[0].append(bonification)
    series = pd.Series(dict(zip([
        "rank",
        "name",
        "nation",
        "starting_number",
        "total_segment_score",
        "total_element_score",
        "total_component_score",
        "total_deductions",
        "bonifications"
    ], rows[0])))
    return series

def parse_elements(page, rect, bonifications:bool):
    header_words = ["#", "Executed", "ofnI", "Base", "GOE", "J1", "J2", "J3", "J4", "J5", "J6", "J7", "J8", "J9", "Ref", "Scores"]
    cropped = page.crop(pdfplumber.utils.objects_to_bbox([rect]))
    words = cropped.extract_words()
    v_lines = [rect["x0"]] + [ [w for w in words if w["text"] == header][0]["x0"] - 8 for header in header_words[1:] ] + [rect["x1"]]
    v_lines = v_lines[:4] + [v_lines[4]+7] + v_lines[4:]
    h_start = [ w for w in words if w["text"] == "Elements" ][0]["bottom"] + 1
    h_end = [ w for w in words if w["text"] == "Components" ][0]["top"] - 1
    center = cropped.crop((rect["x0"], h_start, rect["x1"], h_end))
    tops =  [ x[0]["top"] for x in pdfplumber.utils.cluster_objects(center.chars, "top", 0) ]
    h_lines = tops + [ h_end ]

    table_settings = {
        "explicit_vertical_lines": v_lines,
        "explicit_horizontal_lines": h_lines,
        "vertical_strategy": "explicit",        
        "horizontal_strategy": "explicit",        
    }
    # return table_settings
    rows = page.extract_table(table_settings)
    df = pd.DataFrame(rows, columns=[
            "element_num",
            "element_desc",
            "info_flag",
            "base_value",
            "credit_flag",
            "goe",
            "J1",
            "J2",
            "J3",
            "J4",
            "J5",
            "J6",
            "J7",
            "J8",
            "J9",
            "ref",
            "scores_of_panel"
        ])\
            .replace("-", np.nan)\
            .replace("", np.nan)

    assert (df["base_value"].astype(float).pipe(lambda x: 2*x.iloc[-1]) - df["base_value"].astype(float).pipe(lambda x: x.sum())).round(3) == 0
    panel_score = df["scores_of_panel"].astype(float).pipe(lambda x: 2*x.iloc[-1])
    element_sum  = df["scores_of_panel"].astype(float).pipe(lambda x: x.sum())
    if not bonifications:
        assert (panel_score - element_sum).round(3) == 0
    
    for i in range(9):
        colname = "J{}".format(i + 1)
        df[colname] = df[colname].astype(float)
    
    for colname in [ "base_value", "goe", "scores_of_panel" ]:
        df[colname] = df[colname].astype(float)
    df["num"] = df["element_num"]
    df.iloc[-1, -1] = "total"
    df.set_index("num", inplace=True)    
    
    return df, (panel_score - element_sum).round(3)


def parse_program_components(page, rect):
    header_words = ["Program", "Factor", "J1", "J2", "J3", "J4", "J5", "J6", "J7", "J8", "J9", "Ref", "Scores"]
    cropped = page.crop(pdfplumber.utils.objects_to_bbox([rect]))
    words = cropped.extract_words()
    v_lines = [rect["x0"]] + [ [w for w in words if w["text"] == header][0]["x0"] - 8 for header in header_words[1:] ] + [rect["x1"]]
    h_start = [ w for w in words if w["text"] == "Program" ][0]["bottom"] + 1
    center = cropped.crop((rect["x0"], h_start, rect["x1"], rect["bottom"]))
    tops =  [ x[0]["top"] for x in pdfplumber.utils.cluster_objects(center.chars, "top", 0) ]
    h_lines = tops + [ rect["bottom"] ]
            
    table_settings = {
        "explicit_vertical_lines": v_lines,
        "explicit_horizontal_lines": h_lines,
        "vertical_strategy": "explicit",        
        "horizontal_strategy": "explicit",        
    }
    rows = page.extract_table(table_settings)
    
    df = pd.DataFrame(rows, columns=[
        "component_desc",
        "factor",
        "J1",
        "J2",
        "J3",
        "J4",
        "J5",
        "J6",
        "J7",
        "J8",
        "J9",
        "ref",
        "scores_of_panel"
    ])\
        .replace("-", np.nan)\
        .replace("", np.nan)
    
    total_score = df.iloc[:-1]\
        .pipe(lambda x: x["scores_of_panel"].astype(float) * x["factor"].astype(float)).sum()

    parsed_score = float(df.iloc[-1]["scores_of_panel"])
    assert total_score - parsed_score < 0.1
    
    df = df.iloc[:-1].copy()

    for i in range(9):
        colname = "J{}".format(i + 1)
        df[colname] = df[colname].astype(float)
    
    for colname in [ "factor", "scores_of_panel" ]:
        df[colname] = df[colname].astype(float)
    
    df["component"] = df["component_desc"].map(snake_case)
    df.set_index("component", inplace=True)    
        
    return df

def parse_page(page):
    rects = list(sorted(page.rects, key=lambda x: x["doctop"]))

    if len(rects) == 0:
        raise EmptyResultsException

    assert len(rects) % 3 == 0
    results = []
    for i in range(len(rects) // 3):
        metadata = parse_upper_rect(page, rects[i*3]).to_dict()
        elements, bonifications = parse_elements(page, rects[i*3 + 1], metadata["bonifications"])
        metadata["bonifications"] = bonifications
        components = parse_program_components(page, rects[i*3 + 1])
        results.append({
            "metadata": metadata,
            "elements": dictify(elements),
            "components": dictify(components)
        })
    return results
