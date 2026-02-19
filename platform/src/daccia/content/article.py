"""Article generator for Medium posts and blog pieces."""

from __future__ import annotations

import time

from daccia.content.base import (
    BRAND_VOICE,
    BaseGenerator,
    ContentRequest,
    ContentType,
    GeneratedContent,
)
from daccia.llm.prompts import render


class ArticleGenerator(BaseGenerator):
    """Generates long-form articles for Medium and the daccia.io blog."""

    TEMPLATE_MAP = {
        ContentType.MEDIUM_ARTICLE: "article_medium.j2",
        ContentType.BLOG_POST: "article_blog.j2",
    }

    def get_system_prompt(self, request: ContentRequest) -> str:
        template_name = self.TEMPLATE_MAP[request.content_type]
        return render(
            template_name,
            topic=request.topic,
            audience=request.target_audience,
            word_count=request.target_word_count,
            key_points=request.key_points or [],
            style_context=self._build_style_context(),
            references=request.references or [],
            brand_voice=BRAND_VOICE,
        )

    def generate(self, request: ContentRequest) -> GeneratedContent:
        start = time.time()
        system_prompt = self.get_system_prompt(request)

        user_message = f"Write an article about: {request.topic}"
        if request.key_points:
            user_message += "\n\nKey points to cover:\n"
            user_message += "\n".join(f"- {p}" for p in request.key_points)
        if request.references:
            user_message += "\n\nReferences to incorporate:\n"
            user_message += "\n".join(f"- {r}" for r in request.references)

        response = self._client.generate(
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        lines = response.strip().split("\n")
        title = lines[0].lstrip("# ").strip() if lines else request.topic
        body = "\n".join(lines[1:]).strip()

        return GeneratedContent(
            title=title,
            body=body,
            content_type=request.content_type,
            metadata={
                "word_count": len(body.split()),
                "generation_time_seconds": round(time.time() - start, 2),
                "token_usage": self._client.usage_summary,
            },
        )
