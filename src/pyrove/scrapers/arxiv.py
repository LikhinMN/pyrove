"""arXiv paper scraper for academic content extraction"""
import httpx
import logging
from typing import List, Optional, Dict, Any
from xml.etree import ElementTree as ET
import asyncio

logger = logging.getLogger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"  # Use HTTPS


async def search_arxiv(
    topic: str,
    max_results: int = 10,
    sort_by: str = "relevance"
) -> List[Dict[str, Any]]:
    """
    Search arXiv for papers related to a topic.
    
    Args:
        topic: Search topic (e.g., "deep learning", "reinforcement learning")
        max_results: Maximum number of papers to return
        sort_by: Sort order (relevance, lastUpdatedDate, submittedDate)
    
    Returns:
        List of paper metadata dicts with keys: id, title, summary, authors, url
    """
    if not topic or not topic.strip():
        logger.warning("Empty topic provided to search_arxiv")
        return []
    
    # Build arXiv query
    # Use category search for better relevance
    query = f"search_query=cat:cs.AI+AND+all:{topic}&start=0&max_results={max_results}&sortBy={sort_by}&sortOrder=descending"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{ARXIV_API_URL}?{query}",
                timeout=15.0
            )
            response.raise_for_status()
            
            papers = []
            root = ET.fromstring(response.content)
            
            # Parse Atom XML response
            namespaces = {
                "atom": "http://www.w3.org/2005/Atom"
            }
            
            for entry in root.findall("atom:entry", namespaces):
                try:
                    paper = {
                        "id": entry.find("atom:id", namespaces).text.split("/abs/")[-1],
                        "title": entry.find("atom:title", namespaces).text,
                        "summary": entry.find("atom:summary", namespaces).text.strip(),
                        "authors": [
                            author.find("atom:name", namespaces).text
                            for author in entry.findall("atom:author", namespaces)
                        ],
                        "published": entry.find("atom:published", namespaces).text,
                        "url": entry.find("atom:id", namespaces).text,
                    }
                    papers.append(paper)
                except Exception as e:
                    logger.debug(f"Error parsing paper entry: {e}")
                    continue
            
            logger.info(f"✓ Found {len(papers)} arXiv papers for '{topic}'")
            return papers
    
    except httpx.TimeoutException:
        logger.warning(f"Timeout searching arXiv for '{topic}'")
        return []
    except httpx.HTTPError as e:
        logger.warning(f"HTTP error searching arXiv: {e}")
        return []
    except ET.ParseError as e:
        logger.error(f"Error parsing arXiv response: {e}")
        return []
    except Exception as e:
        logger.error(f"Error searching arXiv: {e}")
        return []


def extract_paper_content(paper: Dict[str, Any]) -> str:
    """
    Extract searchable content from a paper dict.
    
    Args:
        paper: Paper metadata dict from search_arxiv
    
    Returns:
        Formatted text combining title, authors, abstract, and summary
    """
    if not paper:
        return ""
    
    content_parts = [
        f"Title: {paper.get('title', '')}",
        f"Authors: {', '.join(paper.get('authors', []))}",
        f"Published: {paper.get('published', '')}",
        f"",
        "Abstract:",
        paper.get('summary', ''),
    ]
    
    content = "\n".join(content_parts)
    return content.strip()


def extract_multiple_papers(papers: List[Dict[str, Any]]) -> List[str]:
    """
    Extract content from multiple papers.
    
    Args:
        papers: List of paper metadata dicts from search_arxiv
    
    Returns:
        List of formatted paper contents
    """
    if not papers:
        logger.warning("No papers provided to extract_multiple_papers")
        return []
    
    contents = []
    
    for i, paper in enumerate(papers, 1):
        try:
            content = extract_paper_content(paper)
            if content:
                contents.append(content)
            logger.debug(f"Extracted paper {i}/{len(papers)}: {paper.get('id', 'unknown')}")
        except Exception as e:
            logger.error(f"Error extracting paper content: {e}")
            continue
    
    logger.info(f"✓ Extracted content from {len(contents)} papers")
    return contents


async def fetch_arxiv_papers_async(
    topic: str,
    max_results: int = 10
) -> List[str]:
    """
    Async wrapper to search arXiv and extract paper contents.
    
    Args:
        topic: Search topic
        max_results: Maximum papers to fetch
    
    Returns:
        List of paper content strings ready for chunking
    """
    papers = await search_arxiv(topic, max_results=max_results)
    contents = extract_multiple_papers(papers)
    return contents
