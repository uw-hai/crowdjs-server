###
# Variables available: question, task, answer
###
import pickle
import nltk
import string

nltk.download('punkt')
nltk.download('stopwords')
    
old_question = question
old_question_name = question.name

(sentence, sentence_bolded,
 entity1, entity2, relation, taboo_words,
 lineNumber) = old_question_name.split("\t")

old_question_data = question.data
old_question_description = question.description

#sentence = sentence.translate(None, string.punctuation)

new_sentence = answer.value
#new_sentence = new_sentence.translate(None, string.punctuation)

task_data = pickle.loads(task.data)

old_taboo_words_list = []
for word in task_data.keys():
    if task_data[word] >= threshold:
        old_taboo_words_list.append(word)


print "FINDING TABOO WORDS"
sys.stdout.flush()

#Find the taboo words
tokenized_old_sentence = nltk.word_tokenize(sentence.lower())
tokenized_new_sentence = nltk.word_tokenize(new_sentence.lower())

new_taboo_words = set(tokenized_new_sentence) - set(tokenized_old_sentence)
new_taboo_words = new_taboo_words - set(nltk.corpus.stopwords.words('english'))

#Add the new taboo words to the existing taboo words
#and only add it if it's greater than or equal to 3 characters.
for new_taboo_word in new_taboo_words:
    if len(new_taboo_word) < 3:
        continue
    if not new_taboo_word in task_data:
        task_data[new_taboo_word] = 1
    else:
        task_data[new_taboo_word] += 1


new_taboo_words_list = []
for word in task_data.keys():
    if task_data[word] >= threshold:
        new_taboo_words_list.append(word)

#new_taboo_words = new_taboo_words | task_data

print new_taboo_words_list
sys.stdout.flush()

#Save the new taboo words to the task
new_taboo_words_string = ''
for taboo_word in new_taboo_words_list:
    new_taboo_words_string += taboo_word
    new_taboo_words_string += ';'
    
new_task_data = pickle.dumps(task_data)
                         
print "MAKING NEW QUESTION ONLY IF THERE IS A NEW QUESTION TO MAKE"
print new_task_data
sys.stdout.flush()

if len(new_taboo_words_list) != len(old_taboo_words_list):
    #Create and save the new question
    new_data = (sentence, sentence_bolded, entity1, entity2,
                relation, new_taboo_words_string, int(lineNumber))
    
    new_question_name =  "%s\t%s\t%s\t%s\t%s\t%s\t%d" % new_data

    new_questions.append({'name' : new_question_name,
                          'description' : question.description,
                          'data' : question.data,
                          'task' : task,
                          'valid_answers' : question.valid_answers,
                          'requester' : question.requester,
                          'answers_per_question' : answers_per_question})

    old_question_budget = 0
    
