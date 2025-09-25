import sys

from seeder.user import main as user_main
from seeder.administrative import main as administrative_main


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m seeder <command>")
        print("Available commands:")
        print("  user            Create initial admin user")
        print("  administrative  Seed administrative data")
        sys.exit(1)

    command = sys.argv[1]

    if command == "user":
        user_main()
    elif command == "administrative":
        administrative_main()
    else:
        print(f"Unknown command: {command}")
        print("Available commands:")
        print("  user            Create initial admin user")
        print("  administrative  Seed administrative data")
        sys.exit(1)


if __name__ == "__main__":
    main()
