from collections import OrderedDict, deque
import logging
import math
import os
import re
import shutil
import magic
from datetime import timezone, datetime
from pathlib import Path

from feedgen.feed import FeedGenerator
from jinja2 import Template

from .db import DB, User, Message
from . import __version__

_NL2BR = re.compile(r"\n\n+")

log = logging.getLogger("rich")


class Build:
    config = {}
    template = None
    db = None

    def __init__(self, config, db: DB, symlink):
        self.config = config
        self.db: DB = db
        self.symlink = symlink

        self.rss_template: Template or None = None

        # Map of all message IDs across all months and the slug of the page
        # in which they occur (paginated), used to link replies to their
        # parent messages that may be on arbitrary pages.
        self.page_ids = {}
        self.timeline = OrderedDict()

        self._day_counter_template: Template = Build._load_template_file("day-counter-template.js")
        if self.config["new_on_top"]:
            self._dayline_template: Template = Build._load_template_file("dayline-template-new-on-top.js")
            self._timeline_index_template: Template = Build._load_template_file("timeline-index-template-new-on-top.js")
            self._pagination_template: Template = Build._load_template_file("pagination-template-new-on-top.js")
        else:
            self._dayline_template: Template = Build._load_template_file("dayline-template.js")
            self._timeline_index_template: Template = Build._load_template_file("timeline-index-template.js")
            self._pagination_template: Template = Build._load_template_file("pagination-template.js")

    def build(self):
        # (Re)create the output directory.
        self._create_publish_dir()

        log.info("Start building.")

        self.config['build_timestamp'] = int(datetime.timestamp(datetime.now(timezone.utc)))
        new_on_top = self.config["new_on_top"]

        timeline = list(self.db.get_timeline(new_on_top))
        if len(timeline) == 0:
            log.info("no data found to publish site")
            quit()

        for month in timeline:
            if month.date.year not in self.timeline:
                self.timeline[month.date.year] = []
            self.timeline[month.date.year].append(month)

        self._render_timeline_index(self.timeline)

        # Queue to store the latest N items to publish in the RSS feed.
        rss_entries = deque([], self.config["rss_feed_entries"])
        fname = None
        index_page = None
        for month in timeline:
            # Get the days + message counts for the month.
            dayline = OrderedDict()
            d = None
            prev_d = None
            rendered = False
            for d in self.db.get_dayline(month.date.year, month.date.month, new_on_top, self.config["per_page"]):
                dayline[d.slug] = d
                fname = f"day-counter-{d.slug}.js"
                filename_rendered_exists = Path(os.path.join(self.config["publish_dir"], fname)).exists()
                if self.config["incremental_builds"] and filename_rendered_exists:
                    log.info(f"Incremental builds: file {fname} exists. Skip rendering.")
                    prev_d = d
                else:
                    rendered = True
                    self._render_day_counter(d)
                    if prev_d and not filename_rendered_exists:
                        self._render_day_counter(prev_d)
                        prev_d = None

            if self.config["incremental_builds"] and not rendered:
                # always rebuild last day counter page
                self._render_day_counter(d)

            # Paginate and fetch messages for the month until the end...
            last_id = 1000_000_000_000_000_000 if new_on_top else 0
            total = self.db.get_message_count(
                month.date.year, month.date.month)
            total_pages = math.ceil(total / self.config["per_page"])
            page = total_pages+1 if new_on_top else 0

            # render dayline
            if self.config["show_day_index"]:
                self._render_dayline(dayline, month, total_pages)

            self._render_pagination(month, total_pages)

            while True:
                messages = list(self.db.get_messages(month.date.year, month.date.month, new_on_top,
                                                     last_id, self.config["per_page"]))

                if len(messages) == 0:
                    break

                last_id = messages[-1].id

                page = page - 1 if new_on_top else page + 1
                fname = self.make_filename(month, page, total_pages)
                month_top_page = fname.find('_') == -1

                # Collect the message ID -> page name for all messages in the set
                # to link to replies in arbitrary positions across months, paginated pages.
                for m in messages:
                    self.page_ids[m.id] = fname

                if self.config["publish_rss_feed"]:
                    rss_entries.extend(messages)

                filename_rendered_exists = Path(os.path.join(self.config["publish_dir"], fname)).exists()
                if self.config["incremental_builds"] and len(messages) == self.config["per_page"]\
                        and filename_rendered_exists and not month_top_page:
                    log.info(f"Incremental builds: file {fname} exists. Skip rendering.")
                else:
                    self._render_page(messages, month, dayline, fname, page, total_pages)

                if new_on_top:
                    if index_page is None:
                        index_page = fname
                else:
                    index_page = fname

        # The last page chronologically is the latest page. Make it index.
        if index_page:
            if self.symlink:
                os.symlink(index_page, os.path.join(self.config["publish_dir"], "index.html"))
            else:
                shutil.copy(os.path.join(self.config["publish_dir"], index_page),
                            os.path.join(self.config["publish_dir"], "index.html"))

        # Generate RSS feeds.
        if self.config["publish_rss_feed"]:
            self._build_rss(rss_entries, "index.rss", "index.atom")

    def load_template(self, fname):
        with open(fname, "r") as f:
            self.template = Build._load_template_file(fname)

    def load_rss_template(self, fname):
        with open(fname, "r") as f:
            self.rss_template = Build._load_template_file(fname)

    def make_filename(self, month, page, total_pages) -> str:
        if self.config["new_on_top"]:
            fname = "{}{}.html".format(
                month.slug, "_" + str(page) if page < total_pages else "")
        else:
            fname = "{}{}.html".format(
                month.slug, "_" + str(page) if page > 1 else "")
        return fname

    @staticmethod
    def _load_template_file(file_name) -> Template:
        with open(file_name, "r") as f:
            return Template(f.read())

    def _render_page(self, messages, month, dayline, fname, page, total_pages):
        log.info(f"Rendering: : {fname}")
        html = self.template.render(config=self.config,
                                    timeline=self.timeline,
                                    dayline=dayline,
                                    month=month,
                                    messages=messages,
                                    page_ids=self.page_ids,
                                    pagination={"current": page,
                                                "total": total_pages},
                                    make_filename=self.make_filename,
                                    nl2br=self._nl2br)

        with open(os.path.join(self.config["publish_dir"], fname), "w", encoding="utf8") as f:
            f.write(html)

    def _render_day_counter(self, day):
        fname = f"day-counter-{day.slug}.js"
        log.info(f"Rendering: : {fname}")
        html = self._day_counter_template.render(
                                    day=day
        )
        with open(os.path.join(self.config["publish_dir"], fname), "w", encoding="utf8") as f:
            f.write(html)

    def _render_dayline(self, dayline, month, total_pages):
        fname = f"dayline-{month.slug}.js"
        log.info(f"Rendering: : {fname}")
        html = self._dayline_template.render(
            dayline=dayline, make_filename=self.make_filename, month=month, total_pages=total_pages
        )
        with open(os.path.join(self.config["publish_dir"], fname), "w", encoding="utf8") as f:
            f.write(html)

    def _render_timeline_index(self, timeline):
        fname = f"timeline-index.js"
        log.info(f"Rendering: : {fname}")
        html = self._timeline_index_template.render(
            timeline=timeline
        )
        with open(os.path.join(self.config["publish_dir"], fname), "w", encoding="utf8") as f:
            f.write(html)

    def _render_pagination(self, month, total_pages):
        fname = f"pagination-{month.slug}.js"
        log.info(f"Rendering: : {fname}")
        html = self._pagination_template.render(
            month=month, total_pages=total_pages
        )
        with open(os.path.join(self.config["publish_dir"], fname), "w", encoding="utf8") as f:
            f.write(html)

    def _build_rss(self, messages, rss_file, atom_file):
        log.info(f"Building RSS")
        f = FeedGenerator()
        f.id(self.config["site_url"])
        f.generator(
            f"tg-archive {__version__}")
        f.link(href=self.config["site_url"], rel="alternate")
        f.title(self.config["site_name"].format(group=self.config["group"]))
        f.subtitle(self.config["site_description"])

        for m in messages:
            url = "{}/{}#{}".format(self.config["site_url"],
                                    self.page_ids[m.id], m.id)
            e = f.add_entry()
            e.id(url)
            e.title("@{} on {} (#{})".format(m.user.username, m.date, m.id))
            e.published(m.date.replace(tzinfo=timezone.utc))
            e.link({"href": url})

            media_mime = ""
            if m.media and m.media.url:
                murl = "{}/{}/{}".format(self.config["site_url"],
                                         os.path.basename(self.config["media_dir"]), m.media.url)
                try:
                    media_path = "{}/{}".format(self.config["media_dir"], m.media.url)
                    media_mime = magic.from_file(media_path, mime=True)
                    media_size = str(os.path.getsize(media_path))
                except FileNotFoundError:
                    media_mime = "application/octet-stream"
                    media_size = 0
                e.enclosure(murl, media_size, media_mime)
            e.content(self._make_abstract(m, media_mime), type="html")

        f.rss_file(os.path.join(self.config["publish_dir"], "index.xml"))
        f.atom_file(os.path.join(self.config["publish_dir"], "index.atom"))

    def _make_abstract(self, m, media_mime):
        if self.rss_template:
            return self.rss_template.render(config=self.config,
                                            m=m,
                                            media_mime=media_mime,
                                            page_ids=self.page_ids,
                                            nl2br=self._nl2br)
        out = m.content
        if not out and m.media:
            out = m.media.title
        return out if out else ""

    def _nl2br(self, s) -> str:
        # There has to be a \n before <br> so as to not break
        # Jinja's automatic hyperlinking of URLs.
        return _NL2BR.sub("\n\n", s).replace("\n", "\n<br />")

    def _create_publish_dir(self):
        log.info("Creating publish tree if needed.")
        pubdir = self.config["publish_dir"]

        # Clear the output directory HTML files, if not incremental_builds
        if not self.config["incremental_builds"]:
            if os.path.exists(pubdir):
                for path in Path(pubdir).iterdir():
                    if path.is_file():
                        path.unlink()

        # Re-create the output directory.
        Path(pubdir).mkdir(parents=True, exist_ok=True)

        # Copy the static directory into the output directory.
        static_dir = self.config["static_dir"]
        if not os.path.exists(os.path.join(pubdir, os.path.basename(static_dir))):
            for f in [static_dir]:
                target = os.path.join(pubdir, f)
                if self.symlink:
                    os.symlink(os.path.abspath(f), target)
                elif os.path.isfile(f):
                    shutil.copyfile(f, target)
                else:
                    shutil.copytree(f, target)

        # If media downloading is enabled, copy/symlink the media directory.
        mediadir = self.config["media_dir"]
        if not os.path.exists(os.path.abspath(os.path.join(pubdir, os.path.basename(mediadir)))):
            if self.symlink:
                os.symlink(os.path.abspath(mediadir), os.path.join(
                    pubdir, os.path.basename(mediadir)))
            else:
                try:
                    shutil.copytree(mediadir, os.path.join(
                        pubdir, os.path.basename(mediadir)), dirs_exist_ok=True)
                except Exception as e:
                    ...
