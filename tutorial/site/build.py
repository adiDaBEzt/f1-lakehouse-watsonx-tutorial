"""Build the tutorial web page from tutorial/README.md.

    python tutorial/site/build.py [output.html]

The page uses the same layout as the earlier tutorials in this series: a contents rail with
step progress, copy buttons on code, expected-output blocks, captioned figures, callouts and
collapsible troubleshooting entries. Images are referenced as images/<file>.
"""

import re
import sys
from pathlib import Path

import markdown
from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "README.md"

FACTS = [("Author", "Aditya Krishnan"), ("Level", "Intermediate"), ("Time to complete", "About 90 minutes"),
         ("Steps", "15"), ("Tested with", "watsonx.data 2.4 · ADK 2.20")]
CODE_LABELS = {"bash": "Terminal", "python": "Python", "sql": "SQL", "yaml": "YAML", "ini": ".env",
               "text": "Expected output"}
CALLOUTS = {"Note": "note", "Tip": "tip", "Important": "important"}


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:48].rstrip("-")


def build(out: Path) -> None:
    md = SOURCE.read_text()
    # superfences handles code blocks nested inside numbered steps; plain fenced_code does not.
    html = markdown.markdown(md, extensions=["pymdownx.superfences", "pymdownx.highlight", "tables"],
                             extension_configs={"pymdownx.highlight": {"use_pygments": False}})
    soup = BeautifulSoup(html, "html.parser")

    h1 = soup.find("h1")
    title = h1.get_text()
    deck = h1.find_next_sibling("p")
    deck_text = deck.get_text()
    h1.decompose()
    deck.decompose()

    # Headings: ids, and step markup for "Step N. Name".
    nav_items = []
    for h in soup.find_all(["h2", "h3"]):
        text = h.get_text()
        h["id"] = slug(text)
        m = re.match(r"Step (\d+)\. (.+)", text) if h.name == "h3" else None
        if m:
            n, name = m.groups()
            h["class"] = "step"
            h["data-step"] = n
            h.clear()
            no = soup.new_tag("span", attrs={"class": "step-no"}); no.string = f"Step {n}"
            nm = soup.new_tag("span", attrs={"class": "step-name"}); nm.string = name
            h.append(no); h.append(nm)
            nav_items.append(("step", h["id"], n, name))
        elif h.name == "h2":
            nav_items.append(("top", h["id"], None, text))

    # Code blocks.
    for pre in soup.find_all("pre"):
        code = pre.find("code")
        classes = (code.get("class") or []) + (pre.get("class") or [])
        lang = next((c.removeprefix("language-") for c in classes if c.startswith("language-")), "text")
        code.attrs = {}
        pre.attrs = {}
        out_block = lang == "text"
        wrap = soup.new_tag("div", attrs={"class": "code out" if out_block else "code"})
        bar = soup.new_tag("div", attrs={"class": "code-bar"})
        label = soup.new_tag("span"); label.string = CODE_LABELS.get(lang, lang)
        bar.append(label)
        if not out_block:
            btn = soup.new_tag("button", attrs={"type": "button", "class": "copy"}); btn.string = "Copy"
            bar.append(btn)
        pre.wrap(wrap)
        wrap.insert(0, bar)

    # Figures: an image alone in a paragraph, with its title as the caption.
    for img in soup.find_all("img"):
        p = img.parent
        caption = img.get("title") or img.get("alt")
        if "title" in img.attrs:
            del img["title"]
        img["loading"] = "lazy"
        fig = soup.new_tag("figure")
        a = soup.new_tag("a", attrs={"href": img["src"], "target": "_blank", "rel": "noopener"})
        a.append(img.extract())
        fig.append(a)
        cap = soup.new_tag("figcaption"); cap.string = caption
        fig.append(cap)
        p.replace_with(fig) if p.name == "p" and not p.get_text(strip=True) else p.insert_after(fig)

    # Callouts and quoted questions.
    for bq in soup.find_all("blockquote"):
        strong = bq.find("strong")
        kind = strong.get_text().rstrip(":") if strong else None
        if kind in CALLOUTS:
            strong.decompose()
            first = bq.find("p")
            if first and first.contents and isinstance(first.contents[0], str):
                first.contents[0].replace_with(first.contents[0].lstrip())
            aside = soup.new_tag("aside", attrs={"class": f"callout {CALLOUTS[kind]}"})
            lab = soup.new_tag("span", attrs={"class": "callout-label"}); lab.string = kind
            aside.append(lab)
            for child in list(bq.find_all(recursive=False)):
                aside.append(child.extract())
            bq.replace_with(aside)
        else:
            bq["class"] = "ask"

    for table in soup.find_all("table"):
        table.wrap(soup.new_tag("div", attrs={"class": "table"}))

    # Troubleshooting: each h4 and the paragraphs after it become a details element.
    for h4 in soup.find_all("h4"):
        det = soup.new_tag("details")
        summ = soup.new_tag("summary"); summ.string = h4.get_text()
        det.append(summ)
        nxt = h4.find_next_sibling()
        while nxt is not None and nxt.name not in ("h2", "h3", "h4"):
            after = nxt.find_next_sibling()
            det.append(nxt.extract())
            nxt = after
        h4.replace_with(det)

    for a in soup.find_all("a", href=re.compile(r"^https?://")):
        a["target"] = "_blank"; a["rel"] = "noopener"

    nav = ['<div class="progress"><p><b id="done-count">0</b> of 15 steps done</p>'
           '<div class="bar"><i id="done-bar"></i></div></div>']
    in_steps = False
    for kind, sid, n, text in nav_items:
        if kind == "step" and not in_steps:
            nav.append('<ol class="steps">'); in_steps = True
        if kind == "top" and in_steps:
            nav.append("</ol>"); in_steps = False
        if kind == "step":
            nav.append(f'<li><a href="#{sid}" data-step="{n}"><span class="dot" aria-hidden="true">{n}</span>'
                       f'<span>{text}</span></a></li>')
        else:
            nav.append(f'<a class="top" href="#{sid}">{text}</a>')
    if in_steps:
        nav.append("</ol>")

    facts = "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in FACTS)
    page = f"""<title>F1 Medallion Lakehouse</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:ital,wght@0,300;0,400;0,600;1,400&display=swap">
<style>
{(HERE / "style.css").read_text()}
</style>

<header class="masthead">
  <p class="eyebrow">Tutorial · watsonx.data · Confluent · watsonx Orchestrate</p>
  <h1>{title}</h1>
  <p class="deck">{deck_text}</p>
  <dl class="facts">{facts}</dl>
</header>

<div class="wrap">
  <nav class="toc" aria-label="On this page">
    {"".join(nav)}
  </nav>
  <article>
{soup.decode()}
  </article>
</div>
<footer class="foot">Source code, data and the agent definition:
  <a href="https://github.com/adiDaBEzt/f1-lakehouse-watsonx-tutorial" target="_blank" rel="noopener">github.com/adiDaBEzt/f1-lakehouse-watsonx-tutorial</a>.
  The fantasy-league managers, teams and prices are fictional.</footer>

<script>
{(HERE / "page.js").read_text()}
</script>
"""
    out.write_text(page)
    print(f"Wrote {out} ({len(page) // 1024} KB, {sum(1 for i in nav_items if i[0] == 'step')} steps)")


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "index.html")
