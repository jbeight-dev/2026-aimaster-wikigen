import requests
from bs4 import BeautifulSoup


URL = "https://docs.starrocks.io/docs/using_starrocks/SQL_plan_manager/"
OUTPUT_FILE = "SQL_plan_manager.txt"


def save_page_to_text(url: str, output_file: str) -> None:
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
    save_page_to_text(URL, OUTPUT_FILE)