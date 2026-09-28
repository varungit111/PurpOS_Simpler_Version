import ipaddress
import unittest
from unittest.mock import patch

from app.schemas.ai_detective import AIDetectiveGeneration
from app.schemas.assessment import (
    ExternalResearchDocument,
    IdentifyState,
    OrganisationContext,
)
from app.services.ai_client import AIProviderError
from app.services import research
from app.services.research import (
    FetchResponse,
    IdentifyEvidenceResearchProvider,
    ResearchCollectionResult,
    ResearchLimits,
    source_reference_for_url,
    validate_public_url,
)


PUBLIC_IPS = ["93.184.216.34"]


class FakeTransport:
    def __init__(self, routes: dict[str, FetchResponse | Exception]) -> None:
        self.routes = routes
        self.requests: list[str] = []

    def fetch(
        self,
        url: str,
        timeout_seconds: float,
        max_bytes: int | None = None,
    ) -> FetchResponse:
        self.requests.append(url)
        result = self.routes.get(url)
        if result is None:
            return response(url, 404, "text/plain", b"Not found")
        if isinstance(result, Exception):
            raise result
        if max_bytes is not None:
            return FetchResponse(
                status=result.status,
                url=result.url,
                headers=result.headers,
                body=result.body[:max_bytes],
            )
        return result


class WebsiteAIClient:
    def __init__(
        self,
        *,
        invalid_reference: bool = False,
        source_url: str = "https://example.com/",
    ) -> None:
        self.invalid_reference = invalid_reference
        self.source_url = source_url
        self.prompt = ""

    def generate_structured(
        self,
        prompt: str,
        output_schema: type[AIDetectiveGeneration],
        system: str | None = None,
    ) -> AIDetectiveGeneration:
        self.prompt = prompt
        source_ref = (
            "source:missing"
            if self.invalid_reference
            else source_reference_for_url(self.source_url)
        )
        return output_schema(
            findings=[
                {
                    "topic": "Source-derived observation",
                    "summary": (
                        "Fact: Example Co says it supports clinics. "
                        "AI interpretation: this suggests a service-led offer."
                    ),
                    "sourceType": "public-website",
                    "sourceLabel": "Homepage",
                    "sourceReference": source_ref,
                },
                {
                    "topic": "Source-derived observation",
                    "summary": (
                        "Fact: Example Co says it supports clinics. "
                        "AI interpretation: this suggests a service-led offer."
                    ),
                    "sourceType": "public-website",
                    "sourceLabel": "Homepage",
                    "sourceReference": source_ref,
                },
            ]
        )


class FailingAIClient:
    def generate_structured(
        self,
        prompt: str,
        output_schema: type[AIDetectiveGeneration],
        system: str | None = None,
    ) -> AIDetectiveGeneration:
        raise AIProviderError("boom")


def response(
    url: str,
    status: int,
    content_type: str,
    body: bytes,
    headers: dict[str, str] | None = None,
) -> FetchResponse:
    merged_headers = {"content-type": content_type}
    if headers:
        merged_headers.update({key.lower(): value for key, value in headers.items()})
    return FetchResponse(status=status, url=url, headers=merged_headers, body=body)


def html_page(title: str, body: str) -> bytes:
    return (
        f"<html><head><title>{title}</title><script>hide()</script></head>"
        f"<body><nav>Menu</nav><main>{body}</main><footer>Footer</footer></body></html>"
    ).encode("utf-8")


def organisation(url: str = "https://example.com/") -> OrganisationContext:
    return OrganisationContext(companyName="Example Co", website=url)


class ExternalResearchServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.resolve_patch = patch.object(
            research,
            "_resolve_hostname",
            side_effect=fake_resolve_hostname,
        )
        self.resolve_patch.start()

    def tearDown(self) -> None:
        self.resolve_patch.stop()

    def test_successful_public_website_retrieval_and_provenance(self) -> None:
        transport = FakeTransport(
            {
                "https://example.com/robots.txt": response(
                    "https://example.com/robots.txt", 404, "text/plain", b""
                ),
                "https://example.com/": response(
                    "https://example.com/",
                    200,
                    "text/html; charset=utf-8",
                    html_page(
                        "Homepage",
                        "<h1>Example Co</h1><p>We support clinics.</p>",
                    ),
                ),
            }
        )
        provider = provider_with(transport, WebsiteAIClient())

        result = provider.collect(IdentifyState(), organisation())

        self.assertEqual(result.status, "connected")
        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].source_type, "public-website")
        self.assertEqual(
            result.findings[0].source_reference,
            source_reference_for_url("https://example.com/"),
        )
        assert result.external_research is not None
        document = result.external_research.documents[0]
        self.assertEqual(document.status, "retrieved")
        self.assertEqual(document.title, "Homepage")
        self.assertIn("We support clinics", document.content or "")
        self.assertNotIn("hide()", document.content or "")
        self.assertIsNotNone(document.retrieved_at)

    def test_multiple_useful_same_domain_pages_and_partial_failure(self) -> None:
        transport = FakeTransport(
            {
                "https://example.com/robots.txt": response(
                    "https://example.com/robots.txt", 404, "text/plain", b""
                ),
                "https://example.com/": response(
                    "https://example.com/",
                    200,
                    "text/html",
                    html_page(
                        "Home",
                        (
                            '<a href="/about">About</a>'
                            '<a href="/services">Services</a>'
                            '<a href="https://other.test/about">Other</a>'
                            "<p>Homepage copy.</p>"
                        ),
                    ),
                ),
                "https://example.com/about": response(
                    "https://example.com/about",
                    500,
                    "text/html",
                    html_page("About", "<p>Broken.</p>"),
                ),
                "https://example.com/services": response(
                    "https://example.com/services",
                    200,
                    "text/html",
                    html_page("Services", "<p>Clinic workflow services.</p>"),
                ),
            }
        )
        provider = provider_with(transport, WebsiteAIClient(), max_pages=3)

        result = provider.collect(IdentifyState(), organisation())

        assert result.external_research is not None
        statuses = {str(doc.url): doc.status for doc in result.external_research.documents}
        self.assertEqual(statuses["https://example.com/"], "retrieved")
        self.assertEqual(statuses["https://example.com/about"], "unavailable")
        self.assertEqual(statuses["https://example.com/services"], "retrieved")
        self.assertNotIn("https://other.test/about", transport.requests)

    def test_html_text_extraction_is_deterministic(self) -> None:
        extracted = research.extract_html_text(
            """
            <html><head><title> About Us </title><style>.x{}</style></head>
            <body><header>Navigation</header><main><h1>Purpose</h1>
            <p>We help customers.</p><p>We help customers.</p></main></body></html>
            """,
            max_chars=1000,
        )

        self.assertEqual(extracted.title, "About Us")
        self.assertIn("Purpose", extracted.text)
        self.assertIn("We help customers.", extracted.text)
        self.assertNotIn("Navigation", extracted.text)
        self.assertEqual(extracted.text.count("We help customers."), 1)

    def test_homepage_content_can_support_multiple_research_categories(self) -> None:
        transport = FakeTransport(
            {
                "https://example.com/robots.txt": response(
                    "https://example.com/robots.txt", 404, "text/plain", b""
                ),
                "https://example.com/": response(
                    "https://example.com/",
                    200,
                    "text/html",
                    html_page(
                        "Home",
                        (
                            "<p>Our health insurance plans cover diagnostics, "
                            "specialists, surgery and cancer care.</p>"
                            "<p>New members, existing members, businesses and "
                            "health professionals can access dedicated support.</p>"
                        ),
                    ),
                ),
            }
        )

        result = provider_with(transport, None).collect(
            IdentifyState(), organisation()
        )

        assert result.external_research is not None
        homepage = result.external_research.documents[0]
        self.assertEqual(homepage.category, "website")
        self.assertEqual(
            homepage.supported_categories,
            ["website", "products-services", "customer-groups"],
        )
        self.assertEqual(category_status(result, "website"), "done")
        self.assertEqual(category_status(result, "products-services"), "done")
        self.assertEqual(category_status(result, "customer-groups"), "done")
        for category_name in (
            "website",
            "products-services",
            "customer-groups",
        ):
            category = next(
                item
                for item in result.external_research.categories
                if item.category == category_name
            )
            self.assertEqual(category.source_ids, [homepage.id])

    def test_strong_sustainability_and_purpose_content_adds_support(self) -> None:
        document = research._document(
            url="https://example.com/",
            status="retrieved",
            category="website",
            content=(
                "Our sustainability strategy addresses climate change, carbon "
                "emissions and environmental responsibility. Our purpose and "
                "our values guide the executive team and board of directors."
            ),
        )

        self.assertEqual(
            document.supported_categories,
            [
                "website",
                "leadership-values-purpose",
                "sustainability-impact",
            ],
        )

    def test_generic_or_unrelated_content_does_not_add_support(self) -> None:
        for content in (
            "Welcome to Acme. Contact us.",
            "Our community can contact us here.",
            "Learn about one insurance update.",
            "Meet one member of our team.",
            "We value clear communication.",
        ):
            with self.subTest(content=content):
                document = research._document(
                    url="https://example.com/",
                    status="retrieved",
                    category="website",
                    content=content,
                )
                self.assertEqual(document.supported_categories, ["website"])

    def test_primary_category_is_supported_without_matching_content(self) -> None:
        document = research._document(
            url="https://example.com/impact",
            status="retrieved",
            category="sustainability-impact",
            content="A factual update with no category vocabulary.",
        )

        self.assertEqual(
            document.supported_categories,
            ["sustainability-impact"],
        )

    def test_old_document_without_supported_categories_remains_compatible(self) -> None:
        document = ExternalResearchDocument.model_validate(
            {
                "id": "source:legacy",
                "sourceType": "public-website",
                "category": "products-services",
                "url": "https://example.com/plans",
                "status": "retrieved",
                "content": "Legacy persisted content.",
            }
        )

        self.assertEqual(document.supported_categories, [])
        state = research._research_state(
            status="retrieved",
            documents=[document],
            supported_status="done",
            supported_message="1 website page(s) retrieved.",
        )
        product_state = next(
            item
            for item in state.categories
            if item.category == "products-services"
        )
        self.assertEqual(product_state.status, "done")
        self.assertEqual(product_state.source_ids, [document.id])

    def test_normalize_url_strips_tracking_and_preserves_meaningful_query(self) -> None:
        normalized = research.normalize_url(
            "https://EXAMPLE.com/plans?utm_source=google&view=family&gclid=abc"
            "&gclsrc=aw.ds&gad_source=1&gad_campaignid=22&campaignid=33"
            "&gbraid=gb&wbraid=wb&fbclid=fb&utm_medium=cpc"
            "&utm_campaign=spring&utm_term=cover&utm_content=hero&page=2#details"
        )

        self.assertEqual(
            normalized,
            "https://example.com/plans?view=family&page=2",
        )

    def test_tracking_only_link_variants_are_queued_once(self) -> None:
        transport = FakeTransport(
            {
                "https://example.com/robots.txt": response(
                    "https://example.com/robots.txt", 404, "text/plain", b""
                ),
                "https://example.com/": response(
                    "https://example.com/",
                    200,
                    "text/html",
                    html_page(
                        "Home",
                        (
                            '<a href="/services?utm_source=one">Services</a>'
                            '<a href="/services?gclid=two">Our services</a>'
                        ),
                    ),
                ),
                "https://example.com/services": response(
                    "https://example.com/services",
                    200,
                    "text/html",
                    html_page("Services", "<p>Service details.</p>"),
                ),
            }
        )

        result = provider_with(transport, None).collect(
            IdentifyState(), organisation()
        )

        assert result.external_research is not None
        self.assertEqual(transport.requests.count("https://example.com/services"), 1)
        self.assertEqual(len(result.external_research.documents), 2)

    def test_category_links_are_discovered_from_paths_and_anchor_text(self) -> None:
        candidates = research.discover_useful_links(
            """
            <a href="/services">Details</a>
            <a href="/learn-more">Health insurance</a>
            <a href="/about/sustainability">Corporate information</a>
            <a href="/work">Supporting communities</a>
            <a href="/people">Our members</a>
            <a href="/company">Our leadership</a>
            <a href="/contact">Contact</a>
            """,
            "https://example.com/",
        )

        categories = {candidate.url: candidate.category for candidate in candidates}
        self.assertEqual(
            categories["https://example.com/services"],
            "products-services",
        )
        self.assertEqual(
            categories["https://example.com/learn-more"],
            "products-services",
        )
        self.assertEqual(
            categories["https://example.com/about/sustainability"],
            "sustainability-impact",
        )
        self.assertEqual(
            categories["https://example.com/work"],
            "sustainability-impact",
        )
        self.assertEqual(categories["https://example.com/people"], "customer-groups")
        self.assertEqual(
            categories["https://example.com/company"],
            "leadership-values-purpose",
        )
        self.assertNotIn("https://example.com/contact", categories)

    def test_specific_category_precedence_over_about(self) -> None:
        self.assertEqual(
            research._category_for_url("https://example.com/about/sustainability"),
            "sustainability-impact",
        )
        self.assertEqual(
            research._category_for_url("https://example.com/about/health-insurance"),
            "products-services",
        )
        self.assertEqual(
            research._category_for_url("https://example.com/about/members"),
            "customer-groups",
        )

    def test_retrieved_anchor_classified_customer_page_marks_category_done(self) -> None:
        transport = FakeTransport(
            {
                "https://example.com/robots.txt": response(
                    "https://example.com/robots.txt", 404, "text/plain", b""
                ),
                "https://example.com/": response(
                    "https://example.com/",
                    200,
                    "text/html",
                    html_page("Home", '<a href="/audiences">Our members</a>'),
                ),
                "https://example.com/audiences": response(
                    "https://example.com/audiences",
                    200,
                    "text/html",
                    html_page("Members", "<p>We serve families and employers.</p>"),
                ),
            }
        )

        result = provider_with(transport, None).collect(
            IdentifyState(), organisation()
        )

        assert result.external_research is not None
        states = {
            category.category: category
            for category in result.external_research.categories
        }
        self.assertEqual(states["customer-groups"].status, "done")
        self.assertEqual(len(states["customer-groups"].source_ids), 1)
        self.assertEqual(states["competitors"].status, "not-scanned")

    def test_category_aware_frontier_preserves_representative_coverage(self) -> None:
        product_links = "".join(
            f'<a href="/products/{index}">Product {index}</a>'
            for index in range(110)
        )
        category_links = (
            '<a href="/about">About us</a>'
            '<a href="/impact">Our impact</a>'
            '<a href="/audiences">Our members</a>'
        )
        routes = {
            "https://example.com/robots.txt": response(
                "https://example.com/robots.txt", 404, "text/plain", b""
            ),
            "https://example.com/": response(
                "https://example.com/",
                200,
                "text/html",
                html_page("Home", product_links + category_links),
            ),
            "https://example.com/about": response(
                "https://example.com/about",
                200,
                "text/html",
                html_page("About", "<p>Purpose.</p>"),
            ),
            "https://example.com/impact": response(
                "https://example.com/impact",
                200,
                "text/html",
                html_page("Impact", "<p>Impact.</p>"),
            ),
            "https://example.com/audiences": response(
                "https://example.com/audiences",
                200,
                "text/html",
                html_page("Members", "<p>Members.</p>"),
            ),
        }
        for index in range(110):
            url = f"https://example.com/products/{index}"
            routes[url] = response(
                url, 200, "text/html", html_page(f"Product {index}", "<p>Product.</p>")
            )
        transport = FakeTransport(routes)

        result = provider_with(transport, None, max_pages=6).collect(
            IdentifyState(), organisation()
        )

        assert result.external_research is not None
        retrieved_categories = {
            document.category
            for document in result.external_research.documents
            if document.status == "retrieved"
        }
        self.assertEqual(len(result.external_research.documents), 6)
        self.assertTrue(
            {
                "website",
                "products-services",
                "leadership-values-purpose",
                "sustainability-impact",
                "customer-groups",
            }.issubset(retrieved_categories)
        )

    def test_product_404_allows_same_category_replacement(self) -> None:
        transport = replacement_transport(
            '<a href="/products/missing">Missing plan</a>'
            '<a href="/products/available">Available plan</a>',
            {
                "/products/missing": (404, "Missing", ""),
                "/products/available": (200, "Available", "Plan details."),
            },
        )

        result = provider_with(transport, None, max_pages=2).collect(
            IdentifyState(), organisation()
        )

        assert result.external_research is not None
        self.assertEqual(
            document_urls(result.external_research.documents),
            [
                "https://example.com/",
                "https://example.com/products/missing",
                "https://example.com/products/available",
            ],
        )
        self.assertEqual(retrieved_document_count(result), 2)
        self.assertEqual(category_status(result, "products-services"), "done")

    def test_customer_404_allows_same_category_replacement(self) -> None:
        transport = replacement_transport(
            '<a href="/members/missing">Members</a>'
            '<a href="/members/available">Member options</a>',
            {
                "/members/missing": (404, "Missing", ""),
                "/members/available": (200, "Members", "Member details."),
            },
        )

        result = provider_with(transport, None, max_pages=2).collect(
            IdentifyState(), organisation()
        )

        assert result.external_research is not None
        self.assertEqual(retrieved_document_count(result), 2)
        self.assertEqual(category_status(result, "customer-groups"), "done")

    def test_replacement_attempts_are_globally_capped_at_two(self) -> None:
        links = "".join(
            f'<a href="/products/missing-{index}">Plan {index}</a>'
            for index in range(10)
        )
        routes = {
            f"/products/missing-{index}": (404, "Missing", "")
            for index in range(10)
        }
        transport = replacement_transport(links, routes)

        result = provider_with(transport, None, max_pages=2).collect(
            IdentifyState(), organisation()
        )

        assert result.external_research is not None
        self.assertEqual(len(result.external_research.documents), 4)
        self.assertEqual(retrieved_document_count(result), 1)
        self.assertEqual(category_status(result, "products-services"), "not-scanned")
        self.assertNotIn("https://example.com/products/missing-3", transport.requests)

    def test_successful_documents_remain_capped_at_six(self) -> None:
        links = (
            '<a href="/products/missing-one">Missing plan one</a>'
            '<a href="/products/missing-two">Missing plan two</a>'
            '<a href="/products/available-one">Available plan one</a>'
            '<a href="/products/available-two">Available plan two</a>'
            '<a href="/products/not-fetched">Extra plan</a>'
            '<a href="/about">About us</a>'
            '<a href="/impact">Our impact</a>'
            '<a href="/members">Our members</a>'
        )
        transport = replacement_transport(
            links,
            {
                "/products/missing-one": (404, "Missing", ""),
                "/products/missing-two": (410, "Gone", ""),
                "/products/available-one": (200, "Plan one", "Plan one."),
                "/products/available-two": (200, "Plan two", "Plan two."),
                "/products/not-fetched": (200, "Extra", "Extra plan."),
                "/about": (200, "About", "Our purpose."),
                "/impact": (200, "Impact", "Our impact."),
                "/members": (200, "Members", "Member services."),
            },
        )

        result = provider_with(transport, None, max_pages=6).collect(
            IdentifyState(), organisation()
        )

        assert result.external_research is not None
        self.assertEqual(len(result.external_research.documents), 8)
        self.assertEqual(retrieved_document_count(result), 6)
        self.assertNotIn("https://example.com/products/not-fetched", transport.requests)

    def test_southern_cross_shaped_failures_use_bounded_replacements(self) -> None:
        links = (
            '<a href="/products/missing-one">Why choose us</a>'
            '<a href="/products/missing-two">Our plans</a>'
            '<a href="/products/available">Compare plans</a>'
            '<a href="/about">About us</a>'
            '<a href="/impact">In the community</a>'
            '<a href="/members/missing">Member toolbox</a>'
            '<a href="/members/available">For members</a>'
        )
        transport = replacement_transport(
            links,
            {
                "/products/missing-one": (404, "Missing", ""),
                "/products/missing-two": (404, "Missing", ""),
                "/products/available": (200, "Plans", "Plan details."),
                "/about": (200, "About", "Our purpose."),
                "/impact": (200, "Impact", "Community impact."),
                "/members/missing": (404, "Missing", ""),
                "/members/available": (200, "Members", "Member services."),
            },
        )

        result = provider_with(transport, None, max_pages=6).collect(
            IdentifyState(), organisation()
        )

        assert result.external_research is not None
        self.assertEqual(len(result.external_research.documents), 8)
        self.assertLessEqual(retrieved_document_count(result), 6)
        self.assertEqual(category_status(result, "products-services"), "done")
        self.assertEqual(category_status(result, "customer-groups"), "done")
        self.assertEqual(
            document_urls(result.external_research.documents),
            [
                "https://example.com/",
                "https://example.com/products/missing-one",
                "https://example.com/about",
                "https://example.com/impact",
                "https://example.com/members/missing",
                "https://example.com/products/missing-two",
                "https://example.com/products/available",
                "https://example.com/members/available",
            ],
        )

    def test_homepage_evidence_survives_southern_cross_failures(
        self,
    ) -> None:
        links = (
            "<p>Our health insurance plans cover everyday healthcare, diagnostics, "
            "specialists, surgery and cancer care.</p>"
            "<p>New members, existing members, businesses and health professionals "
            "receive dedicated support.</p>"
            '<a href="/products/missing-one">Why choose us</a>'
            '<a href="/products/missing-two">Our plans</a>'
            '<a href="/products/missing-three">Cancer care</a>'
            '<a href="/products/missing-four">Join and buy</a>'
            '<a href="/about">About us</a>'
            '<a href="/impact">In the community</a>'
            '<a href="/members/missing">Member toolbox</a>'
        )
        transport = replacement_transport(
            links,
            {
                "/products/missing-one": (404, "Missing", ""),
                "/products/missing-two": (404, "Missing", ""),
                "/products/missing-three": (404, "Missing", ""),
                "/products/missing-four": (404, "Missing", ""),
                "/about": (200, "About", "Our purpose."),
                "/impact": (200, "Impact", "Community impact."),
                "/members/missing": (404, "Missing", ""),
            },
        )

        result = provider_with(transport, None, max_pages=6).collect(
            IdentifyState(), organisation()
        )

        assert result.external_research is not None
        self.assertEqual(len(result.external_research.documents), 8)
        self.assertEqual(retrieved_document_count(result), 3)
        self.assertEqual(category_status(result, "products-services"), "done")
        self.assertEqual(category_status(result, "customer-groups"), "done")
        homepage = result.external_research.documents[0]
        self.assertEqual(homepage.category, "website")
        self.assertIn("products-services", homepage.supported_categories)
        self.assertIn("customer-groups", homepage.supported_categories)
        failed = [
            document
            for document in result.external_research.documents
            if document.status != "retrieved"
        ]
        self.assertEqual(len(failed), 5)
        self.assertTrue(
            all(not document.supported_categories for document in failed)
        )

    def test_failed_documents_are_not_ai_inputs_or_valid_sources(self) -> None:
        failed_url = "https://example.com/products/missing"
        client = WebsiteAIClient(source_url=failed_url)
        transport = replacement_transport(
            '<a href="/products/missing">Missing plan</a>',
            {"/products/missing": (404, "Missing", "")},
        )

        result = provider_with(transport, client, max_pages=2).collect(
            IdentifyState(), organisation()
        )

        self.assertEqual(result.status, "error")
        self.assertEqual(result.findings, [])
        self.assertNotIn(failed_url, client.prompt)
        assert result.external_research is not None
        self.assertEqual(result.external_research.documents[1].status, "unavailable")

    def test_private_redirect_does_not_grant_replacement_attempt(self) -> None:
        transport = replacement_transport(
            '<a href="/products/blocked">Blocked plan</a>'
            '<a href="/products/available">Available plan</a>',
            {
                "/products/blocked": (
                    302,
                    "Blocked",
                    "",
                    {"location": "http://127.0.0.1/admin"},
                ),
                "/products/available": (200, "Available", "Plan details."),
            },
        )

        result = provider_with(transport, None, max_pages=2).collect(
            IdentifyState(), organisation()
        )

        assert result.external_research is not None
        self.assertEqual(len(result.external_research.documents), 2)
        self.assertNotIn("https://example.com/products/available", transport.requests)
        self.assertEqual(result.external_research.documents[1].status, "blocked")

    def test_robots_denial_does_not_grant_replacement_attempt(self) -> None:
        transport = replacement_transport(
            '<a href="/products/blocked">Blocked plan</a>'
            '<a href="/products/available">Available plan</a>',
            {
                "/products/available": (200, "Available", "Plan details."),
            },
            robots=b"User-agent: *\nDisallow: /products/blocked\n",
        )

        result = provider_with(transport, None, max_pages=2).collect(
            IdentifyState(), organisation()
        )

        assert result.external_research is not None
        self.assertEqual(len(result.external_research.documents), 2)
        self.assertNotIn("https://example.com/products/available", transport.requests)
        self.assertEqual(
            result.external_research.documents[1].status_reason,
            "Blocked by robots.txt.",
        )
        self.assertEqual(
            result.external_research.documents[1].supported_categories,
            [],
        )

    def test_irrelevant_and_duplicate_links_do_not_consume_frontier_budget(self) -> None:
        candidates = research.discover_useful_links(
            """
            <a href="/contact">Contact</a>
            <a href="/services?utm_source=one">Services</a>
            <a href="/services?gclid=two">Services again</a>
            <a href="https://other.example.com/services">Other host</a>
            """,
            "https://example.com/",
        )

        self.assertEqual(
            [(candidate.url, candidate.category) for candidate in candidates],
            [("https://example.com/services", "products-services")],
        )

    def test_arbitrary_subdomains_remain_outside_discovery(self) -> None:
        candidates = research.discover_useful_links(
            '<a href="https://shop.example.com/products">Products</a>',
            "https://example.com/",
        )

        self.assertEqual(candidates, [])

    def test_source_references_are_validated(self) -> None:
        provider = provider_with(
            website_transport(),
            WebsiteAIClient(invalid_reference=True),
        )

        result = provider.collect(IdentifyState(), organisation())

        self.assertEqual(result.status, "error")
        self.assertEqual(result.findings, [])
        assert result.external_research is not None
        self.assertEqual(result.external_research.synthesis_error, "No validated source references returned.")

    def test_website_unavailable_timeout_oversized_and_content_type_states(self) -> None:
        cases = [
            (ResearchFetchError("Network down"), "unavailable"),
            (TimeoutError(), "timeout"),
            (
                response(
                    "https://example.com/",
                    200,
                    "text/html",
                    b"x" * 200,
                ),
                "oversized",
            ),
            (
                response(
                    "https://example.com/",
                    200,
                    "application/pdf",
                    b"%PDF",
                ),
                "unsupported-content-type",
            ),
        ]
        for route_result, expected_status in cases:
            with self.subTest(expected_status=expected_status):
                transport = FakeTransport(
                    {
                        "https://example.com/robots.txt": response(
                            "https://example.com/robots.txt", 404, "text/plain", b""
                        ),
                        "https://example.com/": route_result,
                    }
                )
                provider = provider_with(
                    transport,
                    WebsiteAIClient(),
                    max_content_bytes=50,
                )
                result = provider.collect(IdentifyState(), organisation())
                assert result.external_research is not None
                self.assertEqual(
                    result.external_research.documents[0].status,
                    expected_status,
                )

    def test_ssrf_rejections(self) -> None:
        blocked_urls = [
            "not-a-url",
            "ftp://example.com/",
            "http://localhost/",
            "http://127.0.0.1/",
            "http://10.0.0.1/",
            "http://169.254.169.254/",
        ]
        for url in blocked_urls:
            with self.subTest(url=url):
                with self.assertRaises(research.ResearchError):
                    validate_public_url(url)

    def test_redirect_to_private_destination_is_blocked(self) -> None:
        transport = FakeTransport(
            {
                "https://example.com/robots.txt": response(
                    "https://example.com/robots.txt", 404, "text/plain", b""
                ),
                "https://example.com/": response(
                    "https://example.com/",
                    302,
                    "text/html",
                    b"",
                    {"location": "http://127.0.0.1/admin"},
                ),
            }
        )
        provider = provider_with(transport, WebsiteAIClient())

        result = provider.collect(IdentifyState(), organisation())

        assert result.external_research is not None
        self.assertEqual(result.external_research.documents[0].status, "blocked")

    def test_www_redirect_adopts_canonical_host_for_discovery(self) -> None:
        self._assert_canonical_www_redirect(
            start_url="https://www.example.com/",
            canonical_url="https://example.com/",
        )

    def test_non_www_redirect_adopts_canonical_host_for_discovery(self) -> None:
        self._assert_canonical_www_redirect(
            start_url="https://example.com/",
            canonical_url="https://www.example.com/",
        )

    def test_canonical_host_robots_rules_apply_before_following_links(self) -> None:
        transport = FakeTransport(
            {
                "https://example.com/robots.txt": response(
                    "https://example.com/robots.txt", 404, "text/plain", b""
                ),
                "https://example.com/": response(
                    "https://example.com/",
                    301,
                    "text/html",
                    b"",
                    {"location": "https://www.example.com/"},
                ),
                "https://www.example.com/robots.txt": response(
                    "https://www.example.com/robots.txt",
                    200,
                    "text/plain",
                    b"User-agent: *\nDisallow: /services\n",
                ),
                "https://www.example.com/": response(
                    "https://www.example.com/",
                    200,
                    "text/html",
                    html_page("Home", '<a href="/services">Services</a>'),
                ),
            }
        )

        result = provider_with(transport, None).collect(
            IdentifyState(), organisation("https://example.com/")
        )

        assert result.external_research is not None
        self.assertNotIn("https://www.example.com/services", transport.requests)
        blocked = next(
            document
            for document in result.external_research.documents
            if str(document.url) == "https://www.example.com/services"
        )
        self.assertEqual(blocked.status, "unavailable")
        self.assertEqual(blocked.status_reason, "Blocked by robots.txt.")

    def test_ai_synthesis_failure_preserves_retrieval_state(self) -> None:
        provider = provider_with(website_transport(), FailingAIClient())

        result = provider.collect(IdentifyState(), organisation())

        self.assertEqual(result.status, "error")
        assert result.external_research is not None
        self.assertEqual(result.external_research.documents[0].status, "retrieved")
        self.assertEqual(result.external_research.synthesis_error, "AI synthesis failed.")

    def test_completed_research_does_not_rerun_but_explicit_retry_does(self) -> None:
        transport = website_transport()
        provider = provider_with(transport, WebsiteAIClient())
        first = provider.collect(IdentifyState(), organisation())
        assert first.external_research is not None
        saved_state = IdentifyState()
        saved_state.output.external_research = first.external_research
        saved_state.output.research_findings = first.findings
        request_count = len(transport.requests)

        restored = provider.collect(saved_state, organisation())
        transport.routes["https://example.com/"] = response(
            "https://example.com/",
            200,
            "text/html",
            html_page("Updated homepage", "<p>Updated clinic support.</p>"),
        )
        retried = provider.collect(saved_state, organisation(), refresh=True)

        self.assertEqual(restored.message, "AI Detective research restored from saved sources.")
        self.assertEqual(len(transport.requests), request_count + 2)
        self.assertEqual(retried.status, "connected")
        assert retried.external_research is not None
        self.assertIn(
            "Updated clinic support",
            retried.external_research.documents[0].content or "",
        )

    def test_findings_do_not_duplicate_after_retry_and_state_reloads(self) -> None:
        transport = website_transport()
        provider = provider_with(transport, WebsiteAIClient())

        first = provider.collect(IdentifyState(), organisation())
        second = provider.collect(IdentifyState(), organisation(), refresh=True)

        self.assertEqual(len(first.findings), 1)
        self.assertEqual(len(second.findings), 1)
        assert second.external_research is not None
        dumped = second.external_research.model_dump(mode="json", by_alias=True)
        reloaded = type(second.external_research).model_validate(dumped)
        self.assertEqual(reloaded.documents[0].id, second.external_research.documents[0].id)
        self.assertEqual(
            reloaded.documents[0].supported_categories,
            second.external_research.documents[0].supported_categories,
        )

    def test_broader_search_provider_absent_is_truthful_not_scanned(self) -> None:
        provider = provider_with(website_transport(), WebsiteAIClient())

        result = provider.collect(IdentifyState(), organisation())

        assert result.external_research is not None
        statuses = {
            category.category: category.status
            for category in result.external_research.categories
        }
        self.assertEqual(statuses["competitors"], "not-scanned")
        self.assertEqual(statuses["reviews-ratings"], "not-scanned")
        self.assertEqual(statuses["press-mentions"], "not-scanned")
        self.assertEqual(statuses["market-sector-trends"], "not-scanned")
        self.assertNotEqual(
            next(
                category.message
                for category in result.external_research.categories
                if category.category == "customer-groups"
            ),
            "No public search provider is configured.",
        )

    def test_successful_crawl_marks_only_retrieved_categories_done(self) -> None:
        transport = FakeTransport(
            {
                "https://example.com/robots.txt": response(
                    "https://example.com/robots.txt", 404, "text/plain", b""
                ),
                "https://example.com/": response(
                    "https://example.com/",
                    200,
                    "text/html",
                    html_page("Home", '<a href="/services">Services</a>'),
                ),
                "https://example.com/services": response(
                    "https://example.com/services",
                    200,
                    "text/html",
                    html_page("Services", "<p>Services.</p>"),
                ),
            }
        )

        result = provider_with(transport, None).collect(
            IdentifyState(), organisation()
        )

        assert result.external_research is not None
        statuses = {
            category.category: category.status
            for category in result.external_research.categories
        }
        self.assertEqual(statuses["website"], "done")
        self.assertEqual(statuses["products-services"], "done")
        self.assertEqual(statuses["sustainability-impact"], "not-scanned")
        self.assertEqual(statuses["customer-groups"], "not-scanned")

    def _assert_canonical_www_redirect(
        self,
        *,
        start_url: str,
        canonical_url: str,
    ) -> None:
        start_robots = f"{start_url.rstrip('/')}/robots.txt"
        canonical_robots = f"{canonical_url.rstrip('/')}/robots.txt"
        service_url = f"{canonical_url.rstrip('/')}/services"
        transport = FakeTransport(
            {
                start_robots: response(start_robots, 404, "text/plain", b""),
                start_url: response(
                    start_url,
                    301,
                    "text/html",
                    b"",
                    {"location": canonical_url},
                ),
                canonical_robots: response(
                    canonical_robots, 404, "text/plain", b""
                ),
                canonical_url: response(
                    canonical_url,
                    200,
                    "text/html",
                    html_page("Home", '<a href="/services">Services</a>'),
                ),
                service_url: response(
                    service_url,
                    200,
                    "text/html",
                    html_page("Services", "<p>Services.</p>"),
                ),
            }
        )

        result = provider_with(transport, None).collect(
            IdentifyState(), organisation(start_url)
        )

        assert result.external_research is not None
        self.assertIn(service_url, transport.requests)
        self.assertEqual(
            [
                document.category
                for document in result.external_research.documents
                if document.status == "retrieved"
            ],
            ["website", "products-services"],
        )


def website_transport() -> FakeTransport:
    return FakeTransport(
        {
            "https://example.com/robots.txt": response(
                "https://example.com/robots.txt", 404, "text/plain", b""
            ),
            "https://example.com/": response(
                "https://example.com/",
                200,
                "text/html",
                html_page("Homepage", "<p>We support clinics.</p>"),
            ),
        }
    )


RouteSpec = (
    tuple[int, str, str]
    | tuple[int, str, str, dict[str, str]]
)


def replacement_transport(
    links: str,
    route_specs: dict[str, RouteSpec],
    *,
    robots: bytes | None = None,
) -> FakeTransport:
    routes: dict[str, FetchResponse | Exception] = {
        "https://example.com/robots.txt": response(
            "https://example.com/robots.txt",
            200 if robots is not None else 404,
            "text/plain",
            robots or b"",
        ),
        "https://example.com/": response(
            "https://example.com/",
            200,
            "text/html",
            html_page("Home", links),
        ),
    }
    for path, spec in route_specs.items():
        status, title, body = spec[:3]
        headers = spec[3] if len(spec) == 4 else None
        url = f"https://example.com{path}"
        routes[url] = response(
            url,
            status,
            "text/html",
            html_page(title, f"<p>{body}</p>") if body else b"",
            headers,
        )
    return FakeTransport(routes)


def document_urls(documents: list[ExternalResearchDocument]) -> list[str]:
    return [str(document.url) for document in documents]


def retrieved_document_count(result: ResearchCollectionResult) -> int:
    assert result.external_research is not None
    return sum(
        document.status == "retrieved"
        for document in result.external_research.documents
    )


def category_status(
    result: ResearchCollectionResult,
    category_name: str,
) -> str:
    assert result.external_research is not None
    return next(
        category.status
        for category in result.external_research.categories
        if category.category == category_name
    )


def provider_with(
    transport: FakeTransport,
    ai_client: object | None,
    *,
    max_pages: int = 4,
    max_content_bytes: int = 5000,
) -> IdentifyEvidenceResearchProvider:
    limits = ResearchLimits(
        max_pages=max_pages,
        timeout_seconds=1,
        max_content_bytes=max_content_bytes,
        max_text_chars=2000,
        redirect_limit=2,
    )
    return IdentifyEvidenceResearchProvider(
        ai_client=ai_client,  # type: ignore[arg-type]
        transport=transport,
        limits=limits,
        enabled=True,
    )


def fake_resolve_hostname(hostname: str) -> list[ipaddress._BaseAddress]:
    try:
        return [ipaddress.ip_address(hostname)]
    except ValueError:
        return [ipaddress.ip_address(address) for address in PUBLIC_IPS]


ResearchFetchError = research.ResearchFetchError


if __name__ == "__main__":
    unittest.main()
