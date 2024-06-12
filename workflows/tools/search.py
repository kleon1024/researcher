from duckduckgo_search import DDGS

def search(keywords, search_type, url, **kwargs):
    results = []
    logger = kwargs.get("logger") if "logger" in kwargs else None
    try:
        if "logger" in kwargs:
            logger.info(f"[Searching]: '{ keywords }'")
        with DDGS(proxy=kwargs.get("proxy", None)) as ddgs:
            for index, result in enumerate(
                ddgs.text(
                    keywords,
                    max_results=kwargs.get("max_results", 8),
                    safesearch=kwargs.get("safesearch", "off")
                    # timelimit=kwargs.get("timelimit", "d"),
                )
            ):
                results.append({
                    "id": index,
                    "title": result["title"],
                    "brief": result["body"],
                    "url": result["href"],
                    "source": result["href"].split("/")[2],
                    "image": result.get("image", "")
                })
        return results
    except Exception as e:
        if "logger" in kwargs:
            logger.error(f"[Search]: Can not search '{ keywords }'.\tError: { str(e) }")
        return []