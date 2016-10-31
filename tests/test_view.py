import collections
from matrix import view
import urwid


def render_row(row):
    return urwid.Text("{} {}".format(row["name"], row["status"]))


def test_dict_widget():
    tasks = collections.OrderedDict()
    tasks["alpha"] = {"name": "alpha", "value": "This is alpha", "status": "running"}
    tasks["beta"] = {"name": "beta", "value": "This is beta", "status": "pending"}

    task_walker = view.SimpleDictValueWalker(
            tasks,
            key_func=lambda o: o["name"],
            widget_func=render_row)

    assert task_walker[0].text == "alpha running"
    assert task_walker[1].text == "beta pending"
    assert task_walker["alpha"].text == "alpha running"
    assert task_walker["beta"].text == "beta pending"


def test_list_widget():
    status = [str(i) for i in range(10)]
    status_walker = view.SimpleListRenderWalker(status)
    assert status_walker[0].text == "0"
    assert status_walker[1].text == "1"
