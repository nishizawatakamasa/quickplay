# quickplay

## Overview - 概要

quickplay is a scraping utility library built on Playwright and selectolax.
quickplayはPlaywrightとselectolaxをベースにしたスクレイピングユーティリティライブラリです。

- **PlayPage** — Playwright `Page` のラッパー。ライブスクレイピング用。
- **LocalPage** — 保存済みHTMLファイルをPlayPage風に操作するクラス。selectolaxベースで高速。
- その他ユーティリティ関数群

## Requirements - 必要条件

- Python 3.12 or higher
- Libraries: playwright, selectolax, pandas（自動インストール）
- Browser binary（別途インストールが必要）

## Installation - インストール

### pip
```
pip install quickplay
```

### uv (recommended)
```
uv add quickplay
```

ブラウザバイナリを別途インストールしてください。

### pip
```
python -m playwright install chromium
```

### uv
```
uv run playwright install chromium
```




## Quick Reference - 主要メソッド一覧

### PlayPage のメソッド（スクレイピング中に使用）

- **`ss(selector: str) -> list[ElementHandle]`**  
  指定したCSSセレクタにマッチする**すべての要素**をリストで返します。  
  *例:* `links = p.ss('a')`

- **`s(selector: str) -> ElementHandle | None`**  
  指定したCSSセレクタにマッチする**最初の要素**を返します。見つからなければ `None`。  
  *例:* `title_elem = p.s('h1')`

- **`text(elem: ElementHandle | None) -> str | None`**  
  要素からテキスト内容を取得します（前後の空白は除去されます）。  
  *例:* `title = p.text(p.s('h1'))`

- **`attr(attr_name: str, elem: ElementHandle | None) -> str | None`**  
  要素の指定された属性値を取得します。  
  *例:* `href = p.attr('href', link_elem)`

- **`url(elem: ElementHandle | None) -> str | None`**  
  リンク要素 (`<a>`) の `href` を**絶対URL**に正規化して返します。無効なリンク（`javascript:` など）は除外されます。  
  *例:* `next_url = p.url(p.s('a.next'))`

- **`goto(url: str | None) -> bool`**  
  指定したURLに移動します。成功すれば `True`、失敗すれば `False` を返します。  
  *例:* `if p.goto('https://example.com'): ...`

### ユーティリティ関数

- **`sleep_between(a: float, b: float) -> None`**  
  `a` 〜 `b` 秒の間でランダムに待機します。サーバーに負荷をかけないための基本的なマナーです。  
  *例:* `sleep_between(1, 2)`

- **`append_csv(path: Path | str, row: dict) -> None`**  
  `dict` 形式のデータを1行としてCSVファイルに追記します。ファイルが存在しない場合はヘッダーも自動で書き込みます。  
  *例:* `append_csv('data.csv', {'name': '太郎', 'age': 20})`

- **`browse(fn: Callable[[Page], None], ...) -> None`**  
  Playwrightのブラウザを起動し、引数で渡した関数を実行します。`headless` や `user_agent` などのオプションを指定できます。  
  *例:* `browse(scrape, headless=True, block_resources={'image'})`



## Basic Usage - 基本的な使い方

```python
from playwright.sync_api import Page
from quickplay import PlayPage, BasePaths, browse, append_csv, sleep_between

paths = BasePaths(__file__)

def scrape(page: Page) -> None:
    p = PlayPage(page)
    p.goto('https://www.foobarbaz1.jp')

    pref_urls = [p.url(e) for e in p.ss('li.item > ul > li > a')]

    classroom_urls = []
    for i, url in enumerate(pref_urls, 1):
        print(f'{i}/{len(pref_urls)} pref_urls')
        if not p.goto(url):
            continue
        sleep_between(1, 2)
        links = [p.url(e) for e in p.ss('.school-area h4 a')]
        classroom_urls.extend(links)

    for i, url in enumerate(classroom_urls, 1):
        print(f'{i}/{len(classroom_urls)} classroom_urls')
        if not p.goto(url):
            continue
        sleep_between(1, 2)
        row = {
            'URL': page.url,
            '教室名': p.text(p.s('h1 .text01')),
            '住所': p.text(p.s('.item .mapText')),
            '電話番号': p.text(p.s('.item .phoneNumber')),
            'HP': p.attr('href', p.s_in('a', p.next(p.s_re('th', 'ホームページ')))),
        }
        append_csv(paths.from_here('out.csv'), row)

if __name__ == '__main__':
    browse(
        scrape,
        user_agent='Mozilla/5.0 ...',
        block_resources={'image', 'font'},
    )
```

## Save HTML while scraping - スクレイピングしながらHTMLを保存する

```python
from playwright.sync_api import Page
from quickplay import PlayPage, BasePaths, browse, save_html, html_filename, sleep_between

paths = BasePaths(__file__)

def scrape(page: Page) -> None:
    p = PlayPage(page)
    p.goto('https://www.foobarbaz1.jp')

    item_urls = [p.url(e) for e in p.ss('ul.items > li > a')]

    for i, url in enumerate(item_urls, 1):
        print(f'{i}/{len(item_urls)} item_urls')
        if not p.goto(url):
            continue
        sleep_between(1, 2)
        save_html(paths.from_here('html'), html_filename(page.url), page.content())

if __name__ == '__main__':
    browse(scrape, block_resources={'image', 'font'})
```

## Scrape from local HTML files - 保存済みHTMLからスクレイピングしてCSVに出力する

```python
from quickplay import LocalPage, BasePaths, append_csv

paths = BasePaths(__file__)
p = LocalPage()

for path in paths.from_here('html').glob('*.html'):
    if not p.goto(path):
        continue
    row = {
        '商品名': p.text(p.s('h1.product-name')),
        '価格':   p.text(p.s('span.price')),
        'HP':     p.attr('href', p.s_in('a', p.next(p.s_re('th', 'ホームページ')))),
    }
    append_csv(paths.from_here('out.csv'), row)
```

## License - ライセンス

[MIT](./LICENSE)