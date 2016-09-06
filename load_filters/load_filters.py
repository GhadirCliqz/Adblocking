"""luigi task to download ad blocking filters and save their corresponding md5s and urls to S3"""

import hashlib
import datetime
import requests
import ujson
from boto.s3.connection import S3Connection
import luigi
from luigi.s3 import S3Target, S3Client

class StoreAdblockerFilters(luigi.Task):

    BASE_URL = 'https://raw.githubusercontent.com/uBlockOrigin/uAssets/master/'
    FILTER_LIST_BASE_URL = 'https://raw.githubusercontent.com/gorhill/uBlock/master/'
    # primary account bucket
    S3_BUCKET = "cliqz-mapreduce"
    S3_PATH = "s3://cliqz-mapreduce/adblocker/filters/"
    S3_BUCKET_LATEST = "cdn.cliqz.com"
    S3_PATH_LATEST = "s3://cdn.cliqz.com/adblocking/latest-filters"
    # test account bucket
    # S3_BUCKET = "ghadir-adblocking"
    # S3_PATH = "s3://ghadir-adblocking/filters/"
    # S3_PATH_LATEST = "s3://ghadir-adblocking/latest/"

    date = luigi.DateParameter(default=datetime.datetime.now().date())
    client = S3Client(host='s3.amazonaws.com')
    conn = S3Connection()

    def output(self):
        return S3Target(self.S3_PATH + '{0}/filters_urls.json'.format(self.date), client=self.client, format=luigi.format.Gzip)

    def run(self):
        """download checksums & filter-lists files along with their filters
                save the md5s and urls of the downloaded filters to out_file"""
        with self.output().open('w') as out_file:
            filters_dict = dict()
            # load checksums
            self.download_file('https://raw.githubusercontent.com/uBlockOrigin/uAssets/master/checksums/ublock0.txt')
            # extract urls in checksums file
            filters_dict = self.load_checksums_filters(filters_dict)
            # extract urls in filter-lists file
            filters_dict = self.load_filter_lists(filters_dict)
            # update the checksum of the allowed-lists
            self.update_allowed_lists_checksum(filters_dict)

            out_file.write(ujson.dumps(filters_dict))

        output_key = self.conn.get_bucket(self.S3_BUCKET).get_key(self.output().path.split('/', 3)[-1])
        print output_key
        output_key.set_remote_metadata(metadata_plus={'Content-Encoding': 'gzip'}, metadata_minus={}, preserve_acl=True)
        output_key.make_public()

        self.copy_latest_bucket()

    def load_checksums_filters(self, filters_dict):
        """download the filters included in the checksums file"""
        path = self.S3_PATH + '/{0}/raw.githubusercontent.com/uBlockOrigin/uAssets/master/checksums/' \
                                        'ublock0.txt'.format(self.date)
        target = luigi.s3.S3Target(path, format=luigi.format.Gzip)
        if self.client.exists(path):
            with target.open('r') as in_file:
                for line in in_file:
                    md5 = line.split(' ')[0].rstrip()
                    path = line.split(' ')[1].rstrip()
                    url = self.url_from_path(path)
                    # if this is the path to the filters list file, then directly download it and don't save it
                    self.download_file(url)
                    if not path.startswith('assets/ublock/filter-lists.json'):
                        # otherwise save the md5, path and url
                        filters_dict.update({url: md5})
        return filters_dict

    def load_filter_lists(self, filters_dict):
        """download the filters included in the filter-lists file"""
        path = self.S3_PATH + '{0}/raw.githubusercontent.com/gorhill/uBlock/master/assets/ublock/' \
                                             'filter-lists.json'.format(self.date)
        target = luigi.s3.S3Target(path, format=luigi.format.Gzip)
        if self.client.exists(path):
            with target.open('r') as in_file:
                data = ujson.loads(in_file.read())
            for key in data:
                if 'homeURL' in data[key]:
                    url = str(data[key]['homeURL'])
                else:
                    url = str(key)
                md5 = self.download_file(url)
                if not md5 is None:
                    filters_dict.update({url: md5})
        return filters_dict

    def download_file(self, url):
        """download a file and save the content to S3"""
        name = url.replace("http://", "").replace("https://", "")
        target = luigi.s3.S3Target(self.S3_PATH + '/{0}/{1}'.format(self.date, name), format=luigi.format.Gzip)
        try:
            request = requests.get(url, verify=False)
            print request.status_code
            with target.open('w') as out_file:
                for chunk in request.iter_content(chunk_size=1024):
                    if chunk:
                        out_file.write(chunk)

            print repr(url)
            key = self.conn.get_bucket(self.S3_BUCKET).get_key('adblocker/filters/{0}/{1}'.format(self.date, name.split('?')[0]))
            print key
            key.set_remote_metadata(metadata_plus={'Content-Encoding': 'gzip'}, metadata_minus={}, preserve_acl=True)
            key.make_public()
            md5 = key.etag

        except requests.exceptions.RequestException as request_exception:
            md5 = None
            print request_exception
        return md5

    def url_from_path(self, path):
        """map a given filter path to its corresponding url"""
        if path.startswith('assets/ublock/filter-lists.json'):
            return self.FILTER_LIST_BASE_URL + path
        elif path.startswith('assets/thirdparties/'):
            return path.replace('assets/thirdparties/', self.BASE_URL+'thirdparties/')
        elif path.startswith('assets/ublock/'):
            return path.replace('assets/ublock/', self.BASE_URL + 'filters/')
        else:
            return None

    def copy_latest_bucket(self):
        """copy the backup bucket of today to the latest bucket on S3"""
        self.client.copy(self.S3_PATH + '{0}'.format(self.date), self.S3_PATH_LATEST, preserve_acl=True)

    def update_allowed_lists_checksum(self, filters_dict):
        """updates the checksum values of the allowed lists based on the latest filters_urls list"""
        path = 's3://cdn.cliqz.com/adblocking/allowed-lists.json'
        target = luigi.s3.S3Target(path)
        if self.client.exists(path):
            with target.open('r') as allowed_lists:
                data = ujson.loads(allowed_lists.read())
                for list in data:
                    for url in data[list]:
                        print list
                        print url
                        print data[list][url]['checksum']
                        print filters_dict[url]
                        data[list][url]['checksum'] = filters_dict[url]
            with target.open('w') as allowed_lists:
                allowed_lists.write(ujson.dumps(data))

            key = self.conn.get_bucket(self.S3_BUCKET_LATEST).get_key('adblocking/allowed-lists.json')
            print key
            key.make_public()


if __name__ == "__main__":
    luigi.run()
