# WARNING: Vulnerable code — DO NOT USE
def get_user(username):
    query = f"SELECT * FROM users WHERE username = '{username}'"
    # Attacker input: ' OR 1=1; UPDATE users SET role='admin' WHERE username='attacker'; --
    cursor.execute(query)
    return cursor.fetchall()
