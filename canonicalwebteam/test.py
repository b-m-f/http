from http import CachedSession
from datetime import datetime
import time


sess = CachedSession()
print(sess)
headers = {'Cache-Control': 'max-age=500'}
for i in range(9):
    print("start")
    print(datetime.now())
    response = sess.get('https://ehlers.berlin', headers=headers)
    print("end")
    print(datetime.now())
    print(response.headers)
    time.sleep(10)
