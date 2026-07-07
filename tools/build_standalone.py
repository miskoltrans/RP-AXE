#!/usr/bin/env python3
"""Bundle the tree render prototype into a single, zero-dependency HTML file.

    tree/render/prototype/index.html   (+ tree-data.js + renderer.js + icons/*.png)
        -> tree/render/prototype/axe-tree-standalone.html

index.html loads tree-data.js, renderer.js and icons/<disc>.png over HTTP, so it
only works under a web server. The standalone inlines all of them (icons as base64
data URIs in window.ICON_DATA, which renderer.loadIcons() prefers over icons/*.png),
producing one file that opens straight off disk (file://) or ships as a single share.

Run after tools/build_tree.py refreshes tree-data.js, or after editing renderer.js.
No args: python tools/build_standalone.py
"""
import base64
import glob
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROTO = os.path.normpath(os.path.join(HERE, "..", "tree", "render", "prototype"))
OUT = os.path.join(PROTO, "axe-tree-standalone.html")


def read(name):
    with open(os.path.join(PROTO, name), encoding="utf-8") as f:
        return f.read()


def icon_data_script():
    parts = []
    for path in sorted(glob.glob(os.path.join(PROTO, "icons", "*.png"))):
        key = os.path.splitext(os.path.basename(path))[0]  # RDicon_<disc>
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        parts.append("'%s':'data:image/png;base64,%s'" % (key, b64))
    return "<script>window.ICON_DATA={%s};</script>" % ",".join(parts)


def main():
    html = read("index.html")
    tree = "<script>\n%s\n</script>" % read("tree-data.js")

    # renderer.js loads icons only from 'icons/<nm>.png' (works for the served index.html).
    # For the standalone we patch that one line to prefer the inlined window.ICON_DATA data
    # URIs, falling back to the http path, so the bundle renders icons from file:// too.
    rend_src = read("renderer.js")
    ICON_FROM_HTTP = "im.src='icons/'+nm+'.png';"
    ICON_FROM_DATA = "im.src=(window.ICON_DATA&&window.ICON_DATA[nm])||('icons/'+nm+'.png');"
    if rend_src.count(ICON_FROM_HTTP) != 1:
        raise SystemExit("build_standalone: icon-load line not found in renderer.js "
                         "(loadIcons changed?) — cannot wire up inlined icons")
    rend_src = rend_src.replace(ICON_FROM_HTTP, ICON_FROM_DATA)
    rend = "<script>\n%s\n</script>" % rend_src

    # Prepend the inlined icons before the data script (loadIcons reads window.ICON_DATA),
    # then swap each external <script src> for its inlined content.
    html = html.replace(
        '<script src="tree-data.js"></script>',
        icon_data_script() + "\n" + tree,
    )
    html = html.replace('<script src="renderer.js"></script>', rend)

    for tag in ('src="tree-data.js"', 'src="renderer.js"'):
        if tag in html:
            raise SystemExit("build_standalone: failed to inline %s (index.html changed?)" % tag)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote %s (%d KB)" % (os.path.relpath(OUT, os.path.join(HERE, "..")), len(html.encode("utf-8")) // 1024))


if __name__ == "__main__":
    main()
