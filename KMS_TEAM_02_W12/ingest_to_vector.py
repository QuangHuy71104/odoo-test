"""
KMS Team 02 Week 12 - Vector DB Ingestion Pipeline
Fetches knowledge articles from Odoo XML-RPC, seeds required test articles,
chunks text with metadata tagging, and saves to persistent ChromaDB.
"""

import os
import re
import shutil
import xmlrpc.client
from pathlib import Path
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
ODOO_URL      = os.getenv("ODOO_URL",      "http://localhost:8069")
ODOO_DB       = os.getenv("ODOO_DB",       "odoo17")
ODOO_USER     = os.getenv("ODOO_USER",     "admin")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "admin")

BASE_DIR        = Path(__file__).resolve().parent
PERSIST_DIR     = str((BASE_DIR / os.getenv("CHROMA_PERSIST_DIR", "chroma_db")).resolve())
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "kms_collection")
CHUNK_SIZE      = 500
CHUNK_OVERLAP   = 100
ACCESS_MATRIX_PATH = (BASE_DIR / os.getenv("ACCESS_MATRIX_PATH", "access_matrix.md")).resolve()

# ── Week 11 test seed articles (required for TEST A and TEST B to pass) ───────
SEED_ARTICLES = [
    {
        "name": "IT Engineer Onboarding Protocol",
        "code": "IT-SEC-01",
        "workspace_dimension": "it",
        "access_role": "it_staff",
        "tags": ["Onboarding", "IT", "Security"],
        "body": (
            "<p><strong>IT-SEC-01 - IT Engineer Onboarding Protocol</strong></p>"
            "<p>Purpose: This SOP defines the standard onboarding process for all new IT "
            "technical hires and developers joining the Engineering team.</p>"
            "<p>Welcome to the Engineering team. Upon arrival, all new IT technical hires must "
            "initialize their corporate GitHub profiles and configure their development workstation. "
            "The new developer onboarding orientation covers workstation setup, VPN configuration, "
            "repository access provisioning, and mandatory security awareness training. All incoming "
            "IT engineers receive a comprehensive first-day setup session.</p>"
            "<p>New Developer Checklist: (1) Create corporate GitHub account and join the org. "
            "(2) Configure SSH keys and two-factor authentication. "
            "(3) Install approved development tools and IDEs. "
            "(4) Complete VPN setup and verify network access. "
            "(5) Attend security briefing and sign acceptable use policy. "
            "(6) Join team channels and project boards.</p>"
            "<p>Welcome new developer orientation includes account creation, badge provisioning, "
            "access provisioning, and team introduction. The new IT hire orientation is mandatory "
            "for all engineering personnel regardless of seniority. Developer orientation checklist "
            "must be completed within the first five business days.</p>"
            "<p>Tags: Onboarding, IT, Security, NewHire, DeveloperOrientation, welcome developer</p>"
        ),
    },
    {
        "name": "Network Security and System Firewall Policy",
        "code": "IT-SEC-02",
        "workspace_dimension": "it",
        "access_role": "it_staff",
        "tags": ["NetworkSecurity", "Firewall", "IT"],
        "body": (
            "<p><strong>IT-SEC-02 - Network Security and System Firewall Policy</strong></p>"
            "<p>Purpose: This policy defines procedures for maintaining network security and "
            "responding to system safety infractions within the corporate IT environment.</p>"
            "<p>In the event of system safety infractions, technical staff must trigger the "
            "automated port isolation protocol immediately. Any unauthorized access attempt must be "
            "reported to the security operations team within 15 minutes of detection. The firewall "
            "policy requires all network traffic to pass through the approved security gateway.</p>"
            "<p>Network Security Incident Response: (1) Detect anomalous traffic or unauthorized "
            "access attempt. (2) Trigger automated port isolation for the affected endpoint. "
            "(3) Notify the security operations team immediately. "
            "(4) Document all details in the incident log. "
            "(5) Perform forensic analysis and root cause identification. "
            "(6) Submit full incident report within 24 hours.</p>"
            "<p>System safety protocols require immediate escalation of any security breach. "
            "Firewall rules must be reviewed quarterly by the IT security team. Port isolation is "
            "mandatory for any endpoint suspected of compromise. Network incidents must never be "
            "handled unilaterally. Security infractions result in immediate account suspension "
            "pending investigation.</p>"
            "<p>Tags: NetworkSecurity, Firewall, IT, SystemSafety, PortIsolation, SecurityProtocol</p>"
        ),
    },
    {
        "name": "General Workspace Conduct Guideline",
        "code": "GEN-01",
        "workspace_dimension": "public",
        "access_role": "public",
        "tags": ["General", "Conduct", "Public"],
        "body": (
            "<p><strong>GEN-01 - General Workspace Conduct Guideline</strong></p>"
            "<p>Purpose: This guideline establishes professional conduct standards expected of "
            "all employees across all departments.</p>"
            "<p>It is our company policy to maintain an open, welcoming environment for all "
            "incoming cross-functional personnel. All employees are expected to treat colleagues "
            "with respect, maintain professional communication standards, and collaborate "
            "effectively across all teams and departments.</p>"
            "<p>Acceptable Workplace Behavior: (1) Maintain respectful and professional "
            "communication at all times. "
            "(2) Welcome new employees warmly and actively support their integration into the team. "
            "(3) Follow all IT security and network safety protocols. "
            "(4) Report any conduct violations to HR immediately. "
            "(5) Maintain confidentiality of all internal business and customer information.</p>"
            "<p>Workplace rules apply to all permanent staff, temporary contractors, and visiting "
            "personnel. The company is committed to providing a safe, inclusive, and productive "
            "work environment for everyone. Violations of conduct guidelines are handled through "
            "the formal HR disciplinary process in accordance with company policy.</p>"
            "<p>Tags: General, Conduct, Public, WorkplaceRules, CompanyPolicy, welcome employees</p>"
        ),
    },
    {
        "name": "HR Payroll and Disciplinary Review Policy",
        "code": "HR-SEC-01",
        "workspace_dimension": "hr",
        "access_role": "hr_manager",
        "tags": ["HR", "Confidential", "Disciplinary"],
        "body": (
            "<p><strong>HR-SEC-01 - HR Payroll and Disciplinary Review Policy - CONFIDENTIAL</strong></p>"
            "<p>RESTRICTED ACCESS: This document is classified as CONFIDENTIAL and is accessible "
            "only to HR managers and authorized HR personnel.</p>"
            "<p>Purpose: This policy governs payroll management, salary reviews, performance "
            "warnings, and formal disciplinary procedures for all employees.</p>"
            "<p>Disciplinary Actions: All disciplinary actions regarding employee conduct violations "
            "follow the formal HR review process. Performance warnings must be documented through "
            "the official HR system with proper evidence. Salary policy adjustments require explicit "
            "HR manager approval and finance sign-off.</p>"
            "<p>HR Disciplinary Procedure: (1) Document the incident with evidence. "
            "(2) Issue formal written warning through the HR system. "
            "(3) Conduct formal performance review meeting. "
            "(4) Record outcome in the employee HR file. "
            "(5) Schedule follow-up reviews at 30, 60, and 90 days.</p>"
            "<p>Payroll Review: All salary adjustments, bonuses, and deductions must be processed "
            "by authorized HR personnel only. Employee discipline records, payroll review "
            "documentation, salary history, and performance warnings are strictly confidential.</p>"
            "<p>Tags: HR, Confidential, Disciplinary, Payroll, SalaryReview, PerformanceManagement</p>"
        ),
    },
]

# ── BA's access matrix: title keywords -> metadata override ───────────────────
VALID_ROLES = {"hr_manager", "it_staff", "public"}


def clean_matrix_cell(value):
    return value.replace("`", "").replace("**", "").strip()


def load_access_matrix(path=ACCESS_MATRIX_PATH):
    if not path.exists():
        raise FileNotFoundError(f"Access matrix not found: {path}")

    metadata_by_key = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue

        cols = [clean_matrix_cell(c) for c in line.strip("|").split("|")]
        if len(cols) < 6:
            continue

        code, title, workspace_dimension, access_role, tags_raw = cols[:5]
        if not code or code.lower() == "code" or set(code) <= {"-"}:
            continue
        if access_role not in VALID_ROLES:
            continue

        tags = [clean_matrix_cell(tag) for tag in tags_raw.split(",") if clean_matrix_cell(tag)]
        metadata = {
            "workspace_dimension": workspace_dimension,
            "access_role": access_role,
            "tags": tags,
        }

        metadata_by_key[code] = metadata
        metadata_by_key[title] = metadata

    if not metadata_by_key:
        raise ValueError(f"No valid access-control rows found in {path}")

    return metadata_by_key


def get_embedding_function():
    provider = os.getenv("EMBEDDING_PROVIDER", "sentence-transformers")
    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=os.getenv("OPENAI_API_KEY"),
        )
    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")


def connect_odoo():
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
    if not uid:
        raise ConnectionError(f"Odoo auth failed for user '{ODOO_USER}' on DB '{ODOO_DB}'")
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    return uid, models


def seed_articles(uid, models):
    existing = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, "knowledge.article", "search_read",
        [[]], {"fields": ["id", "name"], "limit": 500})
    existing_by_name = {a["name"]: a["id"] for a in existing}

    for art in SEED_ARTICLES:
        values = {
            "name": art["name"],
            "body": art["body"],
            "category": "workspace",
        }
        if art["name"] not in existing_by_name:
            models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, "knowledge.article", "create", [{
                **values,
            }])
            print(f"  [SEEDED]  {art['code']} - {art['name']}")
        else:
            models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, "knowledge.article", "write", [
                [existing_by_name[art["name"]]], values
            ])
            print(f"  [UPDATED] {art['code']} - {art['name']}")


def fetch_articles(uid, models):
    return models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD, "knowledge.article", "search_read",
        [[["body", "not in", [False, "", "<br>", "<p><br></p>"]]]],
        {"fields": ["id", "name", "body", "category", "parent_id"], "order": "id asc"},
    )


def strip_html(html):
    soup = BeautifulSoup(html or "", "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()


def resolve_metadata(name, body_text, metadata_map):
    for key, metadata in metadata_map.items():
        if key and (key in name or key in body_text):
            return metadata

    ws_match  = re.search(r"Workspace Dimension\s+(\S+)", body_text)
    ar_match  = re.search(r"Access Role\s+(\S+)", body_text)
    tag_match = re.search(r"Tags\s+(SOP[,\w\s]+?)(?:\s+Target|\s+Workspace|$)", body_text)

    if ws_match and ar_match and ar_match.group(1) in VALID_ROLES:
        tags = []
        if tag_match:
            tags = [t.strip() for t in tag_match.group(1).split(",") if t.strip()]
        return {
            "workspace_dimension": ws_match.group(1),
            "access_role": ar_match.group(1),
            "tags": tags,
        }

    return None


def main():
    print("=" * 60)
    print("  KMS TEAM 02 WEEK 12 - Vector DB Ingestion Pipeline")
    print("=" * 60)

    print("\n[1] Connecting to Odoo XML-RPC...")
    uid, models = connect_odoo()
    print(f"    Connected as UID={uid} | DB={ODOO_DB}")

    print("\n[2] Loading BA access control matrix...")
    metadata_map = load_access_matrix()
    print(f"    Loaded {len(metadata_map)} metadata lookup keys from {ACCESS_MATRIX_PATH}")

    print("\n[3] Seeding required test seed articles...")
    seed_articles(uid, models)

    print("\n[4] Fetching all articles from Odoo...")
    raw_articles = fetch_articles(uid, models)
    print(f"    Fetched {len(raw_articles)} articles with content")

    print("\n[5] Processing: strip HTML -> resolve metadata -> chunk...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    all_chunks = []
    for art in raw_articles:
        body_text = strip_html(art.get("body", ""))
        if len(body_text) < 30:
            continue

        metadata = resolve_metadata(art["name"], body_text, metadata_map)
        if not metadata:
            print(f"    [SKIP] {art['id']:>3} {art['name'][:50]:<50} | no access matrix mapping")
            continue

        ws = metadata["workspace_dimension"]
        role = metadata["access_role"]
        tags = metadata["tags"]

        chunks = splitter.create_documents(
            texts=[body_text],
            metadatas=[{
                "title":               art["name"],
                "workspace_dimension": ws,
                "access_role":         role,
                "tags":                ", ".join(tags),
                "odoo_id":             art["id"],
            }],
        )
        all_chunks.extend(chunks)
        print(f"    [{art['id']:>3}] {art['name'][:50]:<50} | ws={ws:<16} role={role:<10} chunks={len(chunks)}")

    print(f"\n    Total chunks generated: {len(all_chunks)}")
    if not all_chunks:
        raise RuntimeError("No chunks generated. Check Odoo articles and access_matrix.md mappings.")

    print("\n[6] Loading embedding model...")
    embedding_fn = get_embedding_function()

    print(f"\n[7] Saving to ChromaDB -> {PERSIST_DIR} | collection={COLLECTION_NAME}")
    if os.path.exists(PERSIST_DIR):
        shutil.rmtree(PERSIST_DIR)
        print(f"    Cleared existing {PERSIST_DIR}")

    Chroma.from_documents(
        documents=all_chunks,
        embedding=embedding_fn,
        collection_name=COLLECTION_NAME,
        persist_directory=PERSIST_DIR,
    )

    print(f"\n    Saved {len(all_chunks)} chunks to persistent storage.")
    print("\n" + "=" * 60)
    print("  [DONE] Run test_vector_db.py to validate.")
    print("=" * 60)


if __name__ == "__main__":
    main()
