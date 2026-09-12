with open("G:/Scrrapi/backend/app/api/deps.py") as f:
    content = f.read()

content = content.replace("user: User = Depends(get_current_user)", "user: User = Depends(get_current_user_or_api_key)")

with open("G:/Scrrapi/backend/app/api/deps.py", "w") as f:
    f.write(content)
