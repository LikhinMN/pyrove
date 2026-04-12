"""github scraper module of the pyrove package"""
import httpx
from typing import List

def search_github(topic:str)->List[str]:
    topic=topic.replace(" ", "+")
    res=httpx.get(f"https://api.github.com/search/repositories?q={topic}&sort=stars&per_page=10",headers={"Accept": "application/vnd.github+json"}).json()
    urls=[item['html_url'] for item in res['items']]
    return urls

def scrape_readme(url:str)->str:
    res=httpx.get(url.replace("github.com", "raw.githubusercontent.com") + "/master/README.md")
    if res.status_code==404:
        res=httpx.get(url.replace("github.com", "raw.githubusercontent.com") + "/main/README.md")
    return res.text

def scrape_all(urls:List[str])->List[str]:
    contents=[]
    for url in urls:
        contents.append(scrape_readme(url))
    return contents