import re
from dataclasses import dataclass

from django.conf import settings

from .models import PolicyDocument


@dataclass
class PolicyAnswer:
    text: str
    source_type: str
    source_label: str
    model: str = ""


def get_policy_answer(query):
    return get_policy_answer_with_meta(query).text


def get_policy_answer_with_meta(query):
    latest_doc = (
        PolicyDocument.objects.filter(
            document_type=PolicyDocument.DocumentType.RBI_MONETARY_POLICY,
            is_latest=True,
        )
        .order_by("-published_date")
        .first()
    )
    if not latest_doc:
        return PolicyAnswer(
            text="No latest RBI monetary policy document has been ingested yet.",
            source_type="missing",
            source_label="No document available",
        )

    connection_string = getattr(settings, "PGVECTOR_CONNECTION_STRING", None)
    if connection_string:
        return _answer_with_pgvector(query, connection_string)

    return _answer_from_latest_document(query, latest_doc)


def _answer_with_pgvector(query, connection_string):
    from langchain_community.vectorstores import PGVector
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    embedding_model = getattr(
        settings, "GOOGLE_GENAI_EMBEDDING_MODEL", "models/embedding-001"
    )
    chat_model = getattr(settings, "GOOGLE_GENAI_CHAT_MODEL", "gemini-1.5-flash")

    embeddings = GoogleGenerativeAIEmbeddings(model=embedding_model)
    store = PGVector(connection_string=connection_string, embedding_function=embeddings)
    docs = store.similarity_search(query, k=3)

    context = "\n\n".join(doc.page_content for doc in docs)
    llm = ChatGoogleGenerativeAI(model=chat_model, temperature=0)
    response = llm.invoke(
        "Answer the question using only the context below. "
        "If the context is insufficient, say what is missing.\n\n"
        f"Context:\n{context}\n\nQuestion: {query}"
    )
    return PolicyAnswer(
        text=getattr(response, "content", response),
        source_type="gemini_pgvector",
        source_label="Gemini AI over pgvector retrieval",
        model=chat_model,
    )


def _answer_from_latest_document(query, document):
    facts = _extract_mpc_facts(document.content)
    fact_context = _format_fact_context(document, facts)
    context = fact_context + "\n\nRelevant MPC excerpts:\n" + _select_relevant_context(
        query,
        document.content,
    )
    prompt = (
        "Answer the question using only the latest RBI MPC meeting context below. "
        "Be concise, factual, and include exact rates/projections when available. "
        "If the context is insufficient, say what is missing.\n\n"
        f"Context:\n{context}\n\nQuestion: {query}"
    )

    if getattr(settings, "GOOGLE_API_KEY", ""):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            chat_model = getattr(settings, "GOOGLE_GENAI_CHAT_MODEL", "gemini-1.5-flash")
            llm = ChatGoogleGenerativeAI(
                model=chat_model,
                temperature=0,
                google_api_key=settings.GOOGLE_API_KEY,
            )
            response = llm.invoke(prompt)
            return PolicyAnswer(
                text=getattr(response, "content", response),
                source_type="gemini",
                source_label="Gemini AI over latest MPC document",
                model=chat_model,
            )
        except Exception:
            return PolicyAnswer(
                text=_parsed_mpc_answer(query, document),
                source_type="parser",
                source_label="Direct parser from latest MPC document",
            )

    return PolicyAnswer(
        text=_parsed_mpc_answer(query, document),
        source_type="parser",
        source_label="Direct parser from latest MPC document",
    )


def _parsed_mpc_answer(query, document):
    text = document.content
    lowered_query = query.lower()
    facts = _extract_mpc_facts(text)

    if any(term in lowered_query for term in ["policy rate", "repo rate", "latest rate", "rate"]):
        parts = []
        if facts.get("repo_rate"):
            parts.append(f"policy repo rate: {facts['repo_rate']}%")
        if facts.get("sdf_rate"):
            parts.append(f"SDF rate: {facts['sdf_rate']}%")
        if facts.get("msf_rate"):
            parts.append(f"MSF/Bank Rate: {facts['msf_rate']}%")
        if facts.get("vote"):
            parts.append(f"vote: {facts['vote']}")
        return f"Based on the latest MPC minutes ({document.published_date.date()}), " + "; ".join(parts) + "."

    if any(term in lowered_query for term in ["inflation", "cpi", "price"]):
        if facts.get("inflation_projection"):
            return f"The latest MPC document states CPI inflation projection at {facts['inflation_projection']}."

    if any(term in lowered_query for term in ["growth", "gdp", "real gdp"]):
        if facts.get("gdp_projection"):
            return f"The latest MPC document states real GDP growth projection at {facts['gdp_projection']}."

    if "stance" in lowered_query:
        if facts.get("stance"):
            return f"The MPC stance in the latest document is {facts['stance']}."

    if any(term in lowered_query for term in ["vote", "voted", "member", "unanimous"]):
        if facts.get("vote"):
            return f"The vote recorded in the latest MPC minutes was: {facts['vote']}."

    if "next meeting" in lowered_query or "next mpc meeting" in lowered_query:
        if facts.get("next_meeting"):
            return f"The next MPC meeting is scheduled for {facts['next_meeting']}."

    summary_parts = [
        f"Latest document: {document.title}.",
        f"Published: {document.published_date.date()}.",
    ]
    if facts.get("repo_rate"):
        summary_parts.append(f"Repo rate: {facts['repo_rate']}%.")
    if facts.get("stance"):
        summary_parts.append(f"Stance: {facts['stance']}.")
    if facts.get("inflation_projection"):
        summary_parts.append(f"CPI inflation projection: {facts['inflation_projection']}.")
    if facts.get("gdp_projection"):
        summary_parts.append(f"Real GDP growth projection: {facts['gdp_projection']}.")

    relevant = _format_excerpt_answer(_select_relevant_context(query, text, max_chars=1200))
    return " ".join(summary_parts) + "\n\nRelevant extract: " + relevant


def _extract_mpc_facts(text):
    facts = {}

    repo_match = re.search(
        r"policy repo rate[^.]*?(?:unchanged at|to|at)\s+([0-9.]+)\s*per cent",
        text,
        flags=re.IGNORECASE,
    )
    if repo_match:
        facts["repo_rate"] = repo_match.group(1)

    sdf_match = re.search(
        r"standing deposit facility rate[^.]*?(?:at|to|remains at)\s+([0-9.]+)\s*per cent",
        text,
        flags=re.IGNORECASE,
    )
    if sdf_match:
        facts["sdf_rate"] = sdf_match.group(1)

    msf_match = re.search(
        r"marginal standing facility rate(?: and the Bank Rate)?[^.]*?(?:at|to|remains at)\s+([0-9.]+)\s*per cent",
        text,
        flags=re.IGNORECASE,
    )
    if msf_match:
        facts["msf_rate"] = msf_match.group(1)

    stance_match = re.search(
        r"(?:decided to|voted to|continue with)\s+(?:remain focused on|continue with)?\s*the\s+([A-Za-z ]+?)\s+stance",
        text,
        flags=re.IGNORECASE,
    )
    if stance_match:
        facts["stance"] = stance_match.group(1).strip().lower()
    elif re.search(r"\bneutral stance\b", text, flags=re.IGNORECASE):
        facts["stance"] = "neutral"

    inflation_match = re.search(
        r"CPI inflation[^.]*?(?:projected|projection)[^.]*?at\s+([0-9.]+)\s*per cent",
        text,
        flags=re.IGNORECASE,
    )
    if inflation_match:
        facts["inflation_projection"] = inflation_match.group(1) + "%"

    gdp_match = re.search(
        r"(?:real\s+)?GDP growth[^.]*?(?:projected|projection)[^.]*?at\s+([0-9.]+)\s*per cent",
        text,
        flags=re.IGNORECASE,
    )
    if gdp_match:
        facts["gdp_projection"] = gdp_match.group(1) + "%"

    vote_match = re.search(
        r"Voting on the Resolution to ([^\n]+?per cent)",
        text,
        flags=re.IGNORECASE,
    )
    if vote_match:
        vote = vote_match.group(1).strip()
        if len(re.findall(r"\bYes\b", text)) >= 6:
            vote += "; all six listed MPC members voted Yes"
        facts["vote"] = vote

    next_match = re.search(
        r"next meeting of the MPC is scheduled for ([^.]+)\.",
        text,
        flags=re.IGNORECASE,
    )
    if next_match:
        facts["next_meeting"] = next_match.group(1)

    return facts


def _format_fact_context(document, facts):
    lines = [
        f"Document title: {document.title}",
        f"Published date: {document.published_date.date()}",
    ]
    if facts.get("repo_rate"):
        lines.append(f"Policy repo rate: {facts['repo_rate']} per cent")
    if facts.get("sdf_rate"):
        lines.append(f"Standing Deposit Facility rate: {facts['sdf_rate']} per cent")
    if facts.get("msf_rate"):
        lines.append(f"MSF rate and Bank Rate: {facts['msf_rate']} per cent")
    if facts.get("stance"):
        lines.append(f"Monetary policy stance: {facts['stance']}")
    if facts.get("inflation_projection"):
        lines.append(f"CPI inflation projection: {facts['inflation_projection']}")
    if facts.get("gdp_projection"):
        lines.append(f"Real GDP growth projection: {facts['gdp_projection']}")
    if facts.get("vote"):
        lines.append(f"MPC vote: {facts['vote']}")
    if facts.get("next_meeting"):
        lines.append(f"Next MPC meeting: {facts['next_meeting']}")
    return "Key facts parsed from the latest MPC document:\n" + "\n".join(lines)


def _answer_with_gemini(prompt):
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        chat_model = getattr(settings, "GOOGLE_GENAI_CHAT_MODEL", "gemini-1.5-flash")
        llm = ChatGoogleGenerativeAI(model=chat_model, temperature=0)
        response = llm.invoke(prompt)
        return getattr(response, "content", response)
    except Exception:
        return ""


def _select_relevant_context(query, text, max_chars=3500):
    query_terms = {
        term.lower()
        for term in re.findall(r"[A-Za-z][A-Za-z\-]{2,}", query)
        if term.lower() not in {"what", "why", "how", "the", "and", "for", "with"}
    }
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n|(?<=\.)\s+(?=\d+\.)", text)]
    scored = []
    for index, paragraph in enumerate(paragraphs):
        lowered = paragraph.lower()
        score = sum(1 for term in query_terms if term in lowered)
        if score:
            scored.append((score, index, paragraph))

    if not scored:
        return text[:max_chars]

    selected = []
    total = 0
    for _, _, paragraph in sorted(scored, key=lambda item: (-item[0], item[1])):
        if total + len(paragraph) > max_chars:
            continue
        selected.append(paragraph)
        total += len(paragraph)
    return "\n\n".join(selected) or text[:max_chars]


def _direct_answer(query, text):
    lowered_query = query.lower()
    if any(term in lowered_query for term in ["policy rate", "repo rate", "latest rate"]):
        vote_match = re.search(
            r"keep policy repo rate unchanged at\s+([0-9.]+)\s*per cent",
            text,
            flags=re.IGNORECASE,
        )
        if vote_match:
            return (
                "The latest RBI MPC minutes say the policy repo rate was kept "
                f"unchanged at {vote_match.group(1)} per cent."
            )

        rate_match = re.search(
            r"policy repo rate(?:\s+under the liquidity adjustment facility)?\s+"
            r"(?:unchanged\s+)?(?:at|to)\s+([0-9.]+)\s*per cent",
            text,
            flags=re.IGNORECASE,
        )
        if rate_match:
            return f"The latest policy repo rate mentioned is {rate_match.group(1)} per cent."

    if "next meeting" in lowered_query:
        match = re.search(
            r"next meeting of the MPC is scheduled for ([^.]+)\.",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            return f"The next MPC meeting is scheduled for {match.group(1)}."

    if "stance" in lowered_query:
        match = re.search(r"stance of monetary policy[^.]*\.", text, flags=re.IGNORECASE)
        if match:
            return match.group(0)

    return ""


def _format_excerpt_answer(context):
    sentences = re.split(r"(?<=[.])\s+", context.strip())
    selected = [sentence for sentence in sentences if len(sentence) > 40][:5]
    return " ".join(selected) if selected else context[:800]
