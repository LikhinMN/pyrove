"""github scraper module of the pyrove package"""
import httpx
from typing import List

def search_github(topic:str)->List[str]:
    topic=topic.replace(" ", "+")
    res=httpx.get(f"https://api.github.com/search/repositories?q={topic}&sort=stars&per_page=10",headers={"Accept": "application/vnd.github+json"}).json()
    urls=[item['html_url'] for item in res['items']]
    return urls

def scrape_readme(url:str)->str:
    base_url = url.replace("github.com", "raw.githubusercontent.com")
    readme_paths = ["/master/README.md", "/main/README.md", "/master/README", "/main/README"]

    last_response = None
    for path in readme_paths:
        last_response = httpx.get(base_url + path)
        if last_response.status_code != 404:
            return last_response.text

    return last_response.text if last_response is not None else ""

def scrape_all(urls:List[str])->List[str]:
    return [scrape_readme(url) for url in urls]
