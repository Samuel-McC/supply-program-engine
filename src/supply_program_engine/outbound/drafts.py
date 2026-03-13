from __future__ import annotations

from supply_program_engine.models import OutboundDraft
from supply_program_engine.outbound.rendering import render_template


def build_email_template(segment: str) -> tuple[str, str]:
    if segment == "industrial_distributor":
        subject = "Film-faced eucalyptus panel supply program for {{ company_name }}"
        body = (
            "Hi {{ company_name }},\n\n"
            "We support {{ segment }} buyers in {{ location }} with a structural panel supply program "
            "focused on film-faced eucalyptus panels for formwork and industrial applications.\n\n"
            "If relevant, we can share:\n"
            "- consistent spec and factory capacity\n"
            "- container program pricing\n"
            "- inspection documents and load photos\n"
            "- stable lead times\n\n"
            "Regards,\n"
            "Supply Program"
        )
        return subject, body

    if segment == "regional_building_supplier":
        subject = "Reusable formwork panel supply for {{ company_name }}"
        body = (
            "Hi {{ company_name }},\n\n"
            "We support {{ segment }} businesses in {{ location }} with reusable film-faced eucalyptus panels "
            "for construction and formwork use.\n\n"
            "If useful, we can share specs and supply terms.\n\n"
            "Regards,\n"
            "Supply Program"
        )
        return subject, body

    if segment == "concrete_contractor_large":
        subject = "Reusable formwork panels for {{ company_name }}"
        body = (
            "Hi {{ company_name }},\n\n"
            "We support {{ segment }} teams in {{ location }} with reusable film-faced eucalyptus panels "
            "designed for concrete formwork use.\n\n"
            "If useful, I can share specs and pricing.\n\n"
            "Regards,\n"
            "Supply Program"
        )
        return subject, body

    if segment == "modular_manufacturer":
        subject = "Structural panel supply program for {{ company_name }}"
        body = (
            "Hi {{ company_name }},\n\n"
            "We support {{ segment }} businesses in {{ location }} with consistent structural panel supply "
            "and repeatable container pricing.\n\n"
            "If relevant, we can share specs and capacity details.\n\n"
            "Regards,\n"
            "Supply Program"
        )
        return subject, body

    subject = "Structural panel supply for {{ company_name }}"
    body = (
        "Hi {{ company_name }},\n\n"
        "We support industrial panel buyers in {{ location }} with structural eucalyptus-based panel supply.\n\n"
        "Regards,\n"
        "Supply Program"
    )
    return subject, body


def make_draft(
    draft_id: str,
    entity_id: str,
    company_name: str,
    location: str | None,
    segment: str,
) -> OutboundDraft:
    subject_template, body_template = build_email_template(segment=segment)

    context = {
        "company_name": company_name or "there",
        "location": location or "your region",
        "segment": segment,
    }

    subject = render_template(subject_template, context)
    body = render_template(body_template, context)

    return OutboundDraft(
        draft_id=draft_id,
        entity_id=entity_id,
        segment=segment,
        subject=subject,
        body=body,
        template_version="v2_merge_fields",
        generation_mode="deterministic",
    )
