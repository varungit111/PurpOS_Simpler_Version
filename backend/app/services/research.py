import hashlib
import html
import ipaddress
import re
import socket
import ssl
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlparse, urlunparse
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    Request,
    build_opener,
)
from urllib.robotparser import RobotFileParser
from uuid import NAMESPACE_URL, uuid5

import certifi

from app.config.settings import settings
from app.schemas.ai_detective import AIDetectiveGeneration
from app.schemas.assessment import (
    ExternalResearchCategoryState,
    ExternalResearchDocument,
    ExternalResearchState,
    IdentifyState,
    OrganisationContext,
    ResearchFinding,
    ResearchSourceType,
    utc_now,
)
from app.services.ai_client import AIClient, AIClientError


SUPPORTED_WEBSITE_CATEGORIES = (
    "website",
    "products-services",
    "leadership-values-purpose",
    "sustainability-impact",
    "customer-groups",
)
UNCONFIGURED_SEARCH_CATEGORIES = (
    "competitors",
    "market-sector-trends",
    "reviews-ratings",
    "press-mentions",
)
WEBSITE_CATEGORY_TERMS = {
    "products-services": (
        "product",
        "products",
        "service",
        "services",
        "solution",
        "solutions",
        "what-we-do",
        "offering",
        "offerings",
        "capability",
        "capabilities",
        "plans",
        "insurance",
        "health-insurance",
    ),
    "leadership-values-purpose": (
        "about",
        "about-us",
        "who-we-are",
        "our-story",
        "purpose",
        "mission",
        "vision",
        "values",
        "leadership",
        "executive",
        "management",
        "board",
        "governance",
        "team",
        "our-team",
    ),
    "sustainability-impact": (
        "sustainability",
        "sustainable",
        "impact",
        "environment",
        "climate",
        "community",
        "communities",
        "social-impact",
        "responsibility",
        "esg",
    ),
    "customer-groups": (
        "customer",
        "customers",
        "client",
        "clients",
        "member",
        "members",
        "membership",
        "partner",
        "partners",
        "who-we-help",
        "for-business",
        "for-individuals",
    ),
}
# Content support is intentionally stricter than link discovery. A strong phrase
# is sufficient; otherwise three distinct signals are required from cleaned page
# text so a lone generic word does not complete a research category.
CATEGORY_CONTENT_SUPPORT_RULES = {
    "products-services": {
        "strong_phrases": (
            "health insurance",
            "insurance plans",
            "insurance cover",
            "medical cover",
            "everyday healthcare",
            "cancer care",
        ),
        "signals": (
            "products",
            "services",
            "plans",
            "insurance",
            "cover",
            "policies",
            "healthcare",
            "diagnostics",
            "specialists",
            "surgery",
            "solutions",
            "offerings",
        ),
    },
    "customer-groups": {
        "strong_phrases": (
            "new members",
            "existing members",
            "health professionals",
            "member benefits",
            "who we serve",
            "who we help",
            "for businesses",
        ),
        "signals": (
            "customers",
            "clients",
            "members",
            "membership",
            "businesses",
            "partners",
            "individuals",
            "families",
        ),
    },
    "sustainability-impact": {
        "strong_phrases": (
            "social impact",
            "community impact",
            "environmental impact",
            "climate change",
            "environmental responsibility",
            "corporate responsibility",
            "sustainability strategy",
            "sustainable future",
        ),
        "signals": (
            "sustainability",
            "sustainable",
            "environmental",
            "climate",
            "communities",
            "responsibility",
            "emissions",
            "carbon",
        ),
    },
    "leadership-values-purpose": {
        "strong_phrases": (
            "our purpose",
            "our mission",
            "our vision",
            "our values",
            "our leadership",
            "executive team",
            "board of directors",
            "corporate governance",
            "our story",
            "who we are",
        ),
        "signals": (
            "purpose",
            "mission",
            "vision",
            "values",
            "leadership",
            "executive",
            "board",
            "governance",
        ),
    },
}
# Specific categories precede generic organisation/about signals.
CATEGORY_CLASSIFICATION_ORDER = (
    "sustainability-impact",
    "products-services",
    "customer-groups",
    "leadership-values-purpose",
)
CATEGORY_FRONTIER_ORDER = (
    "products-services",
    "leadership-values-purpose",
    "sustainability-impact",
    "customer-groups",
)
TRACKING_QUERY_PARAMETERS = frozenset(
    {
        "gclid",
        "gclsrc",
        "gad_source",
        "gad_campaignid",
        "campaignid",
        "gbraid",
        "wbraid",
        "fbclid",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
    }
)
MAX_FRONTIER_CANDIDATES_PER_CATEGORY = 20
MAX_REPLACEMENT_ATTEMPTS = 2
REPLACEMENT_ELIGIBLE_STATUS_REASONS = frozenset({"HTTP 404.", "HTTP 410."})
USER_AGENT = "PurpOSResearchBot/1.0"


@dataclass(frozen=True)
class ResearchCollectionResult:
    findings: list[ResearchFinding]
    status: str
    message: str
    external_research: ExternalResearchState | None = None


@dataclass(frozen=True)
class ResearchLimits:
    max_pages: int = settings.research_max_pages
    timeout_seconds: float = settings.research_timeout_seconds
    max_content_bytes: int = settings.research_max_content_bytes
    max_text_chars: int = settings.research_max_text_chars
    redirect_limit: int = settings.research_redirect_limit


@dataclass(frozen=True)
class FetchResponse:
    status: int
    url: str
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True)
class ResearchCandidate:
    url: str
    category: str
    discovery_order: int


@dataclass(frozen=True)
class DiscoveredAnchor:
    href: str
    text: str


class ResearchTransport(Protocol):
    def fetch(
        self,
        url: str,
        timeout_seconds: float,
        max_bytes: int | None = None,
    ) -> FetchResponse: ...


class ResearchProvider(Protocol):
    def collect(
        self,
        state: IdentifyState,
        organisation: OrganisationContext | None = None,
        *,
        refresh: bool = False,
    ) -> ResearchCollectionResult:
        raise NotImplementedError


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


class UrlLibResearchTransport:
    def __init__(self) -> None:
        self._ssl_context = ssl.create_default_context(cafile=certifi.where())
        self._opener = build_opener(
            _NoRedirectHandler,
            HTTPSHandler(context=self._ssl_context),
        )

    def fetch(
        self,
        url: str,
        timeout_seconds: float,
        max_bytes: int | None = None,
    ) -> FetchResponse:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with self._opener.open(
                request,
                timeout=timeout_seconds,
            ) as response:
                return FetchResponse(
                    status=response.status,
                    url=response.geturl(),
                    headers={key.lower(): value for key, value in response.headers.items()},
                    body=response.read(max_bytes),
                )
        except HTTPError as exc:
            return FetchResponse(
                status=exc.code,
                url=exc.geturl(),
                headers={key.lower(): value for key, value in exc.headers.items()},
                body=exc.read(max_bytes),
            )
        except URLError as exc:
            raise ResearchFetchError(str(exc.reason)) from exc


class ResearchError(ValueError):
    pass


class ResearchFetchError(ResearchError):
    pass


class IdentifyEvidenceResearchProvider:
    def __init__(
        self,
        ai_client: AIClient | None,
        *,
        transport: ResearchTransport | None = None,
        limits: ResearchLimits | None = None,
        enabled: bool | None = None,
    ) -> None:
        self._ai_client = ai_client
        self._transport = transport or UrlLibResearchTransport()
        self._limits = limits or ResearchLimits()
        self._enabled = settings.external_research_enabled if enabled is None else enabled

    def collect(
        self,
        state: IdentifyState,
        organisation: OrganisationContext | None = None,
        *,
        refresh: bool = False,
    ) -> ResearchCollectionResult:
        if not refresh and state.output.external_research.status == "connected":
            return ResearchCollectionResult(
                findings=state.output.research_findings,
                status="connected",
                message="AI Detective research restored from saved sources.",
                external_research=state.output.external_research,
            )

        research_state = self._collect_external_research(organisation)
        documents = [doc for doc in research_state.documents if doc.status == "retrieved"]

        if self._ai_client is None:
            return ResearchCollectionResult(
                findings=state.output.research_findings,
                status="unavailable" if documents else research_state.status,
                message=(
                    "Website research was saved, but AI synthesis is unavailable."
                    if documents
                    else _limited_message(research_state)
                ),
                external_research=research_state,
            )

        if not _has_research_inputs(state, organisation, documents):
            return ResearchCollectionResult(
                findings=state.output.research_findings,
                status=research_state.status,
                message=_limited_message(research_state),
                external_research=research_state,
            )

        try:
            generation = self._ai_client.generate_structured(
                prompt=_build_prompt(state, organisation, research_state),
                output_schema=AIDetectiveGeneration,
                system=AI_DETECTIVE_SYSTEM,
            )
        except AIClientError:
            return ResearchCollectionResult(
                findings=state.output.research_findings,
                status="error",
                message=(
                    "AI Detective synthesis could not complete. Retrieved "
                    "website sources were saved for retry."
                ),
                external_research=research_state.model_copy(
                    update={"status": "error", "synthesis_error": "AI synthesis failed."}
                ),
            )

        findings = _validated_findings(generation.findings, research_state, state)
        if documents and not findings:
            return ResearchCollectionResult(
                findings=state.output.research_findings,
                status="error",
                message=(
                    "AI Detective synthesis did not return findings with valid "
                    "retrieved-source references."
                ),
                external_research=research_state.model_copy(
                    update={
                        "status": "error",
                        "synthesis_error": "No validated source references returned.",
                    }
                ),
            )

        return ResearchCollectionResult(
            findings=findings,
            status="connected" if findings else research_state.status,
            message=(
                "AI Detective findings generated from retrieved public website sources."
                if documents
                else "AI Detective findings generated from available Identify inputs."
            ),
            external_research=research_state.model_copy(
                update={"status": "connected" if findings else research_state.status}
            ),
        )

    def _collect_external_research(
        self,
        organisation: OrganisationContext | None,
    ) -> ExternalResearchState:
        if not self._enabled:
            return _research_state(
                status="not-configured",
                documents=[],
                supported_status="not-configured",
                supported_message="External research is disabled.",
            )

        if organisation is None or organisation.website is None:
            return _research_state(
                status="limited",
                documents=[],
                supported_status="not-scanned",
                supported_message="No public website was supplied.",
            )

        website = str(organisation.website)
        try:
            start_url = validate_public_url(website)
        except ResearchError as exc:
            unavailable = _document(
                url=website,
                status="unavailable",
                status_reason=str(exc),
            )
            return _research_state(
                status="unavailable",
                documents=[unavailable],
                supported_status="unavailable",
                supported_message=str(exc),
            )

        documents = self._crawl_website(start_url)
        retrieved = [doc for doc in documents if doc.status == "retrieved"]
        if retrieved:
            return _research_state(
                status="retrieved",
                documents=documents,
                supported_status="done",
                supported_message=f"{len(retrieved)} website page(s) retrieved.",
            )
        return _research_state(
            status="unavailable",
            documents=documents,
            supported_status="unavailable",
            supported_message="The supplied public website could not be retrieved.",
        )

    def _crawl_website(self, start_url: str) -> list[ExternalResearchDocument]:
        documents: list[ExternalResearchDocument] = []
        normalized_start = normalize_url(start_url)
        frontier = [
            ResearchCandidate(
                url=normalized_start,
                category=_category_for_url(normalized_start),
                discovery_order=0,
            )
        ]
        queued = {normalized_start}
        seen: set[str] = set()
        attempted_categories: set[str] = set()
        retrieved_categories: set[str] = set()
        terminal_failure_categories: set[str] = set()
        robots_by_origin: dict[str, RobotFileParser | None] = {}
        crawl_base_url = normalized_start
        next_discovery_order = 1
        successful_documents = 0
        candidate_attempts = 0
        replacement_attempts_granted = 0
        successful_document_limit = max(1, self._limits.max_pages)

        while (
            frontier
            and successful_documents < successful_document_limit
            and candidate_attempts
            < successful_document_limit + replacement_attempts_granted
        ):
            replacement_categories = (
                terminal_failure_categories - retrieved_categories
            )
            candidate = _pop_next_candidate(
                frontier,
                attempted_categories,
                preferred_categories=replacement_categories,
            )
            url = candidate.url
            queued.discard(url)
            if url in seen:
                continue
            seen.add(url)
            attempted_categories.add(candidate.category)
            candidate_attempts += 1

            document, links = self._fetch_document(
                url,
                category_hint=candidate.category,
                robots_by_origin=robots_by_origin,
            )
            documents.append(document)
            if document.status != "retrieved" or not document.content:
                if (
                    replacement_attempts_granted < MAX_REPLACEMENT_ATTEMPTS
                    and _is_replacement_eligible(candidate, document)
                ):
                    replacement_attempts_granted += 1
                    terminal_failure_categories.add(candidate.category)
                continue

            successful_documents += 1
            retrieved_categories.add(document.category)

            if len(documents) == 1 and _www_equivalent_hosts(
                crawl_base_url,
                str(document.url),
            ):
                crawl_base_url = str(document.url)

            for link in links:
                normalized_link = normalize_url(link.url)
                if normalized_link in seen or not same_host(
                    crawl_base_url, normalized_link
                ):
                    continue
                if normalized_link in queued:
                    _upgrade_queued_candidate(
                        frontier,
                        normalized_link,
                        link.category,
                    )
                    continue
                if sum(
                    queued_candidate.category == link.category
                    for queued_candidate in frontier
                ) >= MAX_FRONTIER_CANDIDATES_PER_CATEGORY:
                    continue
                frontier.append(
                    ResearchCandidate(
                        url=normalized_link,
                        category=link.category,
                        discovery_order=next_discovery_order,
                    )
                )
                queued.add(normalized_link)
                next_discovery_order += 1

        return documents

    def _fetch_document(
        self,
        url: str,
        *,
        category_hint: str,
        robots_by_origin: dict[str, RobotFileParser | None],
    ) -> tuple[ExternalResearchDocument, list[ResearchCandidate]]:
        current_url = url
        redirects = 0
        while True:
            try:
                current_url = validate_public_url(current_url)
                robots = _cached_robots_for(
                    current_url,
                    self._transport,
                    self._limits,
                    robots_by_origin,
                )
                if robots is not None and not robots.can_fetch(USER_AGENT, current_url):
                    return (
                        _document(
                            url=current_url,
                            status="unavailable",
                            status_reason="Blocked by robots.txt.",
                            category=category_hint,
                        ),
                        [],
                    )
                response = self._transport.fetch(
                    current_url,
                    self._limits.timeout_seconds,
                    self._limits.max_content_bytes + 1,
                )
            except ResearchFetchError as exc:
                return (
                    _document(url=current_url, status="unavailable", status_reason=str(exc)),
                    [],
                )
            except TimeoutError:
                return (
                    _document(url=current_url, status="timeout", status_reason="Timed out."),
                    [],
                )
            except ResearchError as exc:
                return (
                    _document(url=current_url, status="blocked", status_reason=str(exc)),
                    [],
                )

            if response.status in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    return (
                        _document(
                            url=current_url,
                            status="unavailable",
                            status_reason=f"Redirect {response.status} had no Location header.",
                        ),
                        [],
                    )
                redirects += 1
                if redirects > self._limits.redirect_limit:
                    return (
                        _document(
                            url=current_url,
                            status="unavailable",
                            status_reason="Redirect limit exceeded.",
                        ),
                        [],
                    )
                current_url = urljoin(current_url, location)
                continue

            if response.status >= 400:
                return (
                    _document(
                        url=current_url,
                        status="unavailable",
                        status_reason=f"HTTP {response.status}.",
                        category=category_hint,
                    ),
                    [],
                )
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" not in content_type:
                return (
                    _document(
                        url=current_url,
                        status="unsupported-content-type",
                        status_reason=content_type or "Missing content type.",
                    ),
                    [],
                )
            if len(response.body) > self._limits.max_content_bytes:
                return (
                    _document(
                        url=current_url,
                        status="oversized",
                        status_reason="Response exceeded configured content limit.",
                    ),
                    [],
                )
            html_text = response.body.decode(_charset(content_type), errors="replace")
            extracted = extract_html_text(
                html_text,
                max_chars=self._limits.max_text_chars,
            )
            if not extracted.text:
                return (
                    _document(
                        url=current_url,
                        status="unavailable",
                        status_reason="No readable text extracted.",
                    ),
                    [],
                )
            links = discover_useful_links(html_text, current_url)
            url_category = _category_for_url(current_url)
            return (
                _document(
                    url=current_url,
                    status="retrieved",
                    title=extracted.title,
                    content=extracted.text,
                    support_content=extracted.support_text,
                    snippet=extracted.text[:600],
                    category=(
                        url_category
                        if url_category != "website"
                        else category_hint
                    ),
                ),
                links,
            )


AI_DETECTIVE_SYSTEM = """
You support the PurpOS Identify stage by organising lightweight public-web and
business research. Use only the retrieved sources and session inputs provided in
the prompt. Distinguish source-derived facts from AI interpretation in the
summary wording. Do not invent citations, URLs, source labels or source
references. Website-derived findings must use sourceType public-website and a
sourceReference copied exactly from the allowed source references. AI synthesis
over saved non-web session inputs may use sourceType ai-synthesis. Do not add
numeric confidence or strength fields.
""".strip()


@dataclass(frozen=True)
class ExtractedHtml:
    title: str | None
    text: str
    support_text: str
    links: list[str]


class ReadableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: str | None = None
        self.links: list[str] = []
        self._text: list[str] = []
        self._support_text: list[str] = []
        self._title_parts: list[str] = []
        self._ignored_depth = 0
        self._in_title = False
        self._active_anchor_href: str | None = None
        self._active_anchor_text: list[str] = []
        self.anchors: list[DiscoveredAnchor] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        if normalized in {"script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form"}:
            self._ignored_depth += 1
        if normalized == "title":
            self._in_title = True
        if normalized == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)
                self._active_anchor_href = href
                self._active_anchor_text = []

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in {"script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form"}:
            self._ignored_depth = max(0, self._ignored_depth - 1)
        if normalized == "title":
            self._in_title = False
            title = _clean_text(" ".join(self._title_parts))
            self.title = title or None
        if normalized == "a" and self._active_anchor_href is not None:
            self.anchors.append(
                DiscoveredAnchor(
                    href=self._active_anchor_href,
                    text=_clean_text(" ".join(self._active_anchor_text)),
                )
            )
            self._active_anchor_href = None
            self._active_anchor_text = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)
        if self._active_anchor_href is not None:
            self._active_anchor_text.append(data)
        if self._ignored_depth:
            return
        cleaned = _clean_text(html.unescape(data))
        if len(cleaned) >= 2:
            self._text.append(cleaned)
            if self._active_anchor_href is None:
                self._support_text.append(cleaned)

    @property
    def text(self) -> str:
        return _dedupe_lines(self._text)

    @property
    def support_text(self) -> str:
        return _dedupe_lines(self._support_text)


def extract_html_text(html_text: str, *, max_chars: int) -> ExtractedHtml:
    parser = ReadableHTMLParser()
    parser.feed(html_text)
    text = parser.text
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0].strip()
    support_text = parser.support_text
    if len(support_text) > max_chars:
        support_text = support_text[:max_chars].rsplit(" ", 1)[0].strip()
    return ExtractedHtml(
        title=parser.title,
        text=text,
        support_text=support_text,
        links=parser.links,
    )


def discover_useful_links(content: str, base_url: str) -> list[ResearchCandidate]:
    # Reparse original content if HTML was stored; tests also call this with HTML.
    parser = ReadableHTMLParser()
    parser.feed(content)
    discovered: list[ResearchCandidate] = []
    discovered_indexes: dict[str, int] = {}
    for anchor in parser.anchors:
        absolute = normalize_url(urljoin(base_url, anchor.href))
        if not same_host(base_url, absolute):
            continue
        category = _category_for_signals(absolute, anchor.text)
        if category == "website":
            continue
        if absolute in discovered_indexes:
            index = discovered_indexes[absolute]
            existing = discovered[index]
            if _category_specificity(category) < _category_specificity(
                existing.category
            ):
                discovered[index] = ResearchCandidate(
                    url=existing.url,
                    category=category,
                    discovery_order=existing.discovery_order,
                )
            continue
        discovered.append(
            ResearchCandidate(
                url=absolute,
                category=category,
                discovery_order=len(discovered),
            )
        )
        discovered_indexes[absolute] = len(discovered) - 1
    return discovered


def validate_public_url(raw_url: str) -> str:
    parsed = urlparse(raw_url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ResearchError("Only http and https URLs are supported.")
    if not parsed.hostname:
        raise ResearchError("Malformed URL.")
    if parsed.username or parsed.password:
        raise ResearchError("URLs with credentials are not supported.")
    hostname = parsed.hostname.strip().lower()
    if hostname in {"localhost", "metadata.google.internal"}:
        raise ResearchError("Internal hostnames are blocked.")
    if hostname.endswith(".localhost"):
        raise ResearchError("Internal hostnames are blocked.")
    for address in _resolve_hostname(hostname):
        if _is_blocked_ip(address):
            raise ResearchError("Private, local, link-local or internal IPs are blocked.")
    return normalize_url(raw_url)


def normalize_url(raw_url: str) -> str:
    parsed = urlparse(raw_url.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    query_items = [
        (name, value)
        for name, value in parse_qsl(parsed.query, keep_blank_values=True)
        if name.lower() not in TRACKING_QUERY_PARAMETERS
    ]
    query = urlencode(query_items, doseq=True)
    return urlunparse((scheme, netloc, path, "", query, ""))


def same_host(first: str, second: str) -> bool:
    return (urlparse(first).hostname or "").lower() == (
        urlparse(second).hostname or ""
    ).lower()


def _www_equivalent_hosts(first: str, second: str) -> bool:
    first_host = (urlparse(first).hostname or "").lower()
    second_host = (urlparse(second).hostname or "").lower()
    if first_host == second_host:
        return True
    return _without_www(first_host) == _without_www(second_host) and (
        first_host.startswith("www.") or second_host.startswith("www.")
    )


def _without_www(hostname: str) -> str:
    return hostname[4:] if hostname.startswith("www.") else hostname


def _resolve_hostname(hostname: str) -> list[ipaddress._BaseAddress]:
    try:
        raw_addresses = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ResearchError("Hostname could not be resolved.") from exc
    addresses: list[ipaddress._BaseAddress] = []
    for item in raw_addresses:
        address = item[4][0]
        try:
            addresses.append(ipaddress.ip_address(address))
        except ValueError:
            continue
    if not addresses:
        raise ResearchError("Hostname could not be resolved.")
    return addresses


def _is_blocked_ip(address: ipaddress._BaseAddress) -> bool:
    return bool(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def _robots_for(
    start_url: str,
    transport: ResearchTransport,
    limits: ResearchLimits,
) -> RobotFileParser | None:
    parsed = urlparse(start_url)
    robots_url = urlunparse((parsed.scheme, parsed.netloc, "/robots.txt", "", "", ""))
    robot_parser = RobotFileParser()
    robot_parser.set_url(robots_url)
    try:
        response = transport.fetch(
            robots_url,
            min(limits.timeout_seconds, 3),
            min(limits.max_content_bytes, 64_000),
        )
    except (ResearchFetchError, TimeoutError, ResearchError):
        return None
    if response.status >= 400:
        return None
    try:
        body = response.body.decode("utf-8", errors="replace").splitlines()
    except UnicodeDecodeError:
        return None
    robot_parser.parse(body)
    return robot_parser


def _cached_robots_for(
    url: str,
    transport: ResearchTransport,
    limits: ResearchLimits,
    cache: dict[str, RobotFileParser | None],
) -> RobotFileParser | None:
    parsed = urlparse(url)
    origin = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    if origin not in cache:
        cache[origin] = _robots_for(url, transport, limits)
    return cache[origin]


def _research_state(
    *,
    status: str,
    documents: list[ExternalResearchDocument],
    supported_status: str,
    supported_message: str,
) -> ExternalResearchState:
    categories: list[ExternalResearchCategoryState] = []
    for category in SUPPORTED_WEBSITE_CATEGORIES:
        source_ids = [
            doc.id
            for doc in documents
            if _document_supports_category(doc, category)
        ]
        status_for_category = supported_status
        message_for_category = supported_message
        if supported_status == "done" and not source_ids:
            status_for_category = "not-scanned"
            message_for_category = "No matching website page was retrieved."
        categories.append(
            ExternalResearchCategoryState(
                category=category,
                status=status_for_category,
                sourceIds=source_ids,
                message=message_for_category,
            )
        )
    categories.extend(
        ExternalResearchCategoryState(
            category=category,
            status="not-scanned",
            message="No public search provider is configured.",
        )
        for category in UNCONFIGURED_SEARCH_CATEGORIES
    )
    return ExternalResearchState(
        status=status,
        updatedAt=utc_now(),
        documents=documents,
        categories=categories,
    )


def _document(
    *,
    url: str,
    status: str,
    status_reason: str | None = None,
    title: str | None = None,
    content: str | None = None,
    support_content: str | None = None,
    snippet: str | None = None,
    category: str | None = None,
) -> ExternalResearchDocument:
    normalized_url = normalize_url(url) if urlparse(url).scheme else f"https://invalid.local/"
    parsed = urlparse(normalized_url)
    content_hash = (
        hashlib.sha256(content.encode("utf-8")).hexdigest() if content else None
    )
    primary_category = category or _category_for_url(normalized_url)
    return ExternalResearchDocument(
        id=source_reference_for_url(normalized_url),
        sourceType="public-website",
        category=primary_category,
        supportedCategories=_supported_categories_for_content(
            primary_category=primary_category,
            status=status,
            content=support_content if support_content is not None else content,
        ),
        url=normalized_url,
        title=title,
        organisationDomain=parsed.hostname,
        retrievedAt=utc_now(),
        status=status,
        statusReason=status_reason,
        content=content,
        snippet=snippet,
        contentHash=content_hash,
    )


def source_reference_for_url(url: str) -> str:
    return f"source:{uuid5(NAMESPACE_URL, normalize_url(url))}"


def _supported_categories_for_content(
    *,
    primary_category: str,
    status: str,
    content: str | None,
) -> list[str]:
    if status != "retrieved":
        return []

    supported = {primary_category}
    normalized_content = _normalized_content_signal(content or "")
    for category, rules in CATEGORY_CONTENT_SUPPORT_RULES.items():
        strong_phrases = rules["strong_phrases"]
        signals = rules["signals"]
        if any(
            _content_contains_term(normalized_content, phrase)
            for phrase in strong_phrases
        ):
            supported.add(category)
            continue
        distinct_signals = {
            signal
            for signal in signals
            if _content_contains_term(normalized_content, signal)
        }
        if len(distinct_signals) >= 3:
            supported.add(category)

    ordered = [
        category for category in SUPPORTED_WEBSITE_CATEGORIES if category in supported
    ]
    if primary_category not in ordered:
        ordered.append(primary_category)
    return ordered


def _document_supports_category(
    document: ExternalResearchDocument,
    category: str,
) -> bool:
    return bool(
        document.status == "retrieved"
        and (
            document.category == category
            or category in document.supported_categories
        )
    )


def _normalized_content_signal(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _content_contains_term(content: str, term: str) -> bool:
    normalized_term = _normalized_content_signal(term)
    return bool(normalized_term and f" {normalized_term} " in f" {content} ")


def _category_for_url(url: str) -> str:
    return _category_for_signals(url)


def _category_for_signals(url: str, anchor_text: str = "") -> str:
    path_signal = _normalized_discovery_signal(unquote(urlparse(url).path))
    anchor_signal = _normalized_discovery_signal(anchor_text)
    for category in CATEGORY_CLASSIFICATION_ORDER:
        terms = WEBSITE_CATEGORY_TERMS[category]
        if any(
            _signal_contains_term(path_signal, term)
            or _signal_contains_term(anchor_signal, term)
            for term in terms
        ):
            return category
    return "website"


def _normalized_discovery_signal(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _signal_contains_term(signal: str, term: str) -> bool:
    normalized_term = _normalized_discovery_signal(term)
    return bool(
        signal
        and re.search(
            rf"(?:^|-){re.escape(normalized_term)}(?:-|$)",
            signal,
        )
    )


def _pop_next_candidate(
    frontier: list[ResearchCandidate],
    attempted_categories: set[str],
    *,
    preferred_categories: set[str] | None = None,
) -> ResearchCandidate:
    preferred = preferred_categories or set()
    category_rank = {
        category: index for index, category in enumerate(CATEGORY_FRONTIER_ORDER)
    }
    selected_index = min(
        range(len(frontier)),
        key=lambda index: (
            frontier[index].category in attempted_categories,
            frontier[index].category not in preferred,
            category_rank.get(frontier[index].category, len(category_rank)),
            frontier[index].discovery_order,
        ),
    )
    return frontier.pop(selected_index)


def _upgrade_queued_candidate(
    frontier: list[ResearchCandidate],
    url: str,
    category: str,
) -> None:
    for index, candidate in enumerate(frontier):
        if candidate.url != url:
            continue
        if _category_specificity(category) < _category_specificity(
            candidate.category
        ):
            frontier[index] = ResearchCandidate(
                url=candidate.url,
                category=category,
                discovery_order=candidate.discovery_order,
            )
        return


def _category_specificity(category: str) -> int:
    try:
        return CATEGORY_CLASSIFICATION_ORDER.index(category)
    except ValueError:
        return len(CATEGORY_CLASSIFICATION_ORDER)


def _is_replacement_eligible(
    candidate: ResearchCandidate,
    document: ExternalResearchDocument,
) -> bool:
    return bool(
        candidate.category in CATEGORY_FRONTIER_ORDER
        and document.status == "unavailable"
        and document.status_reason in REPLACEMENT_ELIGIBLE_STATUS_REASONS
    )


def _has_research_inputs(
    state: IdentifyState,
    organisation: OrganisationContext | None,
    documents: list[ExternalResearchDocument],
) -> bool:
    return bool(
        documents
        or state.evidence
        or state.output.stakeholder_insights
        or state.output.pestle_findings
        or state.output.company_cards_evidence
        or state.output.discovery_brief
        or state.output.research_findings
    )


def _build_prompt(
    state: IdentifyState,
    organisation: OrganisationContext | None,
    research_state: ExternalResearchState,
) -> str:
    retrieved_sources = [
        {
            "sourceReference": doc.id,
            "sourceType": doc.source_type,
            "url": str(doc.url),
            "title": doc.title,
            "category": doc.category,
            "supportedCategories": doc.supported_categories,
            "retrievedAt": doc.retrieved_at.isoformat(),
            "content": doc.content,
        }
        for doc in research_state.documents
        if doc.status == "retrieved"
    ]
    return (
        "Create concise AI Detective research findings for Identify. "
        "Use website sourceReference values exactly as provided and only when "
        "the finding is supported by that retrieved page. Mark website-derived "
        "facts as sourceType public-website. Keep interpretation clearly worded "
        "as interpretation. Broader public search categories are not scanned "
        "unless sources are present. Inputs: "
        f"organisation={_dump_item(organisation)}; "
        f"retrieved_sources={retrieved_sources}; "
        f"research_categories={_dump_items(research_state.categories)}; "
        f"discovery_brief={state.output.discovery_brief!r}; "
        f"identify_evidence={_dump_items(state.evidence)}; "
        f"stakeholders={_dump_items(state.output.stakeholder_insights)}; "
        f"pestle_findings={_dump_items(state.output.pestle_findings)}; "
        f"company_cards={_dump_item(state.output.company_cards_evidence)}; "
        f"existing_research_findings={_dump_items(state.output.research_findings)}"
    )


def _validated_findings(
    findings: list[ResearchFinding],
    research_state: ExternalResearchState,
    state: IdentifyState,
) -> list[ResearchFinding]:
    retrieved_refs = {
        doc.id: doc for doc in research_state.documents if doc.status == "retrieved"
    }
    existing_session_refs = {
        finding.source_reference
        for finding in state.output.research_findings
        if finding.source_reference
    }
    validated: list[ResearchFinding] = []
    seen: set[tuple[str, str, str | None]] = set()
    for finding in findings:
        if finding.source_type == ResearchSourceType.public_website:
            if not finding.source_reference or finding.source_reference not in retrieved_refs:
                continue
            source = retrieved_refs[finding.source_reference]
            finding = finding.model_copy(
                update={
                    "source_label": source.title or str(source.url),
                    "collected_at": source.retrieved_at,
                }
            )
        elif finding.source_type == ResearchSourceType.ai_synthesis:
            if finding.source_reference and finding.source_reference.startswith("source:"):
                continue
        elif finding.source_reference and finding.source_reference not in existing_session_refs:
            continue

        fingerprint = (
            finding.topic.strip().lower(),
            finding.summary.strip().lower(),
            finding.source_reference,
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        validated.append(finding)
    return validated


def _limited_message(research_state: ExternalResearchState) -> str:
    if research_state.status == "not-configured":
        return "External research is disabled."
    if research_state.status == "unavailable":
        return "No public website sources could be retrieved."
    return "No public website was supplied and no retrievable research sources are available."


def _charset(content_type: str) -> str:
    match = re.search(r"charset=([^;\s]+)", content_type, flags=re.IGNORECASE)
    return match.group(1) if match else "utf-8"


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _dedupe_lines(values: list[str]) -> str:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean_text(value)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(cleaned)
    return "\n".join(unique)


def _dump_item(item: object | None) -> object | None:
    if item is None:
        return None
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json", by_alias=True)
    return item


def _dump_items(items: list[object]) -> list[object]:
    dumped: list[object] = []
    for item in items:
        if hasattr(item, "model_dump"):
            dumped.append(item.model_dump(mode="json", by_alias=True))
        else:
            dumped.append(item)
    return dumped
