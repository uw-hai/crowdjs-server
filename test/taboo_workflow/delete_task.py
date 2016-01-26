import requests

def delete_task(crowdjs_url, email, API_KEY, requester_id):
    crowdjs_url += '/tasks/delete'
    
    headers = {'Authentication-Token': API_KEY,
               'content_type' : 'application/json'}

    data = {'requester_id' : requester_id}
        
    r = requests.post(crowdjs_url, headers=headers,
                     json=data)

    return r.json()
