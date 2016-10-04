from matrix import view


def noop(*args):
    return ""


def show_row(row):
    return str(row).rstrip() + "\n"


def test_buffered_dict():
    limit = 6
    d = view.BufferedDict(limit)
    assert d.render(noop) == "\n" * (limit - 1)
    d['foo'] = "testing"
    expect = "\n" * (limit - 1) + "testing\n"
    assert d.render(show_row) == expect
