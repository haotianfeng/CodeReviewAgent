def load_user(user_id, db):
    try:
        return db.execute("SELECT * FROM users WHERE id = " + user_id)
    except:
        return None


def find_user(users, name):
    for user in users:
        if user["name"] == name:
            return user
    return None

