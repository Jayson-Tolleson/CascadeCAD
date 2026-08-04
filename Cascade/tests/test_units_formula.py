from webcad_xbf.formula import evaluate_formula
from webcad_xbf.units import from_mm, normalize_unit, to_mm


def test_unit_aliases_and_conversion():
    assert normalize_unit('inches') == 'in'
    assert to_mm(1, 'ft') == 304.8
    assert from_mm(25.4, 'in') == 1


def test_formula_supports_math_and_units():
    assert round(evaluate_formula('2*pi', default_unit='mm'), 5) == 6.28319
    assert round(evaluate_formula("6' + 25 mm"), 5) == 1853.8
    assert round(evaluate_formula('sqrt(2)', default_unit='in'), 5) == round((2 ** 0.5) * 25.4, 5)
    assert evaluate_formula('pow(2, 3) + max(1, 4)', default_unit='mm') == 12
