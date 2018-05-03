# -*- coding: utf-8 -*-
import textract
import re
from xml.sax.saxutils import unescape # remove &...;
import unicodedata

MIN_LINE_LEN = 20
MIN_ALPHA_PROPORTION = 0.80
MAX_ALONE_CHARS = 0.1

def clean_text(texto, lower=True, stopwords=[], merge=False):

    #Limpiar HTML
    re_clean_html = re.compile('<.*?>')
    output = re.sub(re_clean_html, ' ', texto)
    output = unescape(output) # remove &...;

    #Normaliza los símbolos unicode
    output = unicodedata.normalize('NFC', output)

    #Sustituir todo lo que no sea una letra por un espacio
    output = re.sub('[^a-zA-ZáéíóúÁÉÍÓÚñçüÜ\.]',' ', output)

    #Sustituir varios espacios seguidos por un punto (fin de frase)
    output = re.sub('[\s]{2,}', '.', output)

    #Elimina lineas sin suficiente len
    output = [line.strip() for line in output.split('.') if len(line) > MIN_LINE_LEN]

    #Suficiente fraccion alfanumerica
    output = [line for line in output if (sum(c.isalpha() for c in line)/len(line))>MIN_ALPHA_PROPORTION]

    #Elimina demasiadas letras sueltas
    output = [line for line in output if (sum(len(w)==1 for w in line.split())/len(line.split()))<=MAX_ALONE_CHARS]

    if lower: output = [s.lower() for s in output]

    if merge: output = ' '.join(output)

    return output
