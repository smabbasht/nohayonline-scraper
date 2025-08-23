# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class NohayonlineScraperItem(scrapy.Item):
    id = scrapy.Field()  # from ?id=
    title = scrapy.Field()
    reciter = scrapy.Field()
    poet = scrapy.Field()
    masaib = scrapy.Field()
    lyrics_urdu = scrapy.Field()
    lyrics_eng = scrapy.Field()
    yt_link = scrapy.Field()
    source_url = scrapy.Field()
