import pytest

from app.services.french_ranking.parser import (
    NL_PREFIX,
    normalize_birth,
    parse_french_ranking,
    split_csv_line,
)


def test_split_csv_line_protege_les_virgules_entre_guillemets():
    assert split_csv_line('a,"b,c",d') == ["a", "b,c", "d"]


def test_normalize_birth_convertit_le_format_francais():
    assert normalize_birth("5/3/2010") == "2010-03-05"
    assert normalize_birth("") == ""
    assert normalize_birth("n/a") == ""


def test_parse_accepte_l_alias_filiere():
    csv = "Nom,Prénom,Licence,Club,Sexe,Naissance,Filière,Région\nDUPONT,Léa,123456,TOULOUSE,F,5/3/2010,Nationale,OCC"
    rows = parse_french_ranking(csv)
    assert len(rows) == 1
    assert rows[0].licence == "123456"
    assert rows[0].last == "DUPONT"
    assert rows[0].first == "Léa"
    assert rows[0].birth == "2010-03-05"
    assert rows[0].filiere_raw == "Nationale"


def test_parse_accepte_l_alias_categorie_ancienne_saison():
    csv = "Nom,Prénom,Licence,Club,Sexe,Naissance,Catégorie,Region\nDUPONT,Léa,123456,TOULOUSE,F,5/3/2010,Nationale,OCC"
    rows = parse_french_ranking(csv)
    assert rows[0].filiere_raw == "Nationale"


def test_parse_ignore_les_lignes_sans_licence_numerique():
    csv = "Nom,Prénom,Licence\nDUPONT,Léa,ABC\nMARTIN,Tom,7890"
    rows = parse_french_ranking(csv)
    assert [r.licence for r in rows] == ["7890"]


def test_parse_normalise_le_sexe():
    csv = "Nom,Prénom,Licence,Sexe\nA,B,1,Homme\nC,D,2,Dame"
    rows = parse_french_ranking(csv)
    assert [r.sex for r in rows] == ["M", "F"]


def test_parse_leve_si_entete_obligatoire_absent():
    with pytest.raises(ValueError):
        parse_french_ranking("Foo,Bar\n1,2")


def test_nl_prefix_marque_les_sans_licence_competition():
    csv = f"Nom,Prénom,Licence,Club\nA,B,1,{NL_PREFIX}TOULOUSE"
    rows = parse_french_ranking(csv)
    assert rows[0].club_name.startswith(NL_PREFIX)
