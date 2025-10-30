import csv
import os
import sys

from sqlalchemy.orm import Session
from models.customer import CropType
from database import SessionLocal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def seed_crop_types(db: Session):
    # Seed crop types from CSV file
    csv_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "source",
        "crop_types.csv",
    )
    with open(csv_path, mode="r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            # find or create crop type
            crop_type = (
                db.query(CropType)
                .filter(CropType.id == int(row["id"]))
                .first()
            )
            if not crop_type:
                crop_type = CropType(
                    id=int(row["id"]),
                    name=row["name"],
                )
                db.add(crop_type)
            if crop_type.name != row["name"]:
                crop_type.name = row["name"]
        db.commit()
        db.refresh(crop_type)
    print("✅ Seeded crop types")


if __name__ == "__main__":
    db = SessionLocal()
    seed_crop_types(db)
    db.close()
