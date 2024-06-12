import time
import Agently
import yaml
from datetime import datetime
from .chapter_workflow import start as start_chapter_workflow
from .section_workflow import start as start_section_workflow
from utils.retry import retry

def start(*, agent_factory, SETTINGS, root_path, logger):
    main_workflow = Agently.Workflow()
    chief_editor_agent = agent_factory.create_agent()
    # You can set chief editor agent here, read https://github.com/Maplemx/Agently/tree/main/docs/guidebook to explore
    """
    (
        chief_editor_agent
            .set_role("...")
            .set_user_info("...")
    )
    """

    # Define Workflow Chunks
    @main_workflow.chunk("start", type="Start")

    @main_workflow.chunk("input_topic")
    def input_topic_executor(inputs, storage):
        if not SETTINGS.USE_CUSTOMIZE_OUTLINE:
            storage.set(
                "topic",
                input("[Please input the topic of your research overview]: ")
            )

    @main_workflow.chunk("generate_outline")
    @retry(max_retries=3)
    def generate_outline_executor(inputs, storage):
        if SETTINGS.USE_CUSTOMIZE_OUTLINE:
            storage.set("outline", SETTINGS.CUSTOMIZE_OUTLINE)
            logger.info("[Use Customize Outline]", SETTINGS.CUSTOMIZE_OUTLINE)
        else:
            outline = (
                chief_editor_agent
                    .load_yaml_prompt(
                        path=f"{ root_path }/prompts/create_outline.yaml",
                        variables={
                            "topic": storage.get("topic"),
                            "language": SETTINGS.OUTPUT_LANGUAGE,
                            "max_chapter_num": SETTINGS.MAX_CHAPTER_NUM,
                            "max_section_num": SETTINGS.MAX_SECTION_NUM,
                        }
                    )
                    .start()
            )
            storage.set("outline", outline)
            logger.info("[Chapter Outline Generated]", outline)
            # sleep to avoid requesting too often
            time.sleep(SETTINGS.SLEEP_TIME)

            if not SETTINGS.ADVANCED_MODE:
                return

            for chapter in outline["chapter_list"]:
                section_outline = (
                    chief_editor_agent
                        .load_yaml_prompt(
                            path=f"{ root_path }/prompts/create_section_outline.yaml",
                            variables={
                                "topic": storage.get("topic"),
                                "language": SETTINGS.OUTPUT_LANGUAGE,
                                "max_chapter_num": SETTINGS.MAX_CHAPTER_NUM,
                                "max_section_num": SETTINGS.MAX_SECTION_NUM,
                                "chapter_title": chapter["chapter_title"],
                                "chapter_requirement": chapter["chapter_requirement"],
                                "search_keywords": chapter["search_keywords"],
                            }
                        )
                        .start()
                )
                if section_outline is None:
                    raise Exception("section outline is none")
                logger.info("[Section Outline Generated]", section_outline)
                chapter["section_list"] = section_outline["section_list"]
            storage.set("outline", outline)
            logger.info("[Outline Generated]", outline)
            # sleep to avoid requesting too often
            time.sleep(SETTINGS.SLEEP_TIME)


    @main_workflow.chunk("generate_chapters")
    def generate_chapters_executor(inputs, storage):
        chapters_data = []
        outline = storage.get("outline")
        if SETTINGS.ADVANCED_MODE:
            for chapter_outline in outline["chapter_list"]:
                sections_data = []
                for section_outline in chapter_outline["section_list"]:
                    section_data = start_section_workflow(
                        section_outline=section_outline,
                        agent_factory=agent_factory,
                        SETTINGS=SETTINGS,
                        root_path=root_path,
                        logger=logger,
                    )
                    if section_data:
                        sections_data.append(section_data)
                        logger.info("[Section Data Prepared]", section_data)
                chapter_data = (
                    chief_editor_agent
                        .load_yaml_prompt(
                            path=f"{ root_path }/prompts/write_chapter_summary.yaml",
                            variables={
                                "topic": storage.get("topic"),
                                "language": SETTINGS.OUTPUT_LANGUAGE,
                                "chapter_tile": chapter_outline["chapter_title"],
                                "section_list": [section['summary'] for section in sections_data],
                            }
                        )
                        .start()
                )
                chapter_data["sections_data"] = sections_data
                chapters_data.append(chapter_data)
            storage.set("chapters_data", chapters_data)
        else:
            for chapter_outline in outline["chapter_list"]:
                chapter_data = start_chapter_workflow(
                    chapter_outline=chapter_outline,
                    agent_factory=agent_factory,
                    SETTINGS=SETTINGS,
                    root_path=root_path,
                    logger=logger,
                )
                if chapter_data:
                    chapters_data.append(chapter_data)
                    logger.info("[Chapter Data Prepared]", chapter_data)
            storage.set("chapters_data", chapters_data)

    @main_workflow.chunk("generate_metadata")
    def generate_metadata_executor(inputs, storage):
        outline = storage.get("outline")
        chapters_data = storage.get("chapters_data")
        metadata = (
            chief_editor_agent
                .load_yaml_prompt(
                    path=f"{ root_path }/prompts/generate_metadata.yaml",
                    variables={
                        "topic": storage.get("topic"),
                        "language": SETTINGS.OUTPUT_LANGUAGE,
                        "reference_title": outline["report_title"],
                        "chapter_list": [chapter['revised_title'] for chapter in chapters_data],
                    }
                )
                .start()
        )
        storage.set("metadata", metadata)

    @main_workflow.chunk("generate_markdown")
    def generate_markdown_executor(inputs, storage):
        from datetime import datetime
        
        outline = storage.get("outline")
        chapters_data = storage.get("chapters_data")
        metadata = storage.get("metadata")
        
        if chapters_data and len(chapters_data) > 0:
            md_doc_text = ""
            # Columns
            if SETTINGS.IS_DEBUG:
                logger.debug("[Columns Data]", chapters_data)
                
            for chapter_data in chapters_data:
                if "revised_title" in chapter_data:
                    md_doc_text += f'## {chapter_data["revised_title"]}\n\n'
                else:
                    md_doc_text += f'## {chapter_data["title"]}\n\n'
                md_doc_text += f'{chapter_data["prologue"]}\n\n'

                if SETTINGS.ADVANCED_MODE:
                    for section_data in chapter_data["sections_data"]:
                        if "revised_title" in section_data:
                            md_doc_text += f'### {section_data["revised_title"]}\n\n'
                        else:
                            md_doc_text += f'### {section_data["title"]}\n\n'
                        md_doc_text += f'{section_data["prologue"]}\n\n'
                        md_doc_text += f'{section_data["body"]}\n\n'
                        md_doc_text += f'{section_data["conclusion"]}\n\n'
                else:
                    md_doc_text += f'{chapter_data["body"]}\n\n'
                
                md_doc_text += f'{chapter_data["conclusion"]}\n\n'


            md_doc_text += f'## References\n\n'
            for chapter_data in chapters_data:
                if SETTINGS.ADVANCED_MODE:
                    for section_data in chapter_data["sections_data"]:
                        for info in section_data["information_list"]:
                            md_doc_text += f'1. [{info["title"]}]({info["url"]})\n\n'
                else:
                    for info in chapter_data["information_list"]:
                        md_doc_text += f'1. [{info["title"]}]({info["url"]})\n\n'
            
            # Log the generated markdown
            logger.info("[Markdown Generated]", md_doc_text)
            
            # Write to file
            file_path = f'{root_path}/{metadata["report_title"]}.md'
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(md_doc_text)
        
            if not SETTINGS.MDX:
                return
            
            tags = ",".join([f"'{i.strip()}'" for i in metadata["tags"].split(",")])
            # Main Title
            md_doc_prefix = f'''---
title: '{metadata["report_title"]}'
date: '{datetime.utcnow()}'
lastmod: '{datetime.now().date()}'
tags: [{tags}]
draft: false
summary: {metadata["summary"]}
layout: PostSimple
---

'''
            # Table of Contents
            md_doc_prefix += "<TOCInline toc={props.toc} toHeading={2} asDisclosure />\n\n"
            
            md_doc_text = md_doc_prefix + md_doc_text

            # Write to file
            file_path = f'{root_path}/{metadata["filename"]}.mdx'
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(md_doc_text)
        else:
            logger.info("[Markdown Generation Failed] Due to no chapter data.")

    # Connect Chunks
    (
        main_workflow.chunks["start"]
            .connect_to(main_workflow.chunks["input_topic"])
            .connect_to(main_workflow.chunks["generate_outline"])
            .connect_to(main_workflow.chunks["generate_chapters"])
            .connect_to(main_workflow.chunks["generate_metadata"])
            .connect_to(main_workflow.chunks["generate_markdown"])
    )

    # Start Workflow
    main_workflow.start()