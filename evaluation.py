#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Wed Apr 8 2015
@author: Julio Barbieri
"""

import numpy as np
import nltk
import logging
import re
import pickle
import util
import time
import collections
import matplotlib.pyplot as plt
from util import file_exists
from util import exit_error
from util import setup_logger
from util import get_values
from util import verify_stemmer
from math import log

stemmer = util.NOSTEMMER
sequence = 1

def leia(filename):
	logger =  setup_logger(util.NAME_EVALUATION_LOGGER, util.EVALUATION_LOG)
	
	if not file_exists(filename):
		logger.error(util.FILE_NOT_FOUND % filename)
		exit_error(util.EXITED_WITH_ERROR)
	
	result_list = {}
	
	start_time = time.time()
	
	with open(filename) as fp:
		lidos = 0
		for line in fp:
			query, documents = get_values(line, lidos, util.CSV_SEPARATOR, util.NAME_EVALUATION_LOGGER, util.EVALUATION_LOG)
			elements = return_list_from_str(documents)
			lidos = lidos + 1
			result_list[query] = elements
				
	logger.debug(util.QUERIES_READ_TIME % (time.time() - start_time))
	
	logger.debug(util.LINES_READED_FILE % (lidos, filename))
	
	return result_list

def do_measures(results):
	prepare_data(results)
	
	retrieved_results = results[1]
	expected_results = results[0]
	
	precisions = precision_for_all(retrieved_results)
	recalls = recall_for_all(retrieved_results, expected_results)
	
	precisions_retrieved = precision_for_all(retrieved_results, 10)
	precisions_expected = precision_for_all(expected_results, 10)
	
	MAP = mean_average_precision(precisions_retrieved, precisions_expected)
	f1_scores = f1_score(precisions, recalls)
	dcg = discounted_cumulative_gain(retrieved_results)
	ndcg = normalized_discounted_cumulative_gain(retrieved_results)
	eleven_points = grafico_precisao_11_niveis_recall(retrieved_results, expected_results)
	
	save_in_file(precisions_retrieved, util.PATH + 'precision10K-' + stemmer + '-' + str(sequence) + '.csv')
	save_in_file(MAP, util.PATH + 'map-' + stemmer + '-' + str(sequence) + '.csv')
	save_in_file(f1_scores, util.PATH + 'f1-' + stemmer + '-' + str(sequence) + '.csv')
	save_in_file(dcg, util.PATH + 'discounted_cumulative_gain-' + stemmer + '-' + str(sequence) + '.csv')
	save_in_file(ndcg, util.PATH + 'normalized_discounted_cumulative_gain-' + stemmer + '-' + str(sequence) + '.csv')
	
	save_and_plot_in_file(eleven_points, util.PATH + '11points-' + stemmer + '-' + str(sequence))

def save_in_file(measures, filename):
	logger = setup_logger(util.NAME_EVALUATION_LOGGER, util.EVALUATION_LOG)
	
	if filename == '':
		logger.error(util.NO_FILE_SPECIFIED)
		exit_error(util.EXITED_WITH_ERROR)
	
	logger.debug(util.WRITING_METRIC % filename)
	
	fw = open(filename, 'w') 
	
	if isinstance(measures, collections.Sequence):
		for pair in measures:
			fw.write(str(pair[0]) + util.CSV_SEPARATOR + str(pair[1]) + '\n')
			
	else:
		fw.write(str(measures))
		
	fw.close()

def save_and_plot_in_file(measures, filename):
	logger = setup_logger(util.NAME_EVALUATION_LOGGER, util.EVALUATION_LOG)
	
	if filename == '':
		logger.error(util.NO_FILE_SPECIFIED)
		exit_error(util.EXITED_WITH_ERROR)
	
	logger.debug(util.WRITING_METRIC % (filename + '.pdf'))
	
	recalls = np.array([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1])
	plt.plot(recalls, measures, 'b-')
	plt.ylabel('Precision')
	plt.xlabel('Recall')
	plt.savefig(filename + '.pdf')
	
	logger.debug(util.WRITING_METRIC % (filename + '.csv'))
	
	fw = open(filename + '.csv', 'w') 
	
	for precision, recall in zip(measures, recalls):
		fw.write(str(precision) + util.CSV_SEPARATOR + str(recall) + '\n')
		
	fw.close()

def grafico_precisao_11_niveis_recall( retrieved_results, expected_results):
	points = 11
	
	mean_precisions = []
	mean_recalls = []
	
	for i in range(len(expected_results)):
		precisions = precision_for_all(retrieved_results, i + 1)
		recalls = recall_for_all(retrieved_results, expected_results, i + 1)
		mean_precision = np.mean([precision[1] for precision in precisions])
		mean_recall = np.mean([recall[1] for recall in recalls])
		
		mean_precisions.append(mean_precision)
		mean_recalls.append(mean_recall)
		#print('Precision: ' + str(mean_precision))
		#print('Recall: ' + str(mean_recall))
		
	#print(mean_precisions)
	#print(mean_recalls)
	precision_recalls = np.zeros(points)
		
	for i in range(0,points):
		precision_at_k = 0
		for k in range(len(mean_recalls)):
			if i <= mean_recalls[k]*10:
				precision_at_k = max(precision_at_k, mean_precisions[k])
		precision_recalls[i] = precision_at_k
		
	return precision_recalls
	
def precision_for_all(results, K = -1):
	
	precisions = []
	
	for key in results:
		rank = results[key]
		
		if K == -1:
			precision = precision_at_k(rank, len(rank))
		else:
			precision = precision_at_k(rank, K)
		
		precisions.append([key, round(precision, 2)])
		
	return precisions
	
def recall_for_all(retrieved, expected, K = -1):
	#				Relevant	Nonrelevant
	# Retrieved		tp			fp
	# Nonretrieved	fn			tn
	
	#R = tp/(tp + fn)
	#R = relevant_retrieved/(relevant_retrieved + relevant_nonretrieved)
	
	recalls = []
		
	for key_expected, key_retrieved in zip(expected, retrieved):
		if key_expected == key_retrieved:
		
			relevants_nonretrieved = nonretrieved(expected[key_expected], retrieved[key_retrieved])
			rank = retrieved[key_retrieved]
			if K == -1:
				recall = recall_at_k(rank, len(relevants_nonretrieved), len(rank))
			else:
				recall = recall_at_k(rank, len(relevants_nonretrieved), K)
			
			recalls.append([key_retrieved, round(recall)])
			
	return recalls
	
def precision_at_k(results, K):
	relevant = 0
	i = 0
	for result in results:
		if result[2] == 1:
			relevant = relevant + 1
		if i == K - 1:
			break
		i = i + 1
				
	precision = relevant/K
	#print(str(precision) + ' = ' + str(relevant) + '/' + str(K) )
	return precision
	
def recall_at_k(results, relevants_nonretrieved, K):
	relevant = 0
	i = 0
	for d in results:
		if d[2] == 1:
			relevant = relevant + 1
		if i == K - 1:
			break
		i = i + 1
	
	try:
		recall = relevant/(relevant + relevants_nonretrieved)
		#print(str(recall) + ' = ' + str(relevant) + '/' + str(relevant) + ' + ' + str(relevants_nonretrieved))
	except ZeroDivisionError:
		recall = 0
		#print(str(recall) + ' = ' + str(relevant) + '/' + str(relevant) + ' + ' + str(relevants_nonretrieved))
	return recall
	
def nonretrieved(data_expected, data_retrieved):
	
	documents_retrieved = [element[1] for element in data_retrieved if element[2] == 1]
	documents_expected = [element[1] for element in data_expected if element[2] == 1]
	
	relevants_nonretrieved = [x for x in documents_expected if x not in documents_retrieved]
	
	return relevants_nonretrieved
	
def mean_average_precision(precisions_retrieved, precisions_expected):
	all_precisions_retrieved =	[precision[1] for precision in precisions_retrieved]
	all_precisions_expected =	[precision[1] for precision in precisions_expected]
	mean_retrieved = np.mean(all_precisions_retrieved)
	mean_expected = np.mean(all_precisions_expected)
	return np.mean([mean_retrieved, mean_expected])
	
def discounted_cumulative_gain(results):
	dcg = []
	for key in results:
		data_retrieved = results[key]
		dcg_p = [float(data_retrieved[i][2])*log(i+1) if i != 0 else float(data_retrieved[i][2]) for i in range(len(data_retrieved))]
		dcg.append([key, sum(dcg_p)])
	return dcg
		
def normalized_discounted_cumulative_gain(results):
	ndcg = []
	for key in results:
		data_retrieved = results[key]
		ndcg_p = [float(data_retrieved[i][2])*log(i+1) if i != 0 else 2 + float(data_retrieved[i][2]) for i in range(len(data_retrieved))]
		ndcg.append([key, sum(ndcg_p)])
	return ndcg
	
def f1_score(precisions, recalls):
	# f1 = 2*(precision * recall)/(precision + recall)
	
	f1_scores = []
	
	for precision, recall in zip(precisions, recalls):
		if precision[0] == recall[0]:
			try:
				f1 = 2*(precision[1] * recall[1])/(precision[1] + recall[1])
			except ZeroDivisionError:
				f1 = 0
			f1_scores.append([precision[0], f1])
	
	return f1_scores
	
def prepare_data(results):
	expected = results[0]
	retrieved = results[1]
	
	for key_expected, key_retrieved in zip(expected, retrieved):
		if key_expected == key_retrieved:
			data_expected = expected[key_expected]
			data_retrieved = retrieved[key_retrieved]
			
			documents_retrieved = [element[1] for element in data_retrieved]
			documents_expected = [element[1] for element in data_expected if element[2] == 1]
			
			S1 = set(documents_retrieved)
			S2 = set(documents_expected)
			
			common_elements = S1.intersection(S2)
			
			for i in range(len(data_retrieved)):
				for element in common_elements:
					if data_retrieved[i][1] == element:
						data_retrieved[i][2] = 1
					
			retrieved[key_retrieved] = data_retrieved
			
	results[1] = retrieved

def return_list_from_str(string):
	string = string[:-1]
	string = string[1:]
	
	string = string.replace(', ', ',')
	list_tuples = string.split('],[')

	elements = []
	
	for tuple in list_tuples:
		if tuple[0] == '[':
			tuple = tuple[1:]
			
		if tuple[-1] == ']':
			tuple = tuple[:-1]
			
		list_elements = tuple.split(',')
		
		if (float(list_elements[2]) <= 0.99 and float(list_elements[2]) > 0.6):
			list_elements[2] = 0
		elif (float(list_elements[2]) <= 0.6 and float(list_elements[2]) >= 0.001):
			list_elements[2] = 0
		elif (float(list_elements[2]) <= 8 and float(list_elements[2]) > 3):
			list_elements[2] = 1
		elif (float(list_elements[2]) <= 3 and float(list_elements[2]) >= 0):
			list_elements[2] = 0
		
		elements.append(list_elements)
		
	return elements

def parse_command_file():
	logger =  setup_logger(util.NAME_EVALUATION_LOGGER, util.EVALUATION_LOG)
	
	config_file = util.EVALUATION_FILENAME
	
	results = []
	
	if not file_exists(config_file):
		logger.error(util.FILE_NOT_FOUND % config_file)
		exit_error(util.EXITED_WITH_ERROR)
	
	logger.debug(util.READ_CONFIG_STARTED % config_file)
	
	with open(config_file) as fp:
		count = 0
		for line in fp:
			if count == 0:
				global stemmer
				if verify_stemmer(line, count, util.NAME_EVALUATION_LOGGER, util.EVALUATION_LOG):
					stemmer = util.STEMMER
				count = count + 1
				continue
			
			next_cmd, filename = get_values(line, count, util.CONFIG_SEPARATOR, util.NAME_EVALUATION_LOGGER, util.EVALUATION_LOG)
			
			if next_cmd == util.CMD_LEIA and (count == 1 or count == 2):
				returned_results = leia(filename)
				results.append(returned_results)
				
			else:
				logger.error(util.NE_IO_INSTRUCTION_ERROR % (count + 1))
				exit_error(util.EXITED_WITH_ERROR)
			count = count + 1
			
	logger.debug(util.LINES_READED_CONFIG % count)
	logger.debug(util.CONFIG_END_PROCESSING % config_file)
	
	do_measures(results)

if __name__ == "__main__":
	parse_command_file()
