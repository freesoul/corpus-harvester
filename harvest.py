# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
import requests
from urllib.parse import urlparse
import json
import os
import random
from time import sleep
import re
from modules.clean_text import clean_text
import urllib
import logging
import shutil
from newspaper import Article
import ssl
import textract

class Harvest:

    query_data = {}

    # Config
    VERBOSE = True
    DEBUG_FOLDER = 'debug'
    DEBUG_LINK_FILE_PREFIX = 'debug_links'
    DEBUG_GENERATE_LINKS = False
    DEBUG_USE_LINKS = True

    DATA_FOLDER = 'data'
    TMP_FOLDER = 'tmp'
    TMP_FILE = 'tmp_file'

    LOG_FILE = 'logs/harvest.log'
    logger = None

    NUM_SEARCH = 2
    NUM_PER_SEARCH = 25
    NUM_KEYWORDS_PER_SEARCH = 3
    SLEEP_BETWEEN_SEARCHES = 5

    DISCARD_LINKS_FILE = 'discard_links'

    USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36'

    MIN_USEFULL_BYTES_PER_SOURCE = 500


    #Textract file parsing
    TEXTRACT_SUPPORTED_FILES = ['csv', 'doc', 'docx', 'eml', 'epub', 'odt',
                                'pdf', 'pptx', 'rtf', 'xlsx', 'xls', 'json', 'msg']
    HTML_PAGES = ['html', 'htm', 'php', 'asp', 'aspx']
    SUPPORTED_MIME_TYPES = ['text/csv','application/msword','application/epub+zip',
                            'application/json','application/vnd.oasis.opendocument.text',
                            'application/pdf','application/vnd.ms-powerpoint','application/rtf',
                            'application/vnd.ms-excel','application/xml']
    MAX_REMOTE_FILE_SIZE = 3 * 1024 * 1024
    HTML = 1
    SUPPORTED_FILE = 2
    UNSUPPORTED_FILE = 3


    # GOOGLE CONSTANTS
    MAX_NUM = 1000 # Set by google
    RESULTS_CONTAINER = 'div#ires'
    RESULT_CONTAINER = 'div.g'
    LINK = 'h3 a'



    def __init__(self):
        self.logger = logging.getLogger('harvest')
        hdlr = logging.FileHandler(self.LOG_FILE)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        hdlr.setFormatter(formatter)
        self.logger.addHandler(hdlr)
        self.logger.setLevel(logging.WARNING)



    def load_seeds(self,sFile):
        query_data={}

        # Load seeds
        with open(sFile) as f:
            seeds = json.loads(f.read())

        # Make folders
        if not os.path.isdir(self.DATA_FOLDER):
            os.mkdir(self.DATA_FOLDER)

        # Prepare paths and search queries
        self.query_data = {}
        for seed in seeds:
            # Data folder
            self.query_data[seed] = {"data_folder":"{0}/{1}".format(self.DATA_FOLDER, seed)}
            if not os.path.isdir(self.query_data[seed]["data_folder"]):
                os.mkdir(self.query_data[seed]["data_folder"])

            # Debug folder
            if self.DEBUG_GENERATE_LINKS or self.DEBUG_USE_LINKS:

                if not os.path.isdir(self.DEBUG_FOLDER): os.mkdir(self.DEBUG_FOLDER)

                self.query_data[seed]["links_file"] = "{0}/{1}_{2}.txt".format(
                self.DEBUG_FOLDER,
                self.DEBUG_LINK_FILE_PREFIX,
                seed)
            else:
                self.query_data[seed]

            #Queries
            if not self.DEBUG_GENERATE_LINKS:
                self.query_data[seed]["queries"] = None
            else:
                queries = [random.sample(seeds[seed], self.NUM_KEYWORDS_PER_SEARCH) for i in range(self.NUM_SEARCH)]
                self.query_data[seed]["queries"] = queries



    def get_google_links(self):

        if self.DEBUG_USE_LINKS:

            for seed in self.query_data:
                with open(self.query_data[seed]["links_file"]) as f:
                    self.query_data[seed]["links"] = [link.strip() for link in f.readlines()]

        else:

            s = requests.Session()

            with open(self.DISCARD_LINKS_FILE) as f:
                discard_links = [line.strip() for line in f.readlines()]
                f.close()

            for seed in self.query_data:

                links = []

                for query in self.query_data[seed]["queries"]:

                    result = s.get("https://google.com/search",
                    params={'q':' '.join(query), 'num':self.NUM_PER_SEARCH},
                    headers={'User-agent':self.USER_AGENT}
                    )
                    result = result.content

                    # parse links
                    bs = BeautifulSoup(result, 'html.parser')
                    results_container = bs.select(self.RESULTS_CONTAINER)[0]
                    results = results_container.select(self.RESULT_CONTAINER)
                    links_current = [result.select(self.LINK)[0]['href'] for result in results]
                    links_current = [link for link in links_current if len(urlparse(link).path) > 1] # No domains
                    links.extend(links_current)

                links = set(links)
                links = [link for link in links if 'http'==link[:4]] #sometimes missing schema
                links = [link for link in links if not any([re.search(pattern, link) for pattern in discard_links])]

                self.query_data[seed]["links"] = links

                if self.DEBUG_GENERATE_LINKS:
                    with open(self.query_data[seed]["links_file"], 'w') as f:
                        for link in self.query_data[seed]["links"]:
                            f.write("%s\n" % link)
                        f.close()

                sleep(self.SLEEP_BETWEEN_SEARCHES)



    def get_remote_texts(self,remove_previous=True):
        for seed in self.query_data:
            # Remove previous files
            if remove_previous: shutil.rmtree(self.query_data[seed]["data_folder"])

            links = self.query_data[seed]["links"]
            for link in links:
                file_type, file_size = self._get_link_info(link)

                if file_type == self.HTML:

                    self.logger.info("Reading webpage")
                    article = Article(link)
                    try:
                        article.download()
                        article.parse()
                    except:
                        self.logger.info("Failed downloading webpage, skipping.")
                        continue

                    resulting_text = clean_text(article.text, merge=True)

                    if len(resulting_text) < self.MIN_USEFULL_BYTES_PER_SOURCE:
                        self.logger.info("Article not enough long, skipping.")
                        continue

                    print("Article {0}\t{1}".format(
                    str(len(resulting_text)),
                    link
                    ))

                elif file_type == self.SUPPORTED_FILE:
                    if not file_size:
                        self.logger.info("Could not read filesize, skipping.")
                        continue
                    if file_size <= self.MAX_REMOTE_FILE_SIZE:
                        self.logger.info("Filesize too big ({0}), skipipng.".format(file_size))
                        continue

                    self.logger.info("Downloading file")
                    local_file_path = "{0}/{1}".format(self.TMP_FOLDER, self.TMP_FILE)
                    self._download_file(link, "{0}/{1}".format(self.TMP_FOLDER, self.TMP_FILE))

                    try:
                        file_parsed = textract.process(local_file_path)
                    except:
                        self.logger.info("Problem parsing file, skipping.")
                        continue

                    resulting_text = clean_text(file_parsed, merge=True)

                    if len(resulting_text) < self.MIN_USEFULL_BYTES_PER_SOURCE:
                        self.logger.info("Extracted text from file not enough long, skipping.")
                        continue

                    print("File {0}\t{1}".format(
                    str(len(resulting_text)),
                    link
                    ))

                else:
                    self.logger.info("MIME type not compatible, skipping")
                    continue

                # Test if supported file

                # Try to extract article

                # Clean

                # Save
        return


    def _get_link_info(self, link):

        headers = requests.get(link, stream=True, verify=False).headers

        # Test if its a supported file or not
        file_type = self.UNSUPPORTED_FILE

        # Get file format by link
        url_path = urlparse(link).path
        extension = os.path.splitext(url_path)[1]
        if len(extension):
            if extension[1:] in self.TEXTRACT_SUPPORTED_FILES:
                file_type = self.SUPPORTED_FILE
            elif extension[1:] in self.HTML_PAGES:
                file_type = self.HTML

        # If still unsupported, try to find by MIME types

        if file_type == self.UNSUPPORTED_FILE and 'content-type' in headers:
            if 'text/html' in headers['content-type']:
                file_type = self.HTML
            elif headers['content-type'] in self.SUPPORTED_MIME_TYPES:
                file_type = self.TEXTRACT_SUPPORTED_FILES

        # Get file size
        file_size =  None if 'content-length' not in headers else int(headers['content-length'])

        return file_type, file_size


    def _download_file(self, link, local_file_path):
        if not os.path.isdir(self.TMP_FOLDER): os.mkdir(self.TMP_FOLDER)
        remote_file = urllib.request.urlopen(link, context=ssl.CERT_NONE)
        local_file = open(local_file_path, 'wb')
        local_file.write(remote_file.read())
        size = local_file.tell()
        remote_file.close()
        local_file.close()
        return size



harvest = Harvest()
harvest.load_seeds('seeds.json')
harvest.get_google_links()
harvest.get_remote_texts()
