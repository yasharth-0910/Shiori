# ruff: noqa: E501
"""The text viewer for HTML notices renders text only, and Add document takes .html and .htm (D-37, D-103)."""

import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
SINKS = re.compile(r"innerHTML|outerHTML|dangerouslySetInnerHTML|insertAdjacentHTML|srcdoc|document\.write|DOMParser|createContextualFragment|<iframe|<webview|<object|<embed")


def test_no_source_file_can_render_raw_html() -> None:
    for f in [*(APP / "src").glob("*.ts*"), *(APP / "electron").glob("*.ts")]:
        assert not SINKS.search(f.read_text()), f.name  # the only things drawn from a page are React text nodes


def test_text_viewer_takes_only_extracted_text_and_offsets() -> None:
    src = (APP / "src" / "TextView.tsx").read_text()
    props = re.search(r"props: \{(.+?)\}\)", src, re.S)
    assert props and "html" not in props.group(1).lower()
    assert "<img" not in src and "<link" not in src and "<script" not in src and "<style" not in src
    assert "fetch(" not in src and "src=" not in src and "href=" not in src


def test_html_notice_is_served_as_text_in_the_fields_not_as_a_file() -> None:
    main = (APP / "electron" / "main.ts").read_text()
    assert re.search(r"\\\.pdf\$/\.exec\(rel\)", main)  # the only served document route is still the PDF one
    assert "text/html" not in main.split("serve(")[1].split("const file =")[0]  # an HTML file is never served by id


def test_add_document_filter_accepts_html_and_htm_and_pdf() -> None:
    main = (APP / "electron" / "main.ts").read_text()
    m = re.search(r"filters: \[\{ name: \"[^\"]+\", extensions: \[([^\]]+)\] \}\]", main)
    assert m
    assert re.findall(r"\"(\w+)\"", m.group(1)) == ["pdf", "html", "htm"]
