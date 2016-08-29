"""luigi task to download ad blocking filters and save their corresponding md5s and urls"""

import os
import json
import hashlib
import datetime
import requests
import luigi
from luigi.s3 import S3Target, S3Client

class StoreAdblockerFilters(luigi.Task):

    BASE_URL = 'https://raw.githubusercontent.com/uBlockOrigin/uAssets/master/'
    FILTER_LIST_BASE_URL = 'https://raw.githubusercontent.com/gorhill/uBlock/master/'
    S3_BUCKET = "s3://cdn.cliqz.com/adblocking/filters/"
    S3_BUCKET_LATEST = "s3://cdn.cliqz.com/adblocking/latest-filters"

    date = luigi.DateParameter(default=datetime.datetime.now().date())
    client = S3Client(host='s3.amazonaws.com')

    def output(self):
        return S3Target(self.S3_BUCKET+'/{0}'.format(self.date), client=self.client)

    def run(self):
        newpath = r'files'
        if not os.path.exists(newpath):
            os.makedirs(newpath)
        self.extract_filters_urls()
        self.client.put('filters_urls.txt', self.S3_BUCKET+'/{0}/filters_urls'.format(self.date), policy='public-read')
        self.copy_latest_bucket()
        # out_file = self.output().open('w')
        # out_file.write(open('filters_urls.txt', 'rb').read())
        # out_file.close()

    def extract_filters_urls(self):
        """download checksums & filter-lists files along with their filters
        save the md5s and urls of the downloaded filters"""
        with open('filters_urls.txt', 'wb') as filters_urls_file:
            # load checksums
            self.download_file('https://raw.githubusercontent.com/uBlockOrigin/uAssets/master/checksums/ublock0.txt')
            # extract urls in checksums file
            self.load_checksums_filters(filters_urls_file)
            # extract urls in filter-lists file
            self.load_filter_lists(filters_urls_file)


    def load_checksums_filters(self, filters_md5_urls):
        """download the filters included in the checksums file"""
        checksums_file = open(os.path.join('files', 'ublock0.txt'), 'r')
        for line in checksums_file:
            md5 = line.split(' ')[0].rstrip()
            path = line.split(' ')[1].rstrip()
            url = self.url_from_path(path)
            # if this is the path to the filters list file, then directly download it and don't save it
            if path.startswith('assets/ublock/filter-lists.json'):
                self.download_file(url)
            # otherwise save the md5, path and url
            else:
                self.download_file(url)
                filters_md5_urls.write(md5 + ' ' + url + '\n')

    def load_filter_lists(self, filters_md5_urls):
        """download the filters included in the filter-lists file"""
        with open(os.path.join('files', 'filter-lists.json'), 'r') as data_file:
            data = json.load(data_file)
        for key in data:
            if 'homeURL' in data[key]:
                url = str(data[key]['homeURL'])
            else:
                url = str(key)
                self.download_file(url)
            local_filename = os.path.join('files', url.split('/')[-1])
            if os.path.exists(local_filename):
                md5 = hashlib.md5(open(local_filename, 'rb').read()).hexdigest()
                filters_md5_urls.write(str(md5) + ' ' + url +'\n')


    def download_file(self, url):
        """download a file"""
        filename = url.split('/')[-1]
        local_filename = os.path.join('files', filename)
        try:
            request = requests.get(url)
            print request.status_code
            with open(local_filename, 'wb') as downloaded_file:
                for chunk in request.iter_content(chunk_size=1024):
                    if chunk:
                        downloaded_file.write(chunk)
            url = url.replace("http://", "")
            url = url.replace("https://", "")
            print repr(url)
            self.client.put(local_filename, self.S3_BUCKET+'/{1}/{0}'.format(url, self.date), policy='public-read')
            # S3_CLIENT.Object('ghadir-adblocking-filters', local_filename).put(Body=open(local_filename, 'rb'))

        except requests.exceptions.RequestException as request_exception:
            print request_exception
            # sys.exit(1)
        return


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
        self.client.copy(self.S3_BUCKET+'{0}'.format(self.date), self.S3_BUCKET_LATEST, preserve_acl=True)


if __name__ == "__main__":
    luigi.run()