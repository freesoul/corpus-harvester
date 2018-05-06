
# Corpus harvester

This project emerges from the need of creating text datasets.

This program scraps search engines (currently google) for links based on queries (configurable in seeds.json).

Then it acceses the links to cleverly extract information from text/html pages using Python library newspaper, or extracting information from files such as PDF or DOCs using Textract.

Finally, it cleans the text leaving only words separated by spaces.

Each source is extracted in its correspondant folder in a separate .txt file.


# Dependencies

This program has been only tested on Ubuntu alongisde Python3.5 for the moment. Once you have this context, to use it:

Install textract dependencies

1. apt-get install python-dev libxml2-dev libxslt1-dev antiword unrtf poppler-utils pstotext tesseract-ocr flac ffmpeg lame libmad0 libsox-fmt-mp3 sox libjpeg-dev swig libpulse-dev

2. pip3 install textract


Install Newspaper to extract main content from webpages (I tested library Goose, but this one seems to perform better).

3. pip3 install newspaper3k

