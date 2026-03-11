import hashlib
import random
import re
import time
import unicodedata as ud
from pathlib import Path
from typing import Callable, Generator

import pandas as pd
from playwright.sync_api import sync_playwright, Page, ElementHandle, Route
from selectolax.parser import HTMLParser, Node


class PlayPage:
    def __init__(self, page: Page) -> None:
        self._page = page

    def first(self, elems: list[ElementHandle]) -> ElementHandle | None:
        return elems[0] if elems else None

    def re_filter(self, pattern: str, elems: list[ElementHandle]) -> list[ElementHandle]:
        return [elem for elem in elems if (t := self.text(elem)) is not None and re.search(pattern, ud.normalize("NFKC", t))]

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
        return None if elem is None else elem.evaluate_handle("el => el.nextElementSibling").as_element()

    def text(self, elem: ElementHandle | None) -> str | None:
        if elem is None:
            return None
        return t.strip() if (t := elem.evaluate("el => el.textContent")) else t

    def inner_text(self, elem: ElementHandle | None) -> str | None:
        if elem is None:
            return None
        return t.strip() if (t := elem.evaluate("el => el.innerText")) else t

    def attr(self, attr_name: str, elem: ElementHandle | None) -> str | None:
        if elem is None:
            return None
        return a.strip() if (a := elem.get_attribute(attr_name)) else a

    def goto(self, url: str | None) -> bool:
        if not url:
            return False
        try:
            self._page.goto(url)
            return True
        except Exception as e:
            print(f"{type(e).__name__}: {e}")
            return False

    def wait(self, selector: str, timeout: int = 15000) -> ElementHandle | None:
        try:
            return self._page.wait_for_selector(selector, timeout=timeout)
        except Exception as e:
            print(f"{type(e).__name__}: {e}")
            return None


class LocalPage:
    """保存済みHTMLファイルをPlayPage風に操作するクラス。

    PlayPageと同様に一度インスタンス化し、gotoでファイルを切り替えながら使う。

    Usage:
        lp = LocalPage()
        lp.goto("foo.html")
        nodes = lp.ss("div.item")
        node  = lp.s("h1")
        text  = lp.text(node)
        href  = lp.attr("href", node)

        lp.goto("bar.html")  # 別ファイルに切り替え
    """

    def __init__(self) -> None:
        self._tree: HTMLParser | None = None

    def goto(self, path: Path | str) -> bool:
        try:
            self._tree = HTMLParser(Path(path).read_text(encoding="utf-8"))
            return True
        except Exception as e:
            print(f"{type(e).__name__}: {e}")
            return False

    # ── 内部ユーティリティ ──────────────────────────────────────

    def first(self, nodes: list[Node]) -> Node | None:
        return nodes[0] if nodes else None

    def re_filter(self, pattern: str, nodes: list[Node]) -> list[Node]:
        return [n for n in nodes if (t := self.text(n)) is not None and re.search(pattern, ud.normalize("NFKC", t))]

    # ── セレクタ ────────────────────────────────────────────────

    def ss(self, selector: str) -> list[Node]:
        return self._tree.css(selector) if self._tree else []

    def s(self, selector: str) -> Node | None:
        return self._tree.css_first(selector) if self._tree else None

    def ss_re(self, selector: str, pattern: str) -> list[Node]:
        return self.re_filter(pattern, self.ss(selector))

    def s_re(self, selector: str, pattern: str) -> Node | None:
        return self.first(self.ss_re(selector, pattern))

    def ss_in(self, selector: str, from_: Node | None) -> list[Node]:
        return [] if from_ is None else from_.css(selector)

    def s_in(self, selector: str, from_: Node | None) -> Node | None:
        return None if from_ is None else from_.css_first(selector)

    def ss_re_in(self, selector: str, pattern: str, from_: Node | None) -> list[Node]:
        return self.re_filter(pattern, self.ss_in(selector, from_))

    def s_re_in(self, selector: str, pattern: str, from_: Node | None) -> Node | None:
        return self.first(self.ss_re_in(selector, pattern, from_))

    # ── ノード操作 ──────────────────────────────────────────────

    def next(self, node: Node | None) -> Node | None:
        return None if node is None else node.next

    def text(self, node: Node | None) -> str | None:
        if node is None:
            return None
        return node.text(deep=True, strip=True)

    def attr(self, attr_name: str, node: Node | None) -> str | None:
        if node is None:
            return None
        a = node.attributes.get(attr_name)
        return a.strip() if a else a




class BasePaths:
    """呼び出し元ファイルを基準にしたパス解決。

    Usage:
        paths = BasePaths(__file__)
        csv_path = paths.from_here('data/out.csv')
    """

    def __init__(self, file: str) -> None:
        self._base = Path(file).resolve().parent

    def from_here(self, path: str) -> Path:
        """baseを起点に連結した絶対Pathを返す。"""
        return self._base / path


def sleep_between(a: float, b: float) -> None:
    """a〜b秒のランダムスリープ。"""
    time.sleep(random.uniform(a, b))


def append_csv(path: Path | str, row: dict) -> None:
    """dictを1行としてCSVに追記する。ファイルがなければheaderも書く。"""
    p = Path(path)
    pd.DataFrame([row]).to_csv(
        p,
        mode="a",
        index=False,
        header=not p.exists(),
        encoding="utf-8-sig",
    )


def html_filename(title: str) -> str:
    """タイトル文字列からC案方式のファイル名を生成する。

    - サニタイズした文字列（バイト数で180以内）＋MD5ハッシュ8文字
    - 例: "example.com_item_page_2__a3f5c2d1.html"
    """
    if not title or not title.strip():
        title = "untitled"
    sanitized = re.sub(r'[\\/:*?"<>|\s]+', "_", title)
    sanitized = sanitized.strip("_")
    encoded = sanitized.encode("utf-8")[:180].decode("utf-8", errors="ignore")
    sanitized = encoded.strip("_") or "untitled"
    suffix = hashlib.md5(title.encode()).hexdigest()[:8]
    return f"{sanitized}__{suffix}.html"


def save_html(folder: Path | str, filename: str, html: str) -> Path:
    """HTMLをフォルダに保存する。

    Args:
        folder:   保存先フォルダ（なければ作成）
        filename: ファイル名。html_filename()を使うかそのまま渡すか呼び出し側で決める。
        html:     保存するHTML文字列（page.content() など）

    Returns:
        保存したファイルのPathを返す。

    Usage:
        # C案方式のファイル名を使う場合
        save_html(paths.from_here("html"), html_filename(page.url), page.content())

        # 自前でファイル名を決める場合
        save_html(paths.from_here("html"), f"item_{i:04d}.html", page.content())
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    filepath = folder / filename
    filepath.write_text(html, encoding="utf-8")
    return filepath


def browse(
    fn: Callable[[Page], None],
    *,
    headless: bool = False,
    channel: str = "chrome",
    viewport: dict | None = {"width": 1920, "height": 1080},
    user_agent: str | None = None,
    accept_language: str | None = "ja-JP,ja;q=0.9",
    timeout: int = 15000,
    block_resources: set[str] | None = None,
) -> None:
    """Playwrightの定型起動をまとめたランナー。

    Args:
        fn:               scrape(page) のような関数を渡す。
        headless:         ヘッドレスモードにするか。
        channel:          ブラウザチャンネル（"chrome" など）。
        viewport:         {'width': 1920, 'height': 1080} など。Noneなら未設定。
        user_agent:       User-Agent文字列。Noneなら未設定。chrome://version/で確認できる。
        accept_language:  Accept-Languageヘッダー。Noneなら未設定。
        timeout:          デフォルトタイムアウト（ミリ秒）。
        block_resources:  ブロックするリソースタイプ。例: {'image'}。

    Usage:
        browse(scrape, user_agent='Mozilla/5.0 ...', block_resources={'image', 'font'})
    """
    context_kwargs: dict = {}
    if viewport is not None:
        context_kwargs["viewport"] = viewport
    if user_agent is not None:
        context_kwargs["user_agent"] = user_agent
    if accept_language is not None:
        context_kwargs["extra_http_headers"] = {"Accept-Language": accept_language}

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
                    page.route("**/*", handler)
                fn(page)