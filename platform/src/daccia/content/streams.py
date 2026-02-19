"""Three content streams: Patient Conversations, Ask a Nurse, Ask an ED Doctor."""

from __future__ import annotations

import time

from daccia.content.base import (
    BaseGenerator,
    ContentRequest,
    ContentType,
    GeneratedContent,
)
from daccia.llm.prompts import render

PERSONA_DESCRIPTIONS = {
    ContentType.PATIENT_CONVERSATION: (
        "You are crafting a relatable conversation between a patient and an AI "
        "system in a critical care setting. Show how explainable AI helps patients "
        "understand their care. Use accessible, non-technical language."
    ),
    ContentType.ASK_A_NURSE: (
        "You are a seasoned ICU nurse who has embraced AI tools. You explain how "
        "AI assists in monitoring, early warning systems, and patient safety. "
        "Your tone is warm, practical, and grounded in daily clinical reality."
    ),
    ContentType.ASK_AN_ED_DOCTOR: (
        "You are an emergency physician who uses AI for triage, diagnostics, and "
        "decision support. You speak with authority but acknowledge uncertainty. "
        "You value speed and clarity. You reference evidence-based medicine."
    ),
}

TEMPLATE_MAP = {
    ContentType.PATIENT_CONVERSATION: "stream_patient.j2",
    ContentType.ASK_A_NURSE: "stream_nurse.j2",
    ContentType.ASK_AN_ED_DOCTOR: "stream_doctor.j2",
}


class StreamGenerator(BaseGenerator):
    """Generates conversational content for the three streams."""

    def get_system_prompt(self, request: ContentRequest) -> str:
        return render(
            TEMPLATE_MAP[request.content_type],
            topic=request.topic,
            persona=PERSONA_DESCRIPTIONS[request.content_type],
            audience=request.target_audience,
            word_count=request.target_word_count,
            style_context=self._build_style_context(),
        )

    def generate(self, request: ContentRequest) -> GeneratedContent:
        start = time.time()
        system_prompt = self.get_system_prompt(request)

        response = self._client.generate(
            system=system_prompt,
            messages=[{"role": "user", "content": f"Topic: {request.topic}"}],
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
                "stream": request.content_type.value,
            },
        )
