"""
KMS Team 02 Week 11 - Vector DB Validation Test
Loads the persistent ChromaDB and runs two automated audit scenarios:
  TEST A: Semantic accuracy (synonym-based search)
  TEST B: Security isolation (metadata role filter)
"""

import os
import sys
from dotenv import load_dotenv
from langchain_chroma import Chroma

load_dotenv()

PERSIST_DIR     = "./chroma_db"
COLLECTION_NAME = "kms_collection"


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


# ── Connect to persistent storage ─────────────────────────────────────────────
if not os.path.exists(PERSIST_DIR):
    print(f"[INFO] ChromaDB folder '{PERSIST_DIR}' not found.")
    print("       Running ingest_to_vector.py to create the persistent vector store first.")
    from ingest_to_vector import main as ingest_main
    ingest_main()

embedding_model = get_embedding_function()

db = Chroma(
    persist_directory=PERSIST_DIR,
    collection_name=COLLECTION_NAME,
    embedding_function=embedding_model,
)

print("\n================ RUNNING KMS TEAM 02 WEEK 11 AUDIT ================")

# ── TEST SCENARIO A: SEMANTIC ACCURACY TEST WITH SYNONYMS ─────────────────────
query_synonym = "How do we welcome a new developer into the team?"

# Fetch more results then deduplicate by title to get top-2 distinct articles
_raw_a = db.similarity_search(query_synonym, k=10)
seen_titles: set = set()
results_semantic = []
for doc in _raw_a:
    t = doc.metadata.get("title")
    if t not in seen_titles:
        seen_titles.add(t)
        results_semantic.append(doc)
    if len(results_semantic) == 2:
        break

print(f"\n[TEST A] Semantic Search Results for Query: '{query_synonym}'")
print("-" * 65)
for i, doc in enumerate(results_semantic):
    print(f"[{i+1}] MATCH FOUND:")
    print(f"  -> Source Title : {doc.metadata.get('title')}")
    print(f"  -> Access Role  : {doc.metadata.get('access_role')}")
    print(f"  -> Snippet      : {doc.page_content[:130]}...\n")

expected_semantic_titles = {
    "IT Engineer Onboarding Protocol",
    "General Workspace Conduct Guideline",
}
actual_semantic_titles = {doc.metadata.get("title") for doc in results_semantic}
missing_semantic = expected_semantic_titles - actual_semantic_titles
if missing_semantic:
    print(f"[FAIL] TEST A missing expected semantic matches: {sorted(missing_semantic)}")
    sys.exit(1)

# ── TEST SCENARIO B: SECURITY ISOLATION CHECK (METADATA FILTERS) ──────────────
query_shared     = "System safety and disciplinary actions protocol"
it_user_filter   = {"$or": [{"access_role": "it_staff"}, {"access_role": "public"}]}
results_filtered = db.similarity_search(query_shared, k=2, filter=it_user_filter)

print(f"\n[TEST B] Simulating User with 'it_staff' Role "
      f"(FILTER: access_role == it_staff OR public)")
print("-" * 65)
for i, doc in enumerate(results_filtered):
    print(f"[{i+1}] SECURE MATCH FOUND:")
    print(f"  -> Source Title : {doc.metadata.get('title')}")
    print(f"  -> Access Role  : {doc.metadata.get('access_role')}")
    print(f"  -> Snippet      : {doc.page_content[:130]}...\n")

print("=================================================================")

# ── Automatic leak check ───────────────────────────────────────────────────────
allowed_roles = {"it_staff", "public"}
bad_roles = [
    doc.metadata.get("access_role")
    for doc in results_filtered
    if doc.metadata.get("access_role") not in allowed_roles
]
if len(results_filtered) < 2:
    print("\n[FAIL] TEST B returned fewer than 2 filtered results.")
    sys.exit(1)
if bad_roles:
    print(f"\n[FAIL] TEST B returned roles outside it_staff/public: {bad_roles}")
    sys.exit(1)
if "Network Security and System Firewall Policy" not in {doc.metadata.get("title") for doc in results_filtered}:
    print("\n[FAIL] TEST B missing expected IT security policy result.")
    sys.exit(1)

leaked = [d for d in results_filtered if d.metadata.get("access_role") == "hr_manager"]
if leaked:
    print("\n[FAIL] SECURITY VIOLATION: hr_manager data leaked in TEST B output!")
    sys.exit(1)
else:
    print("\n[PASS] Security check passed: No hr_manager data leaked in TEST B.")
