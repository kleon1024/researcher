import time
import Agently
from .tools.search import search
from .tools.browse import browse
from datetime import datetime, timedelta
from utils.retry import retry

def start(chapter_outline, *, agent_factory, SETTINGS, root_path, logger):
    logger.info("[Start Generate Chapter]", chapter_outline["chapter_title"])
    chapter_workflow = Agently.Workflow()
    chapter_editor_agent = agent_factory.create_agent()
    # You can set chapter editor agent here, read https://github.com/Maplemx/Agently/tree/main/docs/guidebook to explore
    """
    (
        chapter_editor_agent
            .set_role("...")
            .set_user_info("...")
    )
    """

    # Define Workflow Chunks
    @chapter_workflow.chunk("start", type="Start")

    @chapter_workflow.chunk("search")
    def search_executor(inputs, storage):
        if not SETTINGS.ENABLE_SEARCH:
            return
        storage.set(
            "searched_articles",
            search(
                chapter_outline.get("search_keywords", None),
                chapter_outline.get("search_type", None),
                chapter_outline.get("url", None),
                proxy=SETTINGS.PROXY if hasattr(SETTINGS, "PROXY") else None,
                max_results=SETTINGS.MAX_SEARCH_RESULTS,
                logger=logger,
            )
        )

    @chapter_workflow.chunk("pick_article")
    def pick_article_executor(inputs, storage):
        searched_articles = storage.get("searched_articles", [])
        logger.info("[Searched Articles Count]", len(searched_articles))
        if len(searched_articles) > 0:
            pick_results = (
                chapter_editor_agent
                    .load_yaml_prompt(
                        path=f"{ root_path }/prompts/pick_article.yaml",
                        variables={
                            "article": searched_articles,
                            "requirement": chapter_outline["chapter_requirement"],
                        }
                    )
                    .start()
            )
            print(f"pick_results {len(pick_results)}")
            # sleep to avoid requesting too often
            time.sleep(SETTINGS.SLEEP_TIME)
            picked_articles = []
            for pick_result in pick_results:
                if pick_result["can_use"]:
                    article = searched_articles[int(pick_result["id"])].copy()
                    article.update({ "section_body": pick_result["section_body"] })
                    picked_articles.append(article)
            storage.set("picked_articles", picked_articles)
            logger.info("[Picked Articles Count]", len(picked_articles))
        else:
            storage.set("picked_articles", [])
            logger.info("[Picked Articles Count]", 0)

    @chapter_workflow.chunk("read_and_summarize")
    def read_and_summarize_executor(inputs, storage):
        picked_articles = storage.get("picked_articles", [])
        readed_articles = []
        if picked_articles and len(picked_articles) > 0:
            for article in picked_articles:
                logger.info("[Summarzing]", article["title"])
                if "producthunt" in article["url"]:
                    article_content = browse_ph(article["url"])
                else:
                    article_content = browse(article["url"])
                if article_content and article_content != "":
                    try:
                        summary_result = (
                            chapter_editor_agent
                                .load_yaml_prompt(
                                    path=f"{ root_path }/prompts/summarize.yaml",
                                    variables={
                                        "article_content": article_content,
                                        "chapter_requirement": chapter_outline["chapter_requirement"],
                                        "chapter_title": chapter_outline["chapter_title"],
                                        "language": SETTINGS.OUTPUT_LANGUAGE,
                                    }
                                )
                                .start()
                        )
                        if summary_result["can_summarize"]:
                            readed_article_info = article.copy()
                            readed_article_info.update({ 
                                "summary": summary_result["summary"],
                            })
                            readed_articles.append(readed_article_info)
                            logger.info("[Summarzing]", "Success")
                        else:
                            logger.info("[Summarzing]", "Failed")
                        # sleep to avoid requesting too often
                        time.sleep(SETTINGS.SLEEP_TIME)
                    except Exception as e:
                        logger.error(f"[Summarzie]: Can not summarize '{ article['title'] }'.\tError: { str(e) }")
        storage.set("readed_articles", readed_articles)

    @chapter_workflow.chunk("write_chapter")
    @retry(max_retries=3, delay=5)
    def write_chapter_executor(inputs, storage):
        readed_articles = storage.get("readed_articles", [])
        print(f"readed_articles {len(readed_articles)}")
        if readed_articles is not None:
            slimmed_information = []
            for index, article in enumerate(readed_articles):
                slimmed_information.append({
                    "id": index,
                    "title": article["title"],
                    "summary": article["summary"],
                    "url": article["url"],
                    "image": article["image"],
                })
            chapter_result = (
                chapter_editor_agent
                    .load_yaml_prompt(
                        path=f"{ root_path }/prompts/write_chapter.yaml",
                        variables={
                            "slimmed_information": slimmed_information,
                            "chapter_requirement": chapter_outline["chapter_requirement"],
                            "language": SETTINGS.OUTPUT_LANGUAGE,
                        }
                    )
                    .start()
            )
            # sleep to avoid requesting too often
            time.sleep(SETTINGS.SLEEP_TIME)
            final_information_list = []
            print(f'chapter {chapter_result["information_list"]}')
            for article in chapter_result["information_list"]:
                id = article["id"]
                if id >= len(readed_articles):
                    continue
                final_information_list.append({
                    "url": readed_articles[id]["url"],
                    "title": readed_articles[id]["title"],
                    "summary": readed_articles[id]["summary"],
                    "section_body": article["section_body"],
                    "image": readed_articles[id]["image"],
                })
            storage.set("final_result", {
                "title": chapter_outline["chapter_title"],
                "prologue": chapter_result["prologue"],
                "body": chapter_result["body"],
                "conclusion": chapter_result["conclusion"],
                "information_list": final_information_list,
            })
        else:
            storage.set("final_result", None)

    # Connect Chunks
    (
        chapter_workflow.chunks["start"]
            .connect_to(chapter_workflow.chunks["search"])
            .connect_to(chapter_workflow.chunks["pick_article"])
            .connect_to(chapter_workflow.chunks["read_and_summarize"])
            .connect_to(chapter_workflow.chunks["write_chapter"])
    )

    # Start Workflow
    chapter_workflow.start()

    return chapter_workflow.executor.store.get("final_result")
