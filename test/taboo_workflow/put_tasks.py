import requests
from csv import reader
import pickle
import datetime
import json


def put_tasks(crowdjs_url, email, API_KEY, requester_id, answers_per_question,
              threshold, question_file):
    crowdjs_url += '/tasks'

    task_name = "Relation Extraction Taboo"
    task_description = 'Creatively edit sentences so that they no longer express the given relation'


    lineNumber = -1
    questions = []
    for line in reader(question_file):
        lineNumber += 1

        #skip the first line
        if lineNumber == 0:
            continue
    
        sentence = line[0]
        sentence_bolded = line[1]
        entity1 = line[2]
        entity2 = line[3]
        relation = line[4]

        taboo_words = {'not': threshold+1}
        
        data = (sentence, sentence_bolded, entity1, entity2,
                relation, 'not;', lineNumber)

        tabbedData = "%s\t%s\t%s\t%s\t%s\t%s\t%d" % data
        
        question = {'question_name': tabbedData,
                    'question_description': 'Question %d' % lineNumber,
                    'question_data': tabbedData,
                    'requester_id' : requester_id,
                    'answers_per_question' : answers_per_question}
        questions.append(question)

    headers = {'Authentication-Token': API_KEY,
               'content_type' : 'application/json'}

    
    data = {'task_name': task_name,
            'task_description': task_description,
            'requester_id' : requester_id,
            'data' : pickle.dumps(taboo_words),
            'questions' : questions}
        
    r = requests.put(crowdjs_url, headers=headers,
                     json=data)

    print "Here is the response"
    print r.text
    response_content = r.json()
    task_id = response_content['task_id']



    return response_content, questions
