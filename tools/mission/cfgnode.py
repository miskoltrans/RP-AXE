"""Minimal KSP ConfigNode reader, with the game's own splitting rules.

Two rules matter and both bite silently if you get them wrong:

  * KSP splits an assignment at the FIRST '=' and keeps one key per line. A line
    carrying two pairs is not two keys -- the game takes the first and drops the
    rest without a word. This parser does the same rather than being helpful,
    so a config that is broken in game reads as broken here.
  * A key may legitimately repeat inside one node (targetBody, situation, ...),
    so values are a list, never a dict.
"""


class Node:
    __slots__ = ("name", "values", "children", "parent")

    def __init__(self, name, parent=None):
        self.name = name
        self.values = []      # list of (key, value), duplicates preserved
        self.children = []
        self.parent = parent

    # --- values ---------------------------------------------------------
    def get(self, key, default=None):
        for k, v in self.values:
            if k == key:
                return v
        return default

    def getf(self, key, default=None):
        v = self.get(key)
        if v is None:
            return default
        try:
            return float(v)
        except ValueError:
            return default

    def getall(self, key):
        return [v for k, v in self.values if k == key]

    def has(self, key):
        return any(k == key for k, _ in self.values)

    # --- children -------------------------------------------------------
    def nodes(self, name):
        return [c for c in self.children if c.name == name]

    def node(self, name):
        for c in self.children:
            if c.name == name:
                return c
        return None

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def find_all(self, name):
        return [n for n in self.walk() if n.name == name]

    def path(self):
        parts, n = [], self
        while n is not None:
            parts.append(n.name)
            n = n.parent
        return "/".join(reversed(parts))

    def __repr__(self):
        return f"<Node {self.name} {len(self.values)}v {len(self.children)}c>"


def parse(text, root_name="__root__"):
    root = Node(root_name)
    cur = root
    pending = None          # a bare name waiting for its '{'
    for raw in text.splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        while line:
            if line.startswith("{"):
                child = Node(pending if pending is not None else "", cur)
                cur.children.append(child)
                cur = child
                pending = None
                line = line[1:].strip()
                continue
            if line.startswith("}"):
                if cur.parent is not None:
                    cur = cur.parent
                line = line[1:].strip()
                continue
            # split off a trailing brace so `NAME {` and `key = v }` both work
            brace = min([i for i in (line.find("{"), line.find("}")) if i >= 0], default=-1)
            head, line = (line[:brace].strip(), line[brace:].strip()) if brace >= 0 else (line, "")
            if not head:
                continue
            if "=" in head:
                k, v = head.split("=", 1)     # FIRST '=' only, like the game
                cur.values.append((k.strip(), v.strip()))
                pending = None
            else:
                pending = head
    return root


def load(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return parse(fh.read(), root_name=path)
