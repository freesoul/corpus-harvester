# -*- coding: utf-8 -*-

import re

with open('discard_links.json') as f:
	discard_links = f.readlines()
	f.close()


for pattern in discard_links:
	print(re.search(pattern.strip(), 'http://books.google.com/hshsk'))
