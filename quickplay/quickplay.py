import hashlib
import random
import re
import time
import unicodedata as ud
from pathlib import Path
from typing import Callable, Literal
from urllib.parse import urljoin, urlsplit, urlunsplit

import pandas as pd
from camoufox.sync_api import Camoufox
from playwright.sync_api import sync_playwright, Page, ElementHandle, Route
from selectolax.lexbor import LexborHTMLParser, LexborNode


class PlayPage:
    def __init__(self, page: Page) -> None:
        self._page = page

    def first(self, elems: list[ElementHandle]) -> ElementHandle | None:
        return elems[0] if elems else None

    def re_filter(self, pattern: str, elems: list[ElementHandle]) -> list[ElementHandle]:
        return [elem for elem in elems if (t := self.text(elem)) is not None and re.search(pattern, ud.normalize('NFKC', t))]

    def ss(self, selector: str) -> list[ElementHandle]:
        return self._page.query_selector_all(selector)

    def s(self, selector: str) -> ElementHandle | None:
        return self.first(self.ss(selector))

    def ss_re(self, selector: str, pattern: str) -> list[ElementHandle]:
        return self.re_filter(pattern, self.ss(selector))

    def s_re(self, selector: str, pattern: str) -> ElementHandle | None:
        return self.first(self.ss_re(selector, pattern))

    def ss_in(self, selector: str, from_: ElementHandle | None) -> list[ElementHandle]:
        return [] if from_ is None else from_.query_selector_all(selector)

    def s_in(self, selector: str, from_: ElementHandle | None) -> ElementHandle | None:
        return self.first(self.ss_in(selector, from_))

    def ss_re_in(self, selector: str, pattern: str, from_: ElementHandle | None) -> list[ElementHandle]:
        return self.re_filter(pattern, self.ss_in(selector, from_))

    def s_re_in(self, selector: str, pattern: str, from_: ElementHandle | None) -> ElementHandle | None:
        return self.first(self.ss_re_in(selector, pattern, from_))

    def next(self, elem: ElementHandle | None) -> ElementHandle | None:
        return None if elem is None else elem.evaluate_handle('el => el.nextElementSibling').as_element()

    def text(self, elem: ElementHandle | None) -> str | None:
        if elem is None:
            return None
        return t.strip() if (t := elem.evaluate('el => el.textContent')) else t

    def inner_text(self, elem: ElementHandle | None) -> str | None:
        if elem is None:
            return None
        return t.strip() if (t := elem.evaluate('el => el.innerText')) else t

    def attr(self, attr_name: str, elem: ElementHandle | None) -> str | None:
        if elem is None:
            return None
        return a.strip() if (a := elem.get_attribute(attr_name)) else a

    def url(self, elem: ElementHandle | None) -> str | None:
        if not (href := self.attr('href', elem)):
            return None
        if re.search(r'(?i)^(?:#|javascript:|mailto:|tel:|data:)', href):
            return None
        url = urljoin(self._page.url, href)
        parts = urlsplit(url)
        if not parts.netloc:
            return None
        parts = parts._replace(path=re.sub(r'/{2,}', '/', parts.path))
        url = urlunsplit(parts)
        return url

    def goto(self, url: str | None, retry: int = 3) -> bool:
        if not url:
            return False
        for i in range(retry):
            try:
                if (res := self._page.goto(url)) is not None:
                    if res.ok:
                        return True
                    if 400 <= res.status < 500:
                        return False
                    reason = f"status: {res.status}"
                else:
                    reason = "response is None"
            except Exception as e:
                reason = f"{type(e).__name__}: {e}"
            print(f"[goto] {url} ({i+1}/{retry}) {reason}")
            if i + 1 < retry:
                time.sleep(random.uniform(3, 5))
        return False

    def wait(self, selector: str, timeout: int = 15000) -> ElementHandle | None:
        try:
            return self._page.wait_for_selector(selector, timeout=timeout)
        except Exception as e:
            print(f'{type(e).__name__}: {e}')
            return None

class SelectParser:
    def __init__(self) -> None:
        self._parser: LexborHTMLParser | None = None

    @property
    def parser(self) -> LexborHTMLParser | None:
        return self._parser

    def load(self, html_path: Path | str) -> bool:
        try:
            self._parser = LexborHTMLParser(Path(html_path).read_text(encoding='utf-8'))
            return True
        except Exception as e:
            print(f"[load error] {html_path} {type(e).__name__}: {e}")
            return False

    def first(self, nodes: list[LexborNode]) -> LexborNode | None:
        return nodes[0] if nodes else None

    def re_filter(self, pattern: str, nodes: list[LexborNode]) -> list[LexborNode]:
        return [n for n in nodes if (t := self.txt(n)) is not None and re.search(pattern, ud.normalize('NFKC', t))]

    def ss(self, selector: str) -> list[LexborNode]:
        return self._parser.css(selector) if self._parser else []

    def s(self, selector: str) -> LexborNode | None:
        return self.first(self.ss(selector))

    def ss_re(self, selector: str, pattern: str) -> list[LexborNode]:
        return self.re_filter(pattern, self.ss(selector))

    def s_re(self, selector: str, pattern: str) -> LexborNode | None:
        return self.first(self.ss_re(selector, pattern))

    def ss_in(self, selector: str, from_: LexborNode | None) -> list[LexborNode]:
        return [] if from_ is None else from_.css(selector)

    def s_in(self, selector: str, from_: LexborNode | None) -> LexborNode | None:
        return self.first(self.ss_in(selector, from_))

    def ss_re_in(self, selector: str, pattern: str, from_: LexborNode | None) -> list[LexborNode]:
        return self.re_filter(pattern, self.ss_in(selector, from_))

    def s_re_in(self, selector: str, pattern: str, from_: LexborNode | None) -> LexborNode | None:
        return self.first(self.ss_re_in(selector, pattern, from_))

    def nxt(self, selector: str, node: LexborNode | None) -> LexborNode | None:
        if node is None:
            return None
        cur: LexborNode | None = node.next
        while cur is not None:
            if cur.is_element_node and cur.css_matches(selector):
                return cur
            cur = cur.next
        return None

    def txt(self, node: LexborNode | None) -> str | None:
        if node is None:
            return None
        return node.text(strip=True)

    def attr(self, attr_name: str, node: LexborNode | None) -> str | None:
        if node is None:
            return None
        return a.strip() if (a := node.attributes.get(attr_name)) else a

class FromHere:
    def __init__(self, file: str) -> None:
        self._base = Path(file).resolve().parent

    def __call__(self, path: str) -> Path:
        return self._base / path

def sleep_between(a: float, b: float) -> None:
    time.sleep(random.uniform(a, b))

def append_csv(path: Path | str, row: dict) -> None:
    p = Path(path)
    pd.DataFrame([row]).to_csv(
        p,
        mode='a',
        index=False,
        header=not p.exists(),
        encoding='utf-8-sig',
    )

def write_csv(path: Path | str, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(
        Path(path),
        index=False,
        encoding='utf-8-sig',
    )

def hash_name(key: str) -> str:
    return hashlib.md5(key.encode()).hexdigest()

def save_html(filepath: Path, html: str) -> bool:
    try:
        filepath.write_text(html, encoding="utf-8", errors="replace")
        return True
    except Exception as e:
        print(f'{type(e).__name__}: {e}')
        return False

def browse(
    fn: Callable[[Page], None],
    *,
    headless: bool = False,
    channel: str = 'chrome',
    viewport: dict | None = {'width': 1920, 'height': 1080},
    user_agent: str | None = None,
    accept_language: str | None = 'ja-JP,ja;q=0.9',
    timeout: int = 15000,
    block_resources: set[str] | None = None,
) -> None:
    context_kwargs: dict = {}
    if viewport is not None:
        context_kwargs['viewport'] = viewport
    if user_agent is not None:
        context_kwargs['user_agent'] = user_agent
    if accept_language is not None:
        context_kwargs['extra_http_headers'] = {'Accept-Language': accept_language}
    with sync_playwright() as pw:
        with pw.chromium.launch(headless=headless, channel=channel) as browser:
            with browser.new_context(**context_kwargs) as context:
                page = context.new_page()
                page.set_default_timeout(timeout)
                if block_resources:
                    def handler(route: Route) -> None:
                        if route.request.resource_type in block_resources:
                            route.abort()
                        else:
                            route.continue_()
                    page.route('**/*', handler)
                fn(page)

def browse_camoufox(
    fn: Callable[[Page], None],
    *,
    headless: bool | Literal['virtual'] = False,
    os: str | list[str] | None = None,
    locale: str | list[str] | None = 'ja-JP,ja',
    humanize: bool | float = True,
    geoip: str | bool = False,
    block_images: bool = False,
    block_webrtc: bool = False,
    disable_coop: bool = False,
    timeout: int = 15000,
    **kwargs,
) -> None:
    with Camoufox(
        headless=headless,
        os=os,
        locale=locale,
        humanize=humanize,
        geoip=geoip,
        block_images=block_images,
        block_webrtc=block_webrtc,
        disable_coop=disable_coop,
        **kwargs,
    ) as browser:
        page = browser.new_page()
        page.set_default_timeout(timeout)
        fn(page)