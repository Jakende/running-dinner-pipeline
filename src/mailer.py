import os
from typing import Dict, List

from .models import CourseType, DietType, DinnerPlan, Team


COURSE_LABELS = {
    CourseType.STARTER: {"de": "Vorspeise", "en": "Starter"},
    CourseType.MAIN: {"de": "Hauptgang", "en": "Main course"},
    CourseType.DESSERT: {"de": "Dessert", "en": "Dessert"},
}


def _get_diet_str(diet: DietType, lang: str) -> str:
    if lang == "de":
        if diet == DietType.VEGAN:
            return "vegan"
        if diet == DietType.VEGETARIAN:
            return "vegetarisch"
        if diet == DietType.OMNIVORE:
            return "alles / omnivor"
        return "unbekannt"

    if diet == DietType.VEGAN:
        return "vegan"
    if diet == DietType.VEGETARIAN:
        return "vegetarian"
    if diet == DietType.OMNIVORE:
        return "omnivore / no restriction"
    return "unknown"


def _format_allergies(allergies: Dict[str, str], lang: str) -> str:
    items = []

    def is_yes(value):
        return isinstance(value, str) and value.lower() == "ja"

    if is_yes(allergies.get("gluten")):
        items.append("Gluten")
    if is_yes(allergies.get("lactose")):
        items.append("Laktose" if lang == "de" else "Lactose")
    if is_yes(allergies.get("peanuts")):
        items.append("Erdnüsse" if lang == "de" else "Peanuts")
    if is_yes(allergies.get("soya")):
        items.append("Soja" if lang == "de" else "Soy")
    if is_yes(allergies.get("nuts")):
        items.append("Schalenfrüchte" if lang == "de" else "Tree nuts")

    other = allergies.get("other")
    if other and other.lower() not in {"none", "keine", "nein"}:
        items.append(other)

    if not items:
        return "keine angegeben" if lang == "de" else "none listed"
    return ", ".join(items)


def _event_line(event_info: Dict[str, str], lang: str) -> str:
    title = event_info.get("title") or "Running Dinner"
    date = event_info.get("date") or "-"
    time = event_info.get("time") or "-"

    if lang == "de":
        meeting_point = event_info.get("meeting_point") or ""
        line = f"{title} am {date}, Start: {time}"
        if meeting_point:
            line += f", Treffpunkt/Abschluss: {meeting_point}"
        return line

    meeting_point = event_info.get("meeting_point_en") or event_info.get("meeting_point") or ""
    line = f"{title} on {date}, start: {time}"
    if meeting_point:
        line += f", meeting/final location: {meeting_point}"
    return line


def _format_visit(visit: Dict, lang: str) -> str:
    course = COURSE_LABELS[visit["course"]][lang]
    notes = visit["hints"] or ("keine Hinweise" if lang == "de" else "no notes")
    if lang == "de":
        return f"- {course}: {visit['address']}\n  Hinweise zur Adresse: {notes}"
    return f"- {course}: {visit['address']}\n  Address notes: {notes}"


def _format_hosting(hosting, lang: str) -> str:
    course = COURSE_LABELS[hosting.course][lang]
    guest_count = len(hosting.guests) * 2
    if lang == "de":
        lines = [
            f"- {course}: Ihr richtet diesen Gang an eurer Dinner-Location aus.",
            f"  Rechnet mit {guest_count} Gästen aus {len(hosting.guests)} Teams.",
            "  Ernährungsinfos für eure Gäste:",
        ]
        for idx, guest in enumerate(hosting.guests, 1):
            lines.append(
                f"  - Gast-Team {idx}: {_get_diet_str(guest.diet, lang)}; "
                f"Allergien: {_format_allergies(guest.allergies, lang)}"
            )
        return "\n".join(lines)

    lines = [
        f"- {course}: You host this course at your dinner location.",
        f"  Plan for {guest_count} guests from {len(hosting.guests)} teams.",
        "  Dietary information for your guests:",
    ]
    for idx, guest in enumerate(hosting.guests, 1):
        lines.append(
            f"  - Guest team {idx}: {_get_diet_str(guest.diet, lang)}; "
            f"allergies: {_format_allergies(guest.allergies, lang)}"
        )
    return "\n".join(lines)


def _build_language_section(schedule: Dict, event_info: Dict[str, str], lang: str) -> str:
    if lang == "de":
        additional = event_info.get("additional_info", "").strip()
        lines = [
            "DEUTSCH",
            "",
            "Hallo zusammen,",
            "",
            "hier ist euer Plan für das Running Dinner.",
            _event_line(event_info, "de"),
        ]
        if additional:
            lines.extend(["", f"Weitere Informationen: {additional}"])
        lines.extend(["", "Euer Ablauf:"])
    else:
        additional = (
            event_info.get("additional_info_en")
            or event_info.get("additional_info")
            or ""
        ).strip()
        lines = [
            "ENGLISH",
            "",
            "Hello everyone,",
            "",
            "here is your Running Dinner schedule.",
            _event_line(event_info, "en"),
        ]
        if additional:
            lines.extend(["", f"Additional information: {additional}"])
        lines.extend(["", "Your schedule:"])

    for course in [CourseType.STARTER, CourseType.MAIN, CourseType.DESSERT]:
        if schedule.get("hosting") and schedule["hosting"].course == course:
            lines.append(_format_hosting(schedule["hosting"], lang))
            continue

        visit = next((item for item in schedule["visits"] if item["course"] == course), None)
        if visit:
            lines.append(_format_visit(visit, lang))

    if lang == "de":
        lines.extend(["", "Viel Spaß!", "Euer Orga-Team"])
    else:
        lines.extend(["", "Have fun!", "Your organizing team"])

    return "\n".join(lines)


def generate_email_content(team: Team, schedule: Dict, event_info: Dict[str, str] | None = None) -> str:
    event_info = event_info or {}
    recipients = [email for email in [team.email1, team.email2] if email]
    recipient_str = f"An / To: {', '.join(recipients)}"
    subject = event_info.get("title") or "Running Dinner"

    sections = [
        recipient_str,
        f"Betreff / Subject: {subject} - euer Ablauf / your schedule",
        "",
        _build_language_section(schedule, event_info, "de"),
        "",
        "---",
        "",
        _build_language_section(schedule, event_info, "en"),
    ]
    return "\n".join(sections)


def write_emails(
    plan: DinnerPlan,
    teams: List[Team],
    output_dir: str,
    event_info: Dict[str, str] | None = None,
):
    os.makedirs(output_dir, exist_ok=True)
    temp_map = {team.id: team for team in teams}
    schedules = {team.id: {"hosting": None, "visits": []} for team in teams}

    for match in plan.matches:
        host = temp_map[match.host_id]

        class EnrichedMatch:
            pass

        enriched = EnrichedMatch()
        enriched.course = match.course
        enriched.guests = [temp_map[guest_id] for guest_id in match.guest_ids]
        schedules[match.host_id]["hosting"] = enriched

        for guest_id in match.guest_ids:
            schedules[guest_id]["visits"].append(
                {
                    "course": match.course,
                    "address": host.full_address,
                    "hints": host.hints,
                }
            )

    count = 0
    for team_id, schedule in schedules.items():
        team = temp_map[team_id]
        content = generate_email_content(team, schedule, event_info)
        filename = f"{team.name1}_{team.name2}_{team_id}.txt".replace(" ", "_").replace("/", "-")
        with open(os.path.join(output_dir, filename), "w", encoding="utf-8") as f:
            f.write(content)
        count += 1

    return count
