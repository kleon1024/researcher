import re
import requests
from bs4 import BeautifulSoup
import pickle
import os

CACHE_DIR = "cache"

def browse(url, *, logger=None, proxy=None):
    cache_file = os.path.join(CACHE_DIR, f"{hash(url)}.pkl")

    # Check if the content is already cached
    if os.path.exists(cache_file):
        with open(cache_file, "rb") as f:
            content = pickle.load(f)
        if logger:
            logger.info(f"[Browse]: Loaded cached content for '{url}'.")
        return content

    content = ""
    try:
        request_options = {
            "headers": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            }
        }
        if proxy:
            request_options["proxies"] = {"http": proxy, "https": proxy}

        with requests.Session() as session:
            page = session.get(url, **request_options)
            page.raise_for_status()
            soup = BeautifulSoup(page.content, "html.parser")

        # Extract content from ProductHunt's specific structure
        # Adjust selectors based on actual structure
        titles = soup.find_all(["h1", "h2", "h3", "h4", "h5"])
        paragraphs = soup.find_all("p")
        preformatted = soup.find_all("pre")
        table_data = soup.find_all("td")
        
        for tag in titles + paragraphs + preformatted + table_data:
            if tag.name.startswith("h"):
                content += "#" * int(tag.name[-1]) + " " + tag.get_text(strip=True) + "\n"
            else:
                content += tag.get_text(strip=True) + "\n"

        # Example: Extracting specific content blocks from ProductHunt
        posts = soup.find_all("div", class_="post")
        for post in posts:
            title = post.find("h3")
            if title:
                content += "## " + title.get_text(strip=True) + "\n"
            description = post.find("p", class_="description")
            if description:
                content += description.get_text(strip=True) + "\n"

        # Clean up excessive newlines
        content = re.sub(r"\n+", "\n", content).strip()

        # Cache the content
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cache_file, "wb") as f:
            pickle.dump(content, f)

        if logger:
            logger.info(f"[Browse]: Successfully browsed '{url}' and cached the content.")

        return content
    except requests.RequestException as e:
        if logger:
            logger.error(f"[Browse]: HTTP error while browsing '{url}'. Error: {str(e)}")
        return ""
    except Exception as e:
        if logger:
            logger.error(f"[Browse]: Error while browsing '{url}'. Error: {str(e)}")
        return ""