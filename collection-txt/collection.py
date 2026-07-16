from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


SCRIPT_DIR = Path(__file__).resolve().parent
URL_LIST_FILE = SCRIPT_DIR / "url.txt"


def read_urls(url_list_file: Path) -> list[str]:
    with open(url_list_file, "r", encoding="utf-8") as file:
        return [line.strip() for line in file if line.strip()]


def url_to_output_file(url: str) -> Path:
    slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    return SCRIPT_DIR / f"{slug}.txt"


def save_page_to_text(url: str, output_file: Path) -> None:
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # 제목 추출
    title_tag = soup.find("h1")
    title = title_tag.get_text(" ", strip=True) if title_tag else "Unknown Title"

    # StarRocks 문서 본문 영역
    article = soup.find("article")

    if article is None:
        raise ValueError("본문 article 영역을 찾을 수 없습니다.")

    # 불필요한 요소 제거
    for tag in article.select(
        "nav, footer, script, style, button, "
        ".theme-doc-toc-mobile, .pagination-nav"
    ):
        tag.decompose()

    body = article.get_text("\n", strip=True)

    content = f"""TITLE
{title}

BODY
{body}
"""

    with open(output_file, "w", encoding="utf-8") as file:
        file.write(content)

    print(f"저장 완료: {output_file}")


if __name__ == "__main__":
    urls = read_urls(URL_LIST_FILE)
    for url in urls:
        save_page_to_text(url, url_to_output_file(url))