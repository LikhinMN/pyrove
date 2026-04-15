"""GitHub scraper module with rate limiting and error handling"""
import httpx
import asyncio
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com"
RAW_GITHUB_URL = "https://raw.githubusercontent.com"
RATE_LIMIT_DELAY = 5  # seconds to wait if rate limited


@dataclass
class GitHubResult:
    """Result of a GitHub scraping operation"""
    success: bool
    urls: List[str] = None
    error: Optional[str] = None
    rate_limited: bool = False


def _get_github_headers() -> Dict[str, str]:
    """Return GitHub API headers"""
    return {"Accept": "application/vnd.github+json"}


def _handle_rate_limit(response: httpx.Response) -> None:
    """
    Handle GitHub API rate limiting.
    
    Raises:
        httpx.HTTPStatusError: If rate limited, includes retry-after info
    """
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After", RATE_LIMIT_DELAY)
        logger.warning(f"⚠️  Rate limited by GitHub API. Retry after {retry_after}s")
        raise httpx.HTTPStatusError(
            f"GitHub API rate limited. Wait {retry_after}s before retrying.",
            request=response.request,
            response=response,
        )


def search_github(
    topic: str,
    per_page: int = 10,
    max_retries: int = 3,
) -> GitHubResult:
    """
    Search GitHub repositories by topic.
    
    Args:
        topic: Search topic (e.g., "linux kernel")
        per_page: Results per page (default 10)
        max_retries: Retry attempts on network errors
    
    Returns:
        GitHubResult with list of repo URLs or error
    
    Raises:
        ValueError: If topic is empty
    """
    if not topic or not topic.strip():
        return GitHubResult(
            success=False,
            error="Topic cannot be empty",
        )

    topic_encoded = topic.strip().replace(" ", "+")
    url = f"{GITHUB_API_URL}/search/repositories?q={topic_encoded}&sort=stars&per_page={per_page}"

    for attempt in range(max_retries):
        try:
            with httpx.Client() as client:
                response = client.get(url, headers=_get_github_headers(), timeout=10.0)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", RATE_LIMIT_DELAY))
                    logger.warning(f"Rate limited. Waiting {retry_after}s...")
                    asyncio.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                
                data = response.json()
                
                # Validate response structure
                if "items" not in data or not isinstance(data["items"], list):
                    return GitHubResult(
                        success=False,
                        error=f"Invalid API response: missing 'items' field",
                    )
                
                # Extract URLs, filtering out None values
                urls = [
                    item.get("html_url")
                    for item in data["items"]
                    if item.get("html_url")
                ]
                
                if not urls:
                    logger.warning(f"No repositories found for topic: {topic}")
                    return GitHubResult(
                        success=True,
                        urls=[],
                    )
                
                logger.info(f"✓ Found {len(urls)} repositories for '{topic}'")
                return GitHubResult(success=True, urls=urls)

        except httpx.TimeoutException:
            logger.error(f"Timeout on attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                asyncio.sleep(2 ** attempt)  # exponential backoff
                continue
            return GitHubResult(
                success=False,
                error="GitHub search timeout after multiple retries",
            )
        except httpx.HTTPError as e:
            logger.error(f"HTTP error on attempt {attempt + 1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                asyncio.sleep(2 ** attempt)
                continue
            return GitHubResult(
                success=False,
                error=str(e),
            )

    return GitHubResult(
        success=False,
        error="Failed to search GitHub after max retries",
    )


def scrape_readme(url: str, max_retries: int = 2) -> Optional[str]:
    """
    Scrape README.md from a GitHub repository.
    
    Tries both 'master' and 'main' branches. Returns None if not found.
    
    Args:
        url: GitHub repository URL
        max_retries: Retry attempts on network errors
    
    Returns:
        README content or None if not found
    """
    if not url or not url.strip():
        logger.warning("Empty URL provided to scrape_readme")
        return None

    # Clean and validate URL
    url = url.strip()
    if "github.com" not in url:
        logger.warning(f"Invalid GitHub URL: {url}")
        return None

    branches = ["main", "master"]
    
    for branch in branches:
        raw_url = url.replace("github.com", "raw.githubusercontent.com") + f"/{branch}/README.md"
        
        for attempt in range(max_retries):
            try:
                with httpx.Client() as client:
                    response = client.get(raw_url, timeout=10.0)
                    
                    # Success
                    if response.status_code == 200:
                        content = response.text.strip()
                        if content:  # Verify content is not empty
                            logger.debug(f"✓ Scraped README from {branch} branch")
                            return content
                        else:
                            logger.debug(f"README from {branch} branch is empty")
                    
                    # File not found on this branch, try next
                    if response.status_code == 404:
                        logger.debug(f"README not found on {branch} branch")
                        break
                    
                    # Rate limit
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", RATE_LIMIT_DELAY))
                        logger.warning(f"Rate limited. Waiting {retry_after}s...")
                        asyncio.sleep(retry_after)
                        continue
                    
                    response.raise_for_status()

            except httpx.TimeoutException:
                logger.warning(f"Timeout scraping {raw_url} (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    asyncio.sleep(2 ** attempt)
                    continue
            except httpx.HTTPError as e:
                logger.warning(f"Error scraping {raw_url}: {e}")
                if attempt < max_retries - 1:
                    asyncio.sleep(2 ** attempt)
                    continue
    
    logger.warning(f"Could not scrape README from {url}")
    return None


def scrape_all(urls: List[str], skip_empty: bool = True) -> List[str]:
    """
    Scrape README files from multiple GitHub URLs.
    
    Args:
        urls: List of GitHub repository URLs
        skip_empty: Skip repos where README cannot be fetched
    
    Returns:
        List of README contents (empty strings removed if skip_empty=True)
    """
    if not urls:
        logger.warning("No URLs provided to scrape_all")
        return []

    contents = []
    for i, url in enumerate(urls, 1):
        try:
            logger.info(f"Scraping {i}/{len(urls)}: {url}")
            content = scrape_readme(url)
            
            if content:
                contents.append(content)
            elif not skip_empty:
                contents.append("")  # Keep empty placeholder
            else:
                logger.debug(f"Skipped empty README from {url}")
        
        except Exception as e:
            logger.error(f"Unexpected error scraping {url}: {e}")
            if not skip_empty:
                contents.append("")

    logger.info(f"✓ Successfully scraped {len(contents)}/{len(urls)} READMEs")
    return contents