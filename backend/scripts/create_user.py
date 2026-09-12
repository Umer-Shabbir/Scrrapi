"""Create (or update) a user and give them an active license.

There is no self-serve signup endpoint -- `licenses` is the paid gate, so accounts
are provisioned out of band. This is that out-of-band step, and the only way to get
a token that `POST /api/jobs` will accept.

Usage:
    python scripts/create_user.py you@example.com hunter2
    python scripts/create_user.py you@example.com hunter2 --plan pro --seats 5 --days 30

Re-running for an existing email resets that user's password and extends the
license rather than erroring, so it doubles as "I forgot the dev password".
"""

import argparse
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.security import hash_password
from app.db.models.license import License
from app.db.models.user import User
from app.db.session import AppSessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument("password")
    parser.add_argument("--plan", default="dev")
    parser.add_argument("--seats", type=int, default=1)
    parser.add_argument("--days", type=int, default=365, help="license validity in days")
    args = parser.parse_args()

    db = AppSessionLocal()
    try:
        user = db.execute(select(User).where(User.email == args.email)).scalar_one_or_none()
        if user is None:
            user = User(email=args.email, password_hash=hash_password(args.password))
            db.add(user)
            action = "created"
        else:
            user.password_hash = hash_password(args.password)
            action = "updated"
        db.flush()

        # Naive UTC: `licenses.expires_at` is a plain DateTime column, and
        # deps.require_active_license compares it against a naive `utcnow()`.
        expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=args.days)
        license_ = db.execute(select(License).where(License.user_id == user.id)).scalars().first()
        if license_ is None:
            db.add(
                License(
                    user_id=user.id,
                    plan=args.plan,
                    seats=args.seats,
                    expires_at=expires_at,
                )
            )
        else:
            license_.plan = args.plan
            license_.seats = args.seats
            license_.expires_at = expires_at

        db.commit()
        print(
            f"{action} {args.email} (id={user.id}), license {args.plan} until {expires_at:%Y-%m-%d}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
