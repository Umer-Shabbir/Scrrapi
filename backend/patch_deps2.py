import sys

with open('app/api/deps.py', encoding='utf-8') as f:
    content = f.read()

# Make sure not to double patch
if 'get_current_user_or_api_key' in content:
    sys.exit(0)

# Add imports
content = content.replace('from collections.abc import Generator',
    'from collections.abc import Generator\nimport hashlib\nimport ipaddress')

content = content.replace('from fastapi import Depends, HTTPException, status',
    'from fastapi import Depends, HTTPException, status, Request\nfrom fastapi.security.api_key import APIKeyHeader')

content = content.replace('from app.db.models.user import User',
    'from app.db.models.api_key import ApiKey\nfrom app.db.models.user import User')

content = content.replace('oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")',
    'oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")\napi_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)')


new_funcs = '''
def get_api_key(
    request: Request,
    key_str: str | None = Depends(api_key_header),
    db: Session = Depends(get_app_db),
) -> ApiKey:
    """Verifies the X-API-Key header against the api_keys table."""
    if not key_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )
    
    key_hash = hashlib.sha256(key_str.encode()).hexdigest()
    api_key_obj = (
        db.query(ApiKey)
        .filter(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
        .first()
    )
    
    if not api_key_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )

    now = datetime.utcnow()
    if api_key_obj.expires_at and api_key_obj.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired",
        )

    if api_key_obj.ip_allowlist:
        client_ip = request.client.host if request.client else None
        if client_ip:
            allowed = False
            try:
                client_ip_obj = ipaddress.ip_address(client_ip)
                for block in api_key_obj.ip_allowlist.split(","):
                    block = block.strip()
                    if not block:
                        continue
                    try:
                        if client_ip_obj in ipaddress.ip_network(block):
                            allowed = True
                            break
                    except ValueError:
                        continue
            except ValueError:
                pass
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="IP address not allowed for this API key",
                )

    api_key_obj.last_used_at = now
    # Handle usage string -> json -> string if necessary, but assuming JSON type
    usage = list(api_key_obj.usage_daily or [])
    if usage:
        usage[-1] += 1
    api_key_obj.usage_daily = usage

    db.commit()
    return api_key_obj


def get_current_user_or_api_key(
    request: Request,
    token: str | None = Depends(OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)),
    api_key_str: str | None = Depends(api_key_header),
    db: Session = Depends(get_app_db),
) -> User:
    """Authenticates via JWT token OR X-API-Key header, returning the User object for either."""
    if token:
        return get_current_user(token, db)
    elif api_key_str:
        api_key_obj = get_api_key(request=request, key_str=api_key_str, db=db)
        user = db.get(User, api_key_obj.owner_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key owner")
        if user.disabled_at is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "account_disabled", "message": "This account has been disabled"},
            )
        return user
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
'''

content += new_funcs

with open('app/api/deps.py', 'w', encoding='utf-8') as f:
    f.write(content)
