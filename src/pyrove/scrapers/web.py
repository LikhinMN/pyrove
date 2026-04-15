"""Web scraper module using Trafilatura for general article extraction"""
import httpx
import logging
from typing import List, Optional
from pathlib import Path
import asyncio

logger = logging.getLogger(__name__)

try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False
    logger.warning("Trafilatura not installed. Web scraping will be limited.")


async def search_web_articles(
    topic: str,
    num_results: int = 5,
    search_engine: str = "duckduckgo"
) -> List[str]:
    """
    Search the web for articles related to a topic.
    
    Note: This is a placeholder that demonstrates the pattern.
    For production, consider using actual search APIs or RSS feeds.
    
    Args:
        topic: Search topic
        num_results: Number of articles to find
        search_engine: Which search engine to use (duckduckgo, google, etc.)
    
    Returns:
        List of article URLs
    """
    if not topic or not topic.strip():
        logger.warning("Empty topic provided to search_web_articles")
        return []
    
    urls = []
    
    # For MVP, return example URLs related to the topic
    # Production would use actual search engine or RSS feeds
    if search_engine == "duckduckgo":
        # These are example URLs - in production, use proper search
        logger.debug(f"Web search for '{topic}' (using placeholder URLs)")
        examples = {
            "docker": [
                "https://docs.docker.com/get-started/",
                "https://www.digitalocean.com/community/tutorials/docker-containerization",
            ],
            "kubernetes": [
                "https://kubernetes.io/docs/concepts/",
                "https://www.digitalocean.com/community/tutorials/kubernetes",
            ],
            "machine learning": [
                "https://developers.google.com/machine-learning",
                "https://www.coursera.org/learn/machine-learning",
            ],
        }
        
        for key in examples:
            if key in topic.lower():
                urls.extend(examples[key][:num_results])
                break
    
    return urls[:num_results]


def extract_article_content(url: str, timeout: float = 10.0) -> Optional[str]:
    """
    Extract article content from a URL using Trafilatura.
    
    Args:
        url: Article URL to extract
        timeout: Request timeout in seconds
    
    Returns:
        Cleaned article text or None if extraction failed
    """
    if not TRAFILATURA_AVAILABLE:
        logger.warning("Trafilatura not available, cannot extract article")
        return None
    
    if not url or not url.strip():
        logger.warning("Empty URL provided to extract_article_content")
        return None
    
    try:
        with httpx.Client() as client:
            response = client.get(url, timeout=timeout, follow_redirects=True)
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch {url}: HTTP {response.status_code}")
                return None
            
            # Extract article using Trafilatura
            extracted = trafilatura.extract(
                response.text,
                include_comments=False,
                output_format="txt"  # Use 'txt' instead of 'text'
            )
            
            if not extracted or len(extracted.strip()) < 50:
                logger.debug(f"No meaningful content extracted from {url}")
                return None
            
            # Clean up the text
            content = extracted.strip()
            # Remove excessive whitespace
            content = "\n".join(line.strip() for line in content.split("\n") if line.strip())
            
            logger.debug(f"✓ Extracted {len(content)} chars from {url}")
            return content
    
    except httpx.TimeoutException:
        logger.warning(f"Timeout extracting {url}")
        return None
    except httpx.HTTPError as e:
        logger.warning(f"HTTP error extracting {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error extracting {url}: {e}")
        return None


def extract_multiple_articles(urls: List[str], skip_empty: bool = True) -> List[str]:
    """
    Extract content from multiple URLs.
    
    Args:
        urls: List of article URLs
        skip_empty: Skip articles where extraction failed
    
    Returns:
        List of extracted article contents
    """
    if not urls:
        logger.warning("No URLs provided to extract_multiple_articles")
        return []
    
    contents = []
    
    for i, url in enumerate(urls, 1):
        try:
            logger.debug(f"Extracting {i}/{len(urls)}: {url}")
            content = extract_article_content(url)
            
            if content:
                contents.append(content)
            elif not skip_empty:
                contents.append("")
            else:
                logger.debug(f"Skipped empty content from {url}")
        
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            if not skip_empty:
                contents.append("")
    
    logger.info(f"✓ Successfully extracted {len(contents)}/{len(urls)} articles")
    return contents
