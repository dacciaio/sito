"""CLI entry point for the daccia content platform."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def main() -> None:
    """daccia.io content generation platform."""


# ---------------------------------------------------------------------------
# generate — article generation
# ---------------------------------------------------------------------------


@main.command()
@click.option("--topic", "-t", required=True, help="Article topic")
@click.option(
    "--type",
    "-T",
    "content_type",
    type=click.Choice(["medium", "blog"]),
    default="medium",
    help="Content type",
)
@click.option("--words", "-w", default=1500, help="Target word count")
@click.option("--points", "-p", multiple=True, help="Key points to cover (repeatable)")
@click.option("--ref", "-r", multiple=True, help="References to incorporate (repeatable)")
def generate(
    topic: str,
    content_type: str,
    words: int,
    points: tuple[str, ...],
    ref: tuple[str, ...],
) -> None:
    """Generate an article or blog post."""
    from daccia.config import get_settings
    from daccia.content.article import ArticleGenerator
    from daccia.content.base import ContentRequest, ContentType
    from daccia.llm.client import ClaudeClient
    from daccia.style.profile import StyleProfile

    settings = get_settings()
    _check_api_key(settings)
    client = ClaudeClient(settings)
    profile = StyleProfile.load(settings.style_profiles_dir)
    generator = ArticleGenerator(client, style_profile=profile)

    ct = ContentType.MEDIUM_ARTICLE if content_type == "medium" else ContentType.BLOG_POST

    request = ContentRequest(
        topic=topic,
        content_type=ct,
        target_word_count=words,
        key_points=list(points) if points else None,
        references=list(ref) if ref else None,
    )

    with console.status("[bold green]Generating article..."):
        content = generator.generate(request)

    console.print()
    console.print(
        Panel(
            f"[bold]{content.title}",
            subtitle=f"{content.metadata['word_count']} words | "
            f"{content.metadata['generation_time_seconds']}s",
        )
    )
    console.print(Markdown(content.body))
    console.print(
        f"\n[dim]Tokens: {content.metadata.get('token_usage', {})}[/dim]"
    )

    if Prompt.ask("\nSave draft?", choices=["y", "n"], default="y") == "y":
        _save_draft(content, settings)


# ---------------------------------------------------------------------------
# batch — generate articles from a topic list
# ---------------------------------------------------------------------------


@main.command()
@click.option("--file", "-f", "file_path", type=click.Path(exists=True), required=True,
              help="Text file with one topic per line")
@click.option(
    "--type",
    "-T",
    "content_type",
    type=click.Choice(["medium", "blog"]),
    default="medium",
    help="Content type for all articles",
)
@click.option("--words", "-w", default=1500, help="Target word count")
@click.option("--dry-run", is_flag=True, help="List topics without generating")
def batch(file_path: str, content_type: str, words: int, dry_run: bool) -> None:
    """Generate articles for every topic in a file (one topic per line).

    Topics file format: one topic per line. Blank lines and lines
    starting with # are skipped.

    All drafts are auto-saved to platform/data/drafts/.
    """
    from daccia.config import get_settings
    from daccia.content.article import ArticleGenerator
    from daccia.content.base import ContentRequest, ContentType
    from daccia.llm.client import ClaudeClient
    from daccia.style.profile import StyleProfile

    # Parse topics (strip quotes, blank lines, and # comments)
    raw_lines = Path(file_path).read_text().splitlines()
    topics = [
        line.strip().strip('"').strip("'")
        for line in raw_lines
        if line.strip() and not line.strip().startswith("#")
    ]

    if not topics:
        console.print("[yellow]No topics found in file.[/yellow]")
        return

    console.print(f"\n[bold]Batch: {len(topics)} topics from {file_path}[/bold]\n")
    for i, topic in enumerate(topics, 1):
        console.print(f"  {i}. {topic}")
    console.print()

    if dry_run:
        console.print("[dim]Dry run -- no articles generated.[/dim]")
        return

    settings = get_settings()
    _check_api_key(settings)
    client = ClaudeClient(settings)
    profile = StyleProfile.load(settings.style_profiles_dir)
    generator = ArticleGenerator(client, style_profile=profile)

    ct = ContentType.MEDIUM_ARTICLE if content_type == "medium" else ContentType.BLOG_POST

    succeeded = 0
    failed: list[str] = []

    for i, topic in enumerate(topics, 1):
        console.rule(f"[bold] {i}/{len(topics)} [/bold]")
        console.print(f"[bold]{topic}[/bold]\n")

        try:
            request = ContentRequest(
                topic=topic,
                content_type=ct,
                target_word_count=words,
            )
            with console.status("[green]Generating..."):
                content = generator.generate(request)

            console.print(
                Panel(
                    f"[bold]{content.title}",
                    subtitle=f"{content.metadata['word_count']} words | "
                    f"{content.metadata['generation_time_seconds']}s",
                )
            )
            _save_draft(content, settings)
            succeeded += 1

        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            failed.append(topic)

        console.print()

    # Summary
    console.rule("[bold] Batch complete [/bold]")
    console.print(f"  [green]Succeeded:[/green] {succeeded}/{len(topics)}")
    if failed:
        console.print(f"  [red]Failed:[/red] {len(failed)}")
        for t in failed:
            console.print(f"    - {t}")
    console.print(f"\n  Drafts saved to: {settings.drafts_dir}")
    console.print(f"  Token usage: {client.usage_summary}\n")


# ---------------------------------------------------------------------------
# stream — three content streams
# ---------------------------------------------------------------------------


@main.command()
@click.option(
    "--stream",
    "-s",
    "stream_name",
    type=click.Choice(["patient", "nurse", "doctor"]),
    required=True,
    help="Content stream",
)
@click.option("--topic", "-t", required=True, help="Topic")
@click.option("--words", "-w", default=1000, help="Target word count")
def stream(stream_name: str, topic: str, words: int) -> None:
    """Generate content for a specific stream (patient/nurse/doctor)."""
    from daccia.config import get_settings
    from daccia.content.base import ContentRequest, ContentType
    from daccia.content.streams import StreamGenerator
    from daccia.llm.client import ClaudeClient
    from daccia.style.profile import StyleProfile

    stream_map = {
        "patient": ContentType.PATIENT_CONVERSATION,
        "nurse": ContentType.ASK_A_NURSE,
        "doctor": ContentType.ASK_AN_ED_DOCTOR,
    }

    settings = get_settings()
    _check_api_key(settings)
    client = ClaudeClient(settings)
    profile = StyleProfile.load(settings.style_profiles_dir)
    generator = StreamGenerator(client, style_profile=profile)

    request = ContentRequest(
        topic=topic,
        content_type=stream_map[stream_name],
        target_word_count=words,
    )

    with console.status(f"[bold green]Generating {stream_name} content..."):
        content = generator.generate(request)

    console.print()
    console.print(Panel(f"[bold]{content.title}", subtitle=stream_name))
    console.print(Markdown(content.body))

    if Prompt.ask("\nSave draft?", choices=["y", "n"], default="y") == "y":
        _save_draft(content, settings)


# ---------------------------------------------------------------------------
# refine — iterative content refinement
# ---------------------------------------------------------------------------


@main.command()
@click.option("--file", "-f", "file_path", type=click.Path(exists=True), required=True,
              help="Path to the draft to refine")
@click.option("--no-socratic", is_flag=True, help="Skip clarifying questions")
def refine(file_path: str, no_socratic: bool) -> None:
    """Interactively refine a draft with Socratic feedback."""
    from daccia.config import get_settings
    from daccia.content.base import ContentType, GeneratedContent
    from daccia.content.refiner import ContentRefiner
    from daccia.llm.client import ClaudeClient

    settings = get_settings()
    _check_api_key(settings)
    client = ClaudeClient(settings)
    refiner = ContentRefiner(client)

    text = Path(file_path).read_text()
    lines = text.strip().split("\n")
    title = lines[0].lstrip("# ").strip() if lines else "Untitled"
    body = "\n".join(lines[1:]).strip()

    content = GeneratedContent(
        title=title,
        body=body,
        content_type=ContentType.MEDIUM_ARTICLE,
    )

    console.print(f"[bold]Loaded:[/bold] {title}")
    with console.status("[green]Starting refinement session..."):
        initial = refiner.start_refinement(content)
    console.print(Markdown(initial))

    while True:
        feedback = Prompt.ask("\n[bold]Your feedback[/bold] (or 'done' to finish)")
        if feedback.lower() in ("done", "quit", "exit", "q"):
            break

        with console.status("[green]Revising..."):
            revised = refiner.refine(feedback, socratic=not no_socratic)
        console.print(Markdown(revised))
        console.print(f"[dim]Revision #{refiner.revision_count}[/dim]")


# ---------------------------------------------------------------------------
# learn — style learning from edits
# ---------------------------------------------------------------------------


@main.command()
@click.option("--original", "-o", type=click.Path(exists=True), required=True,
              help="Path to the original generated draft")
@click.option("--edited", "-e", type=click.Path(exists=True), required=True,
              help="Path to your edited version")
def learn(original: str, edited: str) -> None:
    """Analyze an edited draft to learn your writing style."""
    from daccia.config import get_settings
    from daccia.llm.client import ClaudeClient
    from daccia.style.analyzer import StyleAnalyzer
    from daccia.style.profile import StyleProfile

    settings = get_settings()
    _check_api_key(settings)
    client = ClaudeClient(settings)
    analyzer = StyleAnalyzer(client)

    profile = StyleProfile.load(settings.style_profiles_dir)
    original_text = Path(original).read_text()
    edited_text = Path(edited).read_text()

    with console.status("[bold green]Analyzing your edits..."):
        updated_profile = analyzer.analyze_edit(original_text, edited_text, profile)

    updated_profile.save(settings.style_profiles_dir)

    console.print("[bold green]Style profile updated!")
    console.print(f"Total edits analyzed: {updated_profile.edit_count}\n")
    for dim in updated_profile.dimensions.values():
        if dim.confidence > 0.1:
            bar = "+" * int(dim.confidence * 10)
            console.print(f"  {dim.name}: {dim.value}")
            console.print(f"    Confidence: [green]{bar}[/green] ({dim.confidence:.0%})")


# ---------------------------------------------------------------------------
# research — fetch and analyze articles, propose topics
# ---------------------------------------------------------------------------


@main.command()
@click.option("--max-articles", "-n", default=20, help="Max articles to fetch per feed")
def research(max_articles: int) -> None:
    """Fetch and analyze latest AI+healthcare articles, propose topics."""
    from daccia.config import get_settings
    from daccia.llm.client import ClaudeClient
    from daccia.research.analyzer import ArticleAnalyzer
    from daccia.research.fetcher import ArticleFetcher
    from daccia.research.proposer import TopicProposer

    settings = get_settings()
    _check_api_key(settings)
    client = ClaudeClient(settings)
    fetcher = ArticleFetcher(settings.research_cache_dir)
    analyzer = ArticleAnalyzer(client)
    proposer = TopicProposer(client)

    # Fetch articles from configured feeds
    all_articles = []
    for feed_url in settings.research_feeds:
        with console.status(f"[green]Fetching {feed_url}..."):
            try:
                articles = fetcher.fetch_feed(feed_url, max_articles=max_articles)
                all_articles.extend(articles)
                console.print(f"  [dim]{len(articles)} articles from {feed_url}[/dim]")
            except Exception as e:
                console.print(f"  [red]Error fetching {feed_url}: {e}[/red]")

    if not all_articles:
        console.print("[yellow]No articles fetched. Check your feed URLs.[/yellow]")
        fetcher.close()
        return

    console.print(f"\nFetched {len(all_articles)} articles total\n")

    # Analyze each article for relevance
    analyses: list[dict] = []
    for article in all_articles:
        with console.status(f"[dim]Analyzing: {article.title[:60]}...[/dim]"):
            result = analyzer.analyze(article)
            analyses.append(result)

    # Filter to relevant articles (score >= 5)
    relevant = [a for a in analyses if a.get("relevance_score", 0) >= 5]
    console.print(f"Found {len(relevant)} relevant articles (score >= 5)\n")

    # Show top articles
    if relevant:
        table = Table(title="Top Research Findings")
        table.add_column("Score", width=5, justify="center")
        table.add_column("Title", width=50)
        table.add_column("Angles", width=40)
        for a in sorted(relevant, key=lambda x: x.get("relevance_score", 0), reverse=True)[:10]:
            table.add_row(
                str(a.get("relevance_score", 0)),
                a.get("title", "")[:50],
                ", ".join(a.get("content_angles", []))[:40],
            )
        console.print(table)

        # Propose new topics
        with console.status("[bold green]Generating topic proposals..."):
            proposals = proposer.propose(relevant)

        if proposals:
            console.print("\n[bold]Proposed Topics:[/bold]\n")
            for i, p in enumerate(proposals, 1):
                console.print(f"  {i}. [bold]{p.get('title', 'Untitled')}[/bold]")
                console.print(
                    f"     Type: {p.get('content_type', 'article')} | "
                    f"Urgency: {p.get('urgency', 'medium')}"
                )
                console.print(f"     Angle: {p.get('angle', '')}")
                console.print()
    else:
        console.print("[yellow]No highly relevant articles found in this batch.[/yellow]")

    fetcher.close()


# ---------------------------------------------------------------------------
# publish — publish to Medium + update blog on daccia.io
# ---------------------------------------------------------------------------


@main.command()
def publish() -> None:
    """Publish drafts to Medium and update the daccia.io blog section."""
    import re

    from sqlmodel import select

    from daccia.config import get_settings
    from daccia.llm.client import ClaudeClient
    from daccia.llm.prompts import render
    from daccia.publishing.medium import MediumClient
    from daccia.storage.database import get_session
    from daccia.storage.models import ContentRecord

    settings = get_settings()
    _check_api_key(settings)

    # 1. Show available drafts
    with get_session(settings.db_path) as session:
        drafts = session.exec(
            select(ContentRecord).where(ContentRecord.status == "draft")
        ).all()

    if not drafts:
        console.print("[yellow]No drafts to publish. Generate some articles first.[/yellow]")
        return

    table = Table(title="Unpublished Drafts")
    table.add_column("ID", width=4, justify="right")
    table.add_column("Title", width=60)
    table.add_column("Words", width=6, justify="right")
    table.add_column("Created", width=12)
    for d in drafts:
        table.add_row(
            str(d.id),
            d.title[:60],
            str(d.word_count),
            d.created_at.strftime("%Y-%m-%d"),
        )
    console.print(table)

    # 2. Select articles
    selection = Prompt.ask(
        "\n[bold]Select articles to publish[/bold] (IDs comma-separated, or 'all')"
    )
    if selection.strip().lower() == "all":
        selected_ids = [d.id for d in drafts]
    else:
        try:
            selected_ids = [int(x.strip()) for x in selection.split(",") if x.strip()]
        except ValueError:
            console.print("[red]Invalid selection. Use numbers separated by commas.[/red]")
            return

    selected = [d for d in drafts if d.id in selected_ids]
    if not selected:
        console.print("[yellow]No matching drafts found.[/yellow]")
        return

    # 3. Set up Medium client (if token available)
    medium_client: MediumClient | None = None
    if settings.medium_token:
        try:
            medium_client = MediumClient(settings.medium_token)
            medium_client.get_user_id()
            console.print("[green]Medium API connected.[/green]\n")
        except Exception as e:
            console.print(f"[yellow]Medium API failed: {e}[/yellow]")
            console.print("[dim]Will prompt for URLs manually.[/dim]\n")
            medium_client = None
    else:
        console.print("[dim]No MEDIUM_TOKEN set. Will prompt for URLs manually.[/dim]\n")

    # 4. Set up Claude for teaser generation
    client = ClaudeClient(settings)
    teaser_system = render("teaser_prompt.j2")

    # 5. Process each selected article
    published_count = 0
    with get_session(settings.db_path) as session:
        for article in selected:
            console.rule(f"[bold]{article.title[:60]}[/bold]")

            # Publish to Medium
            medium_url = ""
            if medium_client:
                try:
                    with console.status("[green]Publishing to Medium..."):
                        post = medium_client.publish(
                            title=article.title,
                            content=article.body,
                            publish_status=settings.medium_publish_status,
                            tags=["AI", "healthcare", "XAI"],
                        )
                    medium_url = post.url
                    console.print(
                        f"  [green]Published to Medium ({post.publish_status}):[/green] {post.url}"
                    )
                except Exception as e:
                    console.print(f"  [yellow]Medium publish failed: {e}[/yellow]")

            if not medium_url:
                medium_url = Prompt.ask("  Medium URL (paste or leave blank)")

            # Generate teaser
            with console.status("[green]Generating teaser..."):
                teaser = client.generate(
                    system=teaser_system,
                    messages=[{
                        "role": "user",
                        "content": f"Article title: {article.title}\n\n"
                        f"Article body (first 1000 chars):\n{article.body[:1000]}",
                    }],
                    temperature=0.7,
                    max_tokens=150,
                )
            teaser = teaser.strip().strip('"')
            console.print(f"  [dim]Teaser: {teaser}[/dim]\n")

            # Update database record
            db_record = session.get(ContentRecord, article.id)
            if db_record:
                db_record.status = "published"
                db_record.medium_url = medium_url
                db_record.teaser = teaser
                db_record.updated_at = datetime.now()
                session.add(db_record)
                published_count += 1

        session.commit()

    if medium_client:
        medium_client.close()

    # 6. Regenerate blog section in index.html
    _regenerate_blog(settings)

    console.print()
    console.rule("[bold] Publish complete [/bold]")
    console.print(f"  [green]Published:[/green] {published_count} articles")
    console.print(f"  [green]Blog updated:[/green] {settings.site_root / 'index.html'}\n")


def _regenerate_blog(settings: object) -> None:
    """Re-render the blog section in index.html from published articles."""
    import re

    from jinja2 import Environment, FileSystemLoader
    from sqlmodel import select

    from daccia.storage.database import get_session
    from daccia.storage.models import ContentRecord

    index_path = settings.site_root / "index.html"
    if not index_path.exists():
        console.print("[yellow]index.html not found, skipping blog update.[/yellow]")
        return

    # Fetch all published articles with medium URLs
    with get_session(settings.db_path) as session:
        published = session.exec(
            select(ContentRecord)
            .where(ContentRecord.status == "published")
            .where(ContentRecord.medium_url != "")
        ).all()
        # Detach from session for use after close
        articles = [
            {"title": a.title, "medium_url": a.medium_url, "teaser": a.teaser}
            for a in published
        ]

    # Render the blog section HTML
    template_dir = Path(__file__).resolve().parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template("blog_section.html.j2")
    blog_html = template.render(articles=articles)

    # Inject into index.html between markers
    html = index_path.read_text()
    pattern = r"<!-- BLOG_START -->.*?<!-- BLOG_END -->"
    if re.search(pattern, html, re.DOTALL):
        html = re.sub(pattern, blog_html, html, flags=re.DOTALL)
    else:
        console.print("[yellow]Blog markers not found in index.html. Skipping.[/yellow]")
        return

    index_path.write_text(html)
    console.print(f"  [green]Blog section updated with {len(articles)} articles.[/green]")


# ---------------------------------------------------------------------------
# style — display current style profile
# ---------------------------------------------------------------------------


@main.command()
def style() -> None:
    """Show your current learned style profile."""
    from daccia.config import get_settings
    from daccia.style.profile import StyleProfile

    settings = get_settings()
    profile = StyleProfile.load(settings.style_profiles_dir)

    console.print(f"\n[bold]Style Profile[/bold] (based on {profile.edit_count} edits)\n")

    if profile.edit_count == 0:
        console.print(
            "[dim]No edits analyzed yet. Use 'daccia learn' to teach the system "
            "your writing style.[/dim]"
        )
        console.print()

    for dim in profile.dimensions.values():
        confidence_bar = "[green]" + ("+" * int(dim.confidence * 10)) + "[/green]"
        confidence_empty = "[dim]" + ("-" * (10 - int(dim.confidence * 10))) + "[/dim]"
        console.print(f"  [bold]{dim.name}[/bold]: {dim.value}")
        console.print(f"    Confidence: {confidence_bar}{confidence_empty} ({dim.confidence:.0%})")
        if dim.examples:
            console.print(f'    Latest example: [italic]"{dim.examples[-1]}"[/italic]')
        console.print()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_api_key(settings: object) -> None:
    """Exit with a helpful message if the API key is not set."""
    if not getattr(settings, "anthropic_api_key", ""):
        console.print(
            "[bold red]Error:[/bold red] ANTHROPIC_API_KEY not set.\n"
            "Edit platform/.env and add your key."
        )
        raise SystemExit(1)


def _save_draft(content: object, settings: object) -> None:
    """Save generated content to drafts directory and database."""
    from daccia.storage.database import get_session
    from daccia.storage.models import ContentRecord

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = content.title.lower().replace(" ", "_")[:40]
    filename = f"{timestamp}_{slug}.md"
    path = settings.drafts_dir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {content.title}\n\n{content.body}")
    console.print(f"[green]Saved to {path}[/green]")

    # Persist in database
    with get_session(settings.db_path) as session:
        record = ContentRecord(
            title=content.title,
            body=content.body,
            content_type=content.content_type.value,
            topic=content.title,
            word_count=content.metadata.get("word_count", 0),
            metadata_json=json.dumps(content.metadata, default=str),
        )
        session.add(record)
        session.commit()
