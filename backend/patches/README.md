# Backend Patches

This directory contains patches for third-party dependencies that fix compatibility issues.

## apply_fastapi_mail_fix.py

**Issue**: fastapi-mail 1.5.0 is incompatible with Pydantic 2.12+
**Error**: `'pydantic_core._pydantic_core.ValidationInfo' object has no attribute 'multipart_subtype'`
**Upstream Issue**: https://github.com/sabuhish/fastapi-mail/issues/236

### Problem
The `validate_alternative_body` model validator in `fastapi_mail.schemas.MessageSchema` uses outdated Pydantic v1 syntax with Pydantic v2 decorators. In Pydantic 2.12+, `@model_validator(mode="after")` receives `self` (the model instance) instead of `cls, values`.

### Fix
This Python script automatically patches the fastapi-mail library on container startup by changing the validator signature from:
```python
def validate_alternative_body(cls, values):
    if values.multipart_subtype != ...:
        values.alternative_body = None
    return values
```

To:
```python
def validate_alternative_body(self):
    if self.multipart_subtype != ...:
        self.alternative_body = None
    return self
```

### Application
- **Development**: Applied automatically by `dev.sh` on container start
- **Production**: Applied automatically during Docker image build via `Dockerfile`

The script is idempotent - it safely detects if the patch is already applied and skips if so.

### Status
This is a **temporary workaround** until fastapi-mail releases an official fix. Monitor [issue #236](https://github.com/sabuhish/fastapi-mail/issues/236) and remove this patch when upgrading to a fixed version.
