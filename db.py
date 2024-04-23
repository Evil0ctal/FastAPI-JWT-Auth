import json


def get_user_by_email(email):
    with open("db.json", "r") as file:
        data = json.load(file)
    for user in data["users"]:
        if user["email"] == email:
            return user
    return None
