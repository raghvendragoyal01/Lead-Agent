import requests; print(requests.post('http://127.0.0.1:5000/start-campaign', data='{"target_leads": 2}', headers={'Content-Type': 'text/plain'}).text)
