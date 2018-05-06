# -*- coding: utf-8 -*-

import json
import os
import random
from time import sleep
import re
import logging
import ssl

import requests
from urllib.parse import urlparse
import urllib
import textract
from newspaper import Article
from bs4 import BeautifulSoup

from modules.clean_text import clean_text


class Harvest:

    # This holds information for all query sets.
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

    DATA_FILE_TEMPLATE = 'data_{0}.txt' # {0} is a counter for each source

    LOG_FILE = 'logs/harvest.log'
    logger = None

    NUM_SEARCH = 2
    NUM_PER_SEARCH = 25
    NUM_KEYWORDS_PER_SEARCH = 3
    SLEEP_BETWEEN_SEARCHES = 5

    DISCARD_LINKS_FILE = 'discard_links'

    USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36'

    # General parsing
    MIN_USEFULL_BYTES_PER_SOURCE = 1000
    MIN_WORDS_PER_SOURCE = 500
    MAX_WORDS_PER_SOURCE = 5000

    # Textract file parsing
    SUPPORTED_FILES = [ 'csv', 'doc', 'docx', 'eml', 'epub', 'odt',
                        'pdf', 'pptx', 'rtf', 'xlsx', 'xls', 'json', 'msg']

    HTML_PAGES = ['html', 'htm', 'php', 'asp', 'aspx']

    SUPPORTED_MIME_TYPES = {
    'text/csv':'csv',
    'application/msword':'doc',
    'application/epub+zip':'epub',
    'application/json':'json',
    'application/vnd.oasis.opendocument.text':'odt',
    'application/pdf':'pdf',
    'application/vnd.ms-powerpoint':'pptx',
    'application/rtf':'rtf',
    'application/vnd.ms-excel':'xls',
    'application/xml':'xls'
    }

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
        self._set_logger()
        self.logger.info("Starting")



    def _set_logger(self):
        self.logger = logging.getLogger('harvest')

        # Formatter
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

        # File handler
        fileHandler = logging.FileHandler(self.LOG_FILE)
        fileHandler.setFormatter(formatter)
        self.logger.addHandler(fileHandler)

        # Console handler
        consoleHandler = logging.StreamHandler()
        consoleHandler.setFormatter(formatter)
        self.logger.addHandler(consoleHandler)

        self.logger.setLevel(logging.INFO)




    #########################################
    #
    #   Loads the query json, prepares the
    #   random queries, and prepare folders.
    #
    #########################################

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




    #########################################
    #
    #   Scraps google for links.
    #
    #########################################

    def get_google_links(self):

        if self.DEBUG_USE_LINKS:

            self.logger.info("Using debug links...")
            for seed in self.query_data:
                with open(self.query_data[seed]["links_file"]) as f:
                    links = [link.strip() for link in f.readlines()]
                    self.query_data[seed]["links"] = links
                    self.logger.info("Found {0} links for {1}".format(len(links), seed))

        else:

            s = requests.Session()

            with open(self.DISCARD_LINKS_FILE) as f:
                discard_links = [line.strip() for line in f.readlines()]
                f.close()

            for seed in self.query_data:

                self.logger.info("Scrapping links for {0}...".format(seed))

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

                self.logger.info("Found {0} links".format(len(links)))
                self.query_data[seed]["links"] = links

                if self.DEBUG_GENERATE_LINKS:
                    with open(self.query_data[seed]["links_file"], 'w') as f:
                        for link in self.query_data[seed]["links"]:
                            f.write("%s\n" % link)
                        f.close()

                sleep(self.SLEEP_BETWEEN_SEARCHES)




    #########################################
    #
    #   Scraps text from articles and files
    #   and cleans it.
    #
    #########################################

    def get_remote_texts(self,remove_previous=True):

        for seed in self.query_data:

            self.logger.info("#"*80)
            self.logger.info("# Extracting text from remote sources for {0}!".format(seed))
            self.logger.info("#"*80)

            current_folder = self.query_data[seed]["data_folder"]

            # Find out in which file we start saving data.
            if remove_previous:
                file_counter = 1
                for file_name in os.listdir(current_folder):
                    file_path = os.path.join(current_folder, file_name)
                    try:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                    except Exception as e:
                        self.logger.info(e)
            else:
                num_files = len([f for f in os.listdir(current_folder) if os.path.isfile(f)])
                file_counter = num_files + 1


            # Iterate links found for this seed.
            links = self.query_data[seed]["links"]

            for link in links:

                file_type, file_size, file_ext = self._get_link_info(link)

                if file_type == None:
                    self.logger.error("Error getting link info, skipping.")
                    continue

                ############################
                #
                #   HTML link
                #
                ############################
                if file_type == self.HTML:

                    article = Article(link)
                    try:
                        article.download()
                        article.parse()
                    except:
                        self.logger.info("Failed downloading webpage, skipping.")
                        continue

                    resulting_text = clean_text(
                        article.text,
                        merge=True,
                        max_words=self.MAX_WORDS_PER_SOURCE
                        )

                    num_words = len(resulting_text.split())

                    if len(resulting_text) < self.MIN_USEFULL_BYTES_PER_SOURCE:
                        self.logger.info("Article not enough long, skipping.")
                        continue

                    if num_words < self.MIN_WORDS_PER_SOURCE:
                        self.logger.info("Source: Not enough words, skipping.")
                        continue

                    self.logger.info("Article {0}w\t{1}b\t{2}".format(
                    num_words,
                    str(len(resulting_text)),
                    link
                    ))

                    # Save to file
                    file_path = '{0}/{1}'.format(
                    current_folder,
                    self.DATA_FILE_TEMPLATE.format(file_counter)
                    )

                    with open(file_path, 'w') as f:
                        f.write(resulting_text)
                        f.close()

                    file_counter+=1

                ############################
                #
                #   File link
                #
                ############################

                elif file_type == self.SUPPORTED_FILE:
                    if not file_size:
                        self.logger.info("Could not read filesize, skipping.")
                        continue
                    if file_size > self.MAX_REMOTE_FILE_SIZE:
                        self.logger.info("Filesize too big ({0}), skipipng.".format(file_size))
                        continue

                    self.logger.info("Downloading file")
                    local_file_path = "{0}/{1}{2}".format(
                        self.TMP_FOLDER,
                        self.TMP_FILE,
                        file_ext # Required by textract to parse correctly files
                    )
                    download_status = self._download_file(link, local_file_path)

                    if not download_status:
                     self.logger.info("Error downloading file, skipping.")
                     continue

                    try:
                        file_parsed = textract.process(local_file_path).decode('utf-8')
                    except Exception as e:
                        self.logger.info("Problem parsing file, skipping.")
                        self.logger.info(str(e))
                        continue

                    resulting_text = clean_text(
                        file_parsed,
                        merge=True,
                        max_words=self.MAX_WORDS_PER_SOURCE
                        )

                    num_words = len(resulting_text.split())

                    if len(resulting_text) < self.MIN_USEFULL_BYTES_PER_SOURCE:
                        self.logger.info("Source: Extracted text not enough long, skipping.")
                        continue

                    if num_words < self.MIN_WORDS_PER_SOURCE:
                        self.logger.info("Source: Not enough words, skipping.")
                        continue

                    self.logger.info("File {0}w\t{1}b\t{2}".format(
                    num_words,
                    str(len(resulting_text)),
                    link
                    ))

                    # Save to file
                    file_path = '{0}/{1}'.format(
                    current_folder,
                    self.DATA_FILE_TEMPLATE.format(file_counter)
                    )

                    with open(file_path, 'w') as f:
                        f.write(resulting_text)
                        f.close()

                    file_counter+=1

                ############################
                #
                #   Unknown link type
                #
                ############################

                else:
                    self.logger.info("MIME type not compatible, skipping")
                    continue

        return



    ##########################################################
    #
    #   Tries to know which kind of file it is. Firstly, by
    #   the link extension. Secondly, by HTTP(s) header.
    #
    ##########################################################

    def _get_link_info(self, link):

        try:
            headers = requests.get(link, stream=True, verify=False).headers
        except Exception as e:
            self.logger.error(str(e))
            return None, None, None

        file_type = self.UNSUPPORTED_FILE
        file_ext = ''

        # Get file format by link
        url_path = urlparse(link).path
        extension = os.path.splitext(url_path)[1]
        if len(extension):
            if extension[1:] in self.SUPPORTED_FILES:
                file_type = self.SUPPORTED_FILE
            elif extension[1:] in self.HTML_PAGES:
                file_type = self.HTML
            file_ext = extension # includes dot

        # If still unsupported, try to find by MIME types
        if file_type == self.UNSUPPORTED_FILE and 'content-type' in headers:
            mime_type = headers['content-type']
            if 'text/html' in mime_type:
                file_type = self.HTML
            elif mime_type in self.SUPPORTED_MIME_TYPES.keys():
                file_type = self.SUPPORTED_FILES
                file_ext = '.{0}'.format(self.SUPPORTED_MIME_TYPES[mime_type])

        # Get file size
        file_size =  None if 'content-length' not in headers else int(headers['content-length'])

        return file_type, file_size, file_ext



    ##########################################################
    #
    #   This downloads a file locally
    #
    ##########################################################

    def _download_file(self, link, local_file_path):
        if not os.path.isdir(self.TMP_FOLDER): os.mkdir(self.TMP_FOLDER)
        try:
            remote_file = urllib.request.urlopen(link, context=ssl.CERT_NONE)
        except Exception as e:
            self.logger.info(str(e))
            return None
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
