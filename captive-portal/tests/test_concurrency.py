import threading
import backend.auth as auth

def worker():
    auth.USERS = {"user": "pass"}
    assert auth.check_user("user", "pass")

def test_concurrency():
    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
import threading
import backend.auth as auth

def worker():
    auth.USERS = {"user": "pass"}
    assert auth.check_user("user", "pass")

def test_concurrent_logins():
    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
