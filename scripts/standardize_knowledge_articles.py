import html
import re
from pathlib import Path

from bs4 import BeautifulSoup


BASE_URL = "https://sig-poetry-language-insurance.trycloudflare.com"
MATRIX_PATH = Path(r"D:\University\knowledgeManagementSystem\KMS_TEAM_02_W12\access_matrix.md")

STANDARD_HEADINGS = [
    "Article Title",
    "Parent Workspace",
    "Workspace Dimension",
    "Access Role",
    "Tags",
    "Target Synonym List",
    "Purpose",
    "When to Use This Article",
    "Problem",
    "Analysis / Root Cause",
    "Verified Solution / SOP Steps",
    "Checklist Before Closing",
    "Canned Response / Shortcut",
    "Related Lognotes",
    "KM Classification",
    "Review Rule",
]

CHECKLIST_ALIASES = {
    "Checklist Before Replying": "Checklist Before Closing",
    "Checklist Before Escalation": "Checklist Before Closing",
    "Validation Checklist": "Checklist Before Closing",
}

EXTRA_TO_STEPS = {
    "Vendor Evidence Guide",
    "Vendor Mapping Rule",
    "Classification Guide",
    "Customer Explanation Rule",
    "Required Evidence by Product Type",
}


def clean_cell(value):
    return value.replace("`", "").replace("**", "").strip()


def load_matrix():
    data = {}
    for raw in MATRIX_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cols = [clean_cell(c) for c in line.strip("|").split("|")]
        if len(cols) < 6:
            continue
        code, title, ws, role, tags_raw, synonyms_raw = cols[:6]
        if code.lower() == "code" or set(code) <= {"-"}:
            continue
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        synonyms = [s.strip() for s in synonyms_raw.split(";") if s.strip()]
        metadata = {
            "code": code,
            "workspace_dimension": ws,
            "access_role": role,
            "tags": tags,
            "synonyms": synonyms,
        }
        data[title] = metadata
        data[code] = metadata
    return data


MATRIX = load_matrix()
Article = env["knowledge.article"].with_context(active_test=False)
MailMessage = env["mail.message"].sudo()

parent_names = [
    "SO KNOWLEDGE",
    "PURCHASE ORDER KNOWLEDGE",
    "TICKET KNOWLEDGE",
    "IT KNOWLEDGE",
    "HR KNOWLEDGE",
    "GENERAL KNOWLEDGE",
]

article_ids = []
for parent in Article.search([("name", "in", parent_names), ("active", "=", True)]):
    article_ids.extend(
        Article.search([("parent_id", "=", parent.id), ("active", "=", True)], order="sequence,id").ids
    )
article_ids = sorted(set(article_ids))

PREDEFINED = {
    71: {
        "Purpose": "<p>This article helps IT staff onboard new technical hires with the correct accounts, workstation setup, VPN access, repository access, and security orientation.</p>",
        "When to Use This Article": "<p>Use this article when:</p><ol><li>A new IT engineer or developer joins Triple H &amp; T.</li><li>IT must prepare workstation, VPN, GitHub, and team access.</li><li>The employee needs first-week technical orientation.</li><li>Security awareness and acceptable use requirements must be confirmed.</li></ol>",
        "Problem": "<p>New IT hires can lose productive time when account creation, workstation setup, VPN access, and repository permissions are not prepared before onboarding.</p>",
        "Analysis / Root Cause": "<p>Onboarding delays usually happen because setup tasks are handled informally, access ownership is unclear, or security training is not tracked as part of the first-week checklist.</p>",
        "Verified Solution / SOP Steps": "<ol><li>Open the IT onboarding checklist.</li><li>Confirm the employee role, department, start date, and manager.</li><li>Create or verify the corporate GitHub account.</li><li>Configure SSH keys and two-factor authentication.</li><li>Prepare the approved development workstation and tools.</li><li>Configure VPN access and test network connectivity.</li><li>Assign repository, project board, and team channel access.</li><li>Complete the security briefing and acceptable use confirmation.</li><li>Add a lognote confirming onboarding completion.</li></ol>",
        "Checklist Before Closing": "<ul><li>Corporate GitHub account is active.</li><li>SSH key and two-factor authentication are configured.</li><li>VPN connectivity has been tested.</li><li>Approved tools and IDEs are installed.</li><li>Security briefing is completed.</li><li>Team channels and project boards are assigned.</li></ul>",
        "Canned Response / Shortcut": "<p>Shortcut: ::it_onboarding</p><p>Response:<br>The IT onboarding checklist has been reviewed. Please confirm that the GitHub account, SSH key, VPN access, workstation tools, and security briefing are complete before closing the onboarding task.</p>",
        "KM Classification": "<p>Layer 1 Source: #Collective<br>Layer 2 Wiig Dimension: #Methodological<br>Layer 3 Topic: #ITOnboarding</p>",
        "Review Rule": "<p>Review this article every 2 weeks or whenever onboarding tools, VPN process, repository access, or security policy changes.</p>",
    },
    72: {
        "Purpose": "<p>This article helps IT staff maintain network security and respond consistently to firewall, port isolation, and unauthorized access incidents.</p>",
        "When to Use This Article": "<p>Use this article when:</p><ol><li>A network security alert is detected.</li><li>Unauthorized access or suspicious traffic is reported.</li><li>Firewall policy or port isolation must be reviewed.</li><li>An endpoint may need immediate containment.</li></ol>",
        "Problem": "<p>Network incidents can expose company systems if IT staff do not isolate affected endpoints and document the response quickly.</p>",
        "Analysis / Root Cause": "<p>Security response gaps usually happen when firewall ownership is unclear, port isolation is delayed, or incident details are not recorded in the correct system.</p>",
        "Verified Solution / SOP Steps": "<ol><li>Open the IT security incident record.</li><li>Identify the affected endpoint, user, IP address, and time of detection.</li><li>Review firewall logs and traffic pattern.</li><li>Trigger port isolation for the affected endpoint when required.</li><li>Notify the security operations owner immediately.</li><li>Document incident details, containment action, and next review step.</li><li>Perform root cause analysis and record findings.</li><li>Submit the incident summary within the required timeline.</li></ol>",
        "Checklist Before Closing": "<ul><li>Endpoint or network segment is identified.</li><li>Firewall logs are reviewed.</li><li>Port isolation decision is documented.</li><li>Security owner has been notified.</li><li>Incident log includes root cause and next action.</li><li>Follow-up review is scheduled if needed.</li></ul>",
        "Canned Response / Shortcut": "<p>Shortcut: ::network_security</p><p>Response:<br>The security alert has been reviewed. Please confirm firewall evidence, containment status, assigned owner, and incident log completion before closing the security case.</p>",
        "KM Classification": "<p>Layer 1 Source: #Collective<br>Layer 2 Wiig Dimension: #Methodological<br>Layer 3 Topic: #NetworkSecurity</p>",
        "Review Rule": "<p>Review this article every 2 weeks or whenever firewall rules, security escalation paths, or port isolation procedures change.</p>",
    },
    73: {
        "Purpose": "<p>This article defines general workplace conduct expectations for all Triple H &amp; T employees and supports consistent, respectful collaboration across departments.</p>",
        "When to Use This Article": "<p>Use this article when:</p><ol><li>A new employee needs general workplace guidance.</li><li>A manager explains expected professional conduct.</li><li>An employee asks about acceptable workplace behavior.</li><li>A cross-functional team needs a shared conduct reference.</li></ol>",
        "Problem": "<p>Employees may interpret workplace conduct expectations differently if the company does not provide a shared guideline.</p>",
        "Analysis / Root Cause": "<p>Conduct issues usually happen when professional communication, confidentiality, and escalation expectations are not documented clearly for all departments.</p>",
        "Verified Solution / SOP Steps": "<ol><li>Review the general workspace conduct guideline with the employee or team.</li><li>Confirm respectful communication standards.</li><li>Remind employees to protect internal business and customer information.</li><li>Explain how to report conduct concerns to HR or the responsible manager.</li><li>Document any clarification or follow-up action in the correct internal record.</li></ol>",
        "Checklist Before Closing": "<ul><li>Employee understands respectful communication expectations.</li><li>Confidentiality requirement is acknowledged.</li><li>Reporting path for conduct concerns is clear.</li><li>Relevant manager or HR owner is identified if follow-up is needed.</li><li>Any required note or confirmation is recorded.</li></ul>",
        "Canned Response / Shortcut": "<p>Shortcut: ::general_conduct</p><p>Response:<br>Please follow Triple H &amp; T workplace conduct expectations: communicate respectfully, protect confidential information, collaborate professionally, and report unresolved conduct concerns to the responsible manager or HR.</p>",
        "KM Classification": "<p>Layer 1 Source: #Collective<br>Layer 2 Wiig Dimension: #Conceptual<br>Layer 3 Topic: #WorkspaceConduct</p>",
        "Review Rule": "<p>Review this article every 2 weeks or whenever company conduct expectations, HR reporting paths, or confidentiality rules change.</p>",
    },
    74: {
        "Purpose": "<p>This confidential article guides HR managers in handling payroll review, salary policy matters, performance warnings, and disciplinary documentation.</p>",
        "When to Use This Article": "<p>Use this article when:</p><ol><li>HR reviews payroll or salary adjustment matters.</li><li>A formal performance warning must be documented.</li><li>A disciplinary case requires evidence and follow-up.</li><li>Confidential employee records must be handled by authorized HR personnel.</li></ol>",
        "Problem": "<p>Payroll and disciplinary information can create confidentiality, compliance, and employee relations risk if handled outside the authorized HR process.</p>",
        "Analysis / Root Cause": "<p>Risk occurs when salary decisions, warning records, or disciplinary evidence are stored informally, shared with unauthorized users, or processed without HR approval.</p>",
        "Verified Solution / SOP Steps": "<ol><li>Open the authorized HR record.</li><li>Confirm that the user has HR manager permission.</li><li>Document the payroll, performance, or disciplinary issue with factual evidence.</li><li>Record the formal review decision and approval owner.</li><li>Schedule follow-up reviews when required.</li><li>Restrict access to authorized HR personnel only.</li><li>Add a confidential HR lognote summarizing the action.</li></ol>",
        "Checklist Before Closing": "<ul><li>Access permission is verified as HR manager only.</li><li>Evidence is factual and relevant.</li><li>Payroll or disciplinary decision has an approval owner.</li><li>Confidential records are stored in the authorized HR workspace.</li><li>Follow-up review date is recorded if required.</li></ul>",
        "Canned Response / Shortcut": "<p>Shortcut: ::hr_confidential_review</p><p>Response:<br>This matter is confidential and must be handled only by authorized HR managers. Please record factual evidence, approval owner, and follow-up action in the restricted HR workspace.</p>",
        "KM Classification": "<p>Layer 1 Source: #Collective<br>Layer 2 Wiig Dimension: #Methodological<br>Layer 3 Topic: #HRConfidential</p>",
        "Review Rule": "<p>Review this article every 2 weeks or whenever HR approval workflow, payroll policy, or disciplinary documentation requirements change.</p>",
    },
    65: {
        "Purpose": "<p>This article helps support staff identify repeated Helpdesk issues and convert validated recurring solutions into Odoo Knowledge articles.</p>",
        "When to Use This Article": "<p>Use this article when:</p><ol><li>The same customer issue appears in multiple Helpdesk tickets.</li><li>Support agents repeat the same troubleshooting explanation.</li><li>A ticket solution should become a reusable SOP.</li><li>Managers need to reduce repeated mistakes or reopened tickets.</li></ol>",
        "Problem": "<p>Repeated support issues create duplicated work when the verified solution stays only inside individual tickets.</p>",
        "Analysis / Root Cause": "<p>Recurring issues usually remain undocumented because agents close tickets after solving the case but do not convert the fix, root cause, and validation steps into a Knowledge article.</p>",
        "Verified Solution / SOP Steps": "<ol><li>Open Helpdesk and search for repeated ticket patterns.</li><li>Group tickets by product, problem type, customer question, or operational process.</li><li>Select the clearest solved ticket as the source example.</li><li>Extract Problem, Analysis, and Solution from the ticket lognote.</li><li>Create or update an Odoo Knowledge article using the standard template.</li><li>Add related ticket lognote links under Related Lognotes.</li><li>Tag the article with the correct workspace, access role, and synonym list.</li><li>Ask the responsible manager to review the article before publishing.</li></ol>",
        "Checklist Before Closing": "<ul><li>At least one solved ticket is linked.</li><li>Problem, Analysis, and Solution are documented.</li><li>Article uses the standard Odoo Knowledge template.</li><li>Access role and workspace dimension are correct.</li><li>Related lognote links are clickable.</li><li>Responsible department has reviewed the SOP.</li></ul>",
        "Canned Response / Shortcut": "<p>Shortcut: ::ticket_to_knowledge</p><p>Response:<br>This issue appears repeatedly in Helpdesk. Please extract the verified ticket solution, create or update the Knowledge article, attach related lognote links, and request manager review before closing.</p>",
        "KM Classification": "<p>Layer 1 Source: #Collective<br>Layer 2 Wiig Dimension: #Methodological<br>Layer 3 Topic: #KnowledgeRetention</p>",
        "Review Rule": "<p>Review this article every 2 weeks or whenever Helpdesk ticket patterns, support escalation rules, or Knowledge article standards change.</p>",
    },
}

PREDEFINED_LOGNOTES = {
    71: [
        "Fix: New IT engineer setup is delayed (P) -> GitHub, VPN, and workstation tasks were not prepared before start date (A) -> prepare access checklist before the first working day (S). #Collective #Methodological #Onboarding",
        "Trick: Developer onboarding can miss security training (P) -> setup focuses on tools but ignores mandatory policy briefing (A) -> include security awareness in the first-week checklist (S). #Individual #Expectational #Security",
        "Fix: Repository access is incomplete for new developer (P) -> SSH key and 2FA are not configured (A) -> verify GitHub account, SSH key, and 2FA before project assignment (S). #Relational #Factual #IT",
        "Trick: VPN setup issues delay onboarding (P) -> laptop network profile is not tested before orientation (A) -> validate VPN connectivity during workstation setup (S). #Collective #Conceptual #Network",
        "Fix: New engineer cannot join team channels (P) -> communication groups were not provisioned (A) -> add the user to approved channels and project boards before handover (S). #Individual #Methodological #Onboarding",
    ],
    72: [
        "Fix: Firewall alert is not documented (P) -> IT resolved the alert but did not record evidence (A) -> add firewall log, owner, and containment result before closing (S). #Collective #Methodological #Security",
        "Trick: Port isolation may be delayed (P) -> endpoint owner is not identified quickly (A) -> record endpoint, IP address, and responsible owner in the incident log (S). #Individual #Expectational #NetworkSecurity",
        "Fix: Unauthorized access review is incomplete (P) -> traffic evidence was not attached (A) -> attach firewall logs and suspicious IP details to the security case (S). #Relational #Factual #Firewall",
        "Trick: Security incident can be reopened (P) -> root cause is not documented after containment (A) -> add root cause analysis before marking the incident resolved (S). #Collective #Conceptual #Security",
        "Fix: Network incident escalation is late (P) -> security owner was not notified within required timing (A) -> notify security operations immediately and record timestamp (S). #Individual #Methodological #Escalation",
    ],
    73: [
        "Fix: Workplace conduct expectation is unclear (P) -> employee did not know reporting path (A) -> document manager or HR escalation path in the conduct record (S). #Collective #Methodological #Conduct",
        "Trick: Cross-team communication can become inconsistent (P) -> teams use different etiquette standards (A) -> refer employees to the general conduct guideline during onboarding (S). #Individual #Expectational #Workspace",
        "Fix: Confidential information was discussed in an open channel (P) -> employee did not identify internal information as confidential (A) -> remind staff to protect customer and business data (S). #Relational #Factual #Confidentiality",
        "Trick: New employee orientation may skip conduct standards (P) -> onboarding focuses only on technical tasks (A) -> include workplace conduct review in first-week orientation (S). #Collective #Conceptual #Onboarding",
        "Fix: Conduct follow-up is not recorded (P) -> verbal clarification was not documented (A) -> add a short internal note with owner and next action (S). #Individual #Methodological #HR",
    ],
    74: [
        "Fix: HR disciplinary review lacks evidence (P) -> warning record was created without supporting facts (A) -> attach factual evidence before HR approval (S). #Collective #Methodological #HR",
        "Trick: Payroll review may expose confidential data (P) -> salary discussion is shared outside authorized HR workspace (A) -> keep payroll notes in restricted HR records only (S). #Individual #Expectational #Confidential",
        "Fix: Performance warning follow-up is missing (P) -> review date was not scheduled (A) -> add 30, 60, and 90 day follow-up where required (S). #Relational #Factual #Disciplinary",
        "Trick: Salary adjustment can be processed without approval trace (P) -> approval owner is not recorded (A) -> document HR manager and finance sign-off before update (S). #Collective #Conceptual #Payroll",
        "Fix: HR case access is too broad (P) -> non-HR user can view confidential context (A) -> restrict the record to HR manager permission before closing (S). #Individual #Methodological #Security",
    ],
    65: [
        "Fix: Repeated SSD delivery tickets are not converted to Knowledge (P) -> support agents answer the same stock question repeatedly (A) -> create a Knowledge SOP from the solved ticket pattern (S). #Collective #Methodological #Helpdesk",
        "Trick: Warranty evidence questions repeat across tickets (P) -> required proof is not documented in a reusable article (A) -> convert evidence checklist into a Knowledge article (S). #Individual #Expectational #Warranty",
        "Fix: VAT explanation tickets are reopened (P) -> customer-facing tax response is inconsistent (A) -> document a standard price and tax explanation SOP (S). #Relational #Factual #Tax",
        "Trick: Delivery delay responses vary by agent (P) -> support does not link SO, PO, and receipt status before replying (A) -> create a delivery delay response SOP with validation steps (S). #Collective #Conceptual #Delivery",
        "Fix: Product quantity mistakes repeat in Helpdesk (P) -> ticket solutions remain isolated in chatter (A) -> extract Problem, Analysis, and Solution into Knowledge with lognote links (S). #Individual #Methodological #KnowledgeRetention",
    ],
}

SUPPLEMENTAL_LOGNOTES = {
    63: [
        (
            "purchase.order",
            "P00017",
            "Trick: Storage reorder quantities can be too low (P) -> recent confirmed SO demand was not reviewed (A) -> compare forecasted demand and vendor lead time before RFQ approval (S). #Collective #Expectational #Inventory",
        )
    ],
    66: [
        (
            "purchase.order",
            "P00040",
            "Trick: RFQ vendor mapping may look correct but the vendor SKU is outdated (P) -> buyer copied an old supplier reference (A) -> verify vendor SKU and purchase price before sending RFQ (S). #Individual #Expectational #Vendor",
        )
    ],
    67: [
        (
            "helpdesk.ticket",
            "Customer reported a wrong quotation total.",
            "Trick: Customer inquiry routing is delayed (P) -> the question is not classified as sales, delivery, pricing, tax, or warranty (A) -> tag the ticket category before assigning the owner (S). #Collective #Conceptual #CustomerService",
        )
    ],
    68: [
        (
            "helpdesk.ticket",
            "Customer pushed back on a delivery delay",
            "Trick: Delivery delay reply may create a wrong promise (P) -> support replies before checking SO delivery and PO receipt status (A) -> verify linked records before giving revised ETA (S). #Individual #Expectational #Delivery",
        )
    ],
}

TICKET2_TARGETS = [
    ("helpdesk.ticket", "Customer disputed the restock date for an unavailable item."),
    ("helpdesk.ticket", "Warranty ticket was opened for the wrong device."),
    ("helpdesk.ticket", "Customer questioned VAT difference between quotation and invoice."),
    ("helpdesk.ticket", "Customer pushed back on a delivery delay"),
    ("helpdesk.ticket", "There's another mistakes in product quantity"),
]


def sectionize(body):
    soup = BeautifulSoup(body or "", "html.parser")
    sections = {heading: [] for heading in STANDARD_HEADINGS}
    current = None
    for child in soup.contents:
        if getattr(child, "name", None) in ("h1", "h2", "h3"):
            heading = child.get_text(" ", strip=True)
            if heading in STANDARD_HEADINGS:
                current = heading
                continue
            if heading in CHECKLIST_ALIASES:
                current = CHECKLIST_ALIASES[heading]
                continue
            if heading in EXTRA_TO_STEPS:
                current = "Verified Solution / SOP Steps"
                sections[current].append(f"<p><strong>{html.escape(heading)}</strong></p>")
                continue
            current = None
            continue
        if current:
            rendered = str(child).strip()
            if rendered:
                sections[current].append(rendered)
    return {key: "".join(value).strip() for key, value in sections.items()}


def plain(html_fragment):
    return BeautifulSoup(html_fragment or "", "html.parser").get_text(" ", strip=True)


def matrix_for(article):
    if article.name in MATRIX:
        return MATRIX[article.name]
    code = article.name.split(":", 1)[0].strip()
    return MATRIX.get(
        code,
        {
            "workspace_dimension": article.workspace_dimension or "general",
            "access_role": "public",
            "tags": ["SOP"],
            "synonyms": [],
        },
    )


def list_html(items):
    return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in items) + "</ul>"


def default_section(article, heading, meta):
    title = article.name
    if heading == "Purpose":
        return f"<p>This article helps Triple H &amp; T employees follow the approved SOP for {html.escape(title)}.</p>"
    if heading == "When to Use This Article":
        return "<p>Use this article when:</p><ol><li>The employee needs to follow this SOP.</li><li>The related Odoo record requires validation.</li><li>A lognote must be added before closing the issue.</li></ol>"
    if heading == "Problem":
        return "<p>The operational issue may be handled inconsistently if employees do not follow a documented SOP.</p>"
    if heading == "Analysis / Root Cause":
        return "<p>The issue usually happens when required fields, ownership, evidence, or validation steps are not checked before the record is closed.</p>"
    if heading == "Verified Solution / SOP Steps":
        return "<ol><li>Open the related Odoo app.</li><li>Find the relevant SO, PO, ticket, or internal record.</li><li>Check the required fields and evidence.</li><li>Apply the approved correction.</li><li>Save the record.</li><li>Add a lognote summarizing the action.</li></ol>"
    if heading == "Checklist Before Closing":
        return "<ul><li>Required record is reviewed.</li><li>Owner or responsible department is confirmed.</li><li>Evidence or validation result is attached.</li><li>Related SO/PO/Ticket or internal record is linked.</li><li>Lognote is added.</li></ul>"
    if heading == "Canned Response / Shortcut":
        code = title.split(":", 1)[0].lower().replace(" ", "_")
        return f"<p>Shortcut: ::{html.escape(code)}</p><p>Response:<br>The SOP has been reviewed. Please confirm all required checks, update the related Odoo record, and add a lognote before closing the issue.</p>"
    if heading == "KM Classification":
        topic = meta["tags"][0] if meta.get("tags") else "SOP"
        return f"<p>Layer 1 Source: #Collective<br>Layer 2 Wiig Dimension: #Methodological<br>Layer 3 Topic: #{html.escape(topic.replace(' ', ''))}</p>"
    if heading == "Review Rule":
        return "<p>Review this article every 2 weeks or whenever process ownership, system workflow, product data, vendor rules, tax rules, or support escalation rules change.</p>"
    return ""


def find_record_by_name(model, name):
    return env[model].sudo().search([("name", "=", name)], limit=1)


def get_or_create_ticket(name):
    ticket = find_record_by_name("helpdesk.ticket", name)
    if ticket:
        return ticket
    vals = {"name": name}
    team = env["helpdesk.team"].sudo().search([], limit=1)
    if team:
        vals["team_id"] = team.id
    return env["helpdesk.ticket"].sudo().create(vals)


def target_record(model, identifier, fallback_article=None):
    if model == "knowledge.article":
        return Article.browse(identifier).exists()
    if model in ("purchase.order", "sale.order"):
        return find_record_by_name(model, identifier)
    if model == "helpdesk.ticket":
        return get_or_create_ticket(identifier)
    if fallback_article:
        return fallback_article
    return False


def get_or_create_lognote(model, res_id, note):
    existing = MailMessage.search(
        [("model", "=", model), ("res_id", "=", res_id), ("body", "ilike", note[:80])],
        limit=1,
    )
    if existing:
        return existing
    record = env[model].sudo().browse(res_id).exists()
    if not record:
        raise ValueError(f"Missing record {model}:{res_id} for lognote")
    return record.message_post(
        body="<p>%s</p>" % html.escape(note),
        message_type="comment",
        subtype_xmlid="mail.mt_note",
    )


def extract_related_notes(article):
    soup = BeautifulSoup(article.body or "", "html.parser")
    result = []
    related = None
    for h in soup.find_all(["h1", "h2", "h3"]):
        if h.get_text(" ", strip=True) == "Related Lognotes":
            related = h
            break
    if not related:
        return result
    for sibling in related.find_next_siblings():
        if getattr(sibling, "name", None) in ("h1", "h2", "h3"):
            break
        items = sibling.find_all("li") if getattr(sibling, "name", None) != "li" else [sibling]
        for li in items:
            a = li.find("a")
            note_parts = []
            for child in li.children:
                if getattr(child, "name", None) == "a":
                    break
                note_parts.append(str(child))
            note = plain("".join(note_parts))
            if not note or note == "Open Lognote":
                continue
            msg_id = None
            if a:
                if a.get("data-lognote-message-id"):
                    msg_id = int(a.get("data-lognote-message-id"))
                else:
                    href = a.get("href", "")
                    match = re.search(r"message_id=(\d+)", href) or re.search(r"id=(\d+)", href)
                    if match:
                        msg_id = int(match.group(1))
            result.append({"note": note, "message_id": msg_id})
    return result


def link_for_message(message):
    return (
        f'<a href="{BASE_URL}/mail/view?message_id={message.id}" '
        'target="_blank" rel="noopener noreferrer" contenteditable="false" '
        'class="o_not_editable kms-lognote-link btn btn-link p-0" '
        'style="cursor: pointer !important; pointer-events: auto !important; text-decoration: underline;" '
        f'title="Open {html.escape(message.model or "mail.message")} {message.res_id} lognote message {message.id}" '
        f'data-lognote-message-id="{message.id}" data-lognote-model="{html.escape(message.model or "")}" '
        f'data-lognote-res-id="{message.res_id}">Open Lognote</a>'
    )


def related_lognotes_html(article):
    existing = extract_related_notes(article)
    notes = []
    for item in existing:
        msg = MailMessage.browse(item["message_id"]).exists() if item.get("message_id") else MailMessage.browse()
        if not msg:
            msg = get_or_create_lognote("knowledge.article", article.id, item["note"])
        notes.append((item["note"], msg))

    if article.id in PREDEFINED_LOGNOTES and not notes:
        predefined = PREDEFINED_LOGNOTES[article.id]
        if article.id == 65:
            for note, (model, rec_name) in zip(predefined, TICKET2_TARGETS):
                rec = target_record(model, rec_name, article)
                msg = get_or_create_lognote(model, rec.id, note)
                notes.append((note, msg))
        else:
            for note in predefined:
                msg = get_or_create_lognote("knowledge.article", article.id, note)
                notes.append((note, msg))

    for model, rec_name, note in SUPPLEMENTAL_LOGNOTES.get(article.id, []):
        if len(notes) >= 5:
            break
        if any(note == existing_note for existing_note, _ in notes):
            continue
        rec = target_record(model, rec_name, article)
        if rec:
            msg = get_or_create_lognote(model, rec.id, note)
            notes.append((note, msg))

    fallback_notes = PREDEFINED_LOGNOTES.get(article.id, [])
    idx = 1
    while len(notes) < 5:
        note = (
            fallback_notes[len(notes)]
            if len(notes) < len(fallback_notes)
            else f"Fix: {article.name} review note {idx} (P) -> SOP validation requires a documented record (A) -> add this lognote link before closing the article review (S). #Collective #Methodological #Knowledge"
        )
        msg = get_or_create_lognote("knowledge.article", article.id, note)
        notes.append((note, msg))
        idx += 1

    items = [f"<li>{html.escape(note)} {link_for_message(msg)}</li>" for note, msg in notes[:5]]
    return "<ul>" + "".join(items) + "</ul>"


def build_body(article):
    meta = matrix_for(article)
    sections = sectionize(article.body)
    pre = PREDEFINED.get(article.id, {})
    parent = article.parent_id.name if article.parent_id else "General Knowledge"
    title = article.name
    body = []
    body.append("<h2>Article Title</h2>")
    body.append(f"<p>{html.escape(title)}</p>")
    body.append("<h2>Parent Workspace</h2>")
    body.append(f"<p>{html.escape(parent)}</p>")
    body.append("<h2>Workspace Dimension</h2>")
    body.append(f"<p>{html.escape(meta.get('workspace_dimension', 'general'))}</p>")
    body.append("<h2>Access Role</h2>")
    body.append(f"<p>{html.escape(meta.get('access_role', 'public'))}</p>")
    body.append("<h2>Tags</h2>")
    body.append(f"<p>{html.escape(', '.join(meta.get('tags', []) or ['SOP']))}</p>")
    body.append("<h2>Target Synonym List</h2>")
    body.append("<p>List the words users may search for:</p>")
    body.append(list_html(meta.get("synonyms", [])[:8] or [title]))

    for heading in STANDARD_HEADINGS[6:]:
        body.append(f"<h2>{heading}</h2>")
        if heading == "Related Lognotes":
            body.append(related_lognotes_html(article))
            continue
        content = pre.get(heading) or sections.get(heading) or default_section(article, heading, meta)
        body.append(content)
    return "".join(body)


updated = []
for article in Article.browse(article_ids):
    article.write({"body": build_body(article)})
    updated.append((article.id, article.name))

env.cr.commit()
print("updated", len(updated))
for row in updated:
    print(row)
