import hashlib, hmac, os
from sqlalchemy import select
from app.database.models import User, AuditLog

class AuthService:
    def __init__(self, db): self.db=db
    @staticmethod
    def _hash(password: str, salt: bytes | None=None) -> str:
        salt=salt or os.urandom(16); digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,600_000)
        return salt.hex()+'$'+digest.hex()
    def create_admin(self, username, password):
        if len(password)<8: raise ValueError('Password must contain at least 8 characters')
        with self.db.session() as s:
            if s.scalar(select(User).where(User.username==username)): raise ValueError('Username already exists')
            s.add(User(username=username,password_hash=self._hash(password))); s.add(AuditLog(username=username,action='Administrator created')); s.commit()
    def authenticate(self, username, password):
        with self.db.session() as s:
            user=s.scalar(select(User).where(User.username==username))
            if not user: return False
            salt, digest=user.password_hash.split('$'); trial=self._hash(password,bytes.fromhex(salt)).split('$')[1]
            ok=hmac.compare_digest(digest,trial)
            if ok: s.add(AuditLog(username=username,action='Login')) ; s.commit()
            return ok
    def change_password(self, username, old, new):
        if not self.authenticate(username,old): raise ValueError('Invalid current password')
        if len(new)<8: raise ValueError('Password must contain at least 8 characters')
        with self.db.session() as s:
            u=s.scalar(select(User).where(User.username==username)); u.password_hash=self._hash(new); s.add(AuditLog(username=username,action='Password changed')); s.commit()
