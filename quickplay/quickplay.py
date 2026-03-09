import random
import re
import time
import unicodedata as ud
from pathlib import Path
from typing import Callable

import pandas as pd
from playwright.sync_api import sync_playwright, Page, ElementHandle



class PlayPage:
    def __init__(self, page: Page) -> None:
        self._page = page

    def first(self, elems: list[ElementHandle]) -> ElementHandle | None:
        return elems[0] if elems else None

    def re_filter(self, pattern: str, elems: list[ElementHandle]) -> list[ElementHandle]:
        return [elem for elem in elems if (text := self.text_c(elem)) is not None and re.search(pattern, ud.normalize("NFKC", text))]

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

    def text_c(self, elem: ElementHandle | None) -> str | None:
        if elem is None:
            return None
        return text.strip() if (text := elem.evaluate("el => el.textContent")) else text

    def i_text(self, elem: ElementHandle | None) -> str | None:
        if elem is None:
            return None
        return text.strip() if (text := elem.evaluate("el => el.innerText")) else text

    def attr(self, attr_name: str, elem: ElementHandle | None) -> str | None:
        if elem is None:
            return None
        return attr.strip() if (attr := elem.get_attribute(attr_name)) else attr

    def goto(self, url: str | None) -> bool:
        if not url:
            return False
        try:
            self._page.goto(url, wait_until="domcontentloaded")
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
        mode='a',
        index=False,
        header=not p.exists(),
        encoding='utf-8-sig',
    )


def run_scraper(
    fn: Callable[[Page], None],
    *,
    headless: bool = False,
    channel: str = "chrome",
    viewport: dict | None = {'width': 1920, 'height': 1080},
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
        user_agent:       User-Agent文字列。Noneなら未設定。
        accept_language:  Accept-Languageヘッダー。Noneなら未設定。
        timeout:          デフォルトタイムアウト（ミリ秒）。
        block_resources:  ブロックするリソースタイプ。例: {'image', 'font', 'media'}。

    Usage:
        run_scraper(scrape, user_agent='Mozilla/5.0 ...', block_resources={'image', 'font'})
    """
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
                    def handler(route):
                        if route.request.resource_type in block_resources:
                            route.abort()
                        else:
                            route.continue_()
                    page.route('**/*', handler)

                fn(page)