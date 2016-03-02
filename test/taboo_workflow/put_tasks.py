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

    global_answer_callback_file = open('global_answer_callback.py', 'r') 
    global_answer_callback_string = global_answer_callback_file.read()
    global_answer_callback_string = ("threshold=%d\nanswers_per_question=%d" %
                                     (threshold, answers_per_question) +
                                     global_answer_callback_string)
    
    data = {'task_name': task_name,
            'task_description': task_description,
            'requester_id' : requester_id,
            'data' : pickle.dumps(taboo_words),
            'global_answer_callback' : global_answer_callback_string,
            'questions' : questions}
    

    #print "Here is what is being sent"
    #print data
    
    r = requests.put(crowdjs_url, headers=headers,
                     json=data)

    print "Here is the response"
    print r.text
    response_content = r.json()
    task_id = response_content['task_id']


    #logfile_name = 'logs/%s.txt' % datetime.datetime.now().ctime()
    #with open(logfile_name, 'w') as logFile:
    #    logFile.write('%s\n' % task_name)
    #    logFile.write('%s\n' % task_description)
    #    logFile.write('%s\n' % task_id)
    #    logFile.write(pickle.dumps(questions))


    return response_content, questions
