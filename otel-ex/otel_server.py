"""
bookshop server — three tools, instrumented automatically by the MCP SDK.

Spans go out over OTLP to a collector/Jaeger

makes calls with lookups against
an in-file JSON catalogue, so each tool call does meaningful work and returns
data that actually depends on its arguments — useful for producing
distinguishable, inspectable spans/attributes per call.
"""

import asyncio
import json

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from mcp.server import MCPServer

# --- OTel setup (server side) -------------------------------------------
provider = TracerProvider(resource=Resource.create({"service.name": "mcp-server-bookshop"}))
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer("bookshop.server")

mcp = MCPServer("Bookshop")

# --- In-file "database" ---------------------------------------------------
# A small embedded catalogue so tools do real lookups instead of calling out
# to a placeholder REST API. Keyed by book_id for O(1) lookups; search does
# a simple case-insensitive substring scan over title/author.

CATALOGUE = {
    "python-crash-course": {
        "title": "Python Crash Course",
        "author": "Eric Matthes",
        "isbn": "978-1-59327-928-8",
        "tags": ["python", "beginner"],
        "related": ["fluent-python", "automate-boring-stuff"],
    },
    "fluent-python": {
        "title": "Fluent Python",
        "author": "Luciano Ramalho",
        "isbn": "978-1-4920-5632-4",
        "tags": ["python", "intermediate", "advanced"],
        "related": ["python-crash-course", "effective-python"],
    },
    "automate-boring-stuff": {
        "title": "Automate the Boring Stuff with Python",
        "author": "Al Sweigart",
        "isbn": "978-1-59327-599-0",
        "tags": ["python", "beginner", "scripting"],
        "related": ["python-crash-course"],
    },
    "effective-python": {
        "title": "Effective Python",
        "author": "Brett Slatkin",
        "isbn": "978-0-13-485398-1",
        "tags": ["python", "intermediate", "best-practices"],
        "related": ["fluent-python"],
    },
    "clean-code": {
        "title": "Clean Code",
        "author": "Robert C. Martin",
        "isbn": "978-0-13-235088-4",
        "tags": ["software-engineering", "best-practices"],
        "related": ["clean-architecture", "pragmatic-programmer"],
    },
    "clean-architecture": {
        "title": "Clean Architecture",
        "author": "Robert C. Martin",
        "isbn": "978-0-13-449416-6",
        "tags": ["software-engineering", "architecture"],
        "related": ["clean-code", "domain-driven-design"],
    },
    "pragmatic-programmer": {
        "title": "The Pragmatic Programmer",
        "author": "David Thomas, Andrew Hunt",
        "isbn": "978-0-13-595705-9",
        "tags": ["software-engineering", "best-practices", "career"],
        "related": ["clean-code"],
    },
    "design-patterns-gof": {
        "title": "Design Patterns: Elements of Reusable Object-Oriented Software",
        "author": "Erich Gamma, Richard Helm, Ralph Johnson, John Vlissides",
        "isbn": "978-0-201-63361-0",
        "tags": ["design-patterns", "oop", "advanced"],
        "related": ["head-first-design-patterns"],
    },
    "head-first-design-patterns": {
        "title": "Head First Design Patterns",
        "author": "Eric Freeman, Elisabeth Robson",
        "isbn": "978-1-4919-7899-6",
        "tags": ["design-patterns", "oop", "beginner"],
        "related": ["design-patterns-gof"],
    },
    "domain-driven-design": {
        "title": "Domain-Driven Design",
        "author": "Eric Evans",
        "isbn": "978-0-321-12521-7",
        "tags": ["architecture", "advanced"],
        "related": ["clean-architecture"],
    },
    "refactoring": {
        "title": "Refactoring: Improving the Design of Existing Code",
        "author": "Martin Fowler",
        "isbn": "978-0-13-475759-9",
        "tags": ["software-engineering", "best-practices"],
        "related": ["clean-code", "working-effectively-legacy-code"],
    },
    "working-effectively-legacy-code": {
        "title": "Working Effectively with Legacy Code",
        "author": "Michael Feathers",
        "isbn": "978-0-13-117705-5",
        "tags": ["software-engineering", "testing", "advanced"],
        "related": ["refactoring"],
    },
    "javascript-good-parts": {
        "title": "JavaScript: The Good Parts",
        "author": "Douglas Crockford",
        "isbn": "978-0-596-51774-8",
        "tags": ["javascript", "intermediate"],
        "related": ["eloquent-javascript", "youre-missing-js"],
    },
    "eloquent-javascript": {
        "title": "Eloquent JavaScript",
        "author": "Marijn Haverbeke",
        "isbn": "978-1-59327-950-9",
        "tags": ["javascript", "beginner"],
        "related": ["javascript-good-parts"],
    },
    "youre-missing-js": {
        "title": "You Don't Know JS Yet",
        "author": "Kyle Simpson",
        "isbn": "978-1-4919-2405-4",
        "tags": ["javascript", "intermediate", "advanced"],
        "related": ["javascript-good-parts", "eloquent-javascript"],
    },
    "cracking-coding-interview": {
        "title": "Cracking the Coding Interview",
        "author": "Gayle Laakmann McDowell",
        "isbn": "978-0-9847828-5-7",
        "tags": ["algorithms", "interviews", "career"],
        "related": ["intro-to-algorithms"],
    },
    "intro-to-algorithms": {
        "title": "Introduction to Algorithms",
        "author": "Thomas H. Cormen, Charles E. Leiserson, Ronald L. Rivest, Clifford Stein",
        "isbn": "978-0-262-04630-5",
        "tags": ["algorithms", "computer-science", "advanced"],
        "related": ["cracking-coding-interview", "algorithm-design-manual"],
    },
    "algorithm-design-manual": {
        "title": "The Algorithm Design Manual",
        "author": "Steven S. Skiena",
        "isbn": "978-3-030-54255-9",
        "tags": ["algorithms", "computer-science"],
        "related": ["intro-to-algorithms"],
    },
    "pragmatic-unit-testing": {
        "title": "Pragmatic Unit Testing in Java 8 with JUnit",
        "author": "Jeff Langr, Andy Hunt, Dave Thomas",
        "isbn": "978-1-941222-59-3",
        "tags": ["java", "testing", "best-practices"],
        "related": ["effective-java"],
    },
    "effective-java": {
        "title": "Effective Java",
        "author": "Joshua Bloch",
        "isbn": "978-0-13-468599-1",
        "tags": ["java", "intermediate", "best-practices"],
        "related": ["pragmatic-unit-testing", "java-concurrency-in-practice"],
    },
    "java-concurrency-in-practice": {
        "title": "Java Concurrency in Practice",
        "author": "Brian Goetz",
        "isbn": "978-0-321-34960-6",
        "tags": ["java", "concurrency", "advanced"],
        "related": ["effective-java"],
    },
}

@mcp.tool()
async def search_books(query: str) -> str:
    """Search the catalogue by title or author (case-insensitive substring match)."""
    with tracer.start_as_current_span("catalogue.search") as span:
        span.set_attribute("bookshop.query", query)

        needle = query.lower()
        matches = [
            entry
            for entry in CATALOGUE.values()
            if needle in entry["title"].lower() or needle in entry["author"].lower()
        ]
        span.set_attribute("bookshop.match_count", len(matches))

        if not matches:
            return f"No books found matching {query!r}."

        lines = [f"- {b['title']} by {b['author']} (ISBN {b['isbn']})" for b in matches]
        return f"Found {len(matches)} book(s) matching {query!r}:\n" + "\n".join(lines)


@mcp.tool()
async def get_recommendations(book_id: str) -> str:
    """Recommend books related to a given book id."""
    with tracer.start_as_current_span("catalogue.recommend") as span:
        span.set_attribute("bookshop.book_id", book_id)

        book = CATALOGUE.get(book_id)
        if book is None:
            span.set_attribute("bookshop.found", False)
            return f"No catalog entry for book id {book_id!r}."

        span.set_attribute("bookshop.found", True)
        related_ids = book.get("related", [])
        span.set_attribute("bookshop.related_count", len(related_ids))

        if not related_ids:
            return f"No recommendations available for {book['title']!r}."

        titles = [CATALOGUE[rid]["title"] for rid in related_ids if rid in CATALOGUE]
        return f"Because you liked {book['title']!r}: " + ", ".join(titles)


@mcp.tool()
async def broken_lookup(isbn: str) -> str:
    """Look up a book by ISBN — raises if not found, for observing an error span."""
    with tracer.start_as_current_span("catalogue.isbn_lookup") as span:
        span.set_attribute("bookshop.isbn", isbn)
        for entry in CATALOGUE.values():
            if entry["isbn"] == isbn:
                return f"{entry['title']} by {entry['author']}"
        raise ValueError(f"no catalog entry for ISBN {isbn}")


if __name__ == "__main__":
    mcp.run()