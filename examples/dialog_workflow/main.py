"""
Dialog workflow.
Implements the following basic features.
    - Insert ambigous queries from file to DB
"""

import argparse
import os
import logging.config
import requests
import utils


# read auth token and app url from the env variables
APP_CONFIG = {"crowdjs_url": os.environ["CROWDJS_URL"],
              "api_key": os.environ["API_KEY"],
              "requester_id": os.environ["REQUESTER_ID"]}


def add_task(question_file):
    """Add a new task to the database.

    Args:
        question_file (str): File containing questions.
    """
    # read questions from the file.
    questions = []
    with open(question_file) as tsvfile:
        reader = utils.UnicodeDictReader(tsvfile, delimiter='\t')
        for row in reader:
            question = {"question_name": row["query"],
                        "question_description": row["id"]}
            questions.append(question)
    crowdjs_url = "%s/tasks" % APP_CONFIG["crowdjs_url"]
    headers = {'Authentication-Token': APP_CONFIG["api_key"],
               'content_type' : 'application/json'}
    task_name = "Lang2code Dialog Induction"
    task_description = ".."
    data = {'task_name': task_name,
            'task_description': task_description,
            'requester_id' : APP_CONFIG["requester_id"],
            'questions' : questions}
    logging.debug("Data %r", data)

    # send request to the server.
    req = requests.put(crowdjs_url, headers=headers, json=data)
    logging.info("Here is the response")
    logging.info(req.text)
    response_content = req.json()
    logging.info(response_content['task_id'])
    return response_content, questions


def delete_task(task_id):
    """Delete a task and its questions from the database.

    Args:
        task_id (str): Id of the task.
    """
    crowdjs_url = "%s/tasks/delete" % APP_CONFIG["crowdjs_url"]
    headers = {"Authentication-Token": APP_CONFIG["api_key"],
               "content_type" : "application/json"}

    data = {"requester_id" : APP_CONFIG["requester_id"],
            "task_id": task_id}
    logging.info("Deleting task %s", task_id)
    req = requests.post(crowdjs_url, headers=headers, json=data)
    return req.json()


def main():
    """
    Main function.

    See module string for implemented features.
    """
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--add_task",
                        help="Insert new task with questions into the database.",
                        action='store_true')
    parser.add_argument("--delete_task",
                        help="Delete a task and questions from the database.",
                        action='store_true')
    parser.add_argument("--query_file", help="Path to file containing queries")
    parser.add_argument("--task_id", help="Id of the task.")
    args = parser.parse_args()
    logging.config.fileConfig('logging_config.ini')

    if args.add_task and args.query_file:
        add_task(args.query_file)

    if args.delete_task and args.task_id:
        delete_task(args.task_id)


if __name__ == "__main__":
    main()

