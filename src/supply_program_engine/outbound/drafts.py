from __future__ import annotations

from supply_program_engine.models import OutboundDraft


def build_email_draft(entity_id: str, segment: str) -> tuple[str, str]:
    """
    Deterministic copy templates.
    No LLM yet. Keep it simple, industrial, and segment-aligned.
    """

    if segment == "industrial_distributor":
        subject = "Film-faced eucalyptus panel supply program (containers/month)"
        body = (
            "Hi —\n\n"
            "We run a U.S. structural panel supply program focused on film-faced eucalyptus panels "
            "for formwork and industrial applications.\n\n"
            "If you’re absorbing containers monthly, we can offer:\n"
            "- consistent spec + factory capacity\n"
            "- container program pricing\n"
            "- inspection docs + load photos\n"
            "- stable lead times\n\n"
            "What volume are you moving per month (containers) and which states do you service?\n\n"
            "Regards,\n"
            "Supply Program"
        )
        return subject, body

    if segment == "regional_building_supplier":
        subject = "Reusable formwork panels (alternative to OSB) — consistent supply"
        body = (
            "Hi —\n\n"
            "We supply film-faced eucalyptus panels used for concrete formwork and industrial use.\n"
            "If you supply contractors/builders regionally, we can support repeat container programs.\n\n"
            "Quick question: do you currently stock formwork panels or OSB alternatives?\n\n"
            "Regards,\n"
            "Supply Program"
        )
        return subject, body

    if segment == "concrete_contractor_large":
        subject = "Reusable formwork panels — stronger alternative to OSB (site use)"
        body = (
            "Hi —\n\n"
            "We supply film-faced eucalyptus panels used on concrete job sites for formwork.\n"
            "They’re designed for repeat reuse cycles and moisture durability.\n\n"
            "If useful, I can send specs + container pricing.\n"
            "How are you currently sourcing formwork panels (and typical monthly usage)?\n\n"
            "Regards,\n"
            "Supply Program"
        )
        return subject, body

    if segment == "modular_manufacturer":
        subject = "Structural panel supply program (consistent spec + container pricing)"
        body = (
            "Hi —\n\n"
            "We provide a consistent structural panel supply program (eucalyptus-based) with "
            "repeatable spec and container pricing.\n\n"
            "If you’re buying on program/forecast, we can share:\n"
            "- capacity + lead time\n"
            "- inspection documentation\n"
            "- consistent spec sheets\n\n"
            "Are you sourcing panels on contract today?\n\n"
            "Regards,\n"
            "Supply Program"
        )
        return subject, body

    subject = "Structural panel supply program"
    body = (
        "Hi —\n\n"
        "We run a structural panel supply program focused on industrial applications.\n"
        "If relevant, I can share specs and pricing.\n\n"
        "Regards,\n"
        "Supply Program"
    )
    return subject, body


def make_draft(draft_id: str, entity_id: str, segment: str) -> OutboundDraft:
    subject, body = build_email_draft(entity_id=entity_id, segment=segment)
    return OutboundDraft(
        draft_id=draft_id,
        entity_id=entity_id,
        segment=segment,
        subject=subject,
        body=body,
    )