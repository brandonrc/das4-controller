"""Read the SKiDL/KiCad s-expression netlist (no KiCad needed)."""
import os
import re

NETLIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "das4-controller.net")


def sexp(text):
    """Tiny s-expression parser -> nested lists of strings."""
    tokens = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+', text)
    stack = [[]]
    for t in tokens:
        if t == "(":
            stack.append([])
        elif t == ")":
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(t[1:-1] if t.startswith('"') else t)
    return stack[0][0]


def find(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def one(node, key, default=None):
    f = find(node, key)
    return f[0][1] if f and len(f[0]) > 1 else default


def read_netlist(path):
    root = sexp(open(path).read())
    comps = {}
    for c in find(find(root, "components")[0], "comp"):
        fields = {}
        for fl in find(c, "fields"):
            for f in find(fl, "field"):
                name = one(f, "name")
                fields[name] = f[-1] if isinstance(f[-1], str) else ""
        comps[one(c, "ref")] = {"value": one(c, "value", ""), "footprint": one(c, "footprint", ""),
                                "fields": fields}
    nets = {}
    for n in find(find(root, "nets")[0], "net"):
        nets[one(n, "name")] = [(one(nd, "ref"), one(nd, "pin")) for nd in find(n, "node")]
    return comps, nets
