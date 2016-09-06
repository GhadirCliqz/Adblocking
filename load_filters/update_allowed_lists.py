"""Class that manages the list of allowed filters in S3 of the adblocker module"""

from sys import argv
import cStringIO
import gzip
import ujson
import boto


class UpdateAllowedLists():
    S3_BUCKET = 'cdn.cliqz.com'
    S3_PATH_ALLOWED_LISTS = 'adblocking/allowed-lists.json'
    S3_PATH_CHECKSUM = 'adblocking/latest-filters/filters_urls.json'
    conn = boto.connect_s3()

    def add_entry(self, list, url, lang=None):
        """Adds a new entry to the list of allowed filters on S3
        :param list: The list in which to add the filter options (country_lists, js_resources, allowed_lists)

        :param url: the url of the filter

        :param lang: optional, the language for country specific filters"""

        checksum_key = self.conn.get_bucket(self.S3_BUCKET).get_key(self.S3_PATH_CHECKSUM)
        allowed_lists_key = self.conn.get_bucket(self.S3_BUCKET).get_key(self.S3_PATH_ALLOWED_LISTS)

        datastring = checksum_key.get_contents_as_string()
        data = cStringIO.StringIO(datastring)
        rawdata = gzip.GzipFile(fileobj=data).read()
        checksum_dict = ujson.loads(rawdata)

        allowed_lists_dict = ujson.loads(allowed_lists_key.get_contents_as_string())

        if list == 'country_lists':
            allowed_lists_dict[list][url] = {'checksum': checksum_dict[url],
                                             'lang': lang}
        else:
            allowed_lists_dict[list][url] = {'checksum': checksum_dict[url]}

        allowed_lists_key.set_contents_from_string(ujson.dumps(allowed_lists_dict))
        allowed_lists_key.make_public()


if __name__ == "__main__":
    update_allowed_lists = UpdateAllowedLists()
    if len(argv) == 3:
        update_allowed_lists.add_entry(argv[1], argv[2])
    elif len(argv) == 4:
        update_allowed_lists.add_entry(argv[1], argv[2], argv[3])
