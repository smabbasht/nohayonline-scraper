import scrapy
from urllib.parse import urljoin, urlparse, parse_qs
from nohayonline_scraper.items import NohayonlineScraperItem


class KalaamSpider(scrapy.Spider):
    name = "kalaam"
    allowed_domains = ["nohayonline.com"]
    start_urls = ["https://nohayonline.com/details_masaib.php"]

    def parse(self, response):
        """
        On the Masaib index page, pick every category link (e.g. details_mb.php?text=Ashoor)
        and follow it, carrying the masaib name via meta.
        """
        # grab all anchors that lead to the masaib listing pages
        for a in response.css('a[href*="details_mb.php?text="]'):
            masaib = a.css("::text").get(default="").strip()
            href = a.attrib.get("href")
            if not href:
                continue
            url = response.urljoin(href)

            # keep the readable masaib name; we’ll store it in DB later
            yield scrapy.Request(
                url,
                callback=self.parse_masaib,
                meta={"masaib": masaib, "masaib_url": url},
            )

    def parse_masaib(self, response):
        """
        On a single masaib page, iterate the listing table (Title | Nohakhan),
        extract the detail link + visible reciter, and follow to the detail page.
        """
        masaib = response.meta.get("masaib")

        # rows typically look like: <tr><td><a href="details_content.php?id=1234">Title</a></td><td>Reciter</td></tr>
        rows = response.css("table tr")

        # skip header if present
        for tr in rows[1:]:
            a = tr.css('a[href*="details_content.php?id="]')
            if not a:
                continue

            title = a.css("::text").get(default="").strip()
            href = a.attrib.get("href")
            reciter_from_list = tr.css("td:nth-child(2)::text").get(default="").strip()

            if not href:
                continue
            detail_url = response.urljoin(href)

            # grab numeric id from the query param (if present)
            try:
                from urllib.parse import urlparse, parse_qs

                q = parse_qs(urlparse(detail_url).query)
                kid = int(q.get("id", ["0"])[0])
            except Exception:
                kid = None

            # follow to detail page; we’ll parse fields in the next step
            yield scrapy.Request(
                detail_url,
                callback=self.parse_detail,
                meta={
                    "masaib": masaib,
                    "reciter_from_list": reciter_from_list,
                    "title_from_list": title,
                    "kalaam_id": kid,
                },
            )

        # pagination guard (if any)
        next_href = response.css('a[href*="page="]::attr(href)').get()
        if next_href:
            yield response.follow(
                next_href, callback=self.parse_masaib, meta={"masaib": masaib}
            )

    def parse_detail(self, response):
        import re

        def clean_join(texts):
            return (
                "\n".join(t.strip() for t in texts if t and t.strip()).strip() or None
            )

        def extract_after_label(label):
            """
            Find any element containing the label (e.g., 'Nohakhan:'), then pull the value after ':'.
            Works even if it's in the same <p> node.
            """
            # get all text within the nearest block that mentions the label
            node_text = clean_join(
                response.xpath(
                    f'//*[contains(normalize-space(.), "{label}")]//text()'
                ).getall()
            )
            if not node_text:
                return None
            m = re.search(rf"{re.escape(label)}\s*(.+)", node_text, flags=re.IGNORECASE)
            return m.group(1).strip() if m else None

        masaib = response.meta.get("masaib")
        reciter_from_list = response.meta.get("reciter_from_list")
        kid = response.meta.get("kalaam_id")

        # title
        title = response.css("h2::text").get()
        if title:
            title = title.strip()

        # reciter & poet via labels, then trim labels
        reciter = extract_after_label("Nohakhan:")
        poet = extract_after_label("Shayar:")

        # fallback to table’s reciter if detail page doesn’t show it
        if not reciter:
            reciter = reciter_from_list or None

        # YouTube (first match)
        yt_link = response.css('a[href*="youtu"]::attr(href)').get()

        # English block is #etext, Urdu block is #utext on the site
        raw_nodes = response.css("#etext").xpath("./node()").getall()
        html_eng = "".join(raw_nodes)
        html_eng = (
            html_eng.replace("<br>", "\n")
            .replace("<br/>", "\n")
            .replace("\t\n", "")
            .replace("\r\n", "\n")
        )
        # lyrics_eng = html_eng.strip()
        lyrics_eng = html_eng

        raw_nodes = response.css("#utext").xpath("./node()").getall()
        html_urdu = "".join(raw_nodes)
        html_urdu = (
            html_urdu.replace("<br>", "\n")
            .replace("<br/>", "\n")
            .replace("\t", "")
            .replace("\r\n", "\n")
            .replace("\n\n\n", "\n\r\n")
            .replace("\n\n", "\n")
            .replace("\n\r\n", "\n\n")
        )

        # lyrics_urdu = html_urdu.strip()
        lyrics_urdu = html_urdu

        # In case the site sometimes omits the wrapper, try a gentle fallback:
        # if not lyrics_eng:
        #     lyrics_eng = clean_join(response.xpath('//*[@id="etext"]//text()').getall())
        # if not lyrics_urdu:
        #     lyrics_urdu = clean_join(
        #         response.xpath('//*[@id="utext"]//text()').getall()
        #     )

        # Normalization of Roman urdu searching

        import re
        from typing import Iterable

        _VOWELS = "aeiou"

        WORD_EQUIV = {
            r"\b(main|mein|mei|mn)\b": "mai",
            r"\b(nahin|nahi|nahee|nai)\b": "nahi",
            r"\b(hain+)\b": "hain",
            r"\b(kya|kia|ky[aa])\b": "kya",
            r"\b(mera+a*h*)\b": "mera",
        }

        SEQRULES: Iterable[tuple[re.Pattern, str]] = [
            # punctuation/spacing
            (re.compile(r"[^\w\s]"), " "),
            (re.compile(r"\s+"), " "),
            # digraphs/phones
            (re.compile(r"kh"), "x"),
            (re.compile(r"gh"), "g"),
            (re.compile(r"sh"), "sh"),
            (re.compile(r"ch"), "ch"),
            (re.compile(r"zh"), "z"),
            (re.compile(r"ph"), "f"),
            (re.compile(r"th"), "t"),
            (re.compile(r"dh"), "d"),
            (re.compile(r"bh"), "b"),
            (re.compile(r"q"), "k"),
            # c→k before a/o/u; c→s before e/i/y else keep c
            (re.compile(r"c(?=[aou])"), "k"),
            (re.compile(r"c(?=[ei y])"), "s"),
            # long vowels
            (re.compile(r"aa+"), "a"),
            (re.compile(r"(ee+|ii+)"), "i"),
            (re.compile(r"oo+"), "u"),
            # ai/ei/ay family → ai
            (re.compile(r"(ei|ay)"), "ai"),
            # terminal h after a vowel → drop
            (re.compile(rf"([{_VOWELS}])h\b"), r"\1"),
            # collapse triple+ repeats
            (re.compile(rf"([{_VOWELS}])\1{{2,}}"), r"\1\1"),  # vowels to max 2
            (re.compile(rf"([^ {_VOWELS}\W])\1{{1,}}"), r"\1"),  # consonants to 1
            # e/i and o/u collapse (after ai handling)
            (re.compile(r"e"), "i"),
            (re.compile(r"o"), "u"),
            # spaces again
            (re.compile(r"\s+"), " "),
        ]

        def normalize_roman_urdu(text: str) -> str:
            s = text.lower().strip()
            # word-level canonical replacements
            for pat, repl in WORD_EQUIV.items():
                s = re.sub(pat, repl, s)
            # sequence rules
            for pat, repl in SEQRULES:
                s = pat.sub(repl, s)
            return s.strip()

        # Finish Normalization

        yield NohayonlineScraperItem(
            id=kid,
            title=title,
            reciter=reciter,
            poet=poet,
            masaib=masaib,
            lyrics_eng=lyrics_eng,
            lyrics_urdu=lyrics_urdu,
            yt_link=yt_link,
            source_url=response.url,
            title_normalized=normalize_roman_urdu(title),
        )
