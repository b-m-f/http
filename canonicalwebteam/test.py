from http import CachedSession
from datetime import datetime
import time


sess = CachedSession()
print(sess)
for i in range(9):
    print("start")
    print(datetime.now())
    response = sess.get('https://ehlers.berlin')
    
    print("is response from cache")
    print(response.from_cache)
    print(datetime.now())
    print(response.headers)
    time.sleep(10)
