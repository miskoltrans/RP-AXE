"""Read the install's ModuleManager.ConfigCache — the *patched* part database.

Part-level ground truth: RO/RA/Kerbalism rewrite almost every field, so the source .cfg in a mod
folder is not what the game runs. Anything that decides a mission (antenna gain, RTG output,
engine Isp) must be read from here.
"""
import re
import sys

CACHE = r"C:/git/ksp/Instance/GameData/ModuleManager.ConfigCache"


def _tokenize(text):
    depth = 0
    start = 0
    for m in re.finditer(r"[{}]", text):
        if m.group(0) == "{":
            if depth == 0:
                start = m.start()
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                yield text[start:m.end()]


class Node:
    __slots__ = ("name", "values", "pairs", "nodes")

    def __init__(self, name):
        self.name = name
        self.values = {}
        self.pairs = []   # keeps repeated keys (atmosphereCurve `key = ...`, RESOURCE lists)
        self.nodes = []

    def all(self, key):
        return [v for k, v in self.pairs if k == key]

    def get(self, key, default=None):
        return self.values.get(key, default)

    def find(self, name):
        return [n for n in self.nodes if n.name == name]

    def first(self, name):
        for n in self.nodes:
            if n.name == name:
                return n
        return None

    def __repr__(self):
        return f"<{self.name} {len(self.values)}v {len(self.nodes)}n>"


def parse_block(lines, i, name):
    """lines[i] is the '{' line."""
    node = Node(name)
    i += 1
    while i < len(lines):
        s = lines[i].strip()
        if s == "}":
            return node, i + 1
        if s == "{" or not s:
            i += 1
            continue
        # a node header may be followed by blank lines before its brace (MM emits these)
        k = i + 1
        while k < len(lines) and not lines[k].strip():
            k += 1
        if k < len(lines) and lines[k].strip() == "{" and "=" not in s:
            child, i = parse_block(lines, k, s)
            node.nodes.append(child)
            continue
        if "=" in s:
            k, v = s.split("=", 1)
            node.values[k.strip()] = v.strip()
            node.pairs.append((k.strip(), v.strip()))
        i += 1
    return node, i


def load_parts(cache=CACHE, want_modules=None):
    """Yield UrlConfig PART nodes. want_modules: only parts having one of these MODULE names."""
    txt = open(cache, encoding="utf-8", errors="replace").read()
    lines = txt.split("\n")
    parts = []
    i = 0
    n = len(lines)
    while i < n:
        s = lines[i].strip()
        if s == "UrlConfig":
            node, i = parse_block(lines, i + 1, s)
            p = node.first("PART")
            if p is not None:
                if want_modules:
                    names = {m.get("name") for m in p.find("MODULE")}
                    if not (names & set(want_modules)):
                        continue
                parts.append(p)
            continue
        i += 1
    return parts


if __name__ == "__main__":
    mods = sys.argv[1:] or ["ModuleRealAntenna"]
    ps = load_parts(want_modules=mods)
    print(f"{len(ps)} parts with {mods}")
    for p in ps[:10]:
        print(p.get("name"), "|", p.get("title"), "|", p.get("TechRequired"))
