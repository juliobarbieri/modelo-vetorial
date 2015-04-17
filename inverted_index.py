#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Sat Mar 28 2015
@author: Julio Barbieri
"""

import nltk
from collections import defaultdict
from nltk.stem.porter import PorterStemmer
 
class InvertedIndex:
 
	def __init__(self, tokenizer, stemmer=None, stopwords=None):
		self.tokenizer = tokenizer
		self.stemmer = stemmer
		self.index = defaultdict(list)
		self.id = 0
		if not stopwords:
			self.stopwords = set()
		else:
			self.stopwords = set(stopwords)
 
	def retrieve(self, word):
		word = word.upper()
		
		return word + ';' + str([id for id in self.index.get(word)]).replace(' ', '').replace('\'', '')
 
	def add(self, identifier, document):
		for token in [t.lower() for t in self.tokenizer(document)]:
			if token in self.stopwords:
				continue
 
			if self.stemmer:
				token = self.stemmer.stem(token)
			
			self.id = identifier
			self.index[token.upper()].append(self.id)
