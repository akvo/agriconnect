#!/usr/bin/env python
"""
Apply fastapi-mail Pydantic 2.12 compatibility fix
Fix for: https://github.com/sabuhish/fastapi-mail/issues/236
"""
import os
import sys


def apply_fix():
    try:
        import fastapi_mail
        schemas_path = os.path.join(
            os.path.dirname(fastapi_mail.__file__), "schemas.py"
        )

        with open(schemas_path, "r") as f:
            content = f.read()

        # Check if already patched
        if "def validate_alternative_body(self):" in content:
            print("fastapi-mail patch already applied")
            return True

        # Apply fix: Change validator signature for Pydantic 2.12+ compatibility
        old_code = """    @model_validator(mode="after")
    def validate_alternative_body(cls, values):
        \"\"\"
        Validate alternative_body field
        \"\"\"
        if (
            values.multipart_subtype != MultipartSubtypeEnum.alternative
            and values.alternative_body
        ):
            values.alternative_body = None
        return values"""

        new_code = """    @model_validator(mode="after")
    def validate_alternative_body(self):
        \"\"\"
        Validate alternative_body field
        Fixed for Pydantic 2.12+ compatibility
        \"\"\"
        if (
            self.multipart_subtype != MultipartSubtypeEnum.alternative
            and self.alternative_body
        ):
            self.alternative_body = None
        return self"""

        if old_code in content:
            content = content.replace(old_code, new_code)
            with open(schemas_path, "w") as f:
                f.write(content)
            print("✓ Applied fastapi-mail Pydantic 2.12 compatibility fix")
            return True
        else:
            print("fastapi-mail code structure changed - manual review needed")
            return False

    except Exception as e:
        print(f"Error applying fastapi-mail fix: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    sys.exit(0 if apply_fix() else 1)
