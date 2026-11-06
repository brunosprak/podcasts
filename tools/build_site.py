#!/usr/bin/env python3
"""Build the static podcast catalog and RSS feeds using only the standard library."""

from __future__ import annotations

import html
import json
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data.json"


def absolute_url(base_url: str, path: str) -> str:
    encoded = "/".join(quote(part) for part in path.split("/"))
    return f"{base_url.rstrip('/')}/{encoded}"


def duration(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def page_shell(title: str, description: str, body: str, base_path: str = "") -> str:
    prefix = f"{base_path}/" if base_path else ""
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{html.escape(description, quote=True)}">
  <meta name="theme-color" content="#17140f">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="{prefix}assets/style.css">
</head>
<body>
  <a class="skip-link" href="#conteudo">Ir para o conteúdo</a>
  {body}
  <footer><span>Arquivo pessoal de podcasts</span><span>Feito para tocar em qualquer lugar.</span></footer>
</body>
</html>
"""


def build_home(data: dict) -> None:
    site = data["site"]
    cards = []
    for podcast in data["podcasts"]:
        latest = podcast["episodes"][0] if podcast["episodes"] else None
        count = len(podcast["episodes"])
        label = "episódio" if count == 1 else "episódios"
        latest_copy = (
            f"<p class='latest'>Mais recente: <strong>{html.escape(latest['title'])}</strong></p>"
            if latest else "<p class='latest'>Episódios aguardando sincronização.</p>"
        )
        cards.append(f"""
        <article class="show-card">
          <a class="cover-link" href="podcasts/{podcast['slug']}/">
            <img src="{html.escape(podcast['image'])}" alt="Capa de {html.escape(podcast['title'])}">
          </a>
          <div class="show-copy">
            <p class="eyebrow">{count} {label}</p>
            <h2><a href="podcasts/{podcast['slug']}/">{html.escape(podcast['title'])}</a></h2>
            <p>{html.escape(podcast['description'])}</p>
            {latest_copy}
            <div class="actions">
              <a class="button primary" href="podcasts/{podcast['slug']}/">Ouvir agora</a>
              <a class="button" href="podcasts/{podcast['slug']}/feed.xml">Assinar RSS</a>
            </div>
          </div>
        </article>""")

    body = f"""
  <header class="masthead">
    <a class="brand" href="./" aria-label="Podcasts — início"><span class="signal">◉</span> PODCASTS</a>
    <p class="edition">coleção independente · {datetime.now().year}</p>
  </header>
  <main id="conteudo">
    <section class="hero">
      <p class="kicker">Uma biblioteca para os seus ouvidos</p>
      <h1>Ideias que cabem<br><em>no seu caminho.</em></h1>
      <p class="intro">{html.escape(site['description'])} Ouça no navegador ou leve o feed para o aplicativo de sua preferência.</p>
    </section>
    <section class="catalog" aria-labelledby="catalog-title">
      <div class="section-heading"><span>01</span><h2 id="catalog-title">Programas</h2></div>
      {''.join(cards)}
    </section>
  </main>"""
    (ROOT / "index.html").write_text(
        page_shell(site["title"], site["description"], body), encoding="utf-8"
    )


def build_podcast_page(data: dict, podcast: dict) -> None:
    episodes = []
    for index, episode in enumerate(podcast["episodes"], start=1):
        date = datetime.fromisoformat(episode["published"].replace("Z", "+00:00"))
        episodes.append(f"""
        <article class="episode">
          <div class="episode-number">{index:02d}</div>
          <div class="episode-main">
            <p class="episode-meta"><time datetime="{episode['published']}">{date.strftime('%d.%m.%Y')}</time> · {duration(episode['duration_seconds'])}</p>
            <h2>{html.escape(episode['title'])}</h2>
            <p>{html.escape(episode['description'])}</p>
            <audio controls preload="metadata" src="media/{Path(episode['audio']).name}">
              Seu navegador não suporta áudio HTML5.
            </audio>
            <div class="episode-links">
              <a href="media/{Path(episode['audio']).name}" download>Baixar MP3</a>
              <a href="{html.escape(episode['source_url'], quote=True)}" target="_blank" rel="noopener">Ver original ↗</a>
            </div>
          </div>
        </article>""")

    page_url = absolute_url(data["site"]["base_url"], f"podcasts/{podcast['slug']}/")
    feed_url = absolute_url(data["site"]["base_url"], f"podcasts/{podcast['slug']}/feed.xml")
    body = f"""
  <header class="masthead">
    <a class="brand" href="../../"><span class="signal">◉</span> PODCASTS</a>
    <a class="back" href="../../">← Todos os programas</a>
  </header>
  <main id="conteudo">
    <section class="podcast-hero">
      <img src="media/{Path(podcast['image']).name}" alt="Capa de {html.escape(podcast['title'])}">
      <div>
        <p class="kicker">Feed não oficial · {html.escape(podcast['language'].upper())}</p>
        <h1>{html.escape(podcast['title'])}</h1>
        <p class="intro">{html.escape(podcast['description'])}</p>
        <div class="actions">
          <a class="button primary" href="feed.xml">Assinar via RSS</a>
          <button class="button" type="button" data-copy="{feed_url}">Copiar URL do feed</button>
          <a class="button" href="{html.escape(podcast['source_url'], quote=True)}" target="_blank" rel="noopener">Canal original ↗</a>
        </div>
        <p class="disclaimer">Conteúdo original de {html.escape(podcast['author'])}. Este feed independente preserva autoria e direciona para a publicação original.</p>
      </div>
    </section>
    <section class="episodes" aria-labelledby="episodes-title">
      <div class="section-heading"><span>02</span><h2 id="episodes-title">Episódios</h2></div>
      {''.join(episodes)}
    </section>
  </main>
  <script src="../../assets/site.js"></script>
  <script type="application/ld+json">{json.dumps({
      '@context': 'https://schema.org',
      '@type': 'PodcastSeries',
      'name': podcast['title'],
      'description': podcast['description'],
      'url': page_url,
      'webFeed': feed_url,
      'author': {'@type': 'Person', 'name': podcast['author']},
  }, ensure_ascii=False)}</script>"""
    output = ROOT / "podcasts" / podcast["slug"] / "index.html"
    output.write_text(
        page_shell(podcast["title"], podcast["description"], body, "../.."), encoding="utf-8"
    )


def build_feed(data: dict, podcast: dict) -> None:
    site = data["site"]
    base_url = site["base_url"]
    podcast_url = absolute_url(base_url, f"podcasts/{podcast['slug']}/")
    feed_url = absolute_url(base_url, f"podcasts/{podcast['slug']}/feed.xml")
    image_url = absolute_url(base_url, podcast["image"])

    ET.register_namespace("atom", "http://www.w3.org/2005/Atom")
    ET.register_namespace("itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = podcast["title"]
    ET.SubElement(channel, "link").text = podcast_url
    ET.SubElement(channel, "description").text = podcast["description"]
    ET.SubElement(channel, "language").text = podcast["language"]
    ET.SubElement(channel, "generator").text = "custom-podcast/tools/build_site.py"
    ET.SubElement(channel, "{http://www.w3.org/2005/Atom}link", {
        "href": feed_url, "rel": "self", "type": "application/rss+xml"
    })
    ET.SubElement(channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}author").text = podcast["author"]
    ET.SubElement(channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}summary").text = podcast["description"]
    ET.SubElement(channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}explicit").text = str(podcast["explicit"]).lower()
    ET.SubElement(channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}type").text = "episodic"
    ET.SubElement(channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}image", {"href": image_url})
    category = ET.SubElement(channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}category", {"text": podcast["category"]})
    ET.SubElement(category, "{http://www.itunes.com/dtds/podcast-1.0.dtd}category", {"text": podcast["subcategory"]})
    image = ET.SubElement(channel, "image")
    ET.SubElement(image, "url").text = image_url
    ET.SubElement(image, "title").text = podcast["title"]
    ET.SubElement(image, "link").text = podcast_url

    for episode in podcast["episodes"]:
        published = datetime.fromisoformat(episode["published"].replace("Z", "+00:00"))
        audio_path = ROOT / episode["audio"]
        audio_url = absolute_url(base_url, episode["audio"])
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = episode["title"]
        ET.SubElement(item, "link").text = episode["source_url"]
        ET.SubElement(item, "description").text = episode["description"]
        ET.SubElement(item, "pubDate").text = format_datetime(published)
        ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = episode["id"]
        ET.SubElement(item, "enclosure", {
            "url": audio_url, "length": str(audio_path.stat().st_size), "type": "audio/mpeg"
        })
        ET.SubElement(item, "{http://www.itunes.com/dtds/podcast-1.0.dtd}author").text = podcast["author"]
        ET.SubElement(item, "{http://www.itunes.com/dtds/podcast-1.0.dtd}summary").text = episode["description"]
        ET.SubElement(item, "{http://www.itunes.com/dtds/podcast-1.0.dtd}duration").text = str(episode["duration_seconds"])
        ET.SubElement(item, "{http://www.itunes.com/dtds/podcast-1.0.dtd}episodeType").text = "full"
        ET.SubElement(item, "{http://www.itunes.com/dtds/podcast-1.0.dtd}explicit").text = str(podcast["explicit"]).lower()
        ET.SubElement(item, "{http://www.itunes.com/dtds/podcast-1.0.dtd}image", {
            "href": absolute_url(base_url, episode["image"])
        })

    ET.indent(rss, space="  ")
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(rss, encoding="unicode") + "\n"
    (ROOT / "podcasts" / podcast["slug"] / "feed.xml").write_text(xml, encoding="utf-8")


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    build_home(data)
    for podcast in data["podcasts"]:
        build_podcast_page(data, podcast)
        build_feed(data, podcast)
    print(f"Built {len(data['podcasts'])} podcast(s).")


if __name__ == "__main__":
    main()
