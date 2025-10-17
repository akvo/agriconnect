import sys

from seeder.administrative import main as administrative_main
from seeder.customer import main as customer_main
from seeder.user import main as user_main


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m seeder <command> [options]")
        print("Available commands:")
        print("  user            Create initial admin user")
        print("  administrative  Seed administrative data")
        print("  customer [count] [country]  Seed fake customers")
        print("                   count: number of customers (default: 50)")
        print("                   country: tanzania|kenya (default: tanzania)")
        sys.exit(1)

    command = sys.argv[1]

    if command == "user":
        user_main()
    elif command == "administrative":
        administrative_main()
    elif command == "customer":
        customer_main()
    else:
        print(f"Unknown command: {command}")
        print("Available commands:")
        print("  user            Create initial admin user")
        print("  administrative  Seed administrative data")
        print("  customer [count] [country]  Seed fake customers")
        sys.exit(1)


if __name__ == "__main__":
    main()
