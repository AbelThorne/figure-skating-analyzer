from re import sub

class EmptyResultsException(Exception):
    pass

def dictify(df):
    if df is None:
        return None
    else:
        return df.to_dict("index")

def snake_case(s):
  return '_'.join(
    sub('([A-Z][a-z]+)', r' \1',
    sub('([A-Z]+)', r' \1',
    s.replace('-', ' '))).split()).lower()