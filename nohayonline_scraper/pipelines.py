from itemadapter import ItemAdapter
import os
import psycopg2
import psycopg2.extras


class NohayonlineScraperPipeline:
    """
    Postgres UPSERT pipeline for table `kalaam`.
    Uses env vars (or Scrapy settings) for DB connection.
    """

    def open_spider(self, spider):
        s = spider.settings

        dsn = s.get("POSTGRES_DSN") or os.getenv("POSTGRES_DSN")
        if not dsn:
            host = os.getenv("POSTGRES_HOST", s.get("POSTGRES_HOST", "127.0.0.1"))
            port = int(os.getenv("POSTGRES_PORT", s.get("POSTGRES_PORT", 5432)))
            db = os.getenv("POSTGRES_DB", s.get("POSTGRES_DB", "yourdb"))
            user = os.getenv("POSTGRES_USER", s.get("POSTGRES_USER", "youruser"))
            pwd = os.getenv("POSTGRES_PASS", s.get("POSTGRES_PASS", "yourpass"))
            dsn = f"host={host} port={port} dbname={db} user={user} password={pwd}"

        self.conn = psycopg2.connect(dsn)
        self.conn.set_session(autocommit=False)
        self.cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # bootstrap table and indexes (safe to run each time)
        self.cur.execute(
            """
        CREATE EXTENSION IF NOT EXISTS pg_trgm;

        CREATE TABLE IF NOT EXISTS kalaam (
          id          INTEGER PRIMARY KEY,
          title       TEXT        NOT NULL,
          reciter     TEXT,
          poet        TEXT,
          masaib      TEXT,
          lyrics_urdu TEXT,
          lyrics_eng  TEXT,
          yt_link     TEXT,
          source_url  TEXT        NOT NULL,
          fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT chk_has_lyrics CHECK (
            coalesce(length(lyrics_urdu),0) > 0 OR coalesce(length(lyrics_eng),0) > 0
          )
        );

        CREATE UNIQUE INDEX IF NOT EXISTS ux_kalaam_source_url ON kalaam (source_url);
        CREATE INDEX IF NOT EXISTS ix_kalaam_title_trgm ON kalaam USING gin (title gin_trgm_ops);
        """
        )
        self.conn.commit()

        self.upsert_sql = """
        INSERT INTO kalaam
          (id, title, reciter, poet, masaib, lyrics_urdu, lyrics_eng, yt_link, source_url)
        VALUES
          (%(id)s, %(title)s, %(reciter)s, %(poet)s, %(masaib)s, %(lyrics_urdu)s, %(lyrics_eng)s, %(yt_link)s, %(source_url)s)
        ON CONFLICT (id) DO UPDATE SET
          title       = EXCLUDED.title,
          reciter     = EXCLUDED.reciter,
          poet        = EXCLUDED.poet,
          masaib      = EXCLUDED.masaib,
          lyrics_urdu = EXCLUDED.lyrics_urdu,
          lyrics_eng  = EXCLUDED.lyrics_eng,
          yt_link     = EXCLUDED.yt_link,
          source_url  = EXCLUDED.source_url,
          fetched_at  = now();
        """

    def process_item(self, item, spider):
        data = dict(ItemAdapter(item).asdict())

        # normalize empties → NULL
        for k in ("reciter", "poet", "masaib", "lyrics_urdu", "lyrics_eng", "yt_link"):
            if isinstance(data.get(k), str) and not data[k].strip():
                data[k] = None

        # required fields
        if data.get("id") is None:
            raise ValueError("Missing kalaam.id")
        if not data.get("title"):
            raise ValueError(f"Missing title for id={data.get('id')}")
        if not data.get("source_url"):
            data["source_url"] = ""

        self.cur.execute(self.upsert_sql, data)
        return item

    def close_spider(self, spider):
        try:
            self.conn.commit()
        finally:
            self.cur.close()
            self.conn.close()
