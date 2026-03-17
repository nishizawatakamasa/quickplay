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
from selectolax.parser import HTMLParser, Node


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
        href = self.attr('href', elem)
        if not href:
            return None
        href = href.strip()
        if re.search(r'(?i)^(?:#|javascript:|mailto:|tel:|data:)', href):
            return None
        url = urljoin(self._page.url, href)
        parts = urlsplit(url)
        if not parts.netloc:
            return None
        parts = parts._replace(path=re.sub(r'/{2,}', '/', parts.path))
        url = urlunsplit(parts)
        return url

    def goto(self, url: str | None) -> bool:
        if not url:
            return False
        try:
            self._page.goto(url)
            return True
        except Exception as e:
            print(f'{type(e).__name__}: {e}')
            return False

    def wait(self, selector: str, timeout: int = 15000) -> ElementHandle | None:
        try:
            return self._page.wait_for_selector(selector, timeout=timeout)
        except Exception as e:
            print(f'{type(e).__name__}: {e}')
            return None

class SelectParser:
    def __init__(self) -> None:
        self._parser: HTMLParser | None = None

    def goto(self, html_path: Path | str) -> bool:
        try:
            self._parser = HTMLParser(Path(html_path).read_text(encoding='utf-8'))
            return True
        except Exception as e:
            print(f'{type(e).__name__}: {e}')
            return False

    def first(self, nodes: list[Node]) -> Node | None:
        return nodes[0] if nodes else None

    def re_filter(self, pattern: str, nodes: list[Node]) -> list[Node]:
        return [n for n in nodes if (t := self.text(n)) is not None and re.search(pattern, ud.normalize('NFKC', t))]

    def ss(self, selector: str) -> list[Node]:
        return self._parser.css(selector) if self._parser else []

    def s(self, selector: str) -> Node | None:
        return self.first(self.ss(selector))

    def ss_re(self, selector: str, pattern: str) -> list[Node]:
        return self.re_filter(pattern, self.ss(selector))

    def s_re(self, selector: str, pattern: str) -> Node | None:
        return self.first(self.ss_re(selector, pattern))

    def ss_in(self, selector: str, from_: Node | None) -> list[Node]:
        return [] if from_ is None else from_.css(selector)

    def s_in(self, selector: str, from_: Node | None) -> Node | None:
        return self.first(self.ss_in(selector, from_))

    def ss_re_in(self, selector: str, pattern: str, from_: Node | None) -> list[Node]:
        return self.re_filter(pattern, self.ss_in(selector, from_))

    def s_re_in(self, selector: str, pattern: str, from_: Node | None) -> Node | None:
        return self.first(self.ss_re_in(selector, pattern, from_))

    def next(self, node: Node | None) -> Node | None:
        return None if node is None else node.next

    def text(self, node: Node | None) -> str | None:
        if node is None:
            return None
        return node.text(strip=True)

    def attr(self, attr_name: str, node: Node | None) -> str | None:
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
    '''dictを1行としてCSVに追記する。ファイルがなければheaderも書く。'''
    p = Path(path)
    pd.DataFrame([row]).to_csv(
        p,
        mode='a',
        index=False,
        header=not p.exists(),
        encoding='utf-8-sig',
    )

def hash_name(key: str) -> str:
    '''キー文字列からハッシュ名を生成する。'''
    return hashlib.md5(key.encode()).hexdigest()

def save_html(filepath: Path, html: str) -> bool:
    '''HTMLをファイルに保存する。'''
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
    '''Playwrightの定型起動をまとめたランナー。

    Args:
        fn:               scrape(page) のような関数を渡す。
        headless:         ヘッドレスモードにするか。
        channel:          ブラウザチャンネル（'chrome' など）。
        viewport:         {'width': 1920, 'height': 1080} など。Noneなら未設定。
        user_agent:       User-Agent文字列。Noneなら未設定。chrome://version/で確認できる。
        accept_language:  Accept-Languageヘッダー。Noneなら未設定。
        timeout:          デフォルトタイムアウト（ミリ秒）。
        block_resources:  ブロックするリソースタイプ。例: {'image'}。

    Usage:
        browse(scrape, user_agent='Mozilla/5.0 ...', block_resources={'image', 'font'})
    '''
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

def browse_camou(
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
    '''Camoufoxを使ったブラウザ自動化のランナー。

    Playwrightの `browse()` と同じ使用感で呼び出せるが、内部はCamoufoxを使うため
    fingerprintの偽装精度が高く、bot検知が厳しいサイトへの対抗手段として有効。
    ブラウザはFirefox固定。viewport・user_agentはCamoufoxが自動生成するため、
    手動設定は原則不要（かつ逆効果になりうる）。

    Args:
        fn:
            `fn(page)` の形で呼び出されるスクレイピング関数。
            Playwrightの `Page` オブジェクトを受け取り、処理を行う。

            例::

                def scrape(page: Page) -> None:
                    page.goto("https://example.com")
                    print(page.title())

                browse_camou(scrape)

        headless:
            ブラウザをヘッドレスモードで起動するかどうか。
            デフォルトは `False`（ウィンドウあり）。

            - `False` : ウィンドウを表示して起動。開発・デバッグ時に推奨。
            - `True`  : ヘッドレスで起動。ただしbot検知に引っかかりやすくなる
              場合があるため、本番環境では注意。
            - `'virtual'` : Linuxサーバー環境でXvfb（仮想ディスプレイ）を使って
              ヘッドレスに近い形で動作させる。GUIが使えないLinux環境での
              推奨オプション。Windowsでは使用不可。

            例::

                # Linuxサーバーで動かす場合
                browse_camou(scrape, headless='virtual')

        os:
            fingerprintを生成する際のOSを指定する。
            Camoufoxはこの値を元にUser-Agent・フォント・画面解像度などの
            一連のfingerprint情報を一貫した形で生成する。

            - `None`（デフォルト）: `'windows'`, `'macos'`, `'linux'` から
              ランダムに選択。最も自然な挙動。
            - `'windows'` : Windows環境のfingerprintを生成。
            - `'macos'`   : macOS環境のfingerprintを生成。
            - `'linux'`   : Linux環境のfingerprintを生成。
            - `list`      : 指定したOSの中からランダムに選択。
              例: `['windows', 'macos']`

            注意: `webgl_config` を同時に指定する場合、そのvendor/rendererが
            このOSで有効な組み合わせかを自分で確認する必要がある。

            例::

                # Windows固定
                browse_camou(scrape, os='windows')

                # WindowsかmacOSをランダムに選択（Linuxは除外したい場合）
                browse_camou(scrape, os=['windows', 'macos'])

        locale:
            ブラウザのロケール（言語・地域設定）を指定する。
            Camoufoxはこの値を元に `navigator.language`、`Intl` API、
            `Accept-Language` ヘッダーを一貫して設定してくれる。
            `browse()` の `accept_language` 引数に相当するが、
            Camoufoxを通すことで整合性のある偽装が可能。

            - 単一の文字列（例: `'ja-JP'`）: そのロケールを使用。
            - カンマ区切りの文字列（例: `'ja-JP,ja'`）: 複数ロケールを指定。
              先頭が `Intl` APIに使われる。
            - リスト（例: `['ja-JP', 'en-US']`）: 複数ロケールを指定。
            - 国コード（例: `'JP'`）: その国の話者分布に基づいてロケールを生成。

            デフォルトは `'ja-JP,ja'`。日本語サイトをスクレイピングする
            想定のため。英語サイト中心なら `'en-US,en'` への変更を検討。

            例::

                # 英語サイト向け
                browse_camou(scrape, locale='en-US,en')

                # 日本語・英語を両方受け入れる
                browse_camou(scrape, locale=['ja-JP', 'en-US'])

        humanize:
            カーソルの動きを人間らしく模倣するかどうか。
            Camoufoxの提供する機能で、マウス移動の軌跡や速度を自然に見せる。
            bot検知回避の効果がある。

            - `True`（デフォルト）: デフォルト設定（最大約1.5秒）で有効化。
            - `False`: 無効。カーソルが瞬時に移動する。
              高速化したい場合やカーソル操作をしないスクレイピングに。
            - `float`: カーソル移動の最大秒数を指定して有効化。
              例: `2.0` なら最大2秒かけて移動。

            注意: クリック操作が必要ないスクレイピング（GETのみ）では
            `False` にしても差し支えない。

            例::

                # カーソル操作が多い場合はゆっくりめに
                browse_camou(scrape, humanize=2.5)

                # カーソル操作なし・速度優先
                browse_camou(scrape, humanize=False)

        geoip:
            IPアドレスを元にジオロケーション（緯度・経度・タイムゾーン・
            国・ロケール）を自動的に設定する。
            プロキシを使用する場合に、IPのロケーションとブラウザの
            ジオロケーションを一致させることでプロキシ検知を防ぐ。

            - `False`（デフォルト）: ジオロケーション設定なし。
              プロキシを使わない場合はこれで問題ない。
            - `True`: 自分のIPアドレスを自動取得して設定。
            - `str`: 指定したIPアドレスを元にジオロケーションを計算して設定。
              プロキシを使う場合はそのプロキシのIPを渡す。

            注意: プロキシを使わない場合は `False` のままでよい。
            プロキシと組み合わせる場合は `True` か具体的なIPを渡すことを推奨。

            例::

                # プロキシのIPを指定
                browse_camou(scrape, geoip='203.0.113.0')

                # 自動取得
                browse_camou(scrape, geoip=True)

        block_images:
            画像リソースのリクエストをすべてブロックするかどうか。
            `browse()` の `block_resources={'image'}` に相当するが、
            Camoufoxのネイティブ機能として実装されているため、
            `page.route()` を使うより安定している。

            - `False`（デフォルト）: 画像を読み込む。
            - `True`: 画像をすべてブロック。プロキシ通信量の節約や
              ページ読み込み速度の向上に効果的。
              テキスト情報だけ取得したい場合に有用。

            例::

                # テキストだけ欲しい場合
                browse_camou(scrape, block_images=True)

        block_webrtc:
            WebRTCをブロックするかどうか。
            WebRTCはプロキシを使っていても実際のIPアドレスが
            漏洩する原因になりうる（WebRTC leak）。

            - `False`（デフォルト）: WebRTCを有効のまま。
              プロキシを使わない場合はこれで問題ない。
            - `True`: WebRTCを完全にブロック。
              プロキシを使う場合はこれを `True` にすることを強く推奨。

            例::

                # プロキシ使用時はセットで指定するのが定石
                browse_camou(scrape, geoip=True, block_webrtc=True)

        disable_coop:
            Cross-Origin-Opener-Policy（COOP）を無効にするかどうか。
            COOPが有効だとクロスオリジンiframe内の要素を操作できないが、
            これを無効にすることでiframe内のボタンなどをクリックできる。

            主な用途はCloudflareのTurnstile（チェックボックス認証）の突破。
            Turnstileはiframe内に描画されるため、クリックするにはこれが必要。

            - `False`（デフォルト）: COOPを有効のまま。通常はこれでよい。
            - `True`: COOPを無効化。Cloudflare Turnstileなど、
              iframe内要素を操作する必要がある場合に指定する。

            注意: セキュリティポリシーを緩める設定なので、必要な場合だけ使う。

            例::

                # Cloudflare Turnstile突破が必要な場合
                browse_camou(scrape, disable_coop=True)

        timeout:
            Playwrightのデフォルトタイムアウト（ミリ秒）。
            `page.goto()` や `page.wait_for_selector()` など、
            タイムアウトを個別指定していない操作すべてに適用される。

            デフォルトは `15000`（15秒）。
            重いページや低速なプロキシ経由の場合は増やすことを検討。

            例::

                # 低速プロキシ使用時
                browse_camou(scrape, timeout=30000)

        **kwargs:
            上記以外のCamoufoxオプションをそのまま渡すための口。
            Camoufoxが受け付けるすべてのキーワード引数が使用可能。

            主な用途:

            - `screen`: fingerprintの画面解像度を制約する。
              `browserforge.fingerprints.Screen` インスタンスを渡す。
              通常はCamoufoxの自動生成で十分。

            - `webgl_config`: WebGLのvendor/rendererペアを固定する。
              `(vendor, renderer)` のタプルを渡す。
              `os` との整合性を自分で確認する必要があり、上級者向け。

            - `addons`: Firefoxの拡張機能を読み込む。
              展開済み拡張機能フォルダのパスのリストを渡す。

            - `proxy`: プロキシを設定する。
              Playwright標準の形式（`{'server': '...'}` など）を渡す。

            例::

                from browserforge.fingerprints import Screen

                # 解像度を制約したい場合
                browse_camou(scrape, screen=Screen(max_width=1920, max_height=1080))

                # プロキシを設定する場合
                browse_camou(
                    scrape,
                    geoip='203.0.113.0',
                    block_webrtc=True,
                    proxy={'server': 'http://203.0.113.0:8080'},
                )

    Usage:
        基本的な使い方::

            from playwright.sync_api import Page

            def scrape(page: Page) -> None:
                page.goto("https://example.com")
                print(page.title())

            browse_camou(scrape)

        プロキシを使う場合の定番セット::

            browse_camou(
                scrape,
                geoip='203.0.113.0',
                block_webrtc=True,
                proxy={'server': 'http://203.0.113.0:8080'},
            )

        Cloudflare Turnstile突破が必要な場合::

            browse_camou(
                scrape,
                disable_coop=True,
                humanize=2.0,
            )

        Linuxサーバーで速度優先の場合::

            browse_camou(
                scrape,
                headless='virtual',
                block_images=True,
                humanize=False,
            )
    '''
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