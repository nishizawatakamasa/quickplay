# quickplay

## Overview - 概要

quickplay is a scraping utility library built on Playwright and selectolax.
quickplayはPlaywrightとselectolaxをベースにしたスクレイピングユーティリティライブラリです。

- **PlayPage** — Playwright `Page` のラッパー。ライブスクレイピング用。
- **LocalPage** — 保存済みHTMLファイルをPlayPage風に操作するクラス。selectolaxベースで高速。
- ユーティリティ関数群 — `browse` / `save_html` / `append_csv` / `html_filename` / `sleep_between`

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

## Basic Usage - 基本的な使い方

```python
from playwright.sync_api import Page
from quickplay import PlayPage, BasePaths, browse, append_csv, sleep_between

paths = BasePaths(__file__)

def scrape(page: Page) -> None:
    p = PlayPage(page)
    p.goto('https://www.foobarbaz1.jp')

    pref_urls = [p.attr('href', e) for e in p.ss('li.item > ul > li > a')]

    classroom_urls = []
    for i, url in enumerate(pref_urls, 1):
        print(f'{i}/{len(pref_urls)} pref_urls')
        if not p.goto(url):
            continue
        sleep_between(1, 2)
        links = [p.attr('href', e) for e in p.ss('.school-area h4 a')]
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

    item_urls = [p.attr('href', e) for e in p.ss('ul.items > li > a')]

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