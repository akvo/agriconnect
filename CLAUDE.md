# Bash commands
- ./dc.sh up -d: Run the development environment
- ./dc.sh exec backend tests: Run backend tests
- ./dc.sh exec backend flake8: Run backend linter
- ./dc.sh exec frontend pretter --write .: Format frontend code

# Code style
- For Python, follow PEP 8 guidelines, and use black for formatting
- The max line length is 79 characters for Python

# Workflow
- Be sure to always run ./dc.sh exec backend <command> to execute commands in the backend container
